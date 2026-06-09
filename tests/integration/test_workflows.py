import io
import re
import zipfile
from xml.etree import ElementTree as ET

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


def test_review_export_workflow_merges_explicit_where_with_default_scope():
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
                "team": ["ESW UI Team"],
            }
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    service.run_workflow("review-export", entity="Bug", filters={"where": 'CreateDate >= "2026-01-01"'})

    assert captured["filters"] == {
        "where": '((Project.Name == "Suunto work") and (Team.Name == "ESW UI Team")) and (CreateDate >= "2026-01-01")'
    }


def test_build_dataset_workflow_merges_explicit_where_and_preserves_dataset_select():
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
                "team": ["ESW China NG3 Driver"],
            },
            default_select=["Id", "Name"],
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    service.run_workflow("build-dataset", entity="Bug", filters={"where": 'CreateDate >= "2026-01-01"'})

    assert captured["filters"]["where"] == '((Project.Name == "Suunto work") and (Team.Name == "ESW China NG3 Driver")) and (CreateDate >= "2026-01-01")'
    assert captured["filters"]["select"] != "{Id,Name}"
    assert "Description" in captured["filters"]["select"]
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
    assert result.records[0]["created_at"] == "2026-06-01 00:00:00"
    assert result.records[0]["updated_at"] == "2026-06-05 00:00:00"
    assert result.records[0]["last_status_change_at"] == "2026-06-05 00:00:00"
    assert result.records[0]["entered_new_at"] == "2026-06-01"
    assert result.records[0]["entered_in_progress_at"] == "2026-06-02"
    assert result.records[0]["entered_in_testing_at"] == "2026-06-03"
    assert result.records[0]["entered_verified_at"] == "2026-06-05"
    assert result.records[0]["reopen_count"] == 1
    assert result.records[0]["history"][0]["to"] == "In Progress"


def test_build_dataset_workflow_default_adds_status_timestamps_without_embedded_history():
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
                ],
                "BugSimpleHistory": [
                    {"Date": "2026-06-01T00:00:00+00:00", "EntityState": {"Name": "New"}, "Bug": {"Id": 201}},
                    {"Date": "2026-06-02T00:00:00+00:00", "EntityState": {"Name": "In Progress"}, "Bug": {"Id": 201}},
                    {"Date": "2026-06-03T00:00:00+00:00", "EntityState": {"Name": "In Testing"}, "Bug": {"Id": 201}},
                    {"Date": "2026-06-04T00:00:00+00:00", "EntityState": {"Name": "New"}, "Bug": {"Id": 201}},
                    {"Date": "2026-06-05T00:00:00+00:00", "EntityState": {"Name": "Verified"}, "Bug": {"Id": 201}},
                ],
        },
    )
    list_calls = []

    def capture_list_entities(entity, filters=None, limit=None):
        list_calls.append(entity)
        return MemoryGateway.list_entities(gateway, entity, filters, limit)

    gateway.list_entities = capture_list_entities
    gateway.bug_history = lambda bug_id: (_ for _ in ()).throw(AssertionError("default build-dataset should not call bug_history"))
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

    result = service.run_workflow("build-dataset", entity="Bug")

    assert list_calls == ["Bug", "BugSimpleHistory"]
    assert result.metadata["history_mode"] == "off"
    assert result.records[0]["created_at"] == "2026-06-01 00:00:00"
    assert result.records[0]["updated_at"] == "2026-06-05 00:00:00"
    assert result.records[0]["last_status_change_at"] == "2026-06-05 00:00:00"
    assert result.records[0]["entered_new_at"] == "2026-06-01"
    assert result.records[0]["entered_in_progress_at"] == "2026-06-02"
    assert result.records[0]["entered_in_testing_at"] == "2026-06-03"
    assert result.records[0]["entered_verified_at"] == "2026-06-05"
    assert result.records[0]["reopen_count"] == 1
    assert "history" not in result.records[0]


def test_review_export_default_adds_status_timestamps_without_embedded_history():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 301,
                    "Name": "Ready for QA crash",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "High"},
                    "EntityState": {"Name": "Ready for QA"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW UI Team"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                    "Tags": [],
                }
                ],
                "BugSimpleHistory": [
                    {"Date": "2026-06-01T00:00:00+00:00", "EntityState": {"Name": "New"}, "Bug": {"Id": 301}},
                    {"Date": "2026-06-02T00:00:00+00:00", "EntityState": {"Name": "Ready for QA"}, "Bug": {"Id": 301}},
                ],
            },
        )
    list_calls = []

    def capture_list_entities(entity, filters=None, limit=None):
        list_calls.append(entity)
        return MemoryGateway.list_entities(gateway, entity, filters, limit)

    gateway.list_entities = capture_list_entities
    gateway.bug_history = lambda bug_id: (_ for _ in ()).throw(AssertionError("default review-export should not call bug_history"))
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"ready_for_qa": ["Ready for QA"]},
            default_scope={"project": ["Suunto work"], "team": ["ESW UI Team"]},
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("review-export", entity="Bug")

    assert list_calls == ["Bug", "BugSimpleHistory"]
    assert result.records[0]["created_at"] == "2026-06-01 00:00:00"
    assert result.records[0]["updated_at"] == "2026-06-03 00:00:00"
    assert result.records[0]["last_status_change_at"] == "2026-06-03 00:00:00"
    assert result.records[0]["entered_new_at"] == "2026-06-01"
    assert result.records[0]["entered_ready_for_qa_at"] == "2026-06-02"
    assert "history" not in result.records[0]


