from datetime import datetime, timedelta, timezone

from tp_codex.rules import WorkflowRulesEngine
from tp_codex.settings import WorkflowRulesSettings


def test_rules_engine_maps_status_and_emits_risk_signals():
    engine = WorkflowRulesEngine(
        WorkflowRulesSettings(
            status_groups={
                "triage": ["New"],
                "ready_for_qa": ["Ready for QA"],
                "closed": ["Done"],
            },
            high_risk_severities=["Critical", "High"],
            stale_days=5,
            reopen_threshold=2,
        )
    )

    record = {
        "bug_id": 42,
        "status_raw": "Ready for QA",
        "severity": "Critical",
        "owner": None,
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "reopen_count": 3,
        "data_gaps": [],
    }

    enriched = engine.enrich_record(record)

    assert enriched["status_group"] == "ready_for_qa"
    codes = {signal["code"] for signal in enriched["risk_signals"]}
    assert {"missing_owner", "stale_bug", "high_severity", "reopen_threshold"} <= codes


def test_rules_engine_marks_unknown_status_as_unmapped():
    engine = WorkflowRulesEngine(WorkflowRulesSettings())

    enriched = engine.enrich_record({"status_raw": "Mystery", "data_gaps": []})

    assert enriched["status_group"] == "unmapped"
