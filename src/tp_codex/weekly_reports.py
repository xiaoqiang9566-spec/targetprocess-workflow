from __future__ import annotations

import json
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import load_workbook

from tp_codex.artifacts import WorkflowArtifact
from tp_codex.errors import InvalidArgsError, OutputIoError


WORKBOOK_SHEET_PREFIX = "固件质量数据概览-"
WEEKLY_SHEET_NAME_PATTERN = re.compile(r"^固件质量数据概览-Week\d+(?:&Week\d+)?$")
ABNORMAL_CLOSE_KEYWORDS = ("duplicate", "invalid", "expired", "later", "wont fix", "won't fix", "rejected", "拒绝")
EFFECTIVE_FIRMWARE_STATES = {
    "new",
    "in progress",
    "in review",
    "in testing",
    "reproduce",
    "verified",
    "wont fix",
    "won't fix",
    "fixed",
    "expired",
    "later",
    "planned",
}
DEFAULT_WEEKLY_REPORT_CONFIG = {
    "product_sections": {
        "NG3": {
            "product_keywords": ["ng3"],
            "team_names": ["ESW China NG3 Driver", "ESW China NG3 Framework", "ESW UI Team"],
        },
        "Dilu": {"product_keywords": ["dilu"]},
        "心率带2": {"product_keywords": ["心率带", "heart"]},
        "Core 2": {"product_keywords": ["core 2", "core2"]},
        "Run 2": {"product_keywords": ["run 2", "run2"]},
        "Race 3S/Race3": {"product_keywords": ["race 3s", "race3s", "race3", "race 3"]},
    },
    "team_groups": {
        "ESW China NG3 Driver": "驱动",
        "ESW China NG3 Framework": "框架",
        "ESW UI Team": "UI",
    },
    "di_weights": {
        "Blocking": 10,
        "Critical": 3,
        "Major": 1,
        "Normal": 0.1,
    },
    "abnormal_close_keywords": list(ABNORMAL_CLOSE_KEYWORDS),
}


@dataclass(frozen=True)
class WeekContext:
    report_year: int
    week_number: int
    dataset_week: str
    week_label: str
    title: str
    sheet_name: str
    start_date: date
    end_date: date
    output_filename: str


def build_weekly_report_summary(
    records: Sequence[dict],
    week_label: str | None,
    generated_at: str,
    weekly_records: Sequence[dict] | None = None,
    weekly_report_config: dict | None = None,
) -> dict:
    context = resolve_week_context(week_label, generated_at)
    config = build_weekly_report_config(weekly_report_config)
    weekly_records = list(weekly_records) if weekly_records is not None else _weekly_records(records, context)
    by_product: dict[str, dict] = {}
    for product_name in ["NG3", "Dilu", "心率带2", "Core 2", "Run 2", "Race 3S/Race3"]:
        product_records = [record for record in records if _match_product(record, config) == product_name]
        product_weekly_records = [record for record in weekly_records if _match_product(record, config) == product_name]
        if not product_records:
            continue
        by_product[product_name] = {
            "total_records": len(product_records),
            "weekly_new_records": len(product_weekly_records),
            "customer_feedback_records": sum(1 for record in product_records if record.get("is_customer_feedback")),
            "high_risk_records": sum(1 for record in product_records if record.get("is_high_risk")),
        }
    return {
        "week_label": context.week_label,
        "sheet_name": context.sheet_name,
        "report_year": context.report_year,
        "total_records": len(records),
        "weekly_new_records": len(weekly_records),
        "by_product": by_product,
    }


def build_weekly_report_artifact(
    records: Sequence[dict],
    week_label: str | None,
    template_path: str,
    generated_at: str,
    weekly_records: Sequence[dict] | None = None,
    weekly_report_config: dict | None = None,
) -> WorkflowArtifact:
    context = resolve_week_context(week_label, generated_at)
    template = Path(template_path)
    if not template.exists():
        raise OutputIoError(f"weekly report template not found: {template}")
    workbook_bytes = append_weekly_sheet(
        template.read_bytes(),
        records,
        context,
        weekly_records=weekly_records,
        weekly_report_config=weekly_report_config,
    )
    return WorkflowArtifact(
        filename=context.output_filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content=workbook_bytes,
    )


