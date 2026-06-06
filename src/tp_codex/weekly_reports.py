from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile
from io import BytesIO

from tp_codex.artifacts import WorkflowArtifact
from tp_codex.errors import InvalidArgsError, OutputIoError


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
APP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"

WORKBOOK_SHEET_PREFIX = "固件质量数据概览-"
WEEKLY_SHEET_NAME_PATTERN = re.compile(r"^固件质量数据概览-Week\d+(?:&Week\d+)?$")
MANUAL_PLACEHOLDER = "待人工补充"
ABNORMAL_CLOSE_KEYWORDS = ("duplicate", "invalid", "expired", "later", "wont fix", "won't fix", "rejected", "拒绝")

TEAM_GROUP_MAP = {
    "esw china ng3 driver": "驱动",
    "esw china ng3 framework": "框架",
    "esw ui team": "UI",
}

SECTION_ROWS = {
    "ng3_weekly": range(9, 13),
    "ng3_effective": range(18, 22),
    "ng3_group": range(24, 27),
    "ng3_customer": range(30, 34),
    "ng3_customer_group": range(36, 39),
    "ng3_stock": range(43, 46),
    "dilu_weekly": range(56, 60),
    "dilu_effective": range(65, 69),
    "dilu_group": range(71, 74),
    "dilu_customer": range(77, 79),
    "dilu_customer_group": range(81, 84),
    "heart": range(107, 110),
    "core": range(118, 121),
    "core_module": range(123, 129),
    "run": range(138, 141),
    "run_group": range(143, 146),
    "race": range(159, 163),
    "race_group": range(165, 168),
}


@dataclass(frozen=True)
class WeekContext:
    report_year: int
    week_number: int
    dataset_week: str
    week_label: str
    title: str
    sheet_name: str


def build_weekly_report_summary(records: Sequence[dict], week_label: str, generated_at: str) -> dict:
    context = resolve_week_context(week_label, generated_at)
    weekly_records = [record for record in records if record.get("created_week") == context.dataset_week]
    product_keys = ["NG3", "Dilu", "心率带2", "Core 2", "Run 2", "Race 3S/Race3"]
    by_product = {}
    for key in product_keys:
        product_records = [record for record in records if _match_product(record) == key]
        if not product_records:
            continue
        by_product[key] = {
            "total_records": len(product_records),
            "weekly_new_records": sum(1 for record in product_records if record.get("created_week") == context.dataset_week),
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
    week_label: str,
    template_path: str,
    generated_at: str,
) -> WorkflowArtifact:
    context = resolve_week_context(week_label, generated_at)
    template = Path(template_path)
    if not template.exists():
        raise OutputIoError(f"weekly report template not found: {template}")
    workbook_bytes = append_weekly_sheet(template.read_bytes(), records, context)
    return WorkflowArtifact(
        filename=f"weekly-report-{context.week_label}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content=workbook_bytes,
    )


def resolve_week_context(week_label: str, generated_at: str) -> WeekContext:
    generated = datetime.fromisoformat(generated_at)
    label = str(week_label or "").strip()
    if not label:
        raise InvalidArgsError("--week-label is required for weekly-report")
    match = re.fullmatch(r"Week(\d{1,2})", label, flags=re.IGNORECASE)
    if match:
        week_number = int(match.group(1))
        report_year = generated.year
        normalized = f"Week{week_number:02d}" if len(match.group(1)) == 2 else f"Week{week_number}"
        return WeekContext(
            report_year=report_year,
            week_number=week_number,
            dataset_week=f"{report_year}-W{week_number:02d}",
            week_label=normalized,
            title=f"固件质量报告{report_year}-{normalized}",
            sheet_name=f"{WORKBOOK_SHEET_PREFIX}{normalized}",
        )
    match = re.fullmatch(r"(\d{4})-W(\d{2})", label, flags=re.IGNORECASE)
    if match:
        report_year = int(match.group(1))
        week_number = int(match.group(2))
        normalized = f"Week{week_number:02d}"
        return WeekContext(
            report_year=report_year,
            week_number=week_number,
            dataset_week=f"{report_year}-W{week_number:02d}",
            week_label=normalized,
            title=f"固件质量报告{report_year}-{normalized}",
            sheet_name=f"{WORKBOOK_SHEET_PREFIX}{normalized}",
        )
    raise InvalidArgsError(f"unsupported week label: {week_label}")


