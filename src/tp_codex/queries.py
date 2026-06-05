from __future__ import annotations

from tp_codex.gateway import HttpGateway, MemoryGateway, QueryResult


def list_entities(
    gateway: HttpGateway | MemoryGateway,
    entity: str,
    filters: dict | None = None,
    limit: int | None = None,
) -> QueryResult:
    return gateway.list_entities(entity=entity, filters=filters, limit=limit)