def resolve_week_context(week_label: str | None, generated_at: str) -> WeekContext:
    generated = _parse_generated_at(generated_at)
    label = str(week_label or "").strip()
    if not label:
        local_date = generated.astimezone(ZoneInfo("Asia/Shanghai")).date()
        current_week_start = local_date - timedelta(days=local_date.weekday())
        return _context_from_week_start(current_week_start - timedelta(days=7), None)
    match = re.fullmatch(r"Week(\d{1,2})", label, flags=re.IGNORECASE)
    if match:
        week_number = int(match.group(1))
        normalized = f"Week{week_number:02d}" if len(match.group(1)) == 2 else f"Week{week_number}"
        report_year = generated.astimezone(ZoneInfo("Asia/Shanghai")).year
        return _context_from_iso_week(report_year, week_number, normalized)
    match = re.fullmatch(r"(\d{4})-W(\d{2})", label, flags=re.IGNORECASE)
    if match:
        report_year = int(match.group(1))
        week_number = int(match.group(2))
        return _context_from_iso_week(report_year, week_number, f"Week{week_number:02d}")
    raise InvalidArgsError(f"unsupported week label: {week_label}")


def build_weekly_created_where(context: WeekContext) -> str:
    exclusive_end = context.end_date + timedelta(days=1)
    return (
        f'CreateDate >= DateTime.Parse("{context.start_date.isoformat()}") '
        f'and CreateDate < DateTime.Parse("{exclusive_end.isoformat()}")'
    )


