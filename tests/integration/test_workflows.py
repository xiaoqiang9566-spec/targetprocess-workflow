import io
import zipfile
from xml.etree import ElementTree as ET
from pathlib import Path

from tp_codex.gateway import MemoryGateway, QueryResult
from tp_codex.errors import UpstreamOrTimeoutError
from tp_codex.service import TargetprocessService
from tp_codex.settings import AuthSettings, Settings, WorkflowRulesSettings
from tp_codex.workbooks import WorkbookRow, WorkbookSheet, _build_xlsx


def test_triage_view_defaults_history_mode_to_off():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 7,
                    "Name": "Login bug",
                    "EntityType": {"Name": "Bug"},
                    "EntityState": {"Name": "New"},
                    "Severity": {"Name": "High"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Web"},
                    "Team": {"Name": "Portal"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ]
        },
        history={"7": []},
        partial_history_ids={"7"},
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("triage-view", entity="Bug")

    assert result.warnings == []
    assert result.records[0]["bug_id"] == 7
    assert "history" not in result.records[0]
    assert result.records[0]["status_group"] == "triage"


def test_triage_view_full_history_mode_includes_history_and_partial_history_warning():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 7,
                    "Name": "Login bug",
                    "EntityType": {"Name": "Bug"},
                    "EntityState": {"Name": "New"},
                    "Severity": {"Name": "High"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Web"},
                    "Team": {"Name": "Portal"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ]
        },
        history={"7": []},
        partial_history_ids={"7"},
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("triage-view", entity="Bug", history_mode="full")

    assert result.warnings == ["partial_history"]
    assert result.records[0]["bug_id"] == 7
    assert result.records[0]["history"] == []
    assert result.records[0]["status_group"] == "triage"


def test_triage_view_includes_entity_partial_warning():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 7,
                    "Name": "Login bug",
                    "EntityType": {"Name": "Bug"},
                    "EntityState": {"Name": "New"},
                    "Severity": {"Name": "High"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Web"},
                    "Team": {"Name": "Portal"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ]
        }
    )

    def partial_list_entities(entity, filters=None, limit=None):
        return QueryResult(
            items=list(gateway.entities[entity]),
            total_count=5,
            pages_completed=1,
            partial=True,
        )

    gateway.list_entities = partial_list_entities
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("triage-view", entity="Bug")

    assert "partial_entities" in result.warnings


def test_triage_view_full_history_mode_keeps_records_when_one_history_request_times_out():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 7,
                    "Name": "Login bug",
                    "EntityType": {"Name": "Bug"},
                    "EntityState": {"Name": "New"},
                    "Severity": {"Name": "High"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Web"},
                    "Team": {"Name": "Portal"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                },
                {
                    "Id": 8,
                    "Name": "Sync bug",
                    "EntityType": {"Name": "Bug"},
                    "EntityState": {"Name": "New"},
                    "Severity": {"Name": "High"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Web"},
                    "Team": {"Name": "Portal"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                },
            ]
        },
        history={"7": [{"Date": "2026-06-03T00:00:00+00:00"}]},
    )

    def flaky_bug_history(bug_id):
        if str(bug_id) == "8":
            raise UpstreamOrTimeoutError("history timeout")
        return MemoryGateway.bug_history(gateway, bug_id)

    gateway.bug_history = flaky_bug_history
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("triage-view", entity="Bug", history_mode="full")

    assert result.warnings == ["partial_history"]
    assert [record["bug_id"] for record in result.records] == [7, 8]
    assert result.records[0]["history"] == [
        {
            "event_type": "unknown",
            "changed_at": "2026-06-03T00:00:00+00:00",
            "field": None,
            "from": None,
            "to": None,
            "modifier": None,
            "release": None,
            "iteration": None,
            "project": None,
        }
    ]
    assert result.records[1]["history"] == []


def test_bug_history_workflow_still_raises_when_history_request_times_out():
    gateway = MemoryGateway()

    def failing_bug_history(bug_id):
        raise UpstreamOrTimeoutError("history timeout")

    gateway.bug_history = failing_bug_history
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    try:
        service.run_workflow("bug-history", filters={"bug_id": "7"})
    except UpstreamOrTimeoutError:
        pass
    else:
        raise AssertionError("bug-history workflow should surface upstream history failures")


