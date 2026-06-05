import json
import os

import pytest

from tp_codex.cli import run_cli


def _require_live_enabled():
    if os.getenv("TP_RUN_LIVE_TESTS") != "1":
        pytest.skip("live tests require TP_RUN_LIVE_TESTS=1")


def _require_bug_id():
    bug_id = os.getenv("TP_LIVE_BUG_ID")
    if not bug_id:
        pytest.skip("live bug history test requires TP_LIVE_BUG_ID")
    return bug_id


def _require_records_if_configured(payload):
    if os.getenv("TP_LIVE_REQUIRE_RECORDS") == "1":
        assert payload["summary"]["total_records"] > 0


def _run_live_cli_json(capsys, argv):
    exit_code = run_cli(argv)

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert isinstance(payload, dict)
    return payload


def _assert_scoped_team(record):
    assert record["team"] in {
        "ESW China NG3 Driver",
        "ESW China NG3 Framework",
        "ESW UI Team",
    }


@pytest.mark.live
def test_live_healthcheck_outputs_real_context(capsys):
    _require_live_enabled()

    payload = _run_live_cli_json(capsys, ["healthcheck", "--format", "json"])
    assert payload["workflow"] == "healthcheck"
    assert payload["summary"]["total_records"] == 1
    assert isinstance(payload["records"][0], dict)
    assert "workflow_rules" in payload["records"][0]


@pytest.mark.live
def test_live_bug_schema_snapshot_succeeds(capsys):
    _require_live_enabled()

    payload = _run_live_cli_json(capsys, ["schema", "snapshot", "--entity", "Bug", "--format", "json"])
    assert payload["workflow"] == "schema-snapshot"
    assert payload["metadata"]["entity"] == "Bug"
    assert payload["summary"]["total_records"] == 1
    assert isinstance(payload["records"][0], dict)


@pytest.mark.live
def test_live_bug_entities_list_returns_payload(capsys):
    _require_live_enabled()

    payload = _run_live_cli_json(capsys, ["entities", "list", "--entity", "Bug", "--limit", "5", "--format", "json"])
    assert payload["workflow"] == "entities-list"
    assert payload["metadata"]["entity"] == "Bug"
    assert payload["summary"]["source_total_records"] >= payload["summary"]["total_records"]
    assert isinstance(payload["records"], list)
    _require_records_if_configured(payload)
    if payload["records"]:
        first = payload["records"][0]
        assert first["bug_id"] is not None
        assert "name" in first
        assert "status_group" in first
        assert isinstance(first["raw"], dict)


@pytest.mark.live
def test_live_bug_history_returns_records(capsys):
    _require_live_enabled()
    bug_id = _require_bug_id()

    payload = _run_live_cli_json(capsys, ["bugs", "history", "--bug-id", bug_id, "--format", "json"])
    assert payload["workflow"] == "bug-history"
    assert payload["metadata"]["filters"]["bug_id"] == bug_id
    assert isinstance(payload["records"], list)
    if payload["records"]:
        first = payload["records"][0]
        assert "event_type" in first
        assert "changed_at" in first
        assert "field" in first
        assert "from" in first
        assert "to" in first


@pytest.mark.live
def test_live_intake_workflow_returns_real_records_or_empty_result(capsys):
    _require_live_enabled()

    payload = _run_live_cli_json(capsys, ["bugs", "intake", "--limit", "5", "--format", "json"])
    assert payload["workflow"] == "intake"
    assert payload["metadata"]["entity"] == "Bug"
    assert "source_total_records" in payload["summary"]
    assert isinstance(payload["records"], list)
    _require_records_if_configured(payload)
    if payload["records"]:
        first = payload["records"][0]
        assert first["bug_id"] is not None
        assert "name" in first
        assert "status_group" in first
        assert isinstance(first["risk_signals"], list)


@pytest.mark.live
def test_live_intake_reads_multiple_pages_when_page_size_is_small(capsys, monkeypatch):
    _require_live_enabled()
    monkeypatch.setenv("TP_PAGE_SIZE", "10")

    payload = _run_live_cli_json(capsys, ["bugs", "intake", "--limit", "25", "--format", "json"])

    assert payload["workflow"] == "intake"
    assert payload["summary"]["total_records"] == 25
    assert payload["summary"]["source_total_records"] >= 25
    assert payload["warnings"] == []
    assert len(payload["records"]) == 25
    for record in payload["records"]:
        _assert_scoped_team(record)


@pytest.mark.live
def test_live_triage_view_defaults_history_mode_to_off(capsys):
    _require_live_enabled()

    payload = _run_live_cli_json(capsys, ["bugs", "triage-view", "--limit", "5", "--format", "json"])

    assert payload["workflow"] == "triage-view"
    assert payload["metadata"]["entity"] == "Bug"
    assert isinstance(payload["records"], list)
    _require_records_if_configured(payload)
    for record in payload["records"]:
        assert "history" not in record


@pytest.mark.live
def test_live_triage_view_full_history_mode_returns_history_when_records_exist(capsys):
    _require_live_enabled()

    payload = _run_live_cli_json(
        capsys,
        ["bugs", "triage-view", "--history-mode", "full", "--limit", "5", "--format", "json"],
    )

    assert payload["workflow"] == "triage-view"
    assert payload["metadata"]["entity"] == "Bug"
    assert isinstance(payload["records"], list)
    _require_records_if_configured(payload)
    for record in payload["records"]:
        assert "history" in record
        assert isinstance(record["history"], list)