def build_weekly_report_config(config: dict | None = None) -> dict:
    merged = deepcopy(DEFAULT_WEEKLY_REPORT_CONFIG)
    for key, value in dict(config or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def build_di_summary(records: Sequence[dict], weekly_report_config: dict | None = None) -> dict:
    config = build_weekly_report_config(weekly_report_config)
    weights = {str(key): float(value) for key, value in dict(config.get("di_weights") or {}).items()}
    by_severity: dict[str, dict] = {}
    detected_di = 0.0
    remaining_di = 0.0
    for record in records:
        if _is_abnormal_close(record):
            continue
        severity = _severity_key(record) or "Normal"
        weight = weights.get(severity, 0.0)
        detected_di += weight
        stats = by_severity.setdefault(
            severity,
            {"detected_count": 0, "remaining_count": 0, "detected_di": 0.0, "remaining_di": 0.0},
        )
        stats["detected_count"] += 1
        stats["detected_di"] += weight
        if record.get("is_open") or record.get("status_group") != "closed":
            remaining_di += weight
            stats["remaining_count"] += 1
            stats["remaining_di"] += weight
    return {
        "detected_di": _clean_number(detected_di),
        "remaining_di": _clean_number(remaining_di),
        "closed_rate": ((detected_di - remaining_di) / detected_di) if detected_di else 0,
        "by_severity": {key: _clean_di_stats(value) for key, value in by_severity.items()},
    }


def append_weekly_sheet(
    template_bytes: bytes,
    records: Sequence[dict],
    context: WeekContext,
    weekly_records: Sequence[dict] | None = None,
    weekly_report_config: dict | None = None,
) -> bytes:
    config = build_weekly_report_config(weekly_report_config)
    weekly_records = list(weekly_records) if weekly_records is not None else _weekly_records(records, context)
    try:
        workbook = load_workbook(BytesIO(template_bytes))
    except Exception as exc:  # pragma: no cover
        raise OutputIoError("weekly report template is not a valid workbook") from exc

    source_sheet = _find_source_weekly_sheet(workbook)
    if source_sheet is None:
        raise OutputIoError("weekly report template does not contain any weekly sheets")

    if source_sheet.title == context.sheet_name:
        target_sheet = source_sheet
    else:
        target_sheet = workbook.copy_worksheet(source_sheet)
        target_sheet.title = context.sheet_name
    for worksheet in list(workbook.worksheets):
        if worksheet is not target_sheet:
            workbook.remove(worksheet)
    _rewrite_weekly_sheet(target_sheet, records, weekly_records, context, config)

    buffer = BytesIO()
    workbook.save(buffer)
    return _normalize_workbook_relationship_targets(buffer.getvalue())


def _rewrite_weekly_sheet(sheet, records: Sequence[dict], weekly_records: Sequence[dict], context: WeekContext, config: dict) -> None:
    _strip_sheet_metadata(sheet)
    _copy_row_style(sheet, 1)
    _copy_row_style(sheet, 2)
    sheet["A1"] = context.title
    sheet["A2"] = f"{context.report_year}年NG3固件每周新增Bug"

    ng3_weekly = [record for record in weekly_records if _match_product(record, config) == "NG3"]
    ng3_full = [record for record in records if _match_product(record, config) == "NG3"]
    ng3_year = [record for record in ng3_full if _record_year(record.get("created_at")) == context.report_year]
    ng3_effective = [record for record in ng3_year if _is_effective_firmware_bug(record)]
    ng3_customer = [record for record in ng3_year if record.get("is_customer_feedback")]

    _fill_ng3_weekly_block(sheet, ng3_weekly, context, config)
    _fill_ng3_effective_block(sheet, ng3_effective, context, config)
    _fill_ng3_customer_block(sheet, ng3_customer, context, config)
    _fill_ng3_stock_block(sheet, ng3_full, context, config)


def _fill_ng3_weekly_block(sheet, records: Sequence[dict], context: WeekContext, config: dict) -> None:
    grouped_by_severity = {severity: [record for record in records if _severity_key(record) == severity] for severity in ["Blocking", "Critical", "Major", "Normal"]}
    total = len(records)
    blocking_count = len(grouped_by_severity["Blocking"])
    critical_count = len(grouped_by_severity["Critical"])
    team_counts = {label: sum(1 for record in records if _group_label(record, config) == label) for label in ["驱动", "框架", "UI"]}
    status_counts = {
        "new": sum(1 for record in records if _status_bucket_ng3(record) == "new"),
        "processing": sum(1 for record in records if _status_bucket_ng3(record) == "processing"),
        "resolved": sum(1 for record in records if _status_bucket_ng3(record) == "resolved"),
        "verified": sum(1 for record in records if _status_bucket_ng3(record) == "verified"),
        "abnormal": sum(1 for record in records if _status_bucket_ng3(record) == "abnormal"),
    }
    issue_lines = _top_focus_issue_lines(records)
    sheet["A3"] = (
        f"1）{context.week_label}新增{total}个Bug，B&C等级Bug分别是{blocking_count}个和{critical_count}个，"
        f"新增Bug在各组的分布为驱动{team_counts['驱动']}个，框架{team_counts['框架']}个，UI{team_counts['UI']}个。\n"
        f"2）新增Bug状态分布为New {status_counts['new']}个（占比{_percent_text(_ratio(status_counts['new'], total))}），"
        f"处理中{status_counts['processing']}个（{_percent_text(_ratio(status_counts['processing'], total))}），"
        f"已解决{status_counts['resolved']}个（占比{_percent_text(_ratio(status_counts['resolved'], total))}），"
        f"已验证{status_counts['verified']}个（占比{_percent_text(_ratio(status_counts['verified'], total))}），"
        f"异常闭环{status_counts['abnormal']}个（占比{_percent_text(_ratio(status_counts['abnormal'], total))}）。\n"
        f"3）待解决重点问题\n{chr(10).join(issue_lines)}"
    )
    for row, severity in zip(range(5, 9), ["Blocking", "Critical", "Major", "Normal"]):
        severity_records = grouped_by_severity[severity]
        values = [
            severity,
            len(severity_records),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "new"),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "processing"),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "resolved"),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "verified"),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "abnormal"),
        ]
        _set_row(sheet, row, values)
    totals = [total, status_counts["new"], status_counts["processing"], status_counts["resolved"], status_counts["verified"], status_counts["abnormal"]]
    _set_row(sheet, 9, ["总计", *totals])
    _set_row(
        sheet,
        10,
        [
            "各状态问题占比",
            "/",
            _ratio(status_counts["new"], total),
            _ratio(status_counts["processing"], total),
            _ratio(status_counts["resolved"], total),
            _ratio(status_counts["verified"], total),
            _ratio(status_counts["abnormal"], total),
        ],
    )


