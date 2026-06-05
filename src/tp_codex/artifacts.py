from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowArtifact:
    filename: str
    media_type: str
    content: bytes