def test_bug_workflow_applies_default_scope_filters():
    gateway = MemoryGateway(entities={"Bug": []})
    captured = {}

    def capture_list_entities(entity, filters=None, limit=None):
        captured["entity"] = entity
        captured["filters"] = filters
        captured["limit"] = limit
        return QueryResult(items=[], total_count=0)

    gateway.list_entities = capture_list_entities
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            default_scope={
                "project": ["Suunto work"],
                "team": [
                    "ESW China NG3 Driver",
                    "ESW China NG3 Framework",
                    "ESW UI Team",
                ],
            }
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    service.run_workflow("intake", entity="Bug")

    assert captured["entity"] == "Bug"
    assert captured["limit"] is None
    assert captured["filters"] == {
        "where": '(Project.Name == "Suunto work") and ((Team.Name == "ESW China NG3 Driver" or Team.Name == "ESW China NG3 Framework" or Team.Name == "ESW UI Team"))',
    }


def test_entities_list_does_not_apply_default_scope_filters():
    gateway = MemoryGateway(entities={"Bug": []})
    captured = {}

    def capture_list_entities(entity, filters=None, limit=None):
        captured["entity"] = entity
        captured["filters"] = filters
        captured["limit"] = limit
        return QueryResult(items=[], total_count=0)

    gateway.list_entities = capture_list_entities
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            default_scope={
                "project": ["Suunto work"],
                "team": [
                    "ESW China NG3 Driver",
                    "ESW China NG3 Framework",
                    "ESW UI Team",
                ],
            }
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    service.run_workflow("entities-list", entity="Bug")

    assert captured["entity"] == "Bug"
    assert captured["limit"] is None
    assert captured["filters"] is None


def test_bug_workflow_applies_default_select_filter():
    gateway = MemoryGateway(entities={"Bug": []})
    captured = {}

    def capture_list_entities(entity, filters=None, limit=None):
        captured["entity"] = entity
        captured["filters"] = filters
        captured["limit"] = limit
        return QueryResult(items=[], total_count=0)

    gateway.list_entities = capture_list_entities
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            default_select=[
                "Id",
                "Name",
                "CreateDate",
                "ModifyDate",
                "LastStateChangeDate",
                "Team",
                "Project",
                "Severity",
                "EntityState",
                "Owner",
                "Suuntoappversion",
                "Suuntoappplatform",
                "Products",
                "Firmwareversion",
                "Reproducibility",
                "Feature",
                "BugCategory",
            ]
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    service.run_workflow("intake", entity="Bug")

    assert captured["entity"] == "Bug"
    assert captured["limit"] is None
    assert captured["filters"] == {
        "select": "{Id,Name,CreateDate,ModifyDate,LastStateChangeDate,Team,Project,Severity,EntityState,Owner,Suuntoappversion,Suuntoappplatform,Products,Firmwareversion,Reproducibility,Feature,BugCategory}"
    }


def test_bug_workflow_merges_explicit_where_with_default_scope():
    gateway = MemoryGateway(entities={"Bug": []})
    captured = {}

    def capture_list_entities(entity, filters=None, limit=None):
        captured["filters"] = filters
        return QueryResult(items=[], total_count=0)

    gateway.list_entities = capture_list_entities
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            default_scope={
                "project": ["Suunto work"],
                "team": [
                    "ESW China NG3 Driver",
                    "ESW China NG3 Framework",
                    "ESW UI Team",
                ],
            }
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    service.run_workflow("intake", entity="Bug", filters={"where": 'EntityState.Name == "New"'})

    assert captured["filters"] == {
        "where": '((Project.Name == "Suunto work") and ((Team.Name == "ESW China NG3 Driver" or Team.Name == "ESW China NG3 Framework" or Team.Name == "ESW UI Team"))) and (EntityState.Name == "New")'
    }


def test_entities_list_does_not_apply_default_select_filter():
    gateway = MemoryGateway(entities={"Bug": []})
    captured = {}

    def capture_list_entities(entity, filters=None, limit=None):
        captured["entity"] = entity
        captured["filters"] = filters
        captured["limit"] = limit
        return QueryResult(items=[], total_count=0)

    gateway.list_entities = capture_list_entities
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(default_select=["Id", "team:Team.Name"]),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    service.run_workflow("entities-list", entity="Bug")

    assert captured["entity"] == "Bug"
    assert captured["limit"] is None
    assert captured["filters"] is None