def _fill_ng3_effective_block(sheet, records: Sequence[dict], context: WeekContext, config: dict) -> None:
    total = len(records)
    pending = sum(1 for record in records if _status_bucket_effective(record) == "pending")
    pending_verification = sum(1 for record in records if _status_bucket_effective(record) == "pending_verification")
    abnormal = sum(1 for record in records if _status_bucket_effective(record) == "abnormal")
    verified = sum(1 for record in records if _status_bucket_effective(record) == "verified")
    close_rate = _ratio(total - pending, total)
    bc_records = [record for record in records if _severity_key(record) in {"Blocking", "Critical"}]
    bc_by_group = {label: [record for record in bc_records if _group_label(record, config) == label] for label in ["驱动", "框架", "UI"]}
    blocking_records = [record for record in records if _severity_key(record) == "Blocking"]
    critical_records = [record for record in records if _severity_key(record) == "Critical"]
    blocking_close_rate = _ratio(len(blocking_records) - sum(1 for record in blocking_records if _status_bucket_effective(record) == "pending"), len(blocking_records))
    critical_close_rate = _ratio(len(critical_records) - sum(1 for record in critical_records if _status_bucket_effective(record) == "pending"), len(critical_records))
    verified_base = max(total - pending - abnormal, 0)
    verify_rate = _ratio(verified, verified_base)
    bc_verify_pending = sum(1 for record in bc_records if _status_bucket_effective(record) == "pending_verification")
    group_rates = {
        label: _ratio(
            len(group_records) - sum(1 for record in group_records if _status_bucket_effective(record) == "pending"),
            len(group_records),
        )
        for label, group_records in bc_by_group.items()
    }
    sheet["A12"] = (
        f"1、{context.report_year}年过程检出有效Bug总数{total}个，当前待解决{pending}个，整体关闭率{_percent_text(close_rate)}"
        f"（目标值65%），B&C问题的关闭率分别为Blocking问题{_percent_text(blocking_close_rate)}，Critical问题{_percent_text(critical_close_rate)}。\n"
        f"2、各工作组B&C问题关闭率分别为驱动{_percent_text(group_rates['驱动'])}，框架{_percent_text(group_rates['框架'])}，"
        f"UI {_percent_text(group_rates['UI'])}；高优先级问题仍主要集中在驱动组，需要继续推进闭环。\n"
        f"3、{context.report_year}年新增问题中已验证{verified}个，整体验证率{_percent_text(verify_rate)}；"
        f"待验证B&C问题共计{bc_verify_pending}个，请持续推进回归验证。\n"
        "注：有效Bug不包含Duplicate、Invalid状态；关闭率=（总数-待解决）/总数，验证率=已验证/（总数-待解决-非常规闭环）。"
    )
    severity_rows = {
        14: "Blocking",
        15: "Critical",
        16: "Major",
        17: "Normal",
    }
    for row, severity in severity_rows.items():
        severity_records = [record for record in records if _severity_key(record) == severity]
        row_total = len(severity_records)
        row_pending = sum(1 for record in severity_records if _status_bucket_effective(record) == "pending")
        row_pending_verification = sum(1 for record in severity_records if _status_bucket_effective(record) == "pending_verification")
        row_abnormal = sum(1 for record in severity_records if _status_bucket_effective(record) == "abnormal")
        row_verified = sum(1 for record in severity_records if _status_bucket_effective(record) == "verified")
        verify_base = max(row_total - row_pending - row_abnormal, 0)
        _set_row(
            sheet,
            row,
            [
                severity,
                row_total,
                row_pending,
                row_pending_verification,
                row_abnormal,
                _ratio(row_total - row_pending, row_total),
                _ratio(row_verified, verify_base),
            ],
        )
    _set_row(sheet, 18, ["总计", total, pending, pending_verification, abnormal, close_rate, verify_rate])
    for row, label in zip(range(20, 23), ["驱动", "框架", "UI"]):
        group_records = bc_by_group[label]
        group_total = len(group_records)
        group_pending = sum(1 for record in group_records if _status_bucket_effective(record) == "pending")
        group_pending_verification = sum(1 for record in group_records if _status_bucket_effective(record) == "pending_verification")
        group_abnormal = sum(1 for record in group_records if _status_bucket_effective(record) == "abnormal")
        group_verified = sum(1 for record in group_records if _status_bucket_effective(record) == "verified")
        verify_base = max(group_total - group_pending - group_abnormal, 0)
        _set_row(
            sheet,
            row,
            [
                label,
                group_total,
                group_pending,
                group_pending_verification,
                group_abnormal,
                _ratio(group_total - group_pending, group_total),
                _ratio(group_verified, verify_base),
            ],
        )


