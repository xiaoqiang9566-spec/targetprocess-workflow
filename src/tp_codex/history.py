from __future__ import annotations

from tp_codex.gateway import HttpGateway, MemoryGateway
from tp_codex.normalizers import normalize_history


def get_bug_history(gateway: HttpGateway | MemoryGateway, bug_id: str) -> tuple[list[dict], bool]:
    raw, partial = gateway.bug_history(str(bug_id))
    return normalize_history(raw), partial