def test_build_dataset_workflow_uses_scope_and_dataset_select():
    gateway = MemoryGateway(entities={"Bug": []})
    captured = {}

    def capture_list_entities(entity, filters=None, limit=None):
        captured["entity"] = entity
        captured["filters"] = filters
        captured["limit"] = limit
        return QueryResult(items=[], total_count=0)

    gateway.list_entities = capture_list_entities
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            default_scope={
                "project": ["Suunto work"],
                "team": ["ESW China NG3 Driver", "ESW China NG3 Framework", "ESW UI Team"],
            },
            default_select=["Id", "Name"],
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("build-dataset", entity="Bug")

    assert result.workflow == "build-dataset"
    assert captured["entity"] == "Bug"
    assert 'Project.Name == "Suunto work"' in captured["filters"]["where"]
    assert "ReopenCount" not in captured["filters"]["select"]
    assert "Tags" in captured["filters"]["select"]


def test_build_dataset_workflow_full_history_mode_adds_status_timestamps_and_recomputes_reopen_count():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 201,
                    "Name": "Reopened after testing",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Normal"},
                    "Priority": {"Name": "High"},
                    "EntityState": {"Name": "Verified"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW China NG3 Driver"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-05T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-05T00:00:00+00:00",
                    "ReopenCount": 0,
                    "Tags": [],
                }
            ]
        },
        history={
            "201": [
                {"Date": "2026-06-02T00:00:00+00:00", "Field": "EntityState", "OldValue": "New", "NewValue": "In Progress"},
                {"Date": "2026-06-03T00:00:00+00:00", "Field": "EntityState", "OldValue": "In Progress", "NewValue": "In Testing"},
                {"Date": "2026-06-04T00:00:00+00:00", "Field": "EntityState", "OldValue": "In Testing", "NewValue": "New"},
                {"Date": "2026-06-05T00:00:00+00:00", "Field": "EntityState", "OldValue": "New", "NewValue": "Verified"},
            ]
        },
    )
    history_calls = []

    def capture_bug_history(bug_id):
        history_calls.append(str(bug_id))
        return MemoryGateway.bug_history(gateway, bug_id)

    gateway.bug_history = capture_bug_history
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={
                "triage": ["New"],
                "in_progress": ["In Progress"],
                "ready_for_qa": ["In Testing"],
                "closed": ["Verified"],
            },
            default_scope={"project": ["Suunto work"], "team": ["ESW China NG3 Driver"]},
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("build-dataset", entity="Bug", history_mode="full")

    assert history_calls == ["201"]
    assert result.metadata["history_mode"] == "full"
    assert "entered_in_testing_at" in result.metadata["csv_fieldnames"]
    assert result.records[0]["entered_new_at"] == "2026-06-01T00:00:00+00:00"
    assert result.records[0]["entered_in_progress_at"] == "2026-06-02T00:00:00+00:00"
    assert result.records[0]["entered_in_testing_at"] == "2026-06-03T00:00:00+00:00"
    assert result.records[0]["entered_verified_at"] == "2026-06-05T00:00:00+00:00"
    assert result.records[0]["reopen_count"] == 1