def _fill_ng3_customer_block(sheet, records: Sequence[dict], context: WeekContext, config: dict) -> None:
    total = len(records)
    closed = sum(1 for record in records if _status_bucket_customer(record) == "closed")
    pending = sum(1 for record in records if _status_bucket_customer(record) == "pending")
    pending_verification = sum(1 for record in records if _status_bucket_customer(record) == "pending_verification")
    abnormal = sum(1 for record in records if _status_bucket_customer(record) == "abnormal")
    by_group = {label: [record for record in records if _group_label(record, config) == label] for label in ["驱动", "框架", "UI"]}
    by_severity = {
        severity: [record for record in records if _severity_key(record) == severity]
        for severity in ["Blocking", "Critical", "Major", "Normal"]
    }
    abnormal_breakdown = Counter((record.get("status_raw") or "").strip() for record in records if _status_bucket_customer(record) == "abnormal")
    abnormal_text_parts = [
        f"{name} {count}个"
        for name, count in [
            ("Wont fix", abnormal_breakdown.get("Wont fix", 0)),
            ("Invalid", abnormal_breakdown.get("Invalid", 0)),
            ("Duplicate", abnormal_breakdown.get("Duplicate", 0)),
            ("Expired", abnormal_breakdown.get("Expired", 0)),
            ("Later", abnormal_breakdown.get("Later", 0)),
        ]
        if count
    ]
    sheet["A24"] = (
        f"1、{context.report_year}年归属NG3固件的售后问题{total}个，各组的售后问题分别是驱动{len(by_group['驱动'])}个，"
        f"框架{len(by_group['框架'])}个，UI {len(by_group['UI'])}个，处理压力仍集中在驱动组。\n"
        f"2、{context.report_year}年新增的售后问题已闭环{closed}个，整体关闭率{_percent_text(_ratio(closed, total))}（目标65%）；"
        f"当前待关闭{pending}个，其中待验证{pending_verification}个。\n"
        f"3、已闭环问题中非常规闭环{abnormal}个（{'，'.join(abnormal_text_parts)}），正常验证闭环{closed - abnormal}个。\n"
        "客诉Bug响应时效要求：\n"
        "（DM1）S级：2天内响应，1-2周内解决并发布；（Blocking Bug：2天内响应，7天内解决）\n"
        "（DM2）A级：3-7天内响应，2-4周内解决并发布；（Critical Bug：7天内响应，21天内解决）\n"
        "（DM3）B级：通过Bug追踪按项目版本迭代计划发布解决；（Major & Normal Bug：30天内响应，60天内解决，NG3按季度推送版本）"
    )
    for row, severity in zip(range(26, 30), ["Blocking", "Critical", "Major", "Normal"]):
        severity_records = by_severity[severity]
        _set_row(
            sheet,
            row,
            [
                severity,
                len(severity_records),
                sum(1 for record in severity_records if _status_bucket_customer(record) == "closed"),
                sum(1 for record in severity_records if _status_bucket_customer(record) == "pending"),
                sum(1 for record in severity_records if _status_bucket_customer(record) == "pending_verification"),
                sum(1 for record in severity_records if _status_bucket_customer(record) == "abnormal"),
                _ratio(sum(1 for record in severity_records if _status_bucket_customer(record) == "closed"), len(severity_records)),
            ],
        )
    _set_row(sheet, 30, ["总计", total, closed, pending, pending_verification, abnormal, _ratio(closed, total)])
    for row, label in zip(range(32, 35), ["驱动", "框架", "UI"]):
        group_records = by_group[label]
        blocking_pending = sum(
            1
            for record in group_records
            if _severity_key(record) == "Blocking" and _status_bucket_customer(record) == "pending"
        )
        critical_pending = sum(
            1
            for record in group_records
            if _severity_key(record) == "Critical" and _status_bucket_customer(record) == "pending"
        )
        critical_solution = sum(
            1
            for record in group_records
            if _severity_key(record) == "Critical" and _status_bucket_customer(record) in {"pending", "pending_verification"}
        )
        _set_row(
            sheet,
            row,
            [
                label,
                blocking_pending,
                blocking_pending,
                critical_pending,
                critical_solution,
                "请继续跟进超期客诉问题闭环",
            ],
        )
    _set_row(
        sheet,
        35,
        [
            "总计",
            sum(sheet[f"B{row}"].value or 0 for row in range(32, 35)),
            sum(sheet[f"C{row}"].value or 0 for row in range(32, 35)),
            sum(sheet[f"D{row}"].value or 0 for row in range(32, 35)),
            sum(sheet[f"E{row}"].value or 0 for row in range(32, 35)),
            "/",
        ],
    )


