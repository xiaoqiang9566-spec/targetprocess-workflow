from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Callable, Iterable, Sequence

from tp_codex.artifacts import WorkflowArtifact
from tp_codex.datasets import BUG_DATASET_FIELDNAMES
from tp_codex.errors import InvalidArgsError, UpstreamOrTimeoutError
from tp_codex.settings import WorkflowRulesSettings
from tp_codex.workbooks import WorkbookRow, WorkbookSheet, _build_xlsx


MONTHLY_AUDIT_SHEET_NAMES = [
    "Monthly_Summary",
    "Monthly_Trend",
    "Risk_Quality",
    "Process_Exceptions",
    "Candidate_Risks",
    "Candidate_History",
    "Unmapped_Status",
    "Bug_Master",
]

MONTHLY_AUDIT_CANDIDATE_FIELDNAMES = [
    "bug_id",
    "name",
    "team",
    "severity",
    "status_group",
    "risk_level",
    "stale_days",
    "reopen_count",
    "is_customer_feedback",
    "aging_bucket",
    "audit_focus",
    "candidate_reason_codes",
    "history_event_count",
]

MONTHLY_AUDIT_HISTORY_FIELDNAMES = [
    "bug_id",
    "name",
    "event_type",
    "changed_at",
    "field",
    "from",
    "to",
]

MONTHLY_REASON_LABELS = {
    "reopen_threshold": "Reopen threshold reached",
    "stale_followup": "Stale follow-up required",
    "high_severity": "High severity bug",
    "customer_feedback": "Customer feedback bug",
    "unmapped_status": "Unmapped status",
    "aging_60_plus": "Aging 60+ days",
}


def resolve_month_label(month_label: str) -> str:
    normalized = str(month_label or "").strip()
    if not normalized:
        raise InvalidArgsError("--month-label is required for monthly-audit")
    if not re.fullmatch(r"\d{4}-\d{2}", normalized):
        raise InvalidArgsError(f"unsupported month label: {month_label}")
    try:
        return datetime.strptime(normalized, "%Y-%m").strftime("%Y-%m")
    except ValueError as exc:
        raise InvalidArgsError(f"unsupported month label: {month_label}") from exc


def build_monthly_audit_summary(
    records: Sequence[dict],
    month_label: str,
    workflow_rules: WorkflowRulesSettings,
) -> dict:
    normalized = resolve_month_label(month_label)
    created_records = [record for record in records if record.get("created_month") == normalized]
    closed_records = [
        record
        for record in records
        if record.get("is_closed") and _month_label(record.get("last_status_change_at")) == normalized
    ]
    reopened_records = [
        record
        for record in records
        if record.get("updated_month") == normalized
        and int(record.get("reopen_count", 0) or 0) >= workflow_rules.reopen_threshold
        and workflow_rules.reopen_threshold > 0
    ]
    candidate_records = [record for record in records if _candidate_reason_codes(record, workflow_rules)]
    return {
        "month_label": normalized,
        "total_records": len(records),
        "created_count": len(created_records),
        "closed_count": len(closed_records),
        "reopened_count": len(reopened_records),
        "candidate_risk_records": len(candidate_records),
        "high_risk_records": sum(1 for record in records if record.get("is_high_risk")),
        "customer_feedback_records": sum(1 for record in records if record.get("is_customer_feedback")),
        "stale_records": sum(1 for record in records if (record.get("stale_days") or 0) >= workflow_rules.stale_days),
        "unmapped_status_records": sum(1 for record in records if record.get("status_group") == "unmapped"),
        "aging_60_plus_records": sum(1 for record in records if record.get("aging_bucket") == "60+"),
        "by_status_group": _count_by(records, "status_group"),
        "by_team": _count_by(records, "team"),
        "by_severity": _count_by(records, "severity"),
    }


