from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from tp_codex.settings import WorkflowRulesSettings


BUG_DATASET_SELECT_FIELDS = [
    "Id",
    "Name",
    "Description",
    "Comments",
    "EntityType",
    "Project",
    "Team",
    "Owner",
    "Severity",
    "Priority",
    "EntityState",
    "CreateDate",
    "ModifyDate",
    "LastStateChangeDate",
    "Suuntoappversion",
    "Suuntoappplatform",
    "Products",
    "Firmwareversion",
    "Reproducibility",
    "BugCategory",
    "Feature",
    "UserStory",
    "Tags",
]


BUG_DATASET_FIELDNAMES = [
    "bug_id",
    "name",
    "description",
    "comments",
    "project",
    "team",
    "owner",
    "severity",
    "priority",
    "status_raw",
    "status_group",
    "created_at",
    "updated_at",
    "last_status_change_at",
    "created_date",
    "updated_date",
    "last_status_change_date",
    "created_week",
    "updated_week",
    "created_month",
    "updated_month",
    "age_days",
    "stale_days",
    "is_open",
    "is_closed",
    "is_customer_feedback",
    "is_high_risk",
    "is_reopened",
    "owner_missing",
    "aging_bucket",
    "risk_level",
    "quality_bucket",
    "audit_focus",
    "team_scope_label",
    "reopen_count",
    "products",
    "suunto_app_version",
    "suunto_app_platform",
    "firmware_version",
    "reproducibility",
    "bug_category",
    "linked_feature_ids",
    "linked_user_story_ids",
    "risk_signals",
    "data_gaps",
]


REVIEW_EXPORT_FIELDNAMES = [
    "bug_id",
    "name",
    "status_raw",
    "status_group",
    "severity",
    "owner",
    "updated_at",
    "team",
    "suunto_app_version",
    "suunto_app_platform",
    "products",
    "firmware_version",
    "reproducibility",
    "bug_category",
    "linked_feature_ids",
]


def build_bug_dataset_records(
    records: Iterable[dict],
    workflow_rules: WorkflowRulesSettings,
    now: datetime | None = None,
) -> List[dict]:
    now = now or datetime.now(timezone.utc)
    dataset_records: list[dict] = []
    default_scope_teams = set(workflow_rules.default_scope.get("team", []))

    for record in records:
        created_at = _parse_datetime(record.get("created_at"))
        updated_at = _parse_datetime(record.get("updated_at"))
        last_status_change_at = _parse_datetime(record.get("last_status_change_at"))
        tags = _extract_tags(record.get("raw", {}).get("Tags") or record.get("raw", {}).get("tags"))
        if "history" in record:
            status_timestamps, reopen_count = _derive_history_metrics(record)
        else:
            status_timestamps, reopen_count = {}, int(record.get("reopen_count", 0) or 0)

        age_days = _days_between(created_at, now)
        stale_days = _days_between(updated_at, now)
        owner_missing = not bool(record.get("owner"))
        is_closed = record.get("status_group") == "closed"
        is_open = not is_closed
        is_customer_feedback = any("customer feedback" in tag.lower() for tag in tags) or (
            "customer feedback" in str(record.get("name") or "").lower()
        )
        is_high_risk = bool(record.get("risk_signals")) or str(record.get("severity") or "") in workflow_rules.high_risk_severities
        is_reopened = reopen_count > 0

        dataset_records.append(
            {
                **record,
                "created_at": _datetime_label(created_at),
                "updated_at": _datetime_label(updated_at),
                "last_status_change_at": _datetime_label(last_status_change_at),
                **status_timestamps,
                "created_date": _date_label(created_at),
                "updated_date": _date_label(updated_at),
                "last_status_change_date": _date_label(last_status_change_at),
                "created_week": _week_label(created_at),
                "updated_week": _week_label(updated_at),
                "created_month": _month_label(created_at),
                "updated_month": _month_label(updated_at),
                "age_days": age_days,
                "stale_days": stale_days,
                "is_open": is_open,
                "is_closed": is_closed,
                "is_customer_feedback": is_customer_feedback,
                "is_high_risk": is_high_risk,
                "is_reopened": is_reopened,
                "owner_missing": owner_missing,
                "aging_bucket": _aging_bucket(age_days),
                "risk_level": _risk_level(is_high_risk, owner_missing, stale_days, workflow_rules.stale_days),
                "quality_bucket": _quality_bucket(is_customer_feedback, is_high_risk, stale_days, workflow_rules.stale_days, is_reopened, is_closed),
                "audit_focus": _audit_focus(
                    status_group=str(record.get("status_group") or ""),
                    owner_missing=owner_missing,
                    stale_days=stale_days,
                    stale_threshold=workflow_rules.stale_days,
                    is_customer_feedback=is_customer_feedback,
                    is_high_risk=is_high_risk,
                    is_reopened=is_reopened,
                ),
                "team_scope_label": "default_scope_team" if str(record.get("team") or "") in default_scope_teams else "unscoped_team",
                "reopen_count": reopen_count,
            }
        )

    return dataset_records