def append_weekly_sheet(template_bytes: bytes, records: Sequence[dict], context: WeekContext) -> bytes:
    entries = _read_zip_entries(template_bytes)
    workbook = ET.fromstring(entries["xl/workbook.xml"])
    workbook_rels = ET.fromstring(entries["xl/_rels/workbook.xml.rels"])
    content_types = ET.fromstring(entries["[Content_Types].xml"])

    source_sheet_name, source_target = _find_source_weekly_sheet(workbook, workbook_rels)
    source_bytes = entries[f"xl/{source_target}"]
    new_sheet_root = ET.fromstring(source_bytes)
    _rewrite_weekly_sheet(new_sheet_root, records, context)

    existing_sheet_indices = [
        int(match.group(1))
        for name in entries
        for match in [re.fullmatch(r"xl/worksheets/sheet(\d+)\.xml", name)]
        if match
    ]
    next_sheet_index = max(existing_sheet_indices) + 1 if existing_sheet_indices else 1
    new_target = f"worksheets/sheet{next_sheet_index}.xml"
    new_target_path = f"xl/{new_target}"
    next_rid = _next_relationship_id(workbook_rels)
    next_sheet_id = _next_sheet_id(workbook)

    ET.SubElement(
        workbook_rels,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Id": next_rid,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": new_target,
        },
    )

    sheets_el = workbook.find(f"{{{MAIN_NS}}}sheets")
    if sheets_el is None:
        raise OutputIoError("workbook has no sheets element")
    ET.SubElement(
        sheets_el,
        f"{{{MAIN_NS}}}sheet",
        {
            "name": context.sheet_name,
            "sheetId": str(next_sheet_id),
            f"{{{REL_NS}}}id": next_rid,
        },
    )

    if not _has_sheet_override(content_types, new_target_path):
        ET.SubElement(
            content_types,
            f"{{{CONTENT_NS}}}Override",
            {
                "PartName": f"/{new_target_path}",
                "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
            },
        )

    _update_app_properties(entries, context.sheet_name)
    entries["xl/workbook.xml"] = _xml_bytes(workbook)
    entries["xl/_rels/workbook.xml.rels"] = _xml_bytes(workbook_rels)
    entries["[Content_Types].xml"] = _xml_bytes(content_types)
    entries[new_target_path] = _xml_bytes(new_sheet_root)
    return _write_zip_entries(entries)


def _rewrite_weekly_sheet(root: ET.Element, records: Sequence[dict], context: WeekContext) -> None:
    ng3_records = [record for record in records if _match_product(record) == "NG3"]
    dilu_records = [record for record in records if _match_product(record) == "Dilu"]
    heart_records = [record for record in records if _match_product(record) == "心率带2"]
    core_records = [record for record in records if _match_product(record) == "Core 2"]
    run_records = [record for record in records if _match_product(record) == "Run 2"]
    race_records = [record for record in records if _match_product(record) == "Race 3S/Race3"]

    _set_cell_value(root, "A1", context.title)

    _clear_rect(root, 2, 4, 6, 5)
    _clear_rect(root, 48, 50, 6, 3)
    _clear_rect(root, 100, 102, 6, 2)
    _clear_rect(root, 112, 114, 6, 1)
    _clear_rect(root, 131, 133, 6, 2)
    _clear_rect(root, 147, 149, 7, 7)

    _fill_ng3_sections(root, ng3_records, context)
    _fill_dilu_sections(root, dilu_records, context)
    _fill_small_product_section(root, heart_records, "心率带2", SECTION_ROWS["heart"], summary_cell="A105")
    _fill_small_product_section(root, core_records, "Core 2", SECTION_ROWS["core"], summary_cell="A116", group_rows=SECTION_ROWS["core_module"])
    _fill_effective_section(root, run_records, SECTION_ROWS["run"], "A136", "Run 2")
    _fill_group_effective_section(root, run_records, SECTION_ROWS["run_group"])
    _fill_effective_section(root, race_records, SECTION_ROWS["race"], "A157", "Race 3S/Race3", severity_mode="cn_with_hint")
    _fill_group_effective_section(root, race_records, SECTION_ROWS["race_group"])

    _set_cell_value(root, "A85", MANUAL_PLACEHOLDER)
    _clear_rect(root, 86, 87, 7, 13)
    _set_cell_value(root, "A92", MANUAL_PLACEHOLDER)
    _clear_rect(root, 93, 94, 7, 6)


