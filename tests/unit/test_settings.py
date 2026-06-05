import os

import pytest

from tp_codex.errors import ConfigError
from tp_codex.settings import load_settings


def test_load_settings_requires_base_url_and_credentials(monkeypatch):
    monkeypatch.delenv("TP_BASE_URL", raising=False)
    monkeypatch.delenv("TP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TP_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("TP_USERNAME", raising=False)
    monkeypatch.delenv("TP_PASSWORD", raising=False)

    with pytest.raises(ConfigError) as exc:
        load_settings()

    assert exc.value.exit_code == 8


def test_load_settings_prefers_access_token_in_auto_mode(monkeypatch):
    monkeypatch.setenv("TP_BASE_URL", "https://example.tpondemand.com")
    monkeypatch.setenv("TP_ACCESS_TOKEN", "access-token")
    monkeypatch.setenv("TP_SERVICE_TOKEN", "service-token")
    monkeypatch.setenv("TP_AUTH_MODE", "auto")

    settings = load_settings()

    assert settings.auth.mode == "access_token"
    assert settings.auth.secret == "access-token"
    assert settings.page_size == 1000
    assert settings.live_tests_enabled is False


def test_load_settings_reads_yaml_rules(tmp_path, monkeypatch):
    rules_path = tmp_path / "workflow_rules.yaml"
    rules_path.write_text(
        """
status_groups:
  ready_for_qa: [Ready for QA]
high_risk_severities: [Critical]
stale_days: 3
reopen_threshold: 2
default_select:
  - Id
  - Team
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("TP_BASE_URL", "https://example.tpondemand.com")
    monkeypatch.setenv("TP_ACCESS_TOKEN", "access-token")

    settings = load_settings(workflow_rules_path=rules_path)

    assert settings.workflow_rules.status_groups["ready_for_qa"] == ["Ready for QA"]
    assert settings.workflow_rules.high_risk_severities == ["Critical"]
    assert settings.workflow_rules.stale_days == 3
    assert settings.workflow_rules.default_select == ["Id", "Team"]
