from __future__ import annotations

from tp_codex.gateway import HttpGateway, MemoryGateway


def snapshot_entity_schema(gateway: HttpGateway | MemoryGateway, entity: str) -> dict:
    return gateway.snapshot_schema(entity)
