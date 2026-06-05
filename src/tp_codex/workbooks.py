from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Iterable, Sequence
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from tp_codex.artifacts import WorkflowArtifact
from tp_codex.datasets import BUG_DATASET_FIELDNAMES
from tp_codex.settings import WorkflowRulesSettings


QUALITY_WORKBOOK_SHEET_NAMES = [
    "Overview",
    "Bug_Master",
    "Team_Status",
    "Severity_Risk",
    "Aging_Stale",
    "Customer_Feedback",
    "Weekly_Trend",
    "Monthly_Trend",
    "Top_Risks",
    "Unmapped_Status",
]

TOP_RISK_FIELDNAMES = [
    "bug_id",
    "name",
    "team",
    "severity",
    "status_group",
    "risk_level",
    "stale_days",
    "reopen_count",
    "owner",
    "audit_focus",
]

CUSTOMER_FEEDBACK_FIELDNAMES = [
    "bug_id",
    "name",
    "team",
    "severity",
    "status_group",
    "risk_level",
    "stale_days",
    "reopen_count",
    "owner",
]


@dataclass(frozen=True)
class WorkbookRow:
    values: Sequence[object]
    kind: str = "body"


@dataclass(frozen=True)
class WorkbookSheet:
    name: str
    rows: Sequence[WorkbookRow]


def build_quality_workbook_artifact(
    records: Iterable[dict],
    workflow_rules: WorkflowRulesSettings,
    metadata: dict | None = None,
    warnings: Sequence[str] | None = None,
) -> WorkflowArtifact:
    rows = list(records)
    workbook_metadata = dict(metadata or {})
    workbook_warnings = list(warnings or [])
    sheets = build_quality_workbook_sheets(rows, workflow_rules, workbook_metadata, workbook_warnings)
    generated_at = str(workbook_metadata.get("generated_at") or datetime.now(timezone.utc).isoformat())
    content = _build_xlsx(sheets, generated_at)
    return WorkflowArtifact(
        filename="quality-analysis-workbook.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content=content,
    )


def build_quality_workbook_sheets(
    records: list[dict],
    workflow_rules: WorkflowRulesSettings,
    metadata: dict | None = None,
    warnings: Sequence[str] | None = None,
) -> list[WorkbookSheet]:
    workbook_metadata = dict(metadata or {})
    workbook_warnings = list(warnings or [])
    return [
        _overview_sheet(records, workflow_rules, workbook_metadata, workbook_warnings),
        _table_sheet("Bug_Master", BUG_DATASET_FIELDNAMES, records),
        _team_status_sheet(records, workflow_rules),
        _severity_risk_sheet(records),
        _aging_stale_sheet(records, workflow_rules.stale_days),
        _customer_feedback_sheet(records, workflow_rules.stale_days),
        _weekly_trend_sheet(records),
        _monthly_trend_sheet(records),
        _top_risks_sheet(records, workflow_rules.stale_days),
        _unmapped_status_sheet(records),
    ]


def _overview_sheet(
    records: list[dict],
    workflow_rules: WorkflowRulesSettings,
    metadata: dict,
    warnings: list[str],
) -> WorkbookSheet:
    stale_threshold = workflow_rules.stale_days
    metrics = [
        ("generated_at", metadata.get("generated_at")),
        ("total_records", len(records)),
        ("open_records", sum(1 for record in records if record.get("is_open"))),
        ("closed_records", sum(1 for record in records if record.get("is_closed"))),
        ("high_risk_records", sum(1 for record in records if record.get("is_high_risk"))),
        ("customer_feedback_records", sum(1 for record in records if record.get("is_customer_feedback"))),
        ("stale_records", sum(1 for record in records if (record.get("stale_days") or 0) >= stale_threshold)),
        ("reopened_records", sum(1 for record in records if record.get("is_reopened"))),
        ("owner_missing_records", sum(1 for record in records if record.get("owner_missing"))),
        ("unmapped_status_records", sum(1 for record in records if record.get("status_group") == "unmapped")),
    ]
    rows: list[WorkbookRow] = [
        WorkbookRow(["Quality Analysis Workbook"], kind="title"),
        WorkbookRow(["Metric", "Value"], kind="header"),
    ]
    rows.extend(WorkbookRow([name, value]) for name, value in metrics)
    rows.append(WorkbookRow([], kind="body"))
    rows.append(WorkbookRow(["Warnings"], kind="title"))
    rows.append(WorkbookRow(["warning_code"], kind="header"))
    if warnings:
        rows.extend(WorkbookRow([warning]) for warning in warnings)
    else:
        rows.append(WorkbookRow(["none"]))
    rows.extend(_distribution_rows("Status Group Distribution", "status_group", records))
    rows.extend(_distribution_rows("Team Distribution", "team", records))
    rows.extend(_distribution_rows("Severity Distribution", "severity", records))
    return WorkbookSheet(name="Overview", rows=rows)