def build_bug_dataset_fieldnames(records: Iterable[dict]) -> List[str]:
    return build_status_timestamp_fieldnames(records, BUG_DATASET_FIELDNAMES)


def build_review_export_fieldnames(records: Iterable[dict]) -> List[str]:
    return build_status_timestamp_fieldnames(records, REVIEW_EXPORT_FIELDNAMES)


def format_bug_report_timestamps(record: dict) -> dict:
    formatted = dict(record)
    for field in ("created_at", "updated_at", "last_status_change_at"):
        formatted[field] = _formatted_timestamp_value(record.get(field), include_time=True)
    for key in list(formatted.keys()):
        if key.startswith("entered_") and key.endswith("_at"):
            formatted[key] = _formatted_timestamp_value(record.get(key), include_time=False)
    return formatted


def build_status_timestamp_fieldnames(records: Iterable[dict], base_fieldnames: Iterable[str]) -> List[str]:
    dynamic_status_fields = sorted(
        {
            key
            for record in records
            for key in record.keys()
            if key.startswith("entered_") and key.endswith("_at")
        }
    )
    return [*base_fieldnames, *dynamic_status_fields]


def summarize_bug_history(
    record: dict,
    history: list[dict],
    *,
    include_history: bool = False,
    recompute_reopen_count: bool = False,
) -> dict:
    status_timestamps, derived_reopen_count = _derive_history_metrics({**record, "history": history})
    summarized = {
        **record,
        **status_timestamps,
        "reopen_count": derived_reopen_count if recompute_reopen_count else int(record.get("reopen_count", 0) or 0),
    }
    if include_history:
        summarized["history"] = history
    return summarized


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value)
        match = re.match(r"^/Date\((?P<ms>-?\d+)(?P<offset>[+-]\d{4})\)/$", text)
        if match:
            ms = int(match.group("ms"))
            offset = match.group("offset")
            sign = 1 if offset[0] == "+" else -1
            hours = int(offset[1:3])
            minutes = int(offset[3:5])
            tz = timezone(sign * timedelta(hours=hours, minutes=minutes))
            parsed = datetime.fromtimestamp(ms / 1000, tz=tz)
        else:
            parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _date_label(value: datetime | None) -> str | None:
    return value.date().isoformat() if value else None


