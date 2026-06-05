from __future__ import annotations

from tp_codex.gateway import HttpGateway, MemoryGateway, QueryResult


class TargetprocessClientV1:
    def __init__(self, gateway: HttpGateway | MemoryGateway) -> None:
        self.gateway = gateway

    def healthcheck(self) -> dict:
        return self.gateway.healthcheck()

    def schema(self, entity: str) -> dict:
        return self.gateway.snapshot_schema(entity)

    def history(self, bug_id: str) -> tuple[list, bool]:
        return self.gateway.bug_history(bug_id)