def _fill_ng3_sections(root: ET.Element, records: Sequence[dict], context: WeekContext) -> None:
    weekly_records = _weekly_records(records, context)
    effective_records = _year_records(records, context.report_year)
    customer_records = [record for record in effective_records if record.get("is_customer_feedback")]
    _set_cell_value(
        root,
        "A7",
        f"1）{context.week_label}新增{len(weekly_records)}个Bug；2）待分析{sum(1 for r in weekly_records if _status_bucket_ng3(r) == 'new')}个，处理中{sum(1 for r in weekly_records if _status_bucket_ng3(r) == 'processing')}个；3）高风险问题{sum(1 for r in weekly_records if r.get('is_high_risk'))}个。",
    )
    _fill_ng3_weekly_table(root, weekly_records)
    _set_cell_value(
        root,
        "A16",
        f"1、{context.report_year}年过程检出有效Bug总数{len(effective_records)}个，当前待解决{sum(1 for r in effective_records if _status_bucket_effective(r) == 'pending')}个；2、待验证{sum(1 for r in effective_records if _status_bucket_effective(r) == 'pending_verification')}个；3、非常规闭环{sum(1 for r in effective_records if _status_bucket_effective(r) == 'abnormal')}个。",
    )
    _fill_effective_section(root, effective_records, SECTION_ROWS["ng3_effective"], "A16", "NG3", overwrite_summary=False, severity_mode="en")
    _fill_group_effective_section(root, [record for record in effective_records if _severity_key(record) in {"Blocking", "Critical"}], SECTION_ROWS["ng3_group"])

    _set_cell_value(
        root,
        "A28",
        f"1、{context.report_year}年售后问题{len(customer_records)}个；2、已关闭{sum(1 for r in customer_records if _status_bucket_customer(r) == 'closed')}个，待关闭{sum(1 for r in customer_records if _status_bucket_customer(r) == 'pending')}个；3、待验证{sum(1 for r in customer_records if _status_bucket_customer(r) == 'pending_verification')}个。",
    )
    _fill_customer_section(root, customer_records, SECTION_ROWS["ng3_customer"], severity_mode="en")
    _fill_group_customer_section(root, customer_records, SECTION_ROWS["ng3_customer_group"])

    _set_cell_value(
        root,
        "A41",
        f"1、当前存量Bug为{sum(1 for r in records if r.get('is_open'))}个；2、{context.report_year}年关闭{sum(1 for r in records if _closed_in_year(r, context.report_year))}个；3、待验证{sum(1 for r in records if _status_bucket_effective(r) == 'pending_verification')}个。",
    )
    _fill_stock_section(root, records, SECTION_ROWS["ng3_stock"], context.report_year)


def _fill_dilu_sections(root: ET.Element, records: Sequence[dict], context: WeekContext) -> None:
    weekly_records = _weekly_records(records, context)
    effective_records = _year_records(records, context.report_year)
    customer_records = [record for record in effective_records if record.get("is_customer_feedback")]
    _set_cell_value(
        root,
        "A54",
        f"1）{context.week_label}新增{len(weekly_records)}个Bug；2）客诉{sum(1 for r in weekly_records if r.get('is_customer_feedback'))}个，开发过程问题{sum(1 for r in weekly_records if not r.get('is_customer_feedback'))}个；3）待处理{sum(1 for r in weekly_records if _status_bucket_small(r) == 'new')}个。",
    )
    _fill_dilu_weekly_table(root, weekly_records)
    _set_cell_value(
        root,
        "A63",
        f"1）{context.report_year}年有效缺陷{len(effective_records)}个，待解决{sum(1 for r in effective_records if _status_bucket_effective(r) == 'pending')}个；2）待验证{sum(1 for r in effective_records if _status_bucket_effective(r) == 'pending_verification')}个。",
    )
    _fill_effective_section(root, effective_records, SECTION_ROWS["dilu_effective"], "A63", "Dilu", overwrite_summary=False)
    _fill_group_effective_section(root, effective_records, SECTION_ROWS["dilu_group"])
    _set_cell_value(
        root,
        "A75",
        f"1、{context.report_year}年固件售后问题{len(customer_records)}个；2、待解决{sum(1 for r in customer_records if _status_bucket_customer(r) == 'pending')}个；3、待验证{sum(1 for r in customer_records if _status_bucket_customer(r) == 'pending_verification')}个。",
    )
    _fill_customer_section(root, customer_records, SECTION_ROWS["dilu_customer"])
    _fill_group_customer_section(root, customer_records, SECTION_ROWS["dilu_customer_group"])