def test_review_export_full_history_mode_keeps_history_and_status_timestamps():
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 301,
                    "Name": "Ready for QA crash",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "High"},
                    "EntityState": {"Name": "Ready for QA"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "Suunto work"},
                    "Team": {"Name": "ESW UI Team"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                    "Tags": [],
                }
            ]
        },
        history={
            "301": [
                {"Date": "2026-06-02T00:00:00+00:00", "Field": "EntityState", "OldValue": "New", "NewValue": "Ready for QA"},
            ]
        },
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"ready_for_qa": ["Ready for QA"]},
            default_scope={"project": ["Suunto work"], "team": ["ESW UI Team"]},
        ),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("review-export", entity="Bug", history_mode="full")

    assert result.records[0]["created_at"] == "2026-06-01 00:00:00"
    assert result.records[0]["updated_at"] == "2026-06-03 00:00:00"
    assert result.records[0]["last_status_change_at"] == "2026-06-03 00:00:00"
    assert result.records[0]["entered_new_at"] == "2026-06-01"
    assert result.records[0]["entered_ready_for_qa_at"] == "2026-06-02"
    assert result.records[0]["history"][0]["to"] == "Ready for QA"


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


def test_weekly_report_workflow_builds_single_sheet_from_highest_week_template(tmp_path):
    template_path = tmp_path / "weekly-template.xlsx"
    template_path.write_bytes(_weekly_template_with_out_of_order_week_sheets_bytes())

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
    assert result.artifacts[0].filename == "质量周报-Week23(2026.6.1-2026.6.7).xlsx"

    workbook_bytes = result.artifacts[0].content
    assert _sheet_names(workbook_bytes) == ["固件质量数据概览-Week23"]
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "A1") == "固件质量报告2026-Week23"
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "B9") == "3"
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "B18") == "3"
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "B30") == "1"
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "A36") == "NG3存量Bug消减情况"
    assert _worksheet_max_column(workbook_bytes, "固件质量数据概览-Week23") == 7
    assert "Week23新增3个Bug" in _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "A3")
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "A4") == "等级"
    assert _sheet_cell(workbook_bytes, "固件质量数据概览-Week23", "A11") == "NG3项目2026年固件有效bug检出&修复情况"
    assert _worksheet_rel_paths(workbook_bytes) == []
    assert _worksheet_hyperlink_count(workbook_bytes, "固件质量数据概览-Week23") == 0


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


def _worksheet_rel_paths(workbook_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as archive:
        return sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/_rels/"))


def _worksheet_hyperlink_count(workbook_bytes: bytes, sheet_name: str) -> int:
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    namespace = {"main": main_ns, "pkg": pkg_rel_ns}

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
            return len(worksheet.findall("main:hyperlinks/main:hyperlink", namespace))
    raise AssertionError(f"sheet not found: {sheet_name}")


def _worksheet_max_column(workbook_bytes: bytes, sheet_name: str) -> int:
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    namespace = {"main": main_ns, "pkg": pkg_rel_ns}

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
            max_column = 0
            for cell in worksheet.findall(".//main:c", namespace):
                ref = cell.attrib.get("r", "")
                match = re.fullmatch(r"([A-Z]+)\d+", ref)
                if match:
                    max_column = max(max_column, _column_index(match.group(1)))
            return max_column
    raise AssertionError(f"sheet not found: {sheet_name}")


def _column_index(label: str) -> int:
    value = 0
    for char in label:
        value = value * 26 + (ord(char) - 64)
    return value


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


def _weekly_template_with_out_of_order_week_sheets_bytes() -> bytes:
    week21 = WorkbookSheet(
        name="固件质量数据概览-Week21",
        rows=[WorkbookRow(["固件质量报告2026-Week21"], kind="title"), *[WorkbookRow([], kind="body") for _ in range(166)]],
    )
    week22 = WorkbookSheet(
        name="固件质量数据概览-Week22",
        rows=_weekly_template_rows(),
    )
    week17 = WorkbookSheet(
        name="固件质量数据概览-Week17&Week18",
        rows=[WorkbookRow(["固件质量报告2026 Week17-Week18"], kind="title"), *[WorkbookRow([], kind="body") for _ in range(166)]],
    )
    helper_sheet = WorkbookSheet(name="数据总览-NG3", rows=[WorkbookRow(["概览"], kind="title")])
    workbook_bytes = _build_xlsx([week21, week22, helper_sheet, week17], "2026-06-05T00:00:00+00:00")
    return _add_week22_hyperlink_relationship(workbook_bytes)


def _add_week22_hyperlink_relationship(workbook_bytes: bytes) -> bytes:
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    namespace = {"main": main_ns, "pkg": pkg_rel_ns}

    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}

    workbook = ET.fromstring(entries["xl/workbook.xml"])
    workbook_rels = ET.fromstring(entries["xl/_rels/workbook.xml.rels"])
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in workbook_rels.findall("pkg:Relationship", namespace)
    }
    target = None
    for sheet in workbook.findall("main:sheets/main:sheet", namespace):
        if sheet.attrib["name"] == "固件质量数据概览-Week22":
            target = rel_map[sheet.attrib[f"{{{rel_ns}}}id"]]
            break
    if target is None:
        raise AssertionError("Week22 sheet missing from test template")

    worksheet_path = f"xl/{target}"
    worksheet = ET.fromstring(entries[worksheet_path])
    hyperlinks = worksheet.find(f"{{{main_ns}}}hyperlinks")
    if hyperlinks is None:
        hyperlinks = ET.SubElement(worksheet, f"{{{main_ns}}}hyperlinks")
    ET.SubElement(
        hyperlinks,
        f"{{{main_ns}}}hyperlink",
        {"ref": "A156", f"{{{rel_ns}}}id": "rId1", "display": "old link"},
    )
    entries[worksheet_path] = ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)
    rels_path = f"xl/worksheets/_rels/{target.split('/')[-1]}.rels"
    entries[rels_path] = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.invalid/old" TargetMode="External"/>'
        b"</Relationships>"
    )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return output.getvalue()


