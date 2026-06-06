import csv
import io
import json
import sys
import zipfile

from tp_codex.cli import build_parser, run_cli
from tp_codex.datasets import BUG_DATASET_FIELDNAMES
from tp_codex.gateway import MemoryGateway
from tp_codex.settings import AuthSettings, Settings, WorkflowRulesSettings
from tp_codex.workbooks import WorkbookRow, WorkbookSheet, _build_xlsx


def test_cli_intake_outputs_json_payload(capsys):
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
                    "Project": {"Name": "QA"},
                    "Team": {"Name": "Mobile"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ]
        }
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"]},
            high_risk_severities=["Critical"],
            stale_days=2,
        ),
    )

    exit_code = run_cli(
        ["bugs", "intake", "--format", "json"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["total_records"] == 1
    assert payload["records"][0]["bug_id"] == 101
    assert payload["records"][0]["status_group"] == "triage"
    assert payload["records"][0]["risk_signals"][0]["code"] == "high_severity"


def test_build_parser_includes_workflow_commands():
    parser = build_parser()

    help_text = parser.format_help()

    assert "healthcheck" in help_text
    assert "triage-view" in help_text


def test_build_parser_includes_reports_build_dataset_command():
    parser = build_parser()

    args = parser.parse_args(["reports", "build-dataset", "--format", "csv"])

    assert args.command == "reports"
    assert args.reports_command == "build-dataset"
    assert args.format == "csv"


def test_build_parser_build_dataset_accepts_history_mode():
    parser = build_parser()

    args = parser.parse_args(["reports", "build-dataset", "--history-mode", "full"])

    assert args.history_mode == "full"


def test_build_parser_build_dataset_accepts_where():
    parser = build_parser()

    args = parser.parse_args(["reports", "build-dataset", "--where", 'CreateDate >= "2026-01-01"'])

    assert args.where == 'CreateDate >= "2026-01-01"'


def test_build_parser_includes_reports_build_workbook_command():
    parser = build_parser()

    args = parser.parse_args(["reports", "build-workbook", "--output", "quality.xlsx"])

    assert args.command == "reports"
    assert args.reports_command == "build-workbook"
    assert args.output == "quality.xlsx"
    assert args.format == "xlsx"


def test_build_parser_includes_reports_weekly_report_command():
    parser = build_parser()

    args = parser.parse_args(
        [
            "reports",
            "weekly-report",
            "--week-label",
            "Week23",
            "--template",
            "weekly-template.xlsx",
            "--output",
            "weekly-report.xlsx",
        ]
    )

    assert args.command == "reports"
    assert args.reports_command == "weekly-report"
    assert args.week_label == "Week23"
    assert args.template == "weekly-template.xlsx"
    assert args.output == "weekly-report.xlsx"
    assert args.format == "xlsx"


def test_build_parser_includes_reports_monthly_audit_command():
    parser = build_parser()

    args = parser.parse_args(
        [
            "reports",
            "monthly-audit",
            "--month-label",
            "2026-06",
            "--output",
            "monthly-audit.xlsx",
        ]
    )

    assert args.command == "reports"
    assert args.reports_command == "monthly-audit"
    assert args.month_label == "2026-06"
    assert args.output == "monthly-audit.xlsx"
    assert args.format == "xlsx"


def test_build_parser_includes_reports_send_command():
    parser = build_parser()

    args = parser.parse_args(["reports", "send", "--manifest", "run-metadata.json"])

    assert args.command == "reports"
    assert args.reports_command == "send"
    assert args.manifest == "run-metadata.json"
    assert args.format == "markdown"


def test_build_parser_includes_reports_run_weekly_command():
    parser = build_parser()

    args = parser.parse_args(
        [
            "reports",
            "run-weekly",
            "--week-label",
            "Week23",
            "--template",
            "weekly-template.xlsx",
            "--output-dir",
            "outputs/reports/weekly/2026-06-05",
        ]
    )

    assert args.command == "reports"
    assert args.reports_command == "run-weekly"
    assert args.week_label == "Week23"
    assert args.template == "weekly-template.xlsx"
    assert args.output_dir == "outputs/reports/weekly/2026-06-05"


def test_build_parser_includes_reports_run_monthly_command():
    parser = build_parser()

    args = parser.parse_args(
        [
            "reports",
            "run-monthly",
            "--month-label",
            "2026-06",
            "--output-dir",
            "outputs/reports/monthly/2026-06",
        ]
    )

    assert args.command == "reports"
    assert args.reports_command == "run-monthly"
    assert args.month_label == "2026-06"
    assert args.output_dir == "outputs/reports/monthly/2026-06"


def test_history_mode_defaults_to_off_for_history_backed_bug_workflows():
    parser = build_parser()

    triage_args = parser.parse_args(["bugs", "triage-view"])
    risk_args = parser.parse_args(["bugs", "risk-scan"])
    review_args = parser.parse_args(["bugs", "review-export"])

    assert triage_args.history_mode == "off"
    assert risk_args.history_mode == "off"
    assert review_args.history_mode == "off"


def test_history_mode_accepts_full_for_history_backed_bug_workflows():
    parser = build_parser()

    triage_args = parser.parse_args(["bugs", "triage-view", "--history-mode", "full"])
    risk_args = parser.parse_args(["bugs", "risk-scan", "--history-mode", "full"])
    review_args = parser.parse_args(["bugs", "review-export", "--history-mode", "full"])

    assert triage_args.history_mode == "full"
    assert risk_args.history_mode == "full"
    assert review_args.history_mode == "full"


def test_review_export_accepts_where():
    parser = build_parser()

    args = parser.parse_args(["bugs", "review-export", "--where", 'CreateDate >= "2026-01-01"'])

    assert args.where == 'CreateDate >= "2026-01-01"'


def test_history_mode_is_not_available_for_unrelated_bug_workflows():
    parser = build_parser()

    intake_args = parser.parse_args(["bugs", "intake"])
    regression_args = parser.parse_args(["bugs", "regression-queue"])
    history_args = parser.parse_args(["bugs", "history", "--bug-id", "7"])

    assert not hasattr(intake_args, "history_mode")
    assert not hasattr(regression_args, "history_mode")
    assert not hasattr(history_args, "history_mode")


def test_where_is_not_available_for_unrelated_workflows():
    parser = build_parser()

    for argv in [
        ["bugs", "intake", "--where", 'CreateDate >= "2026-01-01"'],
        ["bugs", "triage-view", "--where", 'CreateDate >= "2026-01-01"'],
        ["bugs", "risk-scan", "--where", 'CreateDate >= "2026-01-01"'],
        ["reports", "build-workbook", "--where", 'CreateDate >= "2026-01-01"'],
    ]:
        try:
            parser.parse_args(argv)
        except SystemExit as exc:
            assert exc.code == 2
        else:  # pragma: no cover - defensive
            raise AssertionError(f"--where unexpectedly accepted for argv={argv}")


def test_cli_uses_explicit_config_paths(tmp_path, capsys):
    config_path = tmp_path / "targetprocess.yaml"
    rules_path = tmp_path / "workflow_rules.yaml"
    config_path.write_text(
        "base_url: https://example.tpondemand.com\nauth_mode: access_token\naccess_token: token\n",
        encoding="utf-8",
    )
    rules_path.write_text("status_groups:\n  triage: [New]\n", encoding="utf-8")

    exit_code = run_cli(
        [
            "--config",
            str(config_path),
            "--workflow-rules",
            str(rules_path),
            "healthcheck",
            "--format",
            "json",
        ],
        gateway=MemoryGateway(),
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["records"][0]["status"] == "ok"


def test_healthcheck_includes_workflow_rules_summary(capsys):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"]},
            high_risk_severities=["Critical", "High"],
            stale_days=5,
            reopen_threshold=2,
            default_scope={
                "project": ["Suunto work"],
                "team": ["ESW UI Team"],
            },
            default_select=["Id", "Name", "team:Team.Name"],
        ),
    )

    exit_code = run_cli(
        ["healthcheck", "--format", "json"],
        settings=settings,
        gateway=MemoryGateway(),
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["records"][0]["status"] == "ok"
    assert payload["records"][0]["workflow_rules"] == {
        "status_groups": {"triage": ["New"]},
        "high_risk_severities": ["Critical", "High"],
        "stale_days": 5,
        "reopen_threshold": 2,
        "default_scope": {
            "project": ["Suunto work"],
            "team": ["ESW UI Team"],
        },
        "default_select": ["Id", "Name", "team:Team.Name"],
    }


def test_cli_risk_scan_outputs_markdown_cards(capsys):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
                    "EntityState": {"Name": "Ready for QA"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Team": {"Name": "ESW UI Team"},
                    "Reproducibility": {"Name": "Always"},
                    "Products": [{"Name": "Watch A"}, {"Name": "Watch B"}],
                    "Firmwareversion": "FW-9.8.7",
                    "BugCategory": {"Name": "Regression"},
                    "Suuntoappplatform": "Android",
                    "Suuntoappversion": "2.0.1",
                    "Feature": [{"Id": 501}, {"Id": 502}],
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ]
        }
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"ready_for_qa": ["Ready for QA"]},
            high_risk_severities=["Critical"],
        ),
    )

    exit_code = run_cli(
        ["bugs", "risk-scan", "--format", "markdown"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = capsys.readouterr().out
    assert "### `101` Crash on launch [ready_for_qa]" in payload
    assert "- Team: ESW UI Team" in payload
    assert "- Bug Category: Regression" in payload
    assert "- Products: Watch A, Watch B" in payload
    assert "#### Risk Signals" in payload
    assert "- `high_severity`: Bug severity is in the high-risk list" in payload


def test_cli_triage_view_omits_history_by_default(capsys):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
                    "EntityState": {"Name": "New"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "QA"},
                    "Team": {"Name": "Mobile"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ]
        },
        history={"101": [{"Date": "2026-06-03T00:00:00+00:00"}]},
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        ["bugs", "triage-view", "--format", "json"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["records"][0]["bug_id"] == 101
    assert "history" not in payload["records"][0]


def test_cli_triage_view_full_history_mode_includes_history(capsys):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
                    "EntityState": {"Name": "New"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Project": {"Name": "QA"},
                    "Team": {"Name": "Mobile"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ]
        },
        history={
            "101": [
                {
                    "Date": "2026-06-03T00:00:00+00:00",
                    "Action": "Update",
                    "Description": "Severity changed",
                    "Modifier": {"FullName": "QA User"},
                    "Project": {"Name": "QA"},
                    "Release": {"Name": "Release 24.6"},
                    "Iteration": {"Name": "Sprint 23"},
                }
            ]
        },
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        ["bugs", "triage-view", "--history-mode", "full", "--format", "json"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["records"][0]["bug_id"] == 101
    assert payload["records"][0]["history"] == [
        {
            "event_type": "unknown",
            "changed_at": "2026-06-03T00:00:00+00:00",
            "field": None,
            "from": None,
            "to": None,
            "modifier": "QA User",
            "release": "Release 24.6",
            "iteration": "Sprint 23",
            "project": "QA",
        }
    ]


def test_cli_review_export_outputs_expanded_csv(capsys):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Project": {"Name": "Suunto work"},
                    "Severity": {"Name": "Critical"},
                    "Priority": {"Name": "High"},
                    "EntityState": {"Name": "New"},
                    "Owner": None,
                    "Team": {"Name": "ESW China NG3 Driver"},
                    "Reproducibility": {"Name": "Always"},
                    "Products": [{"Name": "Watch A"}, {"Name": "Watch B"}],
                    "Firmwareversion": "FW-9.8.7",
                    "BugCategory": {"Name": "Regression"},
                    "Suuntoappplatform": "Android",
                    "Suuntoappversion": "2.0.1",
                    "Feature": [{"Id": 501}, {"Id": 502}],
                    "UserStory": [{"Id": 601}],
                    "LastStateChangeDate": "2026-06-02T00:00:00+00:00",
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                    "ReopenCount": 1,
                    "Tags": [{"Name": "customer feedback"}],
                }
            ],
                "BugSimpleHistory": [
                    {
                        "Date": "2026-06-01T00:00:00+00:00",
                        "EntityState": {"Name": "New"},
                        "Bug": {"Id": 101, "Name": "Crash on launch"},
                    },
                    {
                        "Date": "2026-06-02T00:00:00+00:00",
                        "EntityState": {"Name": "Ready for QA"},
                        "Bug": {"Id": 101, "Name": "Crash on launch"},
                    }
            ],
        },
    )
    gateway.bug_history = lambda bug_id: (_ for _ in ()).throw(AssertionError("default review-export should not call bug_history"))
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"]},
            high_risk_severities=["Critical"],
            stale_days=5,
            default_scope={"team": ["ESW China NG3 Driver"]},
        ),
    )

    exit_code = run_cli(
        ["bugs", "review-export", "--format", "csv"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = capsys.readouterr().out
    rows = list(csv.DictReader(io.StringIO(payload)))
    assert list(rows[0].keys())[: len(BUG_DATASET_FIELDNAMES)] == BUG_DATASET_FIELDNAMES
    assert rows[0]["created_at"] == "2026-06-01 00:00:00"
    assert rows[0]["updated_at"] == "2026-06-03 00:00:00"
    assert rows[0]["last_status_change_at"] == "2026-06-02 00:00:00"
    assert rows[0]["entered_new_at"] == "2026-06-01"
    assert rows[0]["entered_ready_for_qa_at"] == "2026-06-02"
    assert rows[0]["project"] == "Suunto work"
    assert rows[0]["priority"] == "High"
    assert rows[0]["status_group"] == "triage"
    assert rows[0]["created_week"] == "2026-W23"
    assert rows[0]["quality_bucket"] == "customer_feedback"
    assert rows[0]["audit_focus"] == "owner_missing"
    assert rows[0]["team_scope_label"] == "default_scope_team"
    assert rows[0]["linked_feature_ids"] == "501; 502"
    assert rows[0]["linked_user_story_ids"] == "601"
    assert rows[0]["data_gaps"] == "owner"
    assert "high_severity" in rows[0]["risk_signals"]
    assert "missing_owner" in rows[0]["risk_signals"]


def test_cli_review_export_default_json_omits_history_but_includes_status_timestamps(capsys):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "High"},
                    "EntityState": {"Name": "Ready for QA"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Team": {"Name": "ESW UI Team"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ],
            "BugSimpleHistory": [
                {
                    "Date": "2026-06-01T00:00:00+00:00",
                    "EntityState": {"Name": "New"},
                    "Bug": {"Id": 101, "Name": "Crash on launch"},
                },
                {
                    "Date": "2026-06-02T00:00:00+00:00",
                    "EntityState": {"Name": "Ready for QA"},
                    "Bug": {"Id": 101, "Name": "Crash on launch"},
                },
            ],
        },
    )
    gateway.bug_history = lambda bug_id: (_ for _ in ()).throw(AssertionError("default review-export should not call bug_history"))
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"ready_for_qa": ["Ready for QA"]}),
    )

    exit_code = run_cli(
        ["bugs", "review-export", "--format", "json"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    record = payload["records"][0]
    assert "history" not in record
    assert record["created_at"] == "2026-06-01 00:00:00"
    assert record["updated_at"] == "2026-06-03 00:00:00"
    assert record["last_status_change_at"] == "2026-06-03 00:00:00"
    assert record["entered_new_at"] == "2026-06-01"
    assert record["entered_ready_for_qa_at"] == "2026-06-02"


def test_cli_review_export_passes_where_filter(capsys):
    gateway = MemoryGateway(entities={"Bug": []})
    captured = {}

    def capture_list_entities(entity, filters=None, limit=None):
        captured["entity"] = entity
        captured["filters"] = filters
        captured["limit"] = limit
        return MemoryGateway.list_entities(gateway, entity, filters, limit)

    gateway.list_entities = capture_list_entities
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(default_scope={"team": ["ESW UI Team"]}),
    )

    exit_code = run_cli(
        ["bugs", "review-export", "--where", 'CreateDate >= "2026-01-01"', "--format", "json"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["summary"]["total_records"] == 0
    assert captured["entity"] == "Bug"
    assert captured["limit"] is None
    assert captured["filters"]["where"] == '(Team.Name == "ESW UI Team") and (CreateDate >= "2026-01-01")'


def test_cli_review_export_full_history_mode_keeps_history_and_status_timestamps(capsys):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "High"},
                    "EntityState": {"Name": "Ready for QA"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Team": {"Name": "ESW UI Team"},
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ]
        },
        history={
            "101": [
                {
                    "Date": "2026-06-02T00:00:00+00:00",
                    "Field": "EntityState",
                    "OldValue": "New",
                    "NewValue": "Ready for QA",
                }
            ]
        },
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"ready_for_qa": ["Ready for QA"]}),
    )

    exit_code = run_cli(
        ["bugs", "review-export", "--history-mode", "full", "--format", "json"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    record = payload["records"][0]
    assert record["created_at"] == "2026-06-01 00:00:00"
    assert record["updated_at"] == "2026-06-03 00:00:00"
    assert record["last_status_change_at"] == "2026-06-03 00:00:00"
    assert record["entered_new_at"] == "2026-06-01"
    assert record["entered_ready_for_qa_at"] == "2026-06-02"
    assert record["history"] == [
        {
            "event_type": "unknown",
            "changed_at": "2026-06-02T00:00:00+00:00",
            "field": "EntityState",
            "from": "New",
            "to": "Ready for QA",
            "modifier": None,
            "release": None,
            "iteration": None,
            "project": None,
        }
    ]


def test_cli_build_dataset_outputs_csv_with_reporting_columns(capsys):
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
                }
            ],
                "BugSimpleHistory": [
                    {"Date": "2026-05-26T00:00:00+00:00", "EntityState": {"Name": "New"}, "Bug": {"Id": 101}},
                    {"Date": "2026-05-28T00:00:00+00:00", "EntityState": {"Name": "In Progress"}, "Bug": {"Id": 101}},
                    {"Date": "2026-05-29T00:00:00+00:00", "EntityState": {"Name": "In Testing"}, "Bug": {"Id": 101}},
                    {"Date": "2026-05-30T00:00:00+00:00", "EntityState": {"Name": "New"}, "Bug": {"Id": 101}},
                ],
            },
        )
    gateway.bug_history = lambda bug_id: (_ for _ in ()).throw(AssertionError("default build-dataset should not call bug_history"))
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"]},
            high_risk_severities=["Critical"],
            stale_days=5,
            default_scope={"team": ["ESW China NG3 Driver"]},
        ),
    )

    exit_code = run_cli(
        ["reports", "build-dataset", "--format", "csv"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = capsys.readouterr().out
    row = next(csv.DictReader(io.StringIO(payload)))
    assert row["created_week"] == "2026-W22"
    assert row["is_customer_feedback"] == "True"
    assert row["quality_bucket"] == "customer_feedback"
    assert row["team_scope_label"] == "default_scope_team"
    assert row["created_at"] == "2026-05-26 00:00:00"
    assert row["updated_at"] == "2026-06-03 00:00:00"
    assert row["last_status_change_at"] == "2026-06-02 00:00:00"
    assert row["entered_new_at"] == "2026-05-26"
    assert row["entered_in_progress_at"] == "2026-05-28"
    assert row["entered_in_testing_at"] == "2026-05-29"
    assert row["reopen_count"] == "1"


def test_cli_build_dataset_passes_where_filter(capsys):
    gateway = MemoryGateway(entities={"Bug": []})
    captured = {}

    def capture_list_entities(entity, filters=None, limit=None):
        captured["entity"] = entity
        captured["filters"] = filters
        captured["limit"] = limit
        return MemoryGateway.list_entities(gateway, entity, filters, limit)

    gateway.list_entities = capture_list_entities
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            default_scope={"project": ["Suunto work"], "team": ["ESW China NG3 Driver"]},
            default_select=["Id", "Name"],
        ),
    )

    exit_code = run_cli(
        [
            "reports",
            "build-dataset",
            "--where",
            'CreateDate >= "2026-01-01"',
            "--format",
            "json",
        ],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["summary"]["total_records"] == 0
    assert captured["entity"] == "Bug"
    assert captured["limit"] is None
    assert captured["filters"]["where"] == '((Project.Name == "Suunto work") and (Team.Name == "ESW China NG3 Driver")) and (CreateDate >= "2026-01-01")'
    assert "Description" in captured["filters"]["select"]
    assert captured["filters"]["select"] != "{Id,Name}"


def test_cli_build_dataset_full_history_mode_keeps_history_and_outputs_status_timestamp_columns(capsys):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
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
            "101": [
                {"Date": "2026-06-02T00:00:00+00:00", "Field": "EntityState", "OldValue": "New", "NewValue": "In Progress"},
                {"Date": "2026-06-03T00:00:00+00:00", "Field": "EntityState", "OldValue": "In Progress", "NewValue": "In Testing"},
                {"Date": "2026-06-04T00:00:00+00:00", "Field": "EntityState", "OldValue": "In Testing", "NewValue": "New"},
                {"Date": "2026-06-05T00:00:00+00:00", "Field": "EntityState", "OldValue": "New", "NewValue": "Verified"},
            ]
        },
    )
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
            high_risk_severities=["Critical"],
            stale_days=5,
            default_scope={"team": ["ESW China NG3 Driver"]},
        ),
    )

    exit_code = run_cli(
        ["reports", "build-dataset", "--history-mode", "full", "--format", "json"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    record = payload["records"][0]
    assert record["created_at"] == "2026-06-01 00:00:00"
    assert record["updated_at"] == "2026-06-05 00:00:00"
    assert record["last_status_change_at"] == "2026-06-05 00:00:00"
    assert record["entered_new_at"] == "2026-06-01"
    assert record["entered_in_progress_at"] == "2026-06-02"
    assert record["entered_in_testing_at"] == "2026-06-03"
    assert record["entered_verified_at"] == "2026-06-05"
    assert record["reopen_count"] == 1
    assert record["history"] == [
        {
            "event_type": "unknown",
            "changed_at": "2026-06-02T00:00:00+00:00",
            "field": "EntityState",
            "from": "New",
            "to": "In Progress",
            "modifier": None,
            "release": None,
            "iteration": None,
            "project": None,
        },
        {
            "event_type": "unknown",
            "changed_at": "2026-06-03T00:00:00+00:00",
            "field": "EntityState",
            "from": "In Progress",
            "to": "In Testing",
            "modifier": None,
            "release": None,
            "iteration": None,
            "project": None,
        },
        {
            "event_type": "unknown",
            "changed_at": "2026-06-04T00:00:00+00:00",
            "field": "EntityState",
            "from": "In Testing",
            "to": "New",
            "modifier": None,
            "release": None,
            "iteration": None,
            "project": None,
        },
        {
            "event_type": "unknown",
            "changed_at": "2026-06-05T00:00:00+00:00",
            "field": "EntityState",
            "from": "New",
            "to": "Verified",
            "modifier": None,
            "release": None,
            "iteration": None,
            "project": None,
        },
    ]


def test_cli_build_workbook_requires_output_for_xlsx(capsys):
    gateway = MemoryGateway(entities={"Bug": []})
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        ["reports", "build-workbook", "--format", "xlsx"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 2
    assert "--output is required for xlsx" in capsys.readouterr().err


def test_cli_build_workbook_writes_xlsx_to_output_file(tmp_path, capsys):
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
                }
            ]
        }
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"]},
            high_risk_severities=["Critical"],
            stale_days=5,
            default_scope={"team": ["ESW China NG3 Driver"]},
        ),
    )
    output_path = tmp_path / "exports" / "quality-analysis.xlsx"

    exit_code = run_cli(
        ["reports", "build-workbook", "--format", "xlsx", "--output", str(output_path)],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    with zipfile.ZipFile(output_path) as archive:
        assert "xl/workbook.xml" in archive.namelist()
        assert "xl/worksheets/sheet1.xml" in archive.namelist()


def test_cli_weekly_report_requires_template_for_xlsx(capsys):
    gateway = MemoryGateway(entities={"Bug": []})
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        ["reports", "weekly-report", "--week-label", "Week23", "--format", "xlsx", "--output", "weekly.xlsx"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 2
    assert "--template is required for weekly-report xlsx" in capsys.readouterr().err


def test_cli_weekly_report_requires_week_label_for_xlsx(capsys):
    gateway = MemoryGateway(entities={"Bug": []})
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        [
            "reports",
            "weekly-report",
            "--format",
            "xlsx",
            "--template",
            "weekly-template.xlsx",
            "--output",
            "weekly.xlsx",
        ],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 2
    assert "--week-label is required for weekly-report" in capsys.readouterr().err


def test_cli_monthly_audit_requires_month_label_for_xlsx(capsys):
    gateway = MemoryGateway(entities={"Bug": []})
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        ["reports", "monthly-audit", "--format", "xlsx", "--output", "monthly.xlsx"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 2
    assert "--month-label is required for monthly-audit" in capsys.readouterr().err


def test_cli_monthly_audit_writes_xlsx_to_output_file(tmp_path, capsys):
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
                    "CreateDate": "2026-06-02T00:00:00+00:00",
                    "ModifyDate": "2026-06-20T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-20T00:00:00+00:00",
                    "ReopenCount": 2,
                    "Tags": [{"Name": "customer feedback"}],
                }
            ]
        },
        history={
            "101": [{"Date": "2026-06-21T00:00:00+00:00", "Field": "EntityState", "OldValue": "New", "NewValue": "Fixed"}]
        },
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"], "closed": ["Done"]},
            high_risk_severities=["Critical"],
            stale_days=5,
            reopen_threshold=1,
            default_scope={"team": ["ESW China NG3 Driver"]},
        ),
    )
    output_path = tmp_path / "exports" / "monthly-audit.xlsx"

    exit_code = run_cli(
        [
            "reports",
            "monthly-audit",
            "--month-label",
            "2026-06",
            "--format",
            "xlsx",
            "--output",
            str(output_path),
        ],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    with zipfile.ZipFile(output_path) as archive:
        assert "xl/workbook.xml" in archive.namelist()
        assert "xl/worksheets/sheet1.xml" in archive.namelist()


def test_cli_send_requires_manifest(capsys):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        ["reports", "send"],
        settings=settings,
        gateway=MemoryGateway(),
    )

    assert exit_code == 2
    assert "--manifest is required for send" in capsys.readouterr().err


