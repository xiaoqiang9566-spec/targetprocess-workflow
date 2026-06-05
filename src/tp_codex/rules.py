from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from tp_codex.settings import WorkflowRulesSettings


@dataclass
class WorkflowRulesEngine:
    settings: WorkflowRulesSettings

    def status_group(self, status_raw: str | None) -> str:
        if not status_raw:
            return "unmapped"
        normalized = status_raw.lower()
        for group, values in self.settings.status_groups.items():
            if any(normalized == value.lower() for value in values):
                return group
        return "unmapped"

    def enrich_record(self, record: Dict[str, object]) -> Dict[str, object]:
        enriched = dict(record)
        enriched["status_group"] = self.status_group(record.get("status_raw"))
        signals = list(record.get("risk_signals", []))
        if record.get("severity") in self.settings.high_risk_severities:
            signals.append(self._signal("high_severity", "Bug severity is in the high-risk list"))
        if not record.get("owner"):
            signals.append(self._signal("missing_owner", "Bug has no assigned owner"))
        if self._is_stale(record.get("updated_at")):
            signals.append(self._signal("stale_bug", f"Bug has not been updated for {self.settings.stale_days}+ days"))
        if int(record.get("reopen_count", 0)) >= self.settings.reopen_threshold and self.settings.reopen_threshold > 0:
            signals.append(
                self._signal(
                    "reopen_threshold",
                    f"Bug reopen count reached {record.get('reopen_count')}",
                )
            )
        if record.get("data_gaps"):
            signals.append(self._signal("data_gaps", "Bug record is missing optional fields"))
        enriched["risk_signals"] = self._dedupe(signals)
        return enriched

    def _is_stale(self, updated_at: object) -> bool:
        if not updated_at:
            return False
        try:
            parsed = datetime.fromisoformat(str(updated_at))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)
        return delta.days >= self.settings.stale_days

    @staticmethod
    def _signal(code: str, message: str) -> Dict[str, str]:
        return {"code": code, "message": message}

    @staticmethod
    def _dedupe(signals: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen = set()
        deduped = []
        for signal in signals:
            key = signal["code"]
            if key in seen:
                continue
            deduped.append(signal)
            seen.add(key)
        return deduped