def _weekly_template_rows() -> list[WorkbookRow]:
    cells = {
        1: ["固件质量报告2026-Week22"],
        2: ["2026年NG3固件每周新增Bug"],
        3: ["旧周摘要"],
        4: ["等级", "Bug总数", "New", "处理中", "已解决", "已验证", "异常闭环"],
        5: ["Blocking", 0, 0, 0, 0, 0, 0],
        6: ["Critical", 0, 0, 0, 0, 0, 0],
        7: ["Major", 0, 0, 0, 0, 0, 0],
        8: ["Normal", 0, 0, 0, 0, 0, 0],
        9: ["总计", 0, 0, 0, 0, 0, 0],
        10: ["各状态问题占比", "/", 0, 0, 0, 0, 0],
        11: ["NG3项目2026年固件有效bug检出&修复情况"],
        12: ["旧有效缺陷摘要"],
        13: ["等级", "总bug数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        14: ["Blocking", 0, 0, 0, 0, 0, 0],
        15: ["Critical", 0, 0, 0, 0, 0, 0],
        16: ["Major", 0, 0, 0, 0, 0, 0],
        17: ["Normal", 0, 0, 0, 0, 0, 0],
        18: ["总计", 0, 0, 0, 0, 0, 0],
        19: ["工作组", "B&C bug数", "待解决", "待验证", "非常规闭环单", "关闭率", "验证率"],
        20: ["驱动", 0, 0, 0, 0, 0, 0],
        21: ["框架", 0, 0, 0, 0, 0, 0],
        22: ["UI", 0, 0, 0, 0, 0, 0],
        23: ["2026年NG3固件售后问题"],
        24: ["旧售后摘要"],
        25: ["等级", "售后问题总数", "已关闭", "待关闭", "待验证", "非常规闭环", "关闭率"],
        26: ["Blocking", 0, 0, 0, 0, 0, 0],
        27: ["Critical", 0, 0, 0, 0, 0, 0],
        28: ["Major", 0, 0, 0, 0, 0, 0],
        29: ["Normal", 0, 0, 0, 0, 0, 0],
        30: ["总计", 0, 0, 0, 0, 0, 0],
        31: ["工组组", "Blocking响应超期（>2天）", "Blocking解决超期（>7天）", "Critical响应超期（>7天）", "Critical解决超期（>21天）", "备注"],
        32: ["驱动", 0, 0, 0, 0, ""],
        33: ["框架", 0, 0, 0, 0, ""],
        34: ["UI", 0, 0, 0, 0, ""],
        35: ["总计", 0, 0, 0, 0, ""],
        36: ["NG3存量Bug消减情况"],
        37: ["旧存量摘要"],
        38: ["工作组", "Bug存量", "2026年关闭量", "待研发处理", "待复现", "待验证", "消减率"],
        39: ["驱动", 0, 0, 0, 0, 0, 0],
        40: ["框架", 0, 0, 0, 0, 0, 0],
        41: ["UI", 0, 0, 0, 0, 0, 0],
        42: ["总计", 0, 0, 0, 0, 0, 0],
    }
    rows = []
    for index in range(1, 43):
        rows.append(WorkbookRow(cells.get(index, []), kind="body"))
    return rows