def _fill_small_product_section(
    root: ET.Element,
    records: Sequence[dict],
    product_name: str,
    severity_rows: range,
    summary_cell: str,
    group_rows: range | None = None,
) -> None:
    _set_cell_value(
        root,
        summary_cell,
        f"1、{product_name}当前累计缺陷{len(records)}个；2、待解决{sum(1 for r in records if _status_bucket_small(r) in {'new', 'processing'})}个；3、已验证{sum(1 for r in records if _status_bucket_small(r) == 'verified')}个。",
    )
    _fill_status_distribution_table(root, records, severity_rows)
    if group_rows:
        _fill_group_status_distribution(root, records, group_rows)


def _fill_effective_section(
    root: ET.Element,
    records: Sequence[dict],
    rows: range,
    summary_cell: str,
    product_name: str,
    overwrite_summary: bool = True,
    severity_mode: str = "cn",
) -> None:
    if overwrite_summary:
        _set_cell_value(
            root,
            summary_cell,
            f"1、{product_name}当前累计有效缺陷{len(records)}个；2、待解决{sum(1 for r in records if _status_bucket_effective(r) == 'pending')}个；3、待验证{sum(1 for r in records if _status_bucket_effective(r) == 'pending_verification')}个。",
        )
    labels = [_get_cell_text(root, f"A{row}") for row in rows]
    total_total = pending_total = verification_total = abnormal_total = 0
    verified_total = 0
    for row, label in zip(rows, labels):
        severity_records = [record for record in records if _severity_label_for_mode(record, severity_mode) == label]
        total = len(severity_records)
        pending = sum(1 for record in severity_records if _status_bucket_effective(record) == "pending")
        pending_verification = sum(1 for record in severity_records if _status_bucket_effective(record) == "pending_verification")
        abnormal = sum(1 for record in severity_records if _status_bucket_effective(record) == "abnormal")
        verified = sum(1 for record in severity_records if _status_bucket_effective(record) == "verified")
        close_rate = ((total - pending) / total) if total else 0
        verify_base = max(total - pending - abnormal, 0)
        verify_rate = (verified / verify_base) if verify_base else 0
        total_total += total
        pending_total += pending
        verification_total += pending_verification
        abnormal_total += abnormal
        verified_total += verified
        _set_row_values(root, row, [label, total, pending, pending_verification, abnormal, close_rate, verify_rate])
    total_row = rows.stop
    total_base = max(total_total - pending_total - abnormal_total, 0)
    _set_row_values(
        root,
        total_row,
        [
            "总计",
            total_total,
            pending_total,
            verification_total,
            abnormal_total,
            ((total_total - pending_total) / total_total) if total_total else 0,
            (verified_total / total_base) if total_base else 0,
        ],
    )


def _fill_group_effective_section(root: ET.Element, records: Sequence[dict], rows: range) -> None:
    total_total = pending_total = verification_total = abnormal_total = 0
    verified_total = 0
    for row in rows:
        label = _get_cell_text(root, f"A{row}")
        if label == "总计":
            continue
        group_records = [record for record in records if _group_label(record) == label]
        total = len(group_records)
        pending = sum(1 for record in group_records if _status_bucket_effective(record) == "pending")
        pending_verification = sum(1 for record in group_records if _status_bucket_effective(record) == "pending_verification")
        abnormal = sum(1 for record in group_records if _status_bucket_effective(record) == "abnormal")
        verified = sum(1 for record in group_records if _status_bucket_effective(record) == "verified")
        total_total += total
        pending_total += pending
        verification_total += pending_verification
        abnormal_total += abnormal
        verified_total += verified
        base = max(total - pending - abnormal, 0)
        _set_row_values(root, row, [label, total, pending, pending_verification, abnormal, ((total - pending) / total) if total else 0, (verified / base) if base else 0])


def _fill_customer_section(root: ET.Element, records: Sequence[dict], rows: range, severity_mode: str = "cn") -> None:
    labels = [_get_cell_text(root, f"A{row}") for row in rows]
    totals = [0, 0, 0, 0, 0]
    for row, label in zip(rows, labels):
        severity_records = [record for record in records if _severity_label_for_mode(record, severity_mode) == label]
        total = len(severity_records)
        closed = sum(1 for record in severity_records if _status_bucket_customer(record) == "closed")
        pending = sum(1 for record in severity_records if _status_bucket_customer(record) == "pending")
        pending_verification = sum(1 for record in severity_records if _status_bucket_customer(record) == "pending_verification")
        abnormal = sum(1 for record in severity_records if _status_bucket_customer(record) == "abnormal")
        totals[0] += total
        totals[1] += closed
        totals[2] += pending
        totals[3] += pending_verification
        totals[4] += abnormal
        _set_row_values(root, row, [label, total, closed, pending, pending_verification, abnormal, (closed / total) if total else 0])
    total_row = rows.stop
    _set_row_values(root, total_row, ["总计", totals[0], totals[1], totals[2], totals[3], totals[4], (totals[1] / totals[0]) if totals[0] else 0])


