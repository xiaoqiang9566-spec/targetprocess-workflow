from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from tp_codex.errors import ConfigError


@dataclass(frozen=True)
class AuthSelection:
    mode: str
    headers: Dict[str, str]
    query_params: Dict[str, str]


def select_auth(mode: str, access_token: str, service_token: str, username: str, password: str) -> Tuple[str, str]:
    if mode == "auto":
        if access_token:
            return "access_token", access_token
        if service_token:
            return "service_token", service_token
        if username and password:
            return "basic", f"{username}:{password}"
        raise ConfigError("no Targetprocess credentials configured")
    if mode == "access_token" and access_token:
        return "access_token", access_token
    if mode == "service_token" and service_token:
        return "service_token", service_token
    if mode == "basic" and username and password:
        return "basic", f"{username}:{password}"
    raise ConfigError(f"missing credentials for auth mode '{mode}'")


def build_auth(mode: str, secret: str) -> AuthSelection:
    if mode == "access_token":
        return AuthSelection(mode=mode, headers={}, query_params={"access_token": secret})
    if mode == "service_token":
        return AuthSelection(mode=mode, headers={}, query_params={"token": secret})
    if mode == "basic":
        import base64

        encoded = base64.b64encode(secret.encode("utf-8")).decode("ascii")
        return AuthSelection(mode=mode, headers={"Authorization": f"Basic {encoded}"}, query_params={})
    raise ConfigError(f"unsupported auth mode '{mode}'")
