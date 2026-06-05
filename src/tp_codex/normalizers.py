from __future__ import annotations

from datetime import datetime


def _name(value):
    if isinstance(value, dict):
        if "Name" in value:
            return value["Name"]
        if "name" in value:
            return value["name"]
        first = value.get("FirstName")
        last = value.get("LastName")
        if not (first or last):
            first = value.get("firstName")
            last = value.get("lastName")
        if first or last:
            return " ".join(part for part in [first, last] if part).strip() or None
        if value.get("fullName"):
            return value["fullName"]
    return value


def _iso(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def normalize_bug(raw: dict, base_url: str) -> dict:
    bug_id = raw.get("Id") or raw.get("id")
    linked_features = raw.get("Feature", []) or raw.get("feature") or raw.get("featureIds", [])
    linked_stories = raw.get("UserStory", []) or raw.get("userStory") or raw.get("userStoryIds", [])
    data_gaps = []
    owner = _name(raw.get("Owner") or raw.get("owner"))
    if owner is None:
        data_gaps.append("owner")
    severity = _name(raw.get("Severity") or raw.get("severity"))
    if severity is None:
        data_gaps.append("severity")
    return {
        "bug_id": bug_id,
        "name": raw.get("Name") or raw.get("name"),
        "url": f"{base_url}/entity/{bug_id}" if bug_id else None,
        "entity_type": _name(raw.get("EntityType") or raw.get("entityType")) or "Bug",
        "project": _name(raw.get("Project") or raw.get("project")),
        "team": _name(raw.get("Team") or raw.get("team")),
        "owner": owner,
        "severity": severity,
        "priority": _name(raw.get("Priority") or raw.get("priority")),
        "status_raw": _name(raw.get("EntityState") or raw.get("entityState")) or _name(raw.get("Status") or raw.get("status")) or raw.get("state"),
        "status_group": "unmapped",
        "created_at": _iso(raw.get("CreateDate") or raw.get("createDate")),
        "updated_at": _iso(raw.get("ModifyDate") or raw.get("modifyDate")),
        "last_status_change_at": _iso(raw.get("LastStateChangeDate") or raw.get("lastStateChangeDate") or raw.get("lastStatusChangeAt") or raw.get("ModifyDate") or raw.get("modifyDate")),
        "suunto_app_version": raw.get("Suuntoappversion") or raw.get("suuntoappversion"),
        "suunto_app_platform": raw.get("Suuntoappplatform") or raw.get("suuntoappplatform"),
        "products": _extract_names(raw.get("Products") or raw.get("products")),
        "firmware_version": raw.get("Firmwareversion") or raw.get("firmwareversion"),
        "reproducibility": _name(raw.get("Reproducibility") or raw.get("reproducibility")),
        "bug_category": _name(raw.get("BugCategory") or raw.get("bugCategory")),
        "linked_feature_ids": _extract_ids(linked_features),
        "linked_user_story_ids": _extract_ids(linked_stories),
        "reopen_count": int(raw.get("ReopenCount") or raw.get("reopenCount") or 0),
        "risk_signals": [],
        "data_gaps": data_gaps,
        "raw": raw,
    }


def normalize_history(events: list[dict]) -> list[dict]:
    normalized = []
    for event in events:
        normalized.append(
            {
                "event_type": event.get("EventType") or event.get("eventType") or "unknown",
                "changed_at": _iso(event.get("Date") or event.get("changedAt")),
                "field": event.get("Field") or event.get("field"),
                "from": event.get("OldValue") or event.get("from"),
                "to": event.get("NewValue") or event.get("to"),
            }
        )
    return normalized


def _extract_ids(value):
    if isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, dict):
                candidate = item.get("Id") or item.get("id")
                if candidate is not None:
                    items.append(candidate)
            elif item is not None:
                items.append(item)
        return items
    if isinstance(value, dict):
        candidate = value.get("Id") or value.get("id")
        return [candidate] if candidate is not None else []
    return []


def _extract_names(value):
    if isinstance(value, dict) and "items" in value:
        return _extract_names(value.get("items"))
    if isinstance(value, list):
        items = []
        for item in value:
            name = _name(item)
            if name is not None:
                items.append(name)
        return items
    name = _name(value)
    if name is None:
        return []
    return [name]