def _fill_group_customer_section(root: ET.Element, records: Sequence[dict], rows: range) -> None:
    for row in rows:
        label = _get_cell_text(root, f"A{row}")
        if label == "总计":
            continue
        group_records = [record for record in records if _group_label(record) == label]
        blocking_overdue = sum(1 for record in group_records if _severity_key(record) == "Blocking" and _status_bucket_customer(record) == "pending")
        critical_overdue = sum(1 for record in group_records if _severity_key(record) == "Critical" and _status_bucket_customer(record) == "pending")
        normal_overdue = sum(1 for record in group_records if _severity_key(record) in {"Major", "Normal"} and _status_bucket_customer(record) == "pending")
        if _row_width(root, row) >= 6:
            _set_row_values(root, row, [label, blocking_overdue, 0, critical_overdue, normal_overdue, MANUAL_PLACEHOLDER])
        else:
            _set_row_values(root, row, [label, critical_overdue, normal_overdue, MANUAL_PLACEHOLDER])
    if rows:
        total_row = rows.stop
        if _get_cell_text(root, f"A{total_row}") == "总计":
            width = _row_width(root, rows.start)
            if width >= 6:
                _set_row_values(root, total_row, ["总计", 0, 0, 0, 0, ""])
            else:
                _set_row_values(root, total_row, ["总计", 0, 0, ""])


def _fill_stock_section(root: ET.Element, records: Sequence[dict], rows: range, report_year: int) -> None:
    total_backlog = total_closed = total_pending = total_repro = total_verify = 0
    for row in rows:
        label = _get_cell_text(root, f"A{row}")
        group_records = [record for record in records if _group_label(record) == label]
        backlog = sum(1 for record in group_records if record.get("is_open"))
        year_closed = sum(1 for record in group_records if _closed_in_year(record, report_year))
        pending_dev = sum(1 for record in group_records if _status_bucket_effective(record) == "pending")
        pending_verify = sum(1 for record in group_records if _status_bucket_effective(record) == "pending_verification")
        reduction_rate = (year_closed / (backlog + year_closed)) if (backlog + year_closed) else 0
        total_backlog += backlog
        total_closed += year_closed
        total_pending += pending_dev
        total_verify += pending_verify
        _set_row_values(root, row, [label, backlog, year_closed, pending_dev, 0, pending_verify, reduction_rate])
    total_row = rows.stop
    _set_row_values(
        root,
        total_row,
        [
            "总计",
            total_backlog,
            total_closed,
            total_pending,
            total_repro,
            total_verify,
            (total_closed / (total_backlog + total_closed)) if (total_backlog + total_closed) else 0,
        ],
    )


def _fill_status_distribution_table(root: ET.Element, records: Sequence[dict], rows: range) -> None:
    total_total = total_new = total_processing = total_resolved = total_verified = total_rejected = 0
    for row in rows:
        label = _get_cell_text(root, f"A{row}")
        severity_records = [record for record in records if _severity_label_for_mode(record, "cn") == label]
        total = len(severity_records)
        new = sum(1 for record in severity_records if _status_bucket_small(record) == "new")
        processing = sum(1 for record in severity_records if _status_bucket_small(record) == "processing")
        resolved = sum(1 for record in severity_records if _status_bucket_small(record) == "resolved")
        verified = sum(1 for record in severity_records if _status_bucket_small(record) == "verified")
        rejected = sum(1 for record in severity_records if _status_bucket_small(record) == "rejected")
        total_total += total
        total_new += new
        total_processing += processing
        total_resolved += resolved
        total_verified += verified
        total_rejected += rejected
        _set_row_values(root, row, [label, total, new, processing, resolved, verified, rejected])
    total_row = rows.stop
    _set_row_values(root, total_row, ["总计", total_total, total_new, total_processing, total_resolved, total_verified, total_rejected])