def test_build_workbook_workflow_generates_expected_sheets_and_focus_tabs():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
                    "Priority": {"Name": "High"},
                    "EntityState": {"Name": "New"},
                    "Owner": None,
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW China NG3 Driver"},
                    "CreateDate": "2026-05-26T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-02T00:00:00+00:00",
                    "ReopenCount": 1,
                    "Tags": [{"Name": "customer feedback"}],
                },
                {
                    "Id": 102,
                    "Name": "Expired layout issue",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Normal"},
                    "Priority": {"Name": "Medium"},
                    "EntityState": {"Name": "Expired"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW UI Team"},
                    "CreateDate": "2026-05-20T00:00:00+00:00",
                    "ModifyDate": "2026-06-01T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-01T00:00:00+00:00",
                    "ReopenCount": 0,
                    "Tags": [],
                },
            ]
        }
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"], "closed": ["Done"]},
            high_risk_severities=["Critical"],
            stale_days=5,
            default_scope={
                "project": ["Suunto work"],
                "team": ["ESW China NG3 Driver", "ESW UI Team"],
            },
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("build-workbook", entity="Bug")

    assert result.workflow == "build-workbook"
    assert result.summary["total_records"] == 2
    assert result.summary["sheet_count"] == 10
    assert result.artifacts[0].filename == "quality-analysis-workbook.xlsx"
    assert result.artifacts[0].media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    workbook_bytes = result.artifacts[0].content
    assert _sheet_names(workbook_bytes) == [
        "Overview",
        "Bug_Master",
        "Team_Status",
        "Severity_Risk",
        "Aging_Stale",
        "Customer_Feedback",
        "Weekly_Trend",
        "Monthly_Trend",
        "Top_Risks",
        "Unmapped_Status",
    ]

    top_risks_rows = _sheet_rows(workbook_bytes, "Top_Risks")
    assert any("101" in row for row in top_risks_rows)
    assert any("Crash on launch" in row for row in top_risks_rows)

    unmapped_rows = _sheet_rows(workbook_bytes, "Unmapped_Status")
    assert any("102" in row for row in unmapped_rows)
    assert any("Expired layout issue" in row for row in unmapped_rows)

    team_status_rows = _sheet_rows(workbook_bytes, "Team_Status")
    assert any("ESW China NG3 Driver" in row for row in team_status_rows)
    assert any("ESW UI Team" in row for row in team_status_rows)
    assert any("unmapped" in row for row in team_status_rows)


def test_weekly_report_workflow_appends_new_week_sheet_and_preserves_template_tabs(tmp_path):
    template_path = tmp_path / "weekly-template.xlsx"
    template_path.write_bytes(_weekly_template_bytes())

    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "NG3 crash",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
                    "Priority": {"Name": "High"},
                    "EntityState": {"Name": "New"},
                    "Owner": None,
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW China NG3 Driver"},
                    "Products": [{"Name": "NG3"}],
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-03T00:00:00+00:00",
                    "ReopenCount": 1,
                    "Tags": [{"Name": "customer feedback"}],
                },
                {
                    "Id": 102,
                    "Name": "Dilu waypoint crash",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
                    "Priority": {"Name": "High"},
                    "EntityState": {"Name": "New"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW China NG3 Framework"},
                    "Products": [{"Name": "Dilu"}],
                    "CreateDate": "2026-06-02T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-03T00:00:00+00:00",
                    "ReopenCount": 0,
                    "Tags": [],
                },
                {
                    "Id": 103,
                    "Name": "Core 2 sync issue",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Major"},
                    "Priority": {"Name": "Medium"},
                    "EntityState": {"Name": "Verified"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW UI Team"},
                    "Products": [{"Name": "Core 2"}],
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-04T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-04T00:00:00+00:00",
                    "ReopenCount": 0,
                    "Tags": [],
                },
            ]
        }
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"], "closed": ["Done"], "ready_for_qa": ["Verified"]},
            high_risk_severities=["Critical"],
            stale_days=5,
            default_scope={
                "project": ["Suunto work"],
                "team": ["ESW China NG3 Driver", "ESW China NG3 Framework", "ESW UI Team"],
            },
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow(
        "weekly-report",
        entity="Bug",
        filters={
            "week_label": "Week23",
            "template_path": str(template_path),
        },
    )

    assert result.workflow == "weekly-report"
    assert result.summary["week_label"] == "Week23"
    assert result.summary["total_records"] == 3
    assert result.summary["weekly_new_records"] == 3
    assert result.artifacts[0].filename == "weekly-report-Week23.xlsx"

    workbook_bytes = result.artifacts[0].content
    assert _sheet_names(workbook_bytes) == [
        "固件质量数据概览-Week22",
        "数据总览-NG3",
        "NG3每周解决缺陷",
        "固件质量数据概览-Week23",
    ]
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "A1") == "固件质量报告2026-Week23"
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "B13") == "1"
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "B60") == "1"
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "B121") == "1"
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "A85") == "待人工补充"


