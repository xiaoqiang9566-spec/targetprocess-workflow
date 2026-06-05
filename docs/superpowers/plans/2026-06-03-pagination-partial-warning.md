# Pagination And Partial Warning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure entity workflows can read multiple Targetprocess result pages and surface partial-result warnings when full retrieval is not possible.

**Architecture:** Extend `HttpGateway.list_entities()` to iterate pages using the existing `QueryResult` structure instead of changing higher layers first. Propagate the gateway's `partial` flag into workflow warnings so read-only QA commands stay honest about incomplete data.

**Tech Stack:** Python 3.9+, pytest, stdlib `urllib`

---

### Task 1: Lock Pagination Behavior With Tests

**Files:**
- Create: `tests/unit/test_gateway.py`
- Modify: `tests/integration/test_workflows.py`

- [ ] **Step 1: Write the failing test**

```python
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
    payloads = [
        {"Items": [{"Id": 1}, {"Id": 2}], "TotalCount": 3},
        {"Items": [{"Id": 3}], "TotalCount": 3},
    ]

    def fake_request_json(path, query=None):
        skip = query.get("skip", 0)
        return payloads[skip // 2]

    monkeypatch.setattr(gateway, "_request_json", fake_request_json)

    result = gateway.list_entities("Bug")

    assert [item["Id"] for item in result.items] == [1, 2, 3]
    assert result.total_count == 3
    assert result.pages_completed == 2
    assert result.partial is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_gateway.py::test_http_gateway_list_entities_reads_multiple_pages -v`
Expected: `FAIL` because only the first page is returned and `pages_completed` stays at `1`.

- [ ] **Step 3: Write minimal implementation**

```python
def list_entities(self, entity: str, filters: Optional[dict] = None, limit: Optional[int] = None) -> QueryResult:
    filters = filters or {}
    take = limit or self.settings.page_size
    items = []
    skip = 0
    total = 0
    pages_completed = 0

    while True:
        query = {"take": take, "skip": skip}
        query.update(filters)
        payload = self._request_json(f"{self.api_path_v2}/{entity}", query)
        page_items = payload.get("Items") or payload.get("items") or []
        total = payload.get("TotalCount") or payload.get("totalCount") or len(page_items)
        items.extend(page_items)
        pages_completed += 1
        skip += len(page_items)
        if not page_items or len(items) >= total or (limit is not None and len(items) >= limit):
            break

    if limit is not None:
        items = items[:limit]
    return QueryResult(items=items, total_count=total, pages_completed=pages_completed)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_gateway.py::test_http_gateway_list_entities_reads_multiple_pages -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_gateway.py src/tp_codex/gateway.py
git commit -m "test: cover paginated entity retrieval"
```

### Task 2: Surface Partial Warnings In Workflows

**Files:**
- Modify: `tests/unit/test_gateway.py`
- Modify: `tests/integration/test_workflows.py`
- Modify: `src/tp_codex/service.py`

- [ ] **Step 1: Write the failing test**

```python
def test_http_gateway_list_entities_marks_partial_when_page_fetch_stops(monkeypatch):
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
        raise RuntimeError("page timeout")

    monkeypatch.setattr(gateway, "_request_json", fake_request_json)

    result = gateway.list_entities("Bug")

    assert [item["Id"] for item in result.items] == [1, 2]
    assert result.total_count == 4
    assert result.pages_completed == 1
    assert result.partial is True
```

```python
def test_triage_view_includes_entity_partial_warning():
    gateway = MemoryGateway(
        entities={"Bug": [{"Id": 7, "Name": "Login bug", "EntityState": {"Name": "New"}}]}
    )
    gateway.list_entities = lambda entity, filters=None, limit=None: QueryResult(
        items=gateway.entities["Bug"],
        total_count=5,
        pages_completed=1,
        partial=True,
    )
    settings = Settings(
        base_url="https://example.tpondemand.com",
        auth=AuthSettings(mode="access_token", secret="token"),
        workflow_rules=WorkflowRulesSettings(status_groups={"triage": ["New"]}),
    )
    service = TargetprocessService(settings=settings, gateway=gateway)

    result = service.run_workflow("triage-view", entity="Bug")

    assert "partial_entities" in result.warnings
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_gateway.py tests/integration/test_workflows.py -k partial -v`
Expected: `FAIL` because the gateway currently raises on later-page failure and the service ignores `QueryResult.partial`.

- [ ] **Step 3: Write minimal implementation**

```python
warnings: list[str] = []
if query.partial:
    warnings.append("partial_entities")
```

```python
        try:
            payload = self._request_json(f"{self.api_path_v2}/{entity}", query)
        except UpstreamOrTimeoutError:
            return QueryResult(
                items=items[:limit] if limit is not None else items,
                total_count=total or len(items),
                pages_completed=pages_completed,
                partial=True,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_gateway.py tests/integration/test_workflows.py -k partial -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_gateway.py tests/integration/test_workflows.py src/tp_codex/service.py src/tp_codex/gateway.py
git commit -m "feat: expose partial entity warnings"
```

### Task 3: Full Verification

**Files:**
- Test: `tests/unit/test_gateway.py`
- Test: `tests/integration/test_workflows.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/unit/test_rules.py`
- Test: `tests/unit/test_settings.py`

- [ ] **Step 1: Run the focused regression set**

Run: `pytest tests/unit/test_gateway.py tests/integration/test_workflows.py -v`
Expected: `PASS`

- [ ] **Step 2: Run the full non-live suite**

Run: `pytest -m "not live"`
Expected: `PASS` with all non-live tests green.

- [ ] **Step 3: Review scope**

Confirm the change only affects read-only list retrieval and warning propagation, without adding any create/update/transition behavior.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-06-03-pagination-partial-warning.md
git commit -m "docs: add pagination warning implementation plan"
```
