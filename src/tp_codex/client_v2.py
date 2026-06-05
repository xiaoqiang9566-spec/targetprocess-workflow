from __future__ import annotations

from tp_codex.gateway import HttpGateway, MemoryGateway, QueryResult


class TargetprocessClientV2:
    def __init__(self, gateway: HttpGateway | MemoryGateway) -> None:
        self.gateway = gateway

    def list_entities(self, entity: str, filters: dict | None = None, limit: int | None = None) -> QueryResult:
        return self.gateway.list_entities(entity=entity, filters=filters, limit=limit)
