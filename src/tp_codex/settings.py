from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import yaml

from tp_codex.auth import select_auth
from tp_codex.errors import ConfigError


@dataclass(frozen=True)
class AuthSettings:
    mode: str
    secret: str


@dataclass(frozen=True)
class WorkflowRulesSettings:
    status_groups: Dict[str, List[str]] = field(default_factory=dict)
    high_risk_severities: List[str] = field(default_factory=list)
    stale_days: int = 7
    reopen_threshold: int = 1
    default_scope: Dict[str, List[str]] = field(default_factory=dict)
    default_select: List[str] = field(default_factory=list)
    weekly_report: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    base_url: str
    auth: AuthSettings
    timeout_sec: int = 30
    page_size: int = 1000
    live_tests_enabled: bool = False
    workflow_rules: WorkflowRulesSettings = field(default_factory=WorkflowRulesSettings)


def _load_yaml(path: Optional[Path]) -> Dict[str, object]:
    if not path:
        return {}
    if not path.exists():
        raise ConfigError(f"configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"configuration file must contain an object: {path}")
    return data


def _validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError("TP_BASE_URL must be a valid http(s) URL")
    return base_url.rstrip("/")


def load_settings(
    config_path: Optional[Path] = None,
    workflow_rules_path: Optional[Path] = None,
) -> Settings:
    config = _load_yaml(config_path)
    workflow_rules_raw = _load_yaml(workflow_rules_path)

    base_url = os.getenv("TP_BASE_URL", config.get("base_url", ""))
    mode = os.getenv("TP_AUTH_MODE", str(config.get("auth_mode", "auto")))
    access_token = os.getenv("TP_ACCESS_TOKEN", str(config.get("access_token", "")))
    service_token = os.getenv("TP_SERVICE_TOKEN", str(config.get("service_token", "")))
    username = os.getenv("TP_USERNAME", str(config.get("username", "")))
    password = os.getenv("TP_PASSWORD", str(config.get("password", "")))
    timeout_sec = int(os.getenv("TP_TIMEOUT_SEC", str(config.get("timeout_sec", 30))))
    page_size = int(os.getenv("TP_PAGE_SIZE", str(config.get("page_size", 1000))))
    live_tests_enabled = os.getenv("TP_RUN_LIVE_TESTS", str(config.get("run_live_tests", "0"))) == "1"

    if not base_url:
        raise ConfigError("TP_BASE_URL is required")
    selected_mode, secret = select_auth(mode, access_token, service_token, username, password)
    rules = WorkflowRulesSettings(
        status_groups={
            str(key): [str(item) for item in value]
            for key, value in dict(workflow_rules_raw.get("status_groups", {})).items()
        },
        high_risk_severities=[str(item) for item in workflow_rules_raw.get("high_risk_severities", [])],
        stale_days=int(workflow_rules_raw.get("stale_days", 7)),
        reopen_threshold=int(workflow_rules_raw.get("reopen_threshold", 1)),
        default_scope={
            str(key): [str(item) for item in value]
            for key, value in dict(workflow_rules_raw.get("default_scope", {})).items()
        },
        default_select=[str(item) for item in workflow_rules_raw.get("default_select", [])],
        weekly_report=dict(workflow_rules_raw.get("weekly_report", {}) or {}),
    )
    return Settings(
        base_url=_validate_base_url(base_url),
        auth=AuthSettings(mode=selected_mode, secret=secret),
        timeout_sec=timeout_sec,
        page_size=page_size,
        live_tests_enabled=live_tests_enabled,
        workflow_rules=rules,
    )