def test_monthly_audit_workflow_builds_summary_and_candidates():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 201,
                    "Name": "Critical reopen bug",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
                    "Priority": {"Name": "High"},
                    "EntityState": {"Name": "New"},
                    "Owner": None,
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW China NG3 Driver"},
                    "CreateDate": "2026-06-02T00:00:00+00:00",
                    "ModifyDate": "2026-06-20T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-20T00:00:00+00:00",
                    "ReopenCount": 2,
                    "Tags": [{"Name": "customer feedback"}],
                },
                {
                    "Id": 202,
                    "Name": "Old unmapped bug",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Normal"},
                    "Priority": {"Name": "Medium"},
                    "EntityState": {"Name": "Expired"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW UI Team"},
                    "CreateDate": "2026-04-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-18T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-18T00:00:00+00:00",
                    "ReopenCount": 0,
                    "Tags": [],
                },
                {
                    "Id": 203,
                    "Name": "Routine mapped bug",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Normal"},
                    "Priority": {"Name": "Low"},
                    "EntityState": {"Name": "Done"},
                    "Owner": {"FirstName": "Dev", "LastName": "User"},
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW UI Team"},
                    "CreateDate": "2026-05-10T00:00:00+00:00",
                    "ModifyDate": "2026-05-12T00:00:00+00:00",
                    "LastStateChangeDate": "2026-05-12T00:00:00+00:00",
                    "ReopenCount": 0,
                    "Tags": [],
                },
            ]
        },
        history={
            "201": [
                {
                    "Date": "2026-06-21T00:00:00+00:00",
                    "Field": "EntityState",
                    "OldValue": "New",
                    "NewValue": "Fixed",
                    "Modifier": {"FullName": "QA User"},
                    "Project": {"Name": "Suunto work"},
                    "Release": {"Name": "NG3 Release"},
                    "Iteration": {"Name": "Sprint 25"},
                }
            ],
            "202": [
                {
                    "Date": "2026-06-18T00:00:00+00:00",
                    "Field": "EntityState",
                    "OldValue": "In Progress",
                    "NewValue": "Expired",
                    "Modifier": {"FullName": "Dev User"},
                    "Project": {"Name": "Suunto work"},
                    "Release": {"Name": "NG3 Release"},
                    "Iteration": {"Name": "Sprint 24"},
                }
            ],
        },
    )
    history_calls = []

    def capture_bug_history(bug_id):
        history_calls.append(str(bug_id))
        return MemoryGateway.bug_history(gateway, bug_id)

    gateway.bug_history = capture_bug_history
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"], "closed": ["Done"]},
            high_risk_severities=["Critical", "Blocking"],
            stale_days=5,
            reopen_threshold=1,
            default_scope={
                "project": ["Suunto work"],
                "team": ["ESW China NG3 Driver", "ESW UI Team"],
            },
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("monthly-audit", entity="Bug", filters={"month_label": "2026-06"})

    assert result.workflow == "monthly-audit"
    assert result.summary["month_label"] == "2026-06"
    assert result.summary["created_count"] == 1
    assert result.summary["candidate_risk_records"] == 2
    assert [record["bug_id"] for record in result.records] == [201, 202]
    assert history_calls == ["201", "202"]
    assert result.records[0]["history"][0]["changed_at"] == "2026-06-21T00:00:00+00:00"
    assert result.records[1]["history"][0]["to"] == "Expired"


