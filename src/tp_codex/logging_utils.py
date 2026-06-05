from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_KEYS = {"token", "access_token", "password", "authorization"}


def redact_value(value: str) -> str:
    if not value:
        return value
    if len(value) <= 6:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def sanitize_mapping(payload: dict) -> dict:
    sanitized = {}
    for key, value in payload.items():
        if key.lower() in SENSITIVE_KEYS and isinstance(value, str):
            sanitized[key] = redact_value(value)
        else:
            sanitized[key] = value
    return sanitized


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append((key, redact_value(value) if key.lower() in SENSITIVE_KEYS else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
