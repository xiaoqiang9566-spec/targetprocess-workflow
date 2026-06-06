from datetime import datetime, timezone

from tp_codex.datasets import BUG_DATASET_FIELDNAMES, BUG_DATASET_SELECT_FIELDS, build_bug_dataset_records
from tp_codex.settings import WorkflowRulesSettings


def test_build_bug_dataset_records_derives_reporting_fields():
    assert "Description" in BUG_DATASET_SELECT_FIELDS
    assert "Comments" in BUG_DATASET_SELECT_FIELDS

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
            "description": "Bug description",
            "comments": ["Needs logs", "Reproduced"],
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
    assert "description" in BUG_DATASET_FIELDNAMES
    assert "comments" in BUG_DATASET_FIELDNAMES
    assert record["created_at"] == "2026-05-26 00:00:00"
    assert record["updated_at"] == "2026-06-03 00:00:00"
    assert record["last_status_change_at"] == "2026-06-02 00:00:00"
    assert record["created_week"] == "2026-W22"
    assert record["updated_month"] == "2026-06"
    assert record["age_days"] == 10
    assert record["stale_days"] == 2
    assert record["description"] == "Bug description"
    assert record["comments"] == ["Needs logs", "Reproduced"]
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


def test_build_bug_dataset_records_derives_status_timestamps_and_reopen_count_from_history():
    records = [
        {
            "bug_id": 201,
            "name": "Reopened after testing",
            "project": "Suunto work",
            "team": "ESW China NG3 Driver",
            "owner": "QA User",
            "severity": "Normal",
            "priority": "High",
            "status_raw": "Verified",
            "status_group": "closed",
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-05T00:00:00+00:00",
            "last_status_change_at": "2026-06-05T00:00:00+00:00",
            "reopen_count": 0,
            "risk_signals": [],
            "data_gaps": [],
            "history": [
                {"changed_at": "2026-06-02T00:00:00+00:00", "field": "EntityState", "from": "New", "to": "In Progress"},
                {"changed_at": "2026-06-03T00:00:00+00:00", "field": "EntityState", "from": "In Progress", "to": "In Testing"},
                {"changed_at": "2026-06-04T00:00:00+00:00", "field": "EntityState", "from": "In Testing", "to": "New"},
                {"changed_at": "2026-06-05T00:00:00+00:00", "field": "EntityState", "from": "New", "to": "Verified"},
            ],
            "raw": {"Tags": []},
        }
    ]
    rules = WorkflowRulesSettings(
        status_groups={
            "triage": ["New"],
            "in_progress": ["In Progress"],
            "ready_for_qa": ["In Testing"],
            "closed": ["Verified"],
        },
        stale_days=5,
    )

    dataset = build_bug_dataset_records(records, workflow_rules=rules, now=datetime(2026, 6, 6, tzinfo=timezone.utc))

    record = dataset[0]
    assert record["created_at"] == "2026-06-01 00:00:00"
    assert record["updated_at"] == "2026-06-05 00:00:00"
    assert record["last_status_change_at"] == "2026-06-05 00:00:00"
    assert record["entered_new_at"] == "2026-06-01"
    assert record["entered_in_progress_at"] == "2026-06-02"
    assert record["entered_in_testing_at"] == "2026-06-03"
    assert record["entered_verified_at"] == "2026-06-05"
    assert record["reopen_count"] == 1
    assert record["is_reopened"] is True