def test_monthly_audit_workflow_generates_expected_workbook_sheets():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 201,
                    "Name": "Critical reopen bug",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
                    "Priority": {"Name": "High"},
                    "EntityState": {"Name": "New"},
                    "Owner": None,
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW China NG3 Driver"},
                    "CreateDate": "2026-06-02T00:00:00+00:00",
                    "ModifyDate": "2026-06-20T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-20T00:00:00+00:00",
                    "ReopenCount": 2,
                    "Tags": [{"Name": "customer feedback"}],
                },
                {
                    "Id": 202,
                    "Name": "Old unmapped bug",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Normal"},
                    "Priority": {"Name": "Medium"},
                    "EntityState": {"Name": "Expired"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW UI Team"},
                    "CreateDate": "2026-04-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-18T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-18T00:00:00+00:00",
                    "ReopenCount": 0,
                    "Tags": [],
                },
            ]
        },
        history={
            "201": [
                {
                    "Date": "2026-06-21T00:00:00+00:00",
                    "Field": "EntityState",
                    "OldValue": "New",
                    "NewValue": "Fixed",
                    "Modifier": {"FullName": "QA User"},
                    "Project": {"Name": "Suunto work"},
                    "Release": {"Name": "NG3 Release"},
                    "Iteration": {"Name": "Sprint 25"},
                }
            ],
            "202": [
                {
                    "Date": "2026-06-18T00:00:00+00:00",
                    "Field": "EntityState",
                    "OldValue": "In Progress",
                    "NewValue": "Expired",
                    "Modifier": {"FullName": "Dev User"},
                    "Project": {"Name": "Suunto work"},
                    "Release": {"Name": "NG3 Release"},
                    "Iteration": {"Name": "Sprint 24"},
                }
            ],
        },
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"], "closed": ["Done"]},
            high_risk_severities=["Critical", "Blocking"],
            stale_days=5,
            reopen_threshold=1,
            default_scope={
                "project": ["Suunto work"],
                "team": ["ESW China NG3 Driver", "ESW UI Team"],
            },
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("monthly-audit", entity="Bug", filters={"month_label": "2026-06"})

    assert result.artifacts[0].filename == "monthly-audit-2026-06.xlsx"
    workbook_bytes = result.artifacts[0].content
    assert _sheet_names(workbook_bytes) == [
        "Monthly_Summary",
        "Monthly_Trend",
        "Risk_Quality",
        "Process_Exceptions",
        "Candidate_Risks",
        "Candidate_History",
        "Unmapped_Status",
        "Bug_Master",
    ]
    candidate_rows = _sheet_rows(workbook_bytes, "Candidate_Risks")
    assert any("201" in row for row in candidate_rows)
    assert any("202" in row for row in candidate_rows)
    history_rows = _sheet_rows(workbook_bytes, "Candidate_History")
    assert history_rows[1] == [
        "bug_id",
        "name",
        "event_type",
        "changed_at",
        "field",
        "from",
        "to",
        "modifier",
        "release",
        "iteration",
        "project",
    ]
    assert any("Fixed" in row for row in history_rows)
    assert any("Expired" in row for row in history_rows)
    assert any("QA User" in row for row in history_rows)
    assert any("Sprint 25" in row for row in history_rows)


def _sheet_names(workbook_bytes: bytes) -> list[str]:
    namespace = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    }
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    return [sheet.attrib["name"] for sheet in workbook.findall("main:sheets/main:sheet", namespace)]


def _sheet_rows(workbook_bytes: bytes, sheet_name: str) -> list[list[str]]:
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    namespace = {"main": main_ns, "rel": rel_ns, "pkg": pkg_rel_ns}

    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        workbook_rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))

        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in workbook_rels.findall("pkg:Relationship", namespace)
        }
        for sheet in workbook.findall("main:sheets/main:sheet", namespace):
            if sheet.attrib["name"] != sheet_name:
                continue
            target = rel_map[sheet.attrib[f"{{{rel_ns}}}id"]]
            xml_bytes = archive.read(f"xl/{target}")
            worksheet = ET.fromstring(xml_bytes)
            rows: list[list[str]] = []
            for row in worksheet.findall("main:sheetData/main:row", namespace):
                values: list[str] = []
                for cell in row.findall("main:c", namespace):
                    cell_type = cell.attrib.get("t")
                    if cell_type == "inlineStr":
                        text = "".join(cell.findtext("main:is/main:t", default="", namespaces=namespace))
                        values.append(text)
                    else:
                        values.append(cell.findtext("main:v", default="", namespaces=namespace))
                rows.append(values)
            return rows
    raise AssertionError(f"sheet not found: {sheet_name}")


def _sheet_cell(workbook_bytes: bytes, sheet_name: str, cell_ref: str) -> str:
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    namespace = {"main": main_ns, "rel": rel_ns, "pkg": pkg_rel_ns}

    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        workbook_rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in workbook_rels.findall("pkg:Relationship", namespace)
        }
        for sheet in workbook.findall("main:sheets/main:sheet", namespace):
            if sheet.attrib["name"] != sheet_name:
                continue
            target = rel_map[sheet.attrib[f"{{{rel_ns}}}id"]]
            worksheet = ET.fromstring(archive.read(f"xl/{target}"))
            for cell in worksheet.findall(".//main:c", namespace):
                if cell.attrib.get("r") != cell_ref:
                    continue
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    return cell.findtext("main:is/main:t", default="", namespaces=namespace)
                return cell.findtext("main:v", default="", namespaces=namespace)
    raise AssertionError(f"cell not found: {sheet_name}!{cell_ref}")