def build_monthly_audit_candidates(
    records: Sequence[dict],
    workflow_rules: WorkflowRulesSettings,
    history_loader: Callable[[str], tuple[list[dict], bool]],
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    candidates: list[dict] = []
    for record in sorted(records, key=lambda item: _candidate_sort_key(item, workflow_rules)):
        reason_codes = _candidate_reason_codes(record, workflow_rules)
        if not reason_codes:
            continue
        history: list[dict] = []
        partial = False
        try:
            history, partial = history_loader(str(record.get("bug_id") or ""))
        except UpstreamOrTimeoutError:
            partial = True
        candidate = dict(record)
        candidate["candidate_reason_codes"] = reason_codes
        candidate["candidate_reason_labels"] = [MONTHLY_REASON_LABELS[code] for code in reason_codes]
        candidate["history"] = history
        candidate["history_event_count"] = len(history)
        candidates.append(candidate)
        if partial:
            warnings.append("partial_history")
    return candidates, sorted(set(warnings))


def build_monthly_audit_workbook_artifact(
    records: Sequence[dict],
    candidates: Sequence[dict],
    summary: dict,
    month_label: str,
    generated_at: str,
    workflow_rules: WorkflowRulesSettings,
    warnings: Sequence[str] | None = None,
) -> WorkflowArtifact:
    normalized = resolve_month_label(month_label)
    sheets = build_monthly_audit_workbook_sheets(
        list(records),
        list(candidates),
        summary,
        normalized,
        workflow_rules,
        list(warnings or []),
    )
    content = _build_xlsx(sheets, generated_at)
    return WorkflowArtifact(
        filename=f"monthly-audit-{normalized}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content=content,
    )


def build_monthly_audit_workbook_sheets(
    records: list[dict],
    candidates: list[dict],
    summary: dict,
    month_label: str,
    workflow_rules: WorkflowRulesSettings,
    warnings: list[str],
) -> list[WorkbookSheet]:
    return [
        _monthly_summary_sheet(summary, warnings),
        _monthly_trend_sheet(records),
        _risk_quality_sheet(records, workflow_rules),
        _process_exceptions_sheet(records, workflow_rules),
        _candidate_risks_sheet(candidates),
        _candidate_history_sheet(candidates),
        _table_sheet("Unmapped_Status", BUG_DATASET_FIELDNAMES, [record for record in records if record.get("status_group") == "unmapped"]),
        _table_sheet("Bug_Master", BUG_DATASET_FIELDNAMES, records),
    ]


def _monthly_summary_sheet(summary: dict, warnings: Sequence[str]) -> WorkbookSheet:
    metric_keys = [
        "month_label",
        "total_records",
        "created_count",
        "closed_count",
        "reopened_count",
        "candidate_risk_records",
        "high_risk_records",
        "customer_feedback_records",
        "stale_records",
        "unmapped_status_records",
        "aging_60_plus_records",
    ]
    rows = [
        WorkbookRow(["Monthly Audit Summary"], kind="title"),
        WorkbookRow(["metric", "value"], kind="header"),
    ]
    rows.extend(WorkbookRow([key, summary.get(key)]) for key in metric_keys)
    rows.append(WorkbookRow([], kind="body"))
    rows.append(WorkbookRow(["Warnings"], kind="title"))
    rows.append(WorkbookRow(["warning_code"], kind="header"))
    if warnings:
        rows.extend(WorkbookRow([warning]) for warning in warnings)
    else:
        rows.append(WorkbookRow(["none"]))
    rows.extend(_distribution_rows("Status Group Distribution", "status_group", summary.get("by_status_group", {})))
    rows.extend(_distribution_rows("Team Distribution", "team", summary.get("by_team", {})))
    rows.extend(_distribution_rows("Severity Distribution", "severity", summary.get("by_severity", {})))
    return WorkbookSheet(name="Monthly_Summary", rows=rows)


def _monthly_trend_sheet(records: Sequence[dict]) -> WorkbookSheet:
    created_counts = Counter(str(record.get("created_month") or "unknown") for record in records if record.get("created_month"))
    closed_counts = Counter(
        _month_label(record.get("last_status_change_at"))
        for record in records
        if record.get("is_closed") and record.get("last_status_change_at")
    )
    reopened_counts = Counter(
        str(record.get("updated_month") or "unknown")
        for record in records
        if record.get("updated_month") and int(record.get("reopen_count", 0) or 0) > 0
    )
    candidate_counts = Counter(
        str(record.get("updated_month") or record.get("created_month") or "unknown")
        for record in records
        if record.get("audit_focus") in {"stale_followup", "unmapped_status", "customer_feedback", "high_risk", "reopen_analysis"}
    )
    months = sorted(set(created_counts) | set(closed_counts) | set(reopened_counts) | set(candidate_counts))
    rows = [
        WorkbookRow(["Monthly Trend"], kind="title"),
        WorkbookRow(["month", "created_count", "closed_count", "reopened_count", "candidate_focus_count"], kind="header"),
    ]
    for month in months:
        rows.append(
            WorkbookRow(
                [
                    month,
                    created_counts.get(month, 0),
                    closed_counts.get(month, 0),
                    reopened_counts.get(month, 0),
                    candidate_counts.get(month, 0),
                ]
            )
        )
    if not months:
        rows.append(WorkbookRow(["none", 0, 0, 0, 0]))
    return WorkbookSheet(name="Monthly_Trend", rows=rows)


def _risk_quality_sheet(records: Sequence[dict], workflow_rules: WorkflowRulesSettings) -> WorkbookSheet:
    severities = sorted({str(record.get("severity") or "null") for record in records})
    rows = [
        WorkbookRow(["Risk Quality"], kind="title"),
        WorkbookRow(
            ["severity", "total_records", "high_risk_records", "customer_feedback_records", "reopened_records", "stale_records"],
            kind="header",
        ),
    ]
    for severity in severities:
        scoped = [record for record in records if str(record.get("severity") or "null") == severity]
        rows.append(
            WorkbookRow(
                [
                    severity,
                    len(scoped),
                    sum(1 for record in scoped if record.get("is_high_risk")),
                    sum(1 for record in scoped if record.get("is_customer_feedback")),
                    sum(1 for record in scoped if int(record.get("reopen_count", 0) or 0) >= workflow_rules.reopen_threshold),
                    sum(1 for record in scoped if (record.get("stale_days") or 0) >= workflow_rules.stale_days),
                ]
            )
        )
    if not severities:
        rows.append(WorkbookRow(["none", 0, 0, 0, 0, 0]))
    return WorkbookSheet(name="Risk_Quality", rows=rows)


def _process_exceptions_sheet(records: Sequence[dict], workflow_rules: WorkflowRulesSettings) -> WorkbookSheet:
    rows = [
        WorkbookRow(["Process Exceptions"], kind="title"),
        WorkbookRow(["exception_type", "count"], kind="header"),
        WorkbookRow(["owner_missing", sum(1 for record in records if record.get("owner_missing"))]),
        WorkbookRow(["unmapped_status", sum(1 for record in records if record.get("status_group") == "unmapped")]),
        WorkbookRow(["stale_followup", sum(1 for record in records if (record.get("stale_days") or 0) >= workflow_rules.stale_days)]),
        WorkbookRow(["customer_feedback", sum(1 for record in records if record.get("is_customer_feedback"))]),
        WorkbookRow(["reopen_threshold", sum(1 for record in records if int(record.get("reopen_count", 0) or 0) >= workflow_rules.reopen_threshold)]),
        WorkbookRow(["aging_60_plus", sum(1 for record in records if record.get("aging_bucket") == "60+")]),
    ]
    return WorkbookSheet(name="Process_Exceptions", rows=rows)


def _candidate_risks_sheet(candidates: Sequence[dict]) -> WorkbookSheet:
    rows = [WorkbookRow(["Candidate Risks"], kind="title"), WorkbookRow(list(MONTHLY_AUDIT_CANDIDATE_FIELDNAMES), kind="header")]
    for candidate in candidates:
        rows.append(WorkbookRow([candidate.get(field) for field in MONTHLY_AUDIT_CANDIDATE_FIELDNAMES]))
    if not candidates:
        rows.append(WorkbookRow(["none", "", "", "", "", "", "", "", "", "", "", "", 0]))
    return WorkbookSheet(name="Candidate_Risks", rows=rows)


def _candidate_history_sheet(candidates: Sequence[dict]) -> WorkbookSheet:
    rows = [WorkbookRow(["Candidate History"], kind="title"), WorkbookRow(list(MONTHLY_AUDIT_HISTORY_FIELDNAMES), kind="header")]
    has_rows = False
    for candidate in candidates:
        history = candidate.get("history") or []
        for event in history:
            rows.append(
                WorkbookRow(
                    [
                        candidate.get("bug_id"),
                        candidate.get("name"),
                        event.get("event_type"),
                        event.get("changed_at"),
                        event.get("field"),
                        event.get("from"),
                        event.get("to"),
                    ]
                )
            )
            has_rows = True
    if not has_rows:
        rows.append(WorkbookRow(["none", "", "", "", "", "", ""]))
    return WorkbookSheet(name="Candidate_History", rows=rows)


def _table_sheet(name: str, fieldnames: Sequence[str], records: Iterable[dict]) -> WorkbookSheet:
    rows = [WorkbookRow(list(fieldnames), kind="header")]
    has_rows = False
    for record in records:
        rows.append(WorkbookRow([record.get(field) for field in fieldnames]))
        has_rows = True
    if not has_rows:
        rows.append(WorkbookRow([""] * len(fieldnames)))
    return WorkbookSheet(name=name, rows=rows)


def _distribution_rows(title: str, key: str, counts: dict[str, int]) -> list[WorkbookRow]:
    rows = [WorkbookRow([], kind="body"), WorkbookRow([title], kind="title"), WorkbookRow([key, "count"], kind="header")]
    if counts:
        for label in sorted(counts):
            rows.append(WorkbookRow([label, counts[label]]))
    else:
        rows.append(WorkbookRow(["none", 0]))
    return rows


def _count_by(records: Sequence[dict], key: str) -> dict[str, int]:
    counts = Counter(str(record.get(key) or "null") for record in records)
    return dict(sorted(counts.items()))


def _candidate_reason_codes(record: dict, workflow_rules: WorkflowRulesSettings) -> list[str]:
    codes: list[str] = []
    severity = str(record.get("severity") or "")
    severity_set = set(workflow_rules.high_risk_severities) | {"Blocking", "Critical"}
    is_open = bool(record.get("is_open"))
    if workflow_rules.reopen_threshold > 0 and int(record.get("reopen_count", 0) or 0) >= workflow_rules.reopen_threshold:
        codes.append("reopen_threshold")
    if is_open and (record.get("stale_days") or 0) >= workflow_rules.stale_days:
        codes.append("stale_followup")
    if is_open and severity in severity_set:
        codes.append("high_severity")
    if is_open and record.get("is_customer_feedback"):
        codes.append("customer_feedback")
    if record.get("status_group") == "unmapped":
        codes.append("unmapped_status")
    if is_open and record.get("aging_bucket") == "60+":
        codes.append("aging_60_plus")
    return codes


def _candidate_sort_key(record: dict, workflow_rules: WorkflowRulesSettings) -> tuple[object, ...]:
    reason_codes = _candidate_reason_codes(record, workflow_rules)
    return (
        0 if "high_severity" in reason_codes else 1,
        0 if "customer_feedback" in reason_codes else 1,
        0 if "unmapped_status" in reason_codes else 1,
        0 if "aging_60_plus" in reason_codes else 1,
        -(record.get("stale_days") or 0),
        -int(record.get("reopen_count", 0) or 0),
        int(record.get("bug_id") or 0),
    )


def _month_label(value: object) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    return parsed.strftime("%Y-%m")
