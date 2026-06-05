from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from tp_codex.settings import WorkflowRulesSettings


BUG_DATASET_SELECT_FIELDS = [
    "Id",
    "Name",
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
    "ReopenCount",
    "Tags",
]


BUG_DATASET_FIELDNAMES = [
    "bug_id",
    "name",
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

        age_days = _days_between(created_at, now)
        stale_days = _days_between(updated_at, now)
        owner_missing = not bool(record.get("owner"))
        is_closed = record.get("status_group") == "closed"
        is_open = not is_closed
        is_customer_feedback = any("customer feedback" in tag.lower() for tag in tags) or (
            "customer feedback" in str(record.get("name") or "").lower()
        )
        is_high_risk = bool(record.get("risk_signals")) or str(record.get("severity") or "") in workflow_rules.high_risk_severities
        is_reopened = int(record.get("reopen_count", 0) or 0) > 0

        dataset_records.append(
            {
                **record,
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
            }
        )

    return dataset_records


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