def _distribution_rows(title: str, key: str, records: list[dict]) -> list[WorkbookRow]:
    counts = Counter(str(record.get(key) or "null") for record in records)
    rows = [WorkbookRow([], kind="body"), WorkbookRow([title], kind="title"), WorkbookRow([key, "count"], kind="header")]
    for label in sorted(counts):
        rows.append(WorkbookRow([label, counts[label]]))
    if not counts:
        rows.append(WorkbookRow(["none", 0]))
    return rows


def _table_sheet(name: str, fieldnames: Sequence[str], records: list[dict]) -> WorkbookSheet:
    rows = [WorkbookRow(list(fieldnames), kind="header")]
    for record in records:
        rows.append(WorkbookRow([record.get(field) for field in fieldnames]))
    return WorkbookSheet(name=name, rows=rows)


def _team_status_sheet(records: list[dict], workflow_rules: WorkflowRulesSettings) -> WorkbookSheet:
    status_groups = _ordered_status_groups(records, workflow_rules)
    teams = sorted({str(record.get("team") or "Unassigned") for record in records})
    rows = [
        WorkbookRow(["Team Status"], kind="title"),
        WorkbookRow(["team", *status_groups, "total_records"], kind="header"),
    ]
    for team in teams:
        counts = [sum(1 for record in records if str(record.get("team") or "Unassigned") == team and str(record.get("status_group") or "null") == status) for status in status_groups]
        rows.append(WorkbookRow([team, *counts, sum(counts)]))
    if not teams:
        rows.append(WorkbookRow(["none", *([0] * len(status_groups)), 0]))
    return WorkbookSheet(name="Team_Status", rows=rows)


def _severity_risk_sheet(records: list[dict]) -> WorkbookSheet:
    severities = sorted({str(record.get("severity") or "null") for record in records})
    risk_levels = [label for label in ["high", "medium", "low"] if any(str(record.get("risk_level") or "null") == label for record in records)]
    extras = sorted({str(record.get("risk_level") or "null") for record in records if str(record.get("risk_level") or "null") not in {"high", "medium", "low"}})
    risk_levels.extend(extras)
    rows = [
        WorkbookRow(["Severity Risk"], kind="title"),
        WorkbookRow(["severity", *risk_levels, "total_records"], kind="header"),
    ]
    for severity in severities:
        counts = [sum(1 for record in records if str(record.get("severity") or "null") == severity and str(record.get("risk_level") or "null") == level) for level in risk_levels]
        rows.append(WorkbookRow([severity, *counts, sum(counts)]))
    if not severities:
        rows.append(WorkbookRow(["none", *([0] * len(risk_levels)), 0]))
    return WorkbookSheet(name="Severity_Risk", rows=rows)


def _aging_stale_sheet(records: list[dict], stale_threshold: int) -> WorkbookSheet:
    buckets = [bucket for bucket in ["0-7", "8-14", "15-30", "31-60", "60+"] if any(record.get("aging_bucket") == bucket for record in records)]
    extras = sorted({str(record.get("aging_bucket") or "null") for record in records if record.get("aging_bucket") not in {"0-7", "8-14", "15-30", "31-60", "60+"}})
    buckets.extend(extras)
    rows = [
        WorkbookRow(["Aging Stale"], kind="title"),
        WorkbookRow(
            ["aging_bucket", "total_records", "open_records", "stale_records", "owner_missing_records", "high_risk_records"],
            kind="header",
        ),
    ]
    for bucket in buckets:
        bucket_records = [record for record in records if str(record.get("aging_bucket") or "null") == bucket]
        rows.append(
            WorkbookRow(
                [
                    bucket,
                    len(bucket_records),
                    sum(1 for record in bucket_records if record.get("is_open")),
                    sum(1 for record in bucket_records if (record.get("stale_days") or 0) >= stale_threshold),
                    sum(1 for record in bucket_records if record.get("owner_missing")),
                    sum(1 for record in bucket_records if record.get("is_high_risk")),
                ]
            )
        )
    if not buckets:
        rows.append(WorkbookRow(["none", 0, 0, 0, 0, 0]))
    return WorkbookSheet(name="Aging_Stale", rows=rows)