def _fill_ng3_stock_block(sheet, records: Sequence[dict], context: WeekContext, config: dict) -> None:
    backlog_records = [record for record in records if record.get("is_open")]
    group_backlog = {label: [record for record in backlog_records if _group_label(record, config) == label] for label in ["驱动", "框架", "UI"]}
    closed_year_records = [record for record in records if _closed_in_year(record, context.report_year)]
    group_closed_year = {label: [record for record in closed_year_records if _group_label(record, config) == label] for label in ["驱动", "框架", "UI"]}
    pending_dev_records = [record for record in backlog_records if _status_bucket_effective(record) == "pending"]
    group_pending_dev = {label: [record for record in pending_dev_records if _group_label(record, config) == label] for label in ["驱动", "框架", "UI"]}
    reproduce_records = [record for record in backlog_records if "reproduce" in str(record.get("status_raw") or "").lower()]
    group_reproduce = {label: [record for record in reproduce_records if _group_label(record, config) == label] for label in ["驱动", "框架", "UI"]}
    pending_verify_records = [record for record in backlog_records if _status_bucket_effective(record) == "pending_verification"]
    group_pending_verify = {label: [record for record in pending_verify_records if _group_label(record, config) == label] for label in ["驱动", "框架", "UI"]}

    backlog_total = len(backlog_records)
    closed_year_total = len(closed_year_records)
    pending_dev_total = len(pending_dev_records)
    reproduce_total = len(reproduce_records)
    pending_verify_total = len(pending_verify_records)
    sheet["A37"] = (
        f"1、NG3当前存量Bug为{backlog_total}个，驱动{len(group_backlog['驱动'])}个，框架{len(group_backlog['框架'])}个，"
        f"UI {len(group_backlog['UI'])}个，存量Bug的整体消减率{_percent_text(_ratio(closed_year_total, backlog_total + closed_year_total))}。\n"
        f"2、NG3在{context.report_year}年推进闭环的Bug总量是{backlog_total + closed_year_total}个，驱动{len(group_closed_year['驱动'])}个，"
        f"框架{len(group_closed_year['框架'])}个，UI {len(group_closed_year['UI'])}个。\n"
        f"3、当前Bug存量中，待研发处理问题{pending_dev_total}个，待复现问题{reproduce_total}个，待验证问题{pending_verify_total}个。\n"
        "字段注释：\n"
        "“2026年关闭数”是指关闭时间在2026年，对应的状态是Invalid、Later、Wont Fix、Duplicate、Expired、Fixed、Verified。\n"
        "“消减率”=2026年关闭量/（Bug存量+2026年关闭量）"
    )
    for row, label in zip(range(39, 42), ["驱动", "框架", "UI"]):
        backlog_count = len(group_backlog[label])
        closed_year_count = len(group_closed_year[label])
        pending_dev_count = len(group_pending_dev[label])
        reproduce_count = len(group_reproduce[label])
        pending_verify_count = len(group_pending_verify[label])
        _set_row(
            sheet,
            row,
            [
                label,
                backlog_count,
                closed_year_count,
                pending_dev_count,
                reproduce_count,
                pending_verify_count,
                _ratio(closed_year_count, backlog_count + closed_year_count),
            ],
        )
    _set_row(
        sheet,
        42,
        [
            "总计",
            backlog_total,
            closed_year_total,
            pending_dev_total,
            reproduce_total,
            pending_verify_total,
            _ratio(closed_year_total, backlog_total + closed_year_total),
        ],
    )


def _top_focus_issue_lines(records: Sequence[dict]) -> list[str]:
    def score(record: dict) -> tuple[int, int, int]:
        severity_rank = {"Blocking": 0, "Critical": 1, "Major": 2, "Normal": 3}.get(_severity_key(record), 9)
        status_rank = {
            "new": 0,
            "processing": 1,
            "resolved": 2,
            "verified": 3,
            "abnormal": 4,
        }.get(_status_bucket_ng3(record), 9)
        return (severity_rank, status_rank, int(record.get("bug_id") or 0))

    candidates = [
        record
        for record in records
        if _severity_key(record) in {"Blocking", "Critical"} and _status_bucket_ng3(record) in {"new", "processing"}
    ]
    candidates.sort(key=score)
    lines: list[str] = []
    for record in candidates[:4]:
        name = str(record.get("name") or "")
        if len(name) > 120:
            name = f"{name[:117]}..."
        lines.append(f"{record.get('url')} {_severity_key(record)} {record.get('status_raw')} - {name}")
    return lines or ["待人工补充"]


def _find_source_weekly_sheet(workbook):
    weekly_sheets = [sheet for sheet in workbook.worksheets if WEEKLY_SHEET_NAME_PATTERN.match(sheet.title)]
    if not weekly_sheets:
        return None
    return max(weekly_sheets, key=lambda sheet: _highest_week_number(sheet.title))


