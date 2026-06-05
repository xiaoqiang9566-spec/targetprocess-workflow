from datetime import datetime, timezone

from tp_codex.datasets import BUG_DATASET_FIELDNAMES, build_bug_dataset_records
from tp_codex.settings import WorkflowRulesSettings


def test_build_bug_dataset_records_derives_reporting_fields():
    records = [
        {
            "bug_id": 101,
            "name": "Crash on launch",
            "project": "Suunto work",
            "team": "ESW China NG3 Driver",
            "owner": None,
            "severity": "Critical",
            "priority": "High",
            "status_raw": "New",
            "status_group": "triage",
            "created_at": "2026-05-26T00:00:00+00:00",
            "updated_at": "2026-06-03T00:00:00+00:00",
            "last_status_change_at": "2026-06-02T00:00:00+00:00",
            "reopen_count": 3,
            "risk_signals": [{"code": "high_severity", "message": "Bug severity is in the high-risk list"}],
            "data_gaps": ["owner"],
            "raw": {"Tags": [{"Name": "customer feedback"}]},
        }
    ]
    rules = WorkflowRulesSettings(
        high_risk_severities=["Critical"],
        stale_days=5,
        reopen_threshold=2,
        default_scope={"team": ["ESW China NG3 Driver", "ESW China NG3 Framework", "ESW UI Team"]},
    )

    dataset = build_bug_dataset_records(
        records,
        workflow_rules=rules,
        now=datetime(2026, 6, 5, tzinfo=timezone.utc),
    )

    record = dataset[0]
    assert BUG_DATASET_FIELDNAMES[0] == "bug_id"
    assert record["created_week"] == "2026-W22"
    assert record["updated_month"] == "2026-06"
    assert record["age_days"] == 10
    assert record["stale_days"] == 2
    assert record["is_open"] is True
    assert record["is_closed"] is False
    assert record["is_customer_feedback"] is True
    assert record["is_high_risk"] is True
    assert record["is_reopened"] is True
    assert record["owner_missing"] is True
    assert record["aging_bucket"] == "8-14"
    assert record["risk_level"] == "high"
    assert record["quality_bucket"] == "customer_feedback"
    assert record["audit_focus"] == "owner_missing"
    assert record["team_scope_label"] == "default_scope_team"