def _fill_group_status_distribution(root: ET.Element, records: Sequence[dict], rows: range) -> None:
    totals = [0, 0, 0, 0, 0, 0]
    for row in rows:
        label = _get_cell_text(root, f"A{row}")
        if label == "总计":
            continue
        group_records = [record for record in records if _group_label(record) == label]
        total = len(group_records)
        new = sum(1 for record in group_records if _status_bucket_small(record) == "new")
        processing = sum(1 for record in group_records if _status_bucket_small(record) == "processing")
        resolved = sum(1 for record in group_records if _status_bucket_small(record) == "resolved")
        verified = sum(1 for record in group_records if _status_bucket_small(record) == "verified")
        rejected = sum(1 for record in group_records if _status_bucket_small(record) == "rejected")
        totals[0] += total
        totals[1] += new
        totals[2] += processing
        totals[3] += resolved
        totals[4] += verified
        totals[5] += rejected
        _set_row_values(root, row, [label, total, new, processing, resolved, verified, rejected])
    total_row = rows.stop
    if _get_cell_text(root, f"A{total_row}") == "总计":
        _set_row_values(root, total_row, ["总计", *totals])


def _fill_ng3_weekly_table(root: ET.Element, records: Sequence[dict]) -> None:
    labels = ["Blocking", "Critical", "Major", "Normal"]
    totals = [0, 0, 0, 0, 0, 0]
    for offset, label in enumerate(labels, start=9):
        severity_records = [record for record in records if _severity_key(record) == label]
        values = [
            len(severity_records),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "new"),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "processing"),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "resolved"),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "verified"),
            sum(1 for record in severity_records if _status_bucket_ng3(record) == "abnormal"),
        ]
        totals = [current + value for current, value in zip(totals, values)]
        _set_row_values(root, offset, [label, *values])
    _set_row_values(root, 13, ["总计", *totals])
    total_count = totals[0]
    percentages = [value / total_count if total_count else 0 for value in totals[1:]]
    _set_row_values(root, 14, ["各状态问题占比", "/", *percentages])


def _fill_dilu_weekly_table(root: ET.Element, records: Sequence[dict]) -> None:
    labels = ["致命", "严重", "一般", "提示"]
    totals = [0, 0, 0, 0, 0, 0]
    for offset, label in enumerate(labels, start=56):
        severity_records = [record for record in records if _severity_label_for_mode(record, "cn") == label]
        values = [
            len(severity_records),
            sum(1 for record in severity_records if record.get("is_customer_feedback")),
            sum(1 for record in severity_records if not record.get("is_customer_feedback")),
            sum(1 for record in severity_records if _status_bucket_small(record) == "new"),
            sum(1 for record in severity_records if _status_bucket_small(record) == "processing"),
            sum(1 for record in severity_records if _status_bucket_small(record) in {"resolved", "verified", "rejected"}),
        ]
        totals = [current + value for current, value in zip(totals, values)]
        _set_row_values(root, offset, [label, *values])
    _set_row_values(root, 60, ["总计", *totals])
    total_count = totals[0]
    percentages = [value / total_count if total_count else 0 for value in totals[1:]]
    _set_row_values(root, 61, ["占比", "/", *percentages])


def _weekly_records(records: Sequence[dict], context: WeekContext) -> list[dict]:
    return [record for record in records if record.get("created_week") == context.dataset_week]


def _year_records(records: Sequence[dict], report_year: int) -> list[dict]:
    return [record for record in records if _record_year(record.get("created_at")) == report_year]


def _record_year(value: object) -> int | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value)).year


def _closed_in_year(record: dict, report_year: int) -> bool:
    changed_at = record.get("last_status_change_at")
    if not changed_at or not record.get("is_closed"):
        return False
    return datetime.fromisoformat(str(changed_at)).year == report_year


def _severity_key(record: dict) -> str:
    return str(record.get("severity") or "")


def _severity_label_for_mode(record: dict, mode: str) -> str:
    severity = _severity_key(record).lower()
    if mode == "en":
        mapping = {
            "blocking": "Blocking",
            "critical": "Critical",
            "major": "Major",
            "normal": "Normal",
        }
        return mapping.get(severity, str(record.get("severity") or "Normal"))
    mapping = {
        "blocking": "致命",
        "critical": "严重",
        "major": "一般",
        "normal": "提示",
    }
    return mapping.get(severity, "一般")


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
    if "verified" in status_raw or record.get("status_group") == "ready_for_qa":
        return "verified"
    if any(token in status_raw for token in ("resolved", "fix", "done")) or record.get("status_group") == "closed":
        return "resolved"
    if any(token in status_raw for token in ("new", "planned", "open")):
        return "new"
    return "processing"