def _normalize_workbook_relationship_targets(workbook_bytes: bytes) -> bytes:
    with ZipFile(BytesIO(workbook_bytes), "r") as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    for name in list(entries):
        if name.startswith("xl/worksheets/_rels/"):
            del entries[name]
    rels_path = "xl/_rels/workbook.xml.rels"
    root = ET.fromstring(entries[rels_path])
    namespace = {"pkg": "http://schemas.openxmlformats.org/package/2006/relationships"}
    for rel in root.findall("pkg:Relationship", namespace):
        target = rel.attrib.get("Target", "")
        if target.startswith("/xl/"):
            rel.attrib["Target"] = target.removeprefix("/xl/")
    entries[rels_path] = ET.tostring(root, encoding="utf-8", xml_declaration=False)
    worksheet_ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    for name, payload in list(entries.items()):
        if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
            continue
        worksheet = ET.fromstring(payload)
        hyperlinks = worksheet.find("main:hyperlinks", worksheet_ns)
        if hyperlinks is not None:
            worksheet.remove(hyperlinks)
            entries[name] = ET.tostring(worksheet, encoding="utf-8", xml_declaration=False)
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return output.getvalue()


def _highest_week_number(sheet_name: str) -> int:
    numbers = [int(value) for value in re.findall(r"Week(\d{1,2})", sheet_name)]
    return max(numbers) if numbers else -1


def _strip_sheet_metadata(sheet) -> None:
    sheet.freeze_panes = None
    sheet.print_area = ""
    sheet._hyperlinks = []
    try:
        sheet._rels = []
    except Exception:
        pass
    if getattr(sheet, "_rels", None) is not None:
        try:
            sheet._rels.clear()
        except AttributeError:
            sheet._rels = []
    sheet._hyperlink_map = {}


def _copy_row_style(sheet, row_index: int) -> None:
    dimension = sheet.row_dimensions[row_index]
    if dimension is None:
        return
    for attr in ("height", "hidden", "outlineLevel", "collapsed", "ht"):
        value = getattr(dimension, attr, None)
        if value is not None:
            setattr(dimension, attr, value)


def _set_row(sheet, row_index: int, values: Sequence[object]) -> None:
    for column_index, value in enumerate(values, start=1):
        sheet.cell(row=row_index, column=column_index, value=value)


def _parse_generated_at(generated_at: str) -> datetime:
    parsed = datetime.fromisoformat(str(generated_at))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _context_from_iso_week(report_year: int, week_number: int, week_label: str) -> WeekContext:
    return _context_from_week_start(date.fromisocalendar(report_year, week_number, 1), week_label)


def _context_from_week_start(start_date: date, week_label: str | None) -> WeekContext:
    iso = start_date.isocalendar()
    report_year = iso.year
    week_number = iso.week
    normalized = week_label or f"Week{week_number}"
    end_date = start_date + timedelta(days=6)
    return WeekContext(
        report_year=report_year,
        week_number=week_number,
        dataset_week=f"{report_year}-W{week_number:02d}",
        week_label=normalized,
        title=f"固件质量报告{report_year}-{normalized}",
        sheet_name=f"{WORKBOOK_SHEET_PREFIX}{normalized}",
        start_date=start_date,
        end_date=end_date,
        output_filename=f"质量周报-{normalized}({_date_for_filename(start_date)}-{_date_for_filename(end_date)}).xlsx",
    )


def _date_for_filename(value: date) -> str:
    return f"{value.year}.{value.month}.{value.day}"


def _weekly_records(records: Sequence[dict], context: WeekContext) -> list[dict]:
    return [record for record in records if record.get("created_week") == context.dataset_week]


def _record_year(value: object) -> int | None:
    if not value:
        return None
    text = str(value)
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return int(text[:4])
    parsed = datetime.fromisoformat(text)
    return parsed.year


def _closed_in_year(record: dict, report_year: int) -> bool:
    changed_at = record.get("last_status_change_at")
    if not changed_at or not record.get("is_closed"):
        return False
    year = _record_year(changed_at)
    return year == report_year


def _severity_key(record: dict) -> str:
    severity = str(record.get("severity") or "")
    return severity if severity in {"Blocking", "Critical", "Major", "Normal"} else severity


def _status_bucket_ng3(record: dict) -> str:
    status_raw = str(record.get("status_raw") or "").lower()
    if _is_abnormal_close(record):
        return "abnormal"
    if "verified" in status_raw:
        return "verified"
    if any(token in status_raw for token in ("resolved", "fix", "done", "ready for qa")) or record.get("status_group") == "closed":
        return "resolved"
    if any(token in status_raw for token in ("new", "planned")):
        return "new"
    return "processing"