def _weekly_template_bytes() -> bytes:
    helper_sheet = WorkbookSheet(
        name="数据总览-NG3",
        rows=[WorkbookRow(["概览"], kind="title"), WorkbookRow(["指标", "值"], kind="header"), WorkbookRow(["示例", 1])],
    )
    resolved_sheet = WorkbookSheet(
        name="NG3每周解决缺陷",
        rows=[WorkbookRow(["周", "关闭数"], kind="header"), WorkbookRow(["Week22", 5])],
    )
    weekly_sheet = WorkbookSheet(
        name="固件质量数据概览-Week22",
        rows=_weekly_template_rows(),
    )
    return _build_xlsx([weekly_sheet, helper_sheet, resolved_sheet], "2026-06-05T00:00:00+00:00")


def _weekly_template_rows() -> list[WorkbookRow]:
    cells = {
        1: ["固件质量报告2026-Week22"],
        2: ["NG3 版本发布情况"],
        6: ["2026年NG3固件每周新增Bug"],
        8: ["等级", "Bug总数", "待分析", "处理中", "已解决", "已验证", "异常闭环"],
        9: ["Blocking", 0, 0, 0, 0, 0, 0],
        10: ["Critical", 0, 0, 0, 0, 0, 0],
        11: ["Major", 0, 0, 0, 0, 0, 0],
        12: ["Normal", 0, 0, 0, 0, 0, 0],
        13: ["总计", 0, 0, 0, 0, 0, 0],
        15: ["NG3项目2026年固件有效bug检出&修复情况"],
        17: ["等级", "总有效bug数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        18: ["Blocking", 0, 0, 0, 0, 0, 0],
        19: ["Critical", 0, 0, 0, 0, 0, 0],
        20: ["Major", 0, 0, 0, 0, 0, 0],
        21: ["Normal", 0, 0, 0, 0, 0, 0],
        22: ["总计", 0, 0, 0, 0, 0, 0],
        23: ["工作组", "B&C有效bug数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        24: ["驱动", 0, 0, 0, 0, 0, 0],
        25: ["框架", 0, 0, 0, 0, 0, 0],
        26: ["UI", 0, 0, 0, 0, 0, 0],
        27: ["2026年NG3固件售后问题"],
        29: ["等级", "售后问题总数", "已关闭", "待关闭", "待验证", "非常规闭环", "关闭率"],
        30: ["Blocking", 0, 0, 0, 0, 0, 0],
        31: ["Critical", 0, 0, 0, 0, 0, 0],
        32: ["Major", 0, 0, 0, 0, 0, 0],
        33: ["Normal", 0, 0, 0, 0, 0, 0],
        34: ["总计", 0, 0, 0, 0, 0, 0],
        35: ["工组组", "Blocking响应周期>2天", "Blocking解决周期>7天", "Critical响应周期>7天", "Critical解决周期>21天", "问题处理方案"],
        36: ["驱动", 0, 0, 0, 0, ""],
        37: ["框架", 0, 0, 0, 0, ""],
        38: ["UI", 0, 0, 0, 0, ""],
        39: ["总计", 0, 0, 0, 0, ""],
        40: ["NG3存量Bug消减情况"],
        42: ["工作组", "Bug存量", "2026年关闭量", "待研发处理", "待复现", "待验证", "消减率"],
        43: ["驱动", 0, 0, 0, 0, 0, 0],
        44: ["框架", 0, 0, 0, 0, 0, 0],
        45: ["UI", 0, 0, 0, 0, 0, 0],
        46: ["总计", 0, 0, 0, 0, 0, 0],
        48: ["Dilu 版本发布情况"],
        53: ["2026年Dilu固件每周新增Bug"],
        55: ["等级", "Bug总数", "客诉问题", "开发过程问题", "待处理", "处理中", "已解决&已闭环"],
        56: ["致命", 0, 0, 0, 0, 0, 0],
        57: ["严重", 0, 0, 0, 0, 0, 0],
        58: ["一般", 0, 0, 0, 0, 0, 0],
        59: ["提示", 0, 0, 0, 0, 0, 0],
        60: ["总计", 0, 0, 0, 0, 0, 0],
        62: ["2026年Dilu固件有效Bug修复情况"],
        64: ["等级", "Bug总数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        65: ["致命", 0, 0, 0, 0, 0, 0],
        66: ["严重", 0, 0, 0, 0, 0, 0],
        67: ["一般", 0, 0, 0, 0, 0, 0],
        68: ["提示", 0, 0, 0, 0, 0, 0],
        69: ["总计", 0, 0, 0, 0, 0, 0],
        70: ["工作组", "Bug总数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        71: ["驱动", 0, 0, 0, 0, 0, 0],
        72: ["框架", 0, 0, 0, 0, 0, 0],
        73: ["应用", 0, 0, 0, 0, 0, 0],
        74: ["2026年Dilu 固件售后问题"],
        76: ["等级", "售后问题总数", "正常闭环", "待解决", "待验证", "已拒绝", "关闭率"],
        77: ["严重", 0, 0, 0, 0, 0, 0],
        78: ["一般", 0, 0, 0, 0, 0, 0],
        79: ["总计", 0, 0, 0, 0, 0, 0],
        80: ["工组组", "＞15天的B&C问题", "＞45天的一般问题", "问题处理方案"],
        81: ["驱动", 0, 0, ""],
        82: ["框架", 0, 0, ""],
        83: ["应用", 0, 0, ""],
        84: ["总计", 0, 0, ""],
        85: ["Dilu 固件全量DI值情况（2025年1月至今）"],
        92: ["Dilu 固件版本DI值情况（2026年4月&6月版本）"],
        100: ["心率带2版本发布情况"],
        104: ["心率带2缺陷检出&修复情况"],
        106: ["等级", "总计", "新", "处理中", "已解决", "已验证", "已拒绝"],
        107: ["致命", 0, 0, 0, 0, 0, 0],
        108: ["严重", 0, 0, 0, 0, 0, 0],
        109: ["一般", 0, 0, 0, 0, 0, 0],
        110: ["总计", 0, 0, 0, 0, 0, 0],
        112: ["Core 2 版本发布情况"],
        115: ["Core 2 缺陷检出&修复情况"],
        117: ["等级", "总计", "新", "处理中", "已解决", "已验证", "已拒绝"],
        118: ["致命", 0, 0, 0, 0, 0, 0],
        119: ["严重", 0, 0, 0, 0, 0, 0],
        120: ["一般", 0, 0, 0, 0, 0, 0],
        121: ["总计", 0, 0, 0, 0, 0, 0],
        122: ["模块", "总计", "新", "处理中", "已解决", "已验证", "已拒绝"],
        123: ["UI/UX", 0, 0, 0, 0, 0, 0],
        124: ["基线开发", 0, 0, 0, 0, 0, 0],
        125: ["蓝牙", 0, 0, 0, 0, 0, 0],
        126: ["驱动", 0, 0, 0, 0, 0, 0],
        127: ["算法集成", 0, 0, 0, 0, 0, 0],
        128: ["应用功能", 0, 0, 0, 0, 0, 0],
        129: ["总计", 0, 0, 0, 0, 0, 0],
        131: ["Run 2 版本发布情况"],
        135: ["Run2 缺陷检出&修复情况"],
        137: ["等级", "Bug总数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        138: ["致命", 0, 0, 0, 0, 0, 0],
        139: ["严重", 0, 0, 0, 0, 0, 0],
        140: ["一般", 0, 0, 0, 0, 0, 0],
        141: ["总计", 0, 0, 0, 0, 0, 0],
        142: ["工作组", "Bug总数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        143: ["驱动", 0, 0, 0, 0, 0, 0],
        144: ["框架", 0, 0, 0, 0, 0, 0],
        145: ["应用", 0, 0, 0, 0, 0, 0],
        147: ["Race 3S/Race3 版本发布情况"],
        156: ["Race 3S 缺陷检出&修复情况"],
        158: ["等级", "Bug总数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        159: ["致命", 0, 0, 0, 0, 0, 0],
        160: ["严重", 0, 0, 0, 0, 0, 0],
        161: ["一般", 0, 0, 0, 0, 0, 0],
        162: ["提示", 0, 0, 0, 0, 0, 0],
        163: ["总计", 0, 0, 0, 0, 0, 0],
        164: ["工作组", "Bug总数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        165: ["驱动", 0, 0, 0, 0, 0, 0],
        166: ["框架", 0, 0, 0, 0, 0, 0],
        167: ["UI", 0, 0, 0, 0, 0, 0],
    }
    rows = []
    for index in range(1, 168):
        rows.append(WorkbookRow(cells.get(index, []), kind="body"))
    return rows