def _customer_feedback_sheet(records: list[dict], stale_threshold: int) -> WorkbookSheet:
    customer_feedback_records = [record for record in records if record.get("is_customer_feedback")]
    rows: list[WorkbookRow] = [
        WorkbookRow(["Customer Feedback"], kind="title"),
        WorkbookRow(["Metric", "Value"], kind="header"),
        WorkbookRow(["total_records", len(customer_feedback_records)]),
        WorkbookRow(["open_records", sum(1 for record in customer_feedback_records if record.get("is_open"))]),
        WorkbookRow(["high_risk_records", sum(1 for record in customer_feedback_records if record.get("is_high_risk"))]),
        WorkbookRow(["stale_records", sum(1 for record in customer_feedback_records if (record.get("stale_days") or 0) >= stale_threshold)]),
        WorkbookRow(["reopened_records", sum(1 for record in customer_feedback_records if record.get("is_reopened"))]),
    ]
    rows.extend(_distribution_rows("By Team", "team", customer_feedback_records))
    rows.extend(_distribution_rows("By Status Group", "status_group", customer_feedback_records))
    rows.append(WorkbookRow([], kind="body"))
    rows.append(WorkbookRow(["Detail"], kind="title"))
    rows.append(WorkbookRow(list(CUSTOMER_FEEDBACK_FIELDNAMES), kind="header"))
    for record in customer_feedback_records:
        rows.append(WorkbookRow([record.get(field) for field in CUSTOMER_FEEDBACK_FIELDNAMES]))
    return WorkbookSheet(name="Customer_Feedback", rows=rows)


def _weekly_trend_sheet(records: list[dict]) -> WorkbookSheet:
    created_counts = Counter(str(record.get("created_week") or "unknown") for record in records if record.get("created_week"))
    high_risk_created_counts = Counter(str(record.get("created_week") or "unknown") for record in records if record.get("created_week") and record.get("is_high_risk"))
    customer_feedback_created_counts = Counter(str(record.get("created_week") or "unknown") for record in records if record.get("created_week") and record.get("is_customer_feedback"))
    closed_counts = Counter(
        _week_label(record.get("last_status_change_at"))
        for record in records
        if record.get("is_closed") and record.get("last_status_change_at")
    )
    weeks = sorted(set(created_counts) | set(closed_counts))
    rows = [
        WorkbookRow(["Weekly Trend"], kind="title"),
        WorkbookRow(
            ["week", "created_count", "closed_count", "net_change", "high_risk_created_count", "customer_feedback_created_count"],
            kind="header",
        ),
    ]
    for week in weeks:
        created_count = created_counts.get(week, 0)
        closed_count = closed_counts.get(week, 0)
        rows.append(
            WorkbookRow(
                [
                    week,
                    created_count,
                    closed_count,
                    created_count - closed_count,
                    high_risk_created_counts.get(week, 0),
                    customer_feedback_created_counts.get(week, 0),
                ]
            )
        )
    if not weeks:
        rows.append(WorkbookRow(["none", 0, 0, 0, 0, 0]))
    return WorkbookSheet(name="Weekly_Trend", rows=rows)