def _status_bucket_small(record: dict) -> str:
    status_raw = str(record.get("status_raw") or "").lower()
    if _is_abnormal_close(record):
        return "rejected"
    if "verified" in status_raw or status_raw == "fixed":
        return "verified"
    if any(token in status_raw for token in ("resolved", "fix", "done")) or record.get("status_group") == "closed":
        return "resolved"
    if any(token in status_raw for token in ("new", "planned", "open")):
        return "new"
    return "processing"


def _status_bucket_effective(record: dict) -> str:
    status_raw = str(record.get("status_raw") or "").strip().lower()
    if status_raw in {"wont fix", "won't fix", "expired", "later"}:
        return "abnormal"
    if status_raw in {"verified", "fixed"}:
        return "verified"
    if status_raw == "in testing":
        return "pending_verification"
    return "pending"


def _status_bucket_customer(record: dict) -> str:
    bucket = _status_bucket_small(record)
    return {
        "new": "pending",
        "processing": "pending",
        "resolved": "pending_verification",
        "verified": "closed",
        "rejected": "abnormal",
    }[bucket]


def _is_abnormal_close(record: dict) -> bool:
    status_raw = str(record.get("status_raw") or "").lower()
    return any(keyword in status_raw for keyword in ABNORMAL_CLOSE_KEYWORDS)


def _is_effective_firmware_bug(record: dict) -> bool:
    name = str(record.get("name") or "").lower()
    status_raw = str(record.get("status_raw") or "").strip().lower()
    return "customer feedback" not in name and status_raw in EFFECTIVE_FIRMWARE_STATES


def _match_product(record: dict, weekly_report_config: dict | None = None) -> str | None:
    config = build_weekly_report_config(weekly_report_config)
    sections = dict(config.get("product_sections") or {})
    products = " ".join(str(item) for item in (record.get("products") or [])).lower()
    team = str(record.get("team") or "")
    ng3_section = dict(sections.get("NG3") or {})
    ng3_team_names = {str(item).lower() for item in ng3_section.get("team_names", [])}
    configured_ng3_groups = {str(key).lower() for key in dict(config.get("team_groups") or {})}
    if team.lower() in ng3_team_names or team.lower() in configured_ng3_groups:
        return "NG3"
    for product_name, section in sections.items():
        product_keywords = [str(item).lower() for item in dict(section or {}).get("product_keywords", [])]
        if product_keywords and any(keyword in products for keyword in product_keywords):
            return str(product_name)
    for product_name, section in sections.items():
        team_names = {str(item).lower() for item in dict(section or {}).get("team_names", [])}
        if team.lower() in team_names:
            return str(product_name)
    return None


def _group_label(record: dict, weekly_report_config: dict | None = None) -> str:
    config = build_weekly_report_config(weekly_report_config)
    configured_groups = {str(key).lower(): str(value) for key, value in dict(config.get("team_groups") or {}).items()}
    team = str(record.get("team") or "").lower()
    return configured_groups.get(team, str(record.get("team") or "Unassigned"))


def _clean_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def _clean_di_stats(stats: dict) -> dict:
    cleaned = dict(stats)
    cleaned["detected_di"] = _clean_number(float(cleaned["detected_di"]))
    cleaned["remaining_di"] = _clean_number(float(cleaned["remaining_di"]))
    return cleaned


def _ratio(numerator: int, denominator: int) -> float:
    return (numerator / denominator) if denominator else 0


def _percent_text(value: float) -> str:
    return f"{value:.0%}"


def load_dataset_records(path: str | Path) -> list[dict]:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise OutputIoError(f"dataset not found: {dataset_path}")
    suffix = dataset_path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("records"), list):
            return list(payload["records"])
        if isinstance(payload, list):
            return list(payload)
        raise OutputIoError(f"dataset json has unsupported shape: {dataset_path}")
    if suffix != ".csv":
        raise OutputIoError(f"dataset format not supported: {dataset_path}")
    import csv

    csv.field_size_limit(10**9)
    records: list[dict] = []
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            record = dict(row)
            for key in ("age_days", "stale_days", "reopen_count"):
                if key in record and record[key] not in {"", None}:
                    record[key] = int(float(str(record[key])))
            for key in ("is_open", "is_closed", "is_customer_feedback", "is_high_risk", "is_reopened", "owner_missing"):
                if key in record:
                    record[key] = str(record[key]).lower() == "true"
            products = str(record.get("products") or "")
            record["products"] = [item.strip() for item in products.split(";") if item.strip()]
            records.append(record)
    return records
