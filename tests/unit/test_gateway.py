from urllib.error import HTTPError, URLError

import pytest

from tp_codex.errors import AuthFailedError, ForbiddenError, QuerySchemaError, UpstreamOrTimeoutError
from tp_codex.gateway import HttpGateway
from tp_codex.settings import AuthSettings, Settings, WorkflowRulesSettings


def test_http_gateway_list_entities_reads_multiple_pages(monkeypatch):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        page_size=2,
        workflow_rules=WorkflowRulesSettings(),
    )
    gateway = HttpGateway(settings)
    payloads = {
        0: {"Items": [{"Id": 1}, {"Id": 2}], "TotalCount": 3},
        2: {"Items": [{"Id": 3}], "TotalCount": 3},
    }

    def fake_request_json(path, query=None):
        return payloads[query.get("skip", 0)]

    monkeypatch.setattr(gateway, "_request_json", fake_request_json)

    result = gateway.list_entities("Bug")

    assert [item["Id"] for item in result.items] == [1, 2, 3]
    assert result.total_count == 3
    assert result.pages_completed == 2
    assert result.partial is False


def test_http_gateway_list_entities_marks_partial_when_later_page_fails(monkeypatch):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        page_size=2,
        workflow_rules=WorkflowRulesSettings(),
    )
    gateway = HttpGateway(settings)
    calls = {"count": 0}

    def fake_request_json(path, query=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return {"Items": [{"Id": 1}, {"Id": 2}], "TotalCount": 4}
        raise UpstreamOrTimeoutError("page timeout")

    monkeypatch.setattr(gateway, "_request_json", fake_request_json)

    result = gateway.list_entities("Bug")

    assert [item["Id"] for item in result.items] == [1, 2]
    assert result.total_count == 4
    assert result.pages_completed == 1
    assert result.partial is True


def test_http_gateway_list_entities_reads_multiple_pages_without_total_count(monkeypatch):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        page_size=2,
        workflow_rules=WorkflowRulesSettings(),
    )
    gateway = HttpGateway(settings)
    payloads = {
        0: {"Items": [{"Id": 1}, {"Id": 2}]},
        2: {"Items": [{"Id": 3}]},
    }

    def fake_request_json(path, query=None):
        return payloads.get(query.get("skip", 0), {"Items": []})

    monkeypatch.setattr(gateway, "_request_json", fake_request_json)

    result = gateway.list_entities("Bug")

    assert [item["Id"] for item in result.items] == [1, 2, 3]
    assert result.total_count == 3
    assert result.pages_completed == 2
    assert result.partial is False


def test_http_gateway_request_json_maps_401_to_auth_failed(monkeypatch):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(),
    )
    gateway = HttpGateway(settings)

    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 401, "Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr("tp_codex.gateway.urlopen", fake_urlopen)

    with pytest.raises(AuthFailedError):
        gateway._request_json("/api/v1/Context")


def test_http_gateway_request_json_maps_403_to_forbidden(monkeypatch):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(),
    )
    gateway = HttpGateway(settings)

    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr("tp_codex.gateway.urlopen", fake_urlopen)

    with pytest.raises(ForbiddenError):
        gateway._request_json("/api/v1/Context")


def test_http_gateway_request_json_maps_other_http_errors_to_query_schema_error(monkeypatch):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(),
    )
    gateway = HttpGateway(settings)

    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 400, "Bad Request", hdrs=None, fp=None)

    monkeypatch.setattr("tp_codex.gateway.urlopen", fake_urlopen)

    with pytest.raises(QuerySchemaError):
        gateway._request_json("/api/v2/Bug", {"select": "{BadField}"})


def test_http_gateway_request_json_maps_transport_errors_to_upstream_or_timeout(monkeypatch):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(),
    )
    gateway = HttpGateway(settings)

    def fake_urlopen(request, timeout):
        raise URLError("timed out")

    monkeypatch.setattr("tp_codex.gateway.urlopen", fake_urlopen)

    with pytest.raises(UpstreamOrTimeoutError):
        gateway._request_json("/api/v1/Context")


def test_http_gateway_request_json_adds_format_json_for_v1_requests(monkeypatch):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(),
    )
    gateway = HttpGateway(settings)
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"status":"ok"}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setattr("tp_codex.gateway.urlopen", fake_urlopen)

    payload = gateway._request_json("/api/v1/Context")

    assert payload == {"status": "ok"}
    assert "format=json" in captured["url"]


def test_http_gateway_request_json_does_not_add_format_json_for_v2_requests(monkeypatch):
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(),
    )
    gateway = HttpGateway(settings)
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"Items":[],"TotalCount":0}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setattr("tp_codex.gateway.urlopen", fake_urlopen)

    payload = gateway._request_json("/api/v2/Bug", {"take": 1, "skip": 0})

    assert payload == {"Items": [], "TotalCount": 0}
    assert "format=json" not in captured["url"]
