from __future__ import annotations

from typing import Iterable

from tp_codex.gateway import HttpGateway, MemoryGateway
from tp_codex.queries import list_entities
from tp_codex.normalizers import normalize_history
from tp_codex.errors import UpstreamOrTimeoutError


BUG_SIMPLE_HISTORY_SELECT_FIELDS = [
    "Id",
    "Date",
    "EntityState",
    "Modifier",
    "Project",
    "Release",
    "Iteration",
    "Bug",
]


def get_bug_history(gateway: HttpGateway | MemoryGateway, bug_id: str) -> tuple[list[dict], bool]:
    raw, partial = gateway.bug_history(str(bug_id))
    return normalize_history(raw), partial


def get_bug_simple_history_batch(
    gateway: HttpGateway | MemoryGateway,
    bug_ids: Iterable[object],
    *,
    batch_size: int = 50,
) -> tuple[dict[str, list[dict]], bool]:
    unique_bug_ids = []
    seen = set()
    for bug_id in bug_ids:
        normalized = str(bug_id).strip()
        if not normalized or normalized in seen:
            continue
        unique_bug_ids.append(normalized)
        seen.add(normalized)

    if not unique_bug_ids:
        return {}, False

    grouped: dict[str, list[dict]] = {bug_id: [] for bug_id in unique_bug_ids}
    partial = False
    select = "{" + ",".join(BUG_SIMPLE_HISTORY_SELECT_FIELDS) + "}"

    for chunk in _chunked(unique_bug_ids, batch_size):
        where = "(" + " or ".join(_bug_id_where_clause(bug_id) for bug_id in chunk) + ")"
        try:
            query = list_entities(
                gateway,
                entity="BugSimpleHistory",
                filters={
                    "select": select,
                    "where": where,
                },
                limit=None,
            )
        except UpstreamOrTimeoutError:
            partial = True
            continue

        normalized_events = normalize_history(query.items)
        for raw_event, normalized_event in zip(query.items, normalized_events):
            bug = raw_event.get("Bug") or raw_event.get("bug") or {}
            bug_id = bug.get("Id") or bug.get("id")
            if bug_id is None:
                continue
            grouped.setdefault(str(bug_id), []).append(normalized_event)
        if query.partial:
            partial = True

    return grouped, partial


def _chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _bug_id_where_clause(bug_id: str) -> str:
    if bug_id.isdigit():
        return f"Bug.Id == {bug_id}"
    escaped = bug_id.replace("\\", "\\\\").replace('"', '\\"')
    return f'Bug.Id == "{escaped}"'