def test_cli_run_weekly_requires_template(capsys):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        ["reports", "run-weekly", "--week-label", "Week23"],
        settings=settings,
        gateway=MemoryGateway(),
    )

    assert exit_code == 2
    assert "--template is required for run-weekly" in capsys.readouterr().err


def test_cli_run_weekly_requires_week_label(capsys):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        ["reports", "run-weekly", "--template", "weekly-template.xlsx"],
        settings=settings,
        gateway=MemoryGateway(),
    )

    assert exit_code == 2
    assert "--week-label is required for run-weekly" in capsys.readouterr().err


def test_cli_run_monthly_requires_month_label(capsys):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        ["reports", "run-monthly"],
        settings=settings,
        gateway=MemoryGateway(),
    )

    assert exit_code == 2
    assert "--month-label is required for run-monthly" in capsys.readouterr().err


def test_cli_run_weekly_writes_output_bundle(tmp_path, capsys):
    template_path = tmp_path / "weekly-template.xlsx"
    template_path.write_bytes(_minimal_weekly_template_bytes())
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
                    "Products": [{"Name": "NG3"}],
                    "CreateDate": "2026-06-02T00:00:00+00:00",
                    "ModifyDate": "2026-06-20T00:00:00+00:00",
                    "LastStateChangeDate": "2026-06-20T00:00:00+00:00",
                    "ReopenCount": 1,
                    "Tags": [{"Name": "customer feedback"}],
                }
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
            reopen_threshold=1,
            default_scope={"team": ["ESW China NG3 Driver"]},
        ),
    )
    output_dir = tmp_path / "outputs" / "reports" / "weekly" / "2026-06-05"

    exit_code = run_cli(
        [
            "reports",
            "run-weekly",
            "--week-label",
            "Week23",
            "--template",
            str(template_path),
            "--output-dir",
            str(output_dir),
        ],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    for name in [
        "healthcheck.json",
        "bug_master.json",
        "bug_master.csv",
        "quality-analysis-workbook.xlsx",
        "weekly-report-Week23.xlsx",
        "send-summary.md",
        "run-metadata.json",
    ]:
        assert (output_dir / name).exists(), name
    manifest = json.loads((output_dir / "run-metadata.json").read_text(encoding="utf-8"))
    assert manifest["workflow"] == "run-weekly"
    assert manifest["report_kind"] == "weekly"
    assert manifest["report_label"] == "Week23"
    assert "weekly-report-Week23.xlsx" in (output_dir / "send-summary.md").read_text(encoding="utf-8")


def test_cli_run_monthly_writes_output_bundle(tmp_path, capsys):
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
                }
            ]
        },
        history={
            "201": [{"Date": "2026-06-21T00:00:00+00:00", "Field": "EntityState", "OldValue": "New", "NewValue": "Fixed"}]
        },
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"], "closed": ["Done"]},
            high_risk_severities=["Critical"],
            stale_days=5,
            reopen_threshold=1,
            default_scope={"team": ["ESW China NG3 Driver"]},
        ),
    )
    output_dir = tmp_path / "outputs" / "reports" / "monthly" / "2026-06"

    exit_code = run_cli(
        [
            "reports",
            "run-monthly",
            "--month-label",
            "2026-06",
            "--output-dir",
            str(output_dir),
        ],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    for name in [
        "healthcheck.json",
        "bug_master.json",
        "bug_master.csv",
        "quality-analysis-workbook.xlsx",
        "monthly-audit-2026-06.xlsx",
        "send-summary.md",
        "run-metadata.json",
    ]:
        assert (output_dir / name).exists(), name
    manifest = json.loads((output_dir / "run-metadata.json").read_text(encoding="utf-8"))
    assert manifest["workflow"] == "run-monthly"
    assert manifest["report_kind"] == "monthly"
    assert manifest["report_label"] == "2026-06"
    assert "monthly-audit-2026-06.xlsx" in (output_dir / "send-summary.md").read_text(encoding="utf-8")


def test_cli_send_writes_summary_from_manifest(tmp_path, capsys):
    manifest_path = tmp_path / "run-metadata.json"
    summary_path = tmp_path / "send-summary.md"
    manifest_path.write_text(
        json.dumps(
            {
                "workflow": "run-weekly",
                "report_kind": "weekly",
                "report_label": "Week23",
                "generated_at": "2026-06-05T08:00:00+00:00",
                "warnings": ["partial_entities"],
                "report_summary": {
                    "week_label": "Week23",
                    "total_records": 10,
                    "weekly_new_records": 3,
                    "by_product": {
                        "NG3": {
                            "total_records": 4,
                            "weekly_new_records": 2,
                            "customer_feedback_records": 1,
                            "high_risk_records": 1,
                        }
                    },
                },
                "attachments": [
                    {"filename": "bug_master.csv"},
                    {"filename": "weekly-report-Week23.xlsx"},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )

    exit_code = run_cli(
        [
            "reports",
            "send",
            "--manifest",
            str(manifest_path),
            "--output",
            str(summary_path),
        ],
        settings=settings,
        gateway=MemoryGateway(),
    )

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    payload = summary_path.read_text(encoding="utf-8")
    assert "Week23" in payload
    assert "本次数据不完整" in payload
    assert "weekly-report-Week23.xlsx" in payload


def test_cli_risk_scan_writes_markdown_to_output_file(tmp_path, capsys):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Severity": {"Name": "Critical"},
                    "EntityState": {"Name": "Ready for QA"},
                    "Owner": {"FirstName": "QA", "LastName": "User"},
                    "Team": {"Name": "ESW UI Team"},
                    "Reproducibility": {"Name": "Always"},
                    "Products": [{"Name": "Watch A"}, {"Name": "Watch B"}],
                    "Firmwareversion": "FW-9.8.7",
                    "BugCategory": {"Name": "Regression"},
                    "Suuntoappplatform": "Android",
                    "Suuntoappversion": "2.0.1",
                    "Feature": [{"Id": 501}, {"Id": 502}],
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                }
            ]
        }
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"ready_for_qa": ["Ready for QA"]},
            high_risk_severities=["Critical"],
        ),
    )
    output_path = tmp_path / "exports" / "risk-scan.md"

    exit_code = run_cli(
        ["bugs", "risk-scan", "--format", "markdown", "--output", str(output_path)],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    payload = output_path.read_text(encoding="utf-8")
    assert "### `101` Crash on launch [ready_for_qa]" in payload


def _minimal_weekly_template_bytes() -> bytes:
    weekly_sheet = WorkbookSheet(
        name="固件质量数据概览-Week22",
        rows=[WorkbookRow(["模板"], kind="title")],
    )
    helper_sheet = WorkbookSheet(
        name="数据总览-NG3",
        rows=[WorkbookRow(["辅助"], kind="title")],
    )
    return _build_xlsx([weekly_sheet, helper_sheet], "2026-06-05T00:00:00+00:00")


def test_cli_review_export_writes_csv_to_output_file(tmp_path, capsys):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Crash on launch",
                    "EntityType": {"Name": "Bug"},
                    "Project": {"Name": "Suunto work"},
                    "Severity": {"Name": "Critical"},
                    "Priority": {"Name": "High"},
                    "EntityState": {"Name": "New"},
                    "Owner": None,
                    "Team": {"Name": "ESW China NG3 Driver"},
                    "Reproducibility": {"Name": "Always"},
                    "Products": [{"Name": "Watch A"}, {"Name": "Watch B"}],
                    "Firmwareversion": "FW-9.8.7",
                    "BugCategory": {"Name": "Regression"},
                    "Suuntoappplatform": "Android",
                    "Suuntoappversion": "2.0.1",
                    "Feature": [{"Id": 501}, {"Id": 502}],
                    "UserStory": [{"Id": 601}],
                    "LastStateChangeDate": "2026-06-02T00:00:00+00:00",
                    "CreateDate": "2026-06-01T00:00:00+00:00",
                    "ModifyDate": "2026-06-03T00:00:00+00:00",
                    "ReopenCount": 1,
                    "Tags": [{"Name": "customer feedback"}],
                }
            ]
        }
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(
            status_groups={"triage": ["New"]},
            high_risk_severities=["Critical"],
            stale_days=5,
            default_scope={"team": ["ESW China NG3 Driver"]},
        ),
    )
    output_path = tmp_path / "exports" / "review-export.csv"

    exit_code = run_cli(
        ["bugs", "review-export", "--format", "csv", "--output", str(output_path)],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    payload = output_path.read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(payload)))

    assert list(rows[0].keys())[: len(BUG_DATASET_FIELDNAMES)] == BUG_DATASET_FIELDNAMES
    assert rows[0]["created_at"] == "2026-06-01 00:00:00"
    assert rows[0]["updated_at"] == "2026-06-03 00:00:00"
    assert rows[0]["last_status_change_at"] == "2026-06-02 00:00:00"
    assert rows[0]["entered_new_at"] == "2026-06-01"
    assert rows[0]["quality_bucket"] == "customer_feedback"
    assert rows[0]["linked_user_story_ids"] == "601"


def test_cli_falls_back_when_stdout_encoding_cannot_encode_payload(monkeypatch):
    gateway = MemoryGateway(
        entities={
            "Bug": [
                {
                    "Id": 101,
                    "Name": "Price € bug",
                    "EntityType": {"Name": "Bug"},
                    "EntityState": {"Name": "New"},
                }
            ]
        }
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )
    stdout_buffer = io.BytesIO()
    stdout = io.TextIOWrapper(stdout_buffer, encoding="gbk")
    monkeypatch.setattr(sys, "stdout", stdout)

    exit_code = run_cli(
        ["entities", "list", "--entity", "Bug", "--format", "json"],
        settings=settings,
        gateway=gateway,
    )

    stdout.flush()
    rendered = stdout_buffer.getvalue().decode("gbk")
    assert exit_code == 0
    assert "Price ? bug" in rendered