def _week_label(value: datetime | None) -> str | None:
    if not value:
        return None
    iso = value.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _month_label(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m") if value else None


def _days_between(value: datetime | None, now: datetime) -> int | None:
    if not value:
        return None
    return (now.date() - value.date()).days


def _aging_bucket(age_days: int | None) -> str | None:
    if age_days is None:
        return None
    if age_days <= 7:
        return "0-7"
    if age_days <= 14:
        return "8-14"
    if age_days <= 30:
        return "15-30"
    if age_days <= 60:
        return "31-60"
    return "60+"


def _risk_level(is_high_risk: bool, owner_missing: bool, stale_days: int | None, stale_threshold: int) -> str:
    if is_high_risk or owner_missing or ((stale_days or 0) >= stale_threshold):
        return "high"
    return "low"


def _quality_bucket(
    is_customer_feedback: bool,
    is_high_risk: bool,
    stale_days: int | None,
    stale_threshold: int,
    is_reopened: bool,
    is_closed: bool,
) -> str:
    if is_customer_feedback:
        return "customer_feedback"
    if is_high_risk:
        return "high_risk"
    if (stale_days or 0) >= stale_threshold:
        return "stale"
    if is_reopened:
        return "reopened"
    if is_closed:
        return "closed"
    return "active"


def _audit_focus(
    status_group: str,
    owner_missing: bool,
    stale_days: int | None,
    stale_threshold: int,
    is_customer_feedback: bool,
    is_high_risk: bool,
    is_reopened: bool,
) -> str:
    if owner_missing:
        return "owner_missing"
    if status_group == "unmapped":
        return "unmapped_status"
    if (stale_days or 0) >= stale_threshold:
        return "stale_followup"
    if is_customer_feedback:
        return "customer_feedback"
    if is_high_risk:
        return "high_risk"
    if is_reopened:
        return "reopen_analysis"
    if status_group == "ready_for_qa":
        return "verification_queue"
    return "routine"


def _extract_tags(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, dict):
        if "items" in value:
            return _extract_tags(value.get("items"))
        name = value.get("Name") or value.get("name")
        return [str(name)] if name else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_extract_tags(item))
        return result
    return [str(value)]


def _derive_history_metrics(record: dict) -> tuple[dict[str, str], int]:
    fallback_reopen_count = int(record.get("reopen_count", 0) or 0)
    reopen_count = 0
    history = _ordered_state_history(record.get("history") or [])
    current_status = str(record.get("status_raw") or "").strip()
    created_at = _normalized_timestamp(record.get("created_at"))
    current_status_at = _normalized_timestamp(
        record.get("last_status_change_at") or record.get("updated_at") or record.get("created_at")
    )

    if not history:
        if current_status and current_status_at:
            return {_status_timestamp_field(current_status): created_at or current_status_at}, fallback_reopen_count
        return {}, fallback_reopen_count

    status_timestamps: dict[str, str] = {}
    first_from = str(history[0].get("from") or "").strip()
    if first_from and created_at:
        status_timestamps[_status_timestamp_field(first_from)] = created_at
    first_to = str(history[0].get("to") or "").strip()
    if not first_from and first_to and created_at:
        status_timestamps.setdefault(_status_timestamp_field(first_to), created_at)

    awaiting_reopen = False
    for event in history:
        state = str(event.get("to") or "").strip()
        if not state:
            continue
        changed_at = _normalized_timestamp(event.get("changed_at"))
        if changed_at:
            status_timestamps.setdefault(_status_timestamp_field(state), changed_at)

        lowered = state.lower()
        if lowered == "in testing":
            awaiting_reopen = True
        elif awaiting_reopen and lowered in {"new", "in progress"}:
            reopen_count += 1
            awaiting_reopen = False

    if current_status and current_status_at:
        status_timestamps.setdefault(_status_timestamp_field(current_status), current_status_at)

    return status_timestamps, reopen_count


def _ordered_state_history(history: list[dict]) -> list[dict]:
    indexed = []
    for idx, event in enumerate(history):
        if str(event.get("field") or "") != "EntityState":
            continue
        indexed.append((idx, _parse_datetime(event.get("changed_at")), event))
    indexed.sort(key=lambda item: (item[1] is None, item[1] or datetime.max.replace(tzinfo=timezone.utc), item[0]))
    return [event for _, _, event in indexed]


def _normalized_timestamp(value: object) -> str | None:
    return _formatted_timestamp_value(value, include_time=False)


def _datetime_label(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _formatted_timestamp_value(value: object, *, include_time: bool) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return str(value) if value not in (None, "") else None
    if include_time:
        return _datetime_label(parsed)
    return _date_label(parsed)


def _status_timestamp_field(status: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", status.lower()).strip("_")
    return f"entered_{slug}_at"