def _monthly_trend_sheet(records: list[dict]) -> WorkbookSheet:
    created_counts = Counter(str(record.get("created_month") or "unknown") for record in records if record.get("created_month"))
    high_risk_created_counts = Counter(str(record.get("created_month") or "unknown") for record in records if record.get("created_month") and record.get("is_high_risk"))
    customer_feedback_created_counts = Counter(str(record.get("created_month") or "unknown") for record in records if record.get("created_month") and record.get("is_customer_feedback"))
    closed_counts = Counter(
        _month_label(record.get("last_status_change_at"))
        for record in records
        if record.get("is_closed") and record.get("last_status_change_at")
    )
    reopened_counts = Counter(str(record.get("updated_month") or "unknown") for record in records if record.get("updated_month") and record.get("is_reopened"))
    months = sorted(set(created_counts) | set(closed_counts) | set(reopened_counts))
    rows = [
        WorkbookRow(["Monthly Trend"], kind="title"),
        WorkbookRow(
            ["month", "created_count", "closed_count", "reopened_count", "customer_feedback_created_count", "high_risk_created_count"],
            kind="header",
        ),
    ]
    for month in months:
        rows.append(
            WorkbookRow(
                [
                    month,
                    created_counts.get(month, 0),
                    closed_counts.get(month, 0),
                    reopened_counts.get(month, 0),
                    customer_feedback_created_counts.get(month, 0),
                    high_risk_created_counts.get(month, 0),
                ]
            )
        )
    if not months:
        rows.append(WorkbookRow(["none", 0, 0, 0, 0, 0]))
    return WorkbookSheet(name="Monthly_Trend", rows=rows)


def _top_risks_sheet(records: list[dict], stale_threshold: int) -> WorkbookSheet:
    risk_records = [record for record in records if _is_top_risk_candidate(record, stale_threshold)]
    risk_records.sort(key=lambda record: _top_risk_sort_key(record))
    rows = [
        WorkbookRow(["Top Risks"], kind="title"),
        WorkbookRow(list(TOP_RISK_FIELDNAMES), kind="header"),
    ]
    for record in risk_records:
        rows.append(WorkbookRow([record.get(field) for field in TOP_RISK_FIELDNAMES]))
    return WorkbookSheet(name="Top_Risks", rows=rows)


def _unmapped_status_sheet(records: list[dict]) -> WorkbookSheet:
    unmapped_records = [record for record in records if record.get("status_group") == "unmapped"]
    rows = [
        WorkbookRow(["Unmapped Status"], kind="title"),
        WorkbookRow(list(BUG_DATASET_FIELDNAMES), kind="header"),
    ]
    for record in unmapped_records:
        rows.append(WorkbookRow([record.get(field) for field in BUG_DATASET_FIELDNAMES]))
    return WorkbookSheet(name="Unmapped_Status", rows=rows)


def _ordered_status_groups(records: list[dict], workflow_rules: WorkflowRulesSettings) -> list[str]:
    configured = list(workflow_rules.status_groups.keys())
    seen = set(configured)
    present = [status for status in configured if any(str(record.get("status_group") or "null") == status for record in records)]
    extras = sorted({str(record.get("status_group") or "null") for record in records if str(record.get("status_group") or "null") not in seen})
    return present + extras


def _is_top_risk_candidate(record: dict, stale_threshold: int) -> bool:
    return bool(
        record.get("risk_level") == "high"
        or record.get("is_customer_feedback")
        or record.get("owner_missing")
        or record.get("status_group") == "unmapped"
        or (record.get("stale_days") or 0) >= stale_threshold
        or int(record.get("reopen_count", 0) or 0) > 0
    )


def _top_risk_sort_key(record: dict) -> tuple[object, ...]:
    return (
        0 if record.get("risk_level") == "high" else 1,
        0 if record.get("is_customer_feedback") else 1,
        0 if record.get("owner_missing") else 1,
        -(record.get("stale_days") or 0),
        -int(record.get("reopen_count", 0) or 0),
        str(record.get("bug_id") or ""),
    )


def _week_label(value: object) -> str | None:
    parsed = _parse_datetime(value)
    if not parsed:
        return None
    iso = parsed.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _month_label(value: object) -> str | None:
    parsed = _parse_datetime(value)
    if not parsed:
        return None
    return parsed.strftime("%Y-%m")


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_xlsx(sheets: list[WorkbookSheet], generated_at: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", _root_relationships_xml())
        archive.writestr("docProps/core.xml", _core_properties_xml(generated_at))
        archive.writestr("docProps/app.xml", _app_properties_xml(sheets))
        archive.writestr("xl/workbook.xml", _workbook_xml(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships_xml(sheets))
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, sheet in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet_xml(sheet))
    return buffer.getvalue()


def _content_types_xml(sheet_count: int) -> str:
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        f"{sheet_overrides}"
        "</Types>"
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _core_properties_xml(generated_at: str) -> str:
    timestamp = escape(generated_at)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:creator>tp_codex</dc:creator>"
        "<cp:lastModifiedBy>tp_codex</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _app_properties_xml(sheets: list[WorkbookSheet]) -> str:
    titles = "".join(f"<vt:lpstr>{escape(sheet.name)}</vt:lpstr>" for sheet in sheets)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>tp_codex</Application>"
        "<DocSecurity>0</DocSecurity>"
        "<ScaleCrop>false</ScaleCrop>"
        '<HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>'
        f"<vt:variant><vt:i4>{len(sheets)}</vt:i4></vt:variant></vt:vector></HeadingPairs>"
        f'<TitlesOfParts><vt:vector size="{len(sheets)}" baseType="lpstr">{titles}</vt:vector></TitlesOfParts>'
        "</Properties>"
    )