def _status_bucket_effective(record: dict) -> str:
    bucket = _status_bucket_small(record)
    if bucket in {"new", "processing"}:
        return "pending"
    if bucket == "resolved":
        return "pending_verification"
    if bucket == "verified":
        return "verified"
    return "abnormal"


def _status_bucket_customer(record: dict) -> str:
    bucket = _status_bucket_small(record)
    if bucket in {"new", "processing"}:
        return "pending"
    if bucket == "resolved":
        return "pending_verification"
    if bucket == "verified":
        return "closed"
    return "abnormal"


def _is_abnormal_close(record: dict) -> bool:
    status_raw = str(record.get("status_raw") or "").lower()
    return any(keyword in status_raw for keyword in ABNORMAL_CLOSE_KEYWORDS)


def _match_product(record: dict) -> str | None:
    products = " ".join(str(item) for item in (record.get("products") or [])).lower()
    if any(keyword in products for keyword in ("dilu",)):
        return "Dilu"
    if any(keyword in products for keyword in ("心率带", "heart")):
        return "心率带2"
    if any(keyword in products for keyword in ("core 2", "core2")):
        return "Core 2"
    if any(keyword in products for keyword in ("run 2", "run2")):
        return "Run 2"
    if any(keyword in products for keyword in ("race 3s", "race3s", "race3", "race 3")):
        return "Race 3S/Race3"
    if "ng3" in products:
        return "NG3"
    team = str(record.get("team") or "").lower()
    if team in TEAM_GROUP_MAP:
        return "NG3"
    return None


def _group_label(record: dict) -> str:
    team = str(record.get("team") or "").lower()
    return TEAM_GROUP_MAP.get(team, str(record.get("team") or "Unassigned"))


def _read_zip_entries(data: bytes) -> dict[str, bytes]:
    with ZipFile(BytesIO(data), "r") as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _write_zip_entries(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def _find_source_weekly_sheet(workbook: ET.Element, workbook_rels: ET.Element) -> tuple[str, str]:
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in workbook_rels.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    sheets = workbook.findall(f".//{{{MAIN_NS}}}sheet")
    weekly_sheets = [sheet for sheet in sheets if WEEKLY_SHEET_NAME_PATTERN.match(sheet.attrib.get("name", ""))]
    if not weekly_sheets:
        raise OutputIoError("weekly report template does not contain any weekly sheets")
    source_sheet = weekly_sheets[-1]
    rel_id = source_sheet.attrib[f"{{{REL_NS}}}id"]
    return source_sheet.attrib["name"], rel_map[rel_id]


def _next_relationship_id(workbook_rels: ET.Element) -> str:
    current = 0
    for rel in workbook_rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
        match = re.fullmatch(r"rId(\d+)", rel.attrib.get("Id", ""))
        if match:
            current = max(current, int(match.group(1)))
    return f"rId{current + 1}"


def _next_sheet_id(workbook: ET.Element) -> int:
    current = 0
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        current = max(current, int(sheet.attrib.get("sheetId", "0")))
    return current + 1


def _has_sheet_override(content_types: ET.Element, target_path: str) -> bool:
    expected = f"/{target_path}"
    return any(node.attrib.get("PartName") == expected for node in content_types.findall(f"{{{CONTENT_NS}}}Override"))


def _update_app_properties(entries: dict[str, bytes], sheet_name: str) -> None:
    if "docProps/app.xml" not in entries:
        return
    root = ET.fromstring(entries["docProps/app.xml"])
    titles_container = root.find(f".//{{{APP_NS}}}TitlesOfParts/{{{VT_NS}}}vector")
    if titles_container is not None:
        ET.SubElement(titles_container, f"{{{VT_NS}}}lpstr").text = sheet_name
        titles_container.set("size", str(len(titles_container.findall(f'{{{VT_NS}}}lpstr'))))
    i4 = root.find(f".//{{{APP_NS}}}HeadingPairs//{{{VT_NS}}}i4")
    if i4 is not None:
        try:
            i4.text = str(int(i4.text or "0") + 1)
        except ValueError:
            pass
    entries["docProps/app.xml"] = _xml_bytes(root)


def _xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _clear_rect(root: ET.Element, start_row: int, start_col: int, width: int, height: int) -> None:
    for row in range(start_row, start_row + height):
        for col in range(start_col, start_col + width):
            _set_cell_value(root, f"{_column_name(col)}{row}", "")


def _set_row_values(root: ET.Element, row: int, values: Sequence[object]) -> None:
    for col, value in enumerate(values, start=1):
        _set_cell_value(root, f"{_column_name(col)}{row}", value)


def _get_cell_text(root: ET.Element, cell_ref: str) -> str:
    cell = _find_cell(root, cell_ref)
    if cell is None:
        return ""
    if cell.attrib.get("t") == "inlineStr":
        return cell.findtext(f"{{{MAIN_NS}}}is/{{{MAIN_NS}}}t", default="")
    return cell.findtext(f"{{{MAIN_NS}}}v", default="")


def _row_width(root: ET.Element, row: int) -> int:
    row_element = _find_row(root, row)
    if row_element is None:
        return 0
    return len(row_element.findall(f"{{{MAIN_NS}}}c"))


def _set_cell_value(root: ET.Element, cell_ref: str, value: object) -> None:
    cell = _ensure_cell(root, cell_ref)
    for child_tag in (f"{{{MAIN_NS}}}f", f"{{{MAIN_NS}}}v", f"{{{MAIN_NS}}}is"):
        child = cell.find(child_tag)
        if child is not None:
            cell.remove(child)
    if value is None or value == "":
        cell.attrib["t"] = "inlineStr"
        is_el = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
        t_el = ET.SubElement(is_el, f"{{{MAIN_NS}}}t")
        t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t_el.text = ""
        return
    if isinstance(value, bool):
        cell.attrib["t"] = "b"
        ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = "1" if value else "0"
        return
    if isinstance(value, (int, float)):
        cell.attrib.pop("t", None)
        ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = f"{value:.6f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
        return
    cell.attrib["t"] = "inlineStr"
    is_el = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
    t_el = ET.SubElement(is_el, f"{{{MAIN_NS}}}t")
    t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t_el.text = str(value)


def _find_row(root: ET.Element, row_number: int) -> ET.Element | None:
    sheet_data = root.find(f"{{{MAIN_NS}}}sheetData")
    if sheet_data is None:
        return None
    for row in sheet_data.findall(f"{{{MAIN_NS}}}row"):
        if int(row.attrib.get("r", "0")) == row_number:
            return row
    return None


def _find_cell(root: ET.Element, cell_ref: str) -> ET.Element | None:
    row_number = _cell_row(cell_ref)
    row = _find_row(root, row_number)
    if row is None:
        return None
    for cell in row.findall(f"{{{MAIN_NS}}}c"):
        if cell.attrib.get("r") == cell_ref:
            return cell
    return None


def _ensure_cell(root: ET.Element, cell_ref: str) -> ET.Element:
    sheet_data = root.find(f"{{{MAIN_NS}}}sheetData")
    if sheet_data is None:
        sheet_data = ET.SubElement(root, f"{{{MAIN_NS}}}sheetData")
    row_number = _cell_row(cell_ref)
    row = _find_row(root, row_number)
    if row is None:
        row = ET.Element(f"{{{MAIN_NS}}}row", {"r": str(row_number)})
        inserted = False
        for index, existing in enumerate(list(sheet_data)):
            if int(existing.attrib.get("r", "0")) > row_number:
                sheet_data.insert(index, row)
                inserted = True
                break
        if not inserted:
            sheet_data.append(row)
    for cell in row.findall(f"{{{MAIN_NS}}}c"):
        if cell.attrib.get("r") == cell_ref:
            return cell
    new_cell = ET.Element(f"{{{MAIN_NS}}}c", {"r": cell_ref})
    inserted = False
    new_col = _cell_col_index(cell_ref)
    for index, existing in enumerate(list(row)):
        if _cell_col_index(existing.attrib.get("r", "A1")) > new_col:
            row.insert(index, new_cell)
            inserted = True
            break
    if not inserted:
        row.append(new_cell)
    return new_cell


def _cell_row(cell_ref: str) -> int:
    match = re.fullmatch(r"[A-Z]+(\d+)", cell_ref)
    if not match:
        raise ValueError(f"invalid cell reference: {cell_ref}")
    return int(match.group(1))


def _cell_col_index(cell_ref: str) -> int:
    match = re.fullmatch(r"([A-Z]+)\d+", cell_ref)
    if not match:
        raise ValueError(f"invalid cell reference: {cell_ref}")
    return _column_index(match.group(1))


def _column_index(label: str) -> int:
    value = 0
    for char in label:
        value = value * 26 + (ord(char) - 64)
    return value


def _column_name(index: int) -> str:
    label = ""
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        label = chr(65 + remainder) + label
    return label or "A"