def _workbook_xml(sheets: list[WorkbookSheet]) -> str:
    sheet_xml = "".join(
        f'<sheet name="{escape(sheet.name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, sheet in enumerate(sheets, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="14000"/></bookViews>'
        f"<sheets>{sheet_xml}</sheets>"
        "</workbook>"
    )


def _workbook_relationships_xml(sheets: list[WorkbookSheet]) -> str:
    sheet_relationships = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index, _sheet in enumerate(sheets, start=1)
    )
    styles_rel_id = len(sheets) + 1
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{sheet_relationships}"
        f'<Relationship Id="rId{styles_rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="3">'
        '<font><sz val="11"/><color rgb="FF000000"/><name val="Calibri"/><family val="2"/></font>'
        '<font><b/><sz val="11"/><color rgb="FF000000"/><name val="Calibri"/><family val="2"/></font>'
        '<font><b/><sz val="14"/><color rgb="FF000000"/><name val="Calibri"/><family val="2"/></font>'
        "</fonts>"
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFD9E2F3"/><bgColor indexed="64"/></patternFill></fill>'
        "</fills>"
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="3">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _worksheet_xml(sheet: WorkbookSheet) -> str:
    max_columns = max((len(row.values) for row in sheet.rows), default=1)
    max_rows = max(len(sheet.rows), 1)
    last_ref = f"{_column_name(max_columns)}{max_rows}"
    cols = _worksheet_cols_xml(sheet)
    rows_xml = "".join(_worksheet_row_xml(index, row) for index, row in enumerate(sheet.rows, start=1))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:{last_ref}"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f"{cols}"
        f"<sheetData>{rows_xml}</sheetData>"
        "</worksheet>"
    )


def _worksheet_cols_xml(sheet: WorkbookSheet) -> str:
    widths = _column_widths(sheet)
    if not widths:
        return ""
    cols = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    return f"<cols>{cols}</cols>"


def _column_widths(sheet: WorkbookSheet) -> list[int]:
    widths: list[int] = []
    for row in sheet.rows:
        for index, value in enumerate(row.values):
            display = _display_cell_value(value)
            size = min(max(len(display) + 2, 10), 50)
            if index >= len(widths):
                widths.append(size)
            else:
                widths[index] = max(widths[index], size)
    return widths


def _worksheet_row_xml(row_index: int, row: WorkbookRow) -> str:
    cells = "".join(_worksheet_cell_xml(row_index, column_index, value, _style_id(row.kind)) for column_index, value in enumerate(row.values, start=1))
    return f'<row r="{row_index}">{cells}</row>'


def _worksheet_cell_xml(row_index: int, column_index: int, value: object, style_id: int) -> str:
    cell_ref = f"{_column_name(column_index)}{row_index}"
    style = f' s="{style_id}"' if style_id else ""
    if isinstance(value, bool):
        return f'<c r="{cell_ref}"{style} t="b"><v>{"1" if value else "0"}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{cell_ref}"{style}><v>{value}</v></c>'
    text = escape(_display_cell_value(value))
    return f'<c r="{cell_ref}"{style} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _style_id(kind: str) -> int:
    if kind == "header":
        return 1
    if kind == "title":
        return 2
    return 0


def _column_name(index: int) -> str:
    label = ""
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        label = chr(65 + remainder) + label
    return label or "A"


def _display_cell_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, list):
        return "; ".join(_display_cell_value(item) for item in value)
    if isinstance(value, dict):
        if "code" in value and "message" in value:
            return f'{value.get("code")}: {value.get("message")}'
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
