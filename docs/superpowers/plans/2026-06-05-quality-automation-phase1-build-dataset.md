# Targetprocess Quality Automation Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-ready `reports build-dataset` workflow so the project can generate a standardized `bug_master` dataset from the existing read-only Targetprocess bug scope.

**Architecture:** Keep the existing read-only CLI and workflow service as the entrypoint, then add one reporting workflow that reuses `review-export` scope rules and enriches each normalized bug with reporting-specific derived fields. Keep spreadsheet generation and weekly/monthly workbook shaping out of this phase so later phases can consume a stable dataset contract instead of re-querying Targetprocess.

**Tech Stack:** Python 3.9+, pytest, stdlib `datetime`, existing `tp_codex` CLI/service/gateway stack

---

## Phase Roadmap

This implementation sequence follows the approved design and keeps the scope decomposed into testable phases:

1. `build-dataset`
2. `build-workbook`
3. `weekly-report`
4. `monthly-audit`
5. `send`
6. `run-weekly` / `run-monthly`

This plan executes **Phase 1** only.

### Task 1: Lock The Dataset Contract With Failing Tests

**Files:**
- Create: `D:\3681\Documents\Targetprocess\tests\unit\test_datasets.py`
- Modify: `D:\3681\Documents\Targetprocess\tests\unit\test_cli.py`
- Modify: `D:\3681\Documents\Targetprocess\tests\integration\test_workflows.py`

- [ ] **Step 1: Write the failing parser test**

```python
def test_build_parser_includes_reports_build_dataset_command():
    parser = build_parser()

    args = parser.parse_args(["reports", "build-dataset", "--format", "csv"])

    assert args.command == "reports"
    assert args.reports_command == "build-dataset"
    assert args.format == "csv"
```

- [ ] **Step 2: Write the failing dataset derivation test**

```python
from datetime import datetime, timezone

from tp_codex.datasets import BUG_DATASET_FIELDNAMES, build_bug_dataset_records
from tp_codex.settings import WorkflowRulesSettings


def test_build_bug_dataset_records_derives_reporting_fields():
    records = [
        {
            "bug_id": 101,
            "name": "Crash on launch",
            "team": "ESW China NG3 Driver",
            "owner": None,
            "severity": "Critical",
            "status_raw": "New",
            "status_group": "triage",
            "created_at": "2026-05-26T00:00:00+00:00",
            "updated_at": "2026-06-03T00:00:00+00:00",
            "last_status_change_at": "2026-06-02T00:00:00+00:00",
            "reopen_count": 3,
            "risk_signals": [{"code": "high_severity", "message": "Bug severity is in the high-risk list"}],
            "data_gaps": ["owner"],
            "raw": {"Tags": [{"Name": "customer feedback"}]},
        }
    ]
    rules = WorkflowRulesSettings(
        high_risk_severities=["Critical"],
        stale_days=5,
        reopen_threshold=2,
        default_scope={"team": ["ESW China NG3 Driver", "ESW China NG3 Framework", "ESW UI Team"]},
    )

    dataset = build_bug_dataset_records(
        records,
        workflow_rules=rules,
        now=datetime(2026, 6, 5, tzinfo=timezone.utc),
    )

    record = dataset[0]
    assert BUG_DATASET_FIELDNAMES[0] == "bug_id"
    assert record["created_week"] == "2026-W22"
    assert record["updated_month"] == "2026-06"
    assert record["age_days"] == 10
    assert record["stale_days"] == 2
    assert record["is_open"] is True
    assert record["is_closed"] is False
    assert record["is_customer_feedback"] is True
    assert record["is_high_risk"] is True
    assert record["is_reopened"] is True
    assert record["owner_missing"] is True
    assert record["aging_bucket"] == "8-14"
    assert record["risk_level"] == "high"
    assert record["quality_bucket"] == "customer_feedback"
    assert record["audit_focus"] == "owner_missing"
    assert record["team_scope_label"] == "default_scope_team"
```

- [ ] **Step 3: Write the failing workflow integration test**

```python
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
    assert "ReopenCount" in captured["filters"]["select"]
    assert "Tags" in captured["filters"]["select"]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/unit/test_cli.py tests/unit/test_datasets.py tests/integration/test_workflows.py -k "build_dataset or test_build_bug_dataset_records_derives_reporting_fields" -v`
Expected: `FAIL` because the `reports build-dataset` parser, dataset module, and service workflow do not exist yet.

- [ ] **Step 5: Record the current git limitation**

Run: `git rev-parse --show-toplevel`
Expected: `fatal: not a git repository (or any of the parent directories): .git`

### Task 2: Implement Dataset Derivation And Workflow Dispatch

**Files:**
- Create: `D:\3681\Documents\Targetprocess\src\tp_codex\datasets.py`
- Modify: `D:\3681\Documents\Targetprocess\src\tp_codex\cli.py`
- Modify: `D:\3681\Documents\Targetprocess\src\tp_codex\service.py`
- Modify: `D:\3681\Documents\Targetprocess\src\tp_codex\__init__.py`

- [ ] **Step 1: Write the minimal dataset module**

```python
BUG_DATASET_FIELDNAMES = [
    "bug_id",
    "name",
    "project",
    "team",
    "owner",
    "severity",
    "priority",
    "status_raw",
    "status_group",
    "created_at",
    "updated_at",
    "last_status_change_at",
    "created_date",
    "updated_date",
    "last_status_change_date",
    "created_week",
    "updated_week",
    "created_month",
    "updated_month",
    "age_days",
    "stale_days",
    "is_open",
    "is_closed",
    "is_customer_feedback",
    "is_high_risk",
    "is_reopened",
    "owner_missing",
    "aging_bucket",
    "risk_level",
    "quality_bucket",
    "audit_focus",
    "team_scope_label",
    "reopen_count",
    "products",
    "suunto_app_version",
    "suunto_app_platform",
    "firmware_version",
    "reproducibility",
    "bug_category",
    "linked_feature_ids",
    "linked_user_story_ids",
    "risk_signals",
    "data_gaps",
]
```

```python
def build_bug_dataset_records(records, workflow_rules, now):
    ...
    return dataset_records
```

The implementation must derive:
- ISO week labels such as `2026-W22`
- month labels such as `2026-06`
- `age_days` and `stale_days`
- `is_open` / `is_closed`
- `is_customer_feedback`
- `is_high_risk`
- `is_reopened`
- `owner_missing`
- `aging_bucket`
- `risk_level`
- `quality_bucket`
- `audit_focus`
- `team_scope_label`

- [ ] **Step 2: Extend the CLI parser with a `reports build-dataset` command**

```python
reports = subparsers.add_parser("reports")
reports_sub = reports.add_subparsers(dest="reports_command")
build_dataset = reports_sub.add_parser("build-dataset", parents=[common])
build_dataset.add_argument("--entity", default="Bug")
build_dataset.add_argument("--limit", type=int)
```

- [ ] **Step 3: Dispatch the new workflow in `run_cli()`**

```python
elif args.command == "reports" and args.reports_command == "build-dataset":
    result = service.run_workflow("build-dataset", entity=args.entity, limit=args.limit)
```

- [ ] **Step 4: Add the workflow implementation in `TargetprocessService`**

```python
if workflow == "build-dataset":
    return self._build_dataset(entity, filters, limit)
```

```python
def _build_dataset(self, entity: str, filters: Optional[dict], limit: Optional[int]) -> WorkflowResult:
    dataset_filters = self._merge_default_bug_filters(
        {
            "select": self._format_select(
                [
                    "Id",
                    "Name",
                    "EntityType",
                    "Project",
                    "Team",
                    "Owner",
                    "Severity",
                    "Priority",
                    "EntityState",
                    "CreateDate",
                    "ModifyDate",
                    "LastStateChangeDate",
                    "Suuntoappversion",
                    "Suuntoappplatform",
                    "Products",
                    "Firmwareversion",
                    "Reproducibility",
                    "BugCategory",
                    "Feature",
                    "UserStory",
                    "ReopenCount",
                    "Tags",
                ]
            )
        }
    )
    query = list_entities(self.gateway, entity, filters=dataset_filters, limit=limit)
    base_records = [self.rules.enrich_record(normalize_bug(item, self.settings.base_url)) for item in query.items]
    dataset_records = build_bug_dataset_records(base_records, self.settings.workflow_rules, datetime.now(timezone.utc))
    ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_cli.py tests/unit/test_datasets.py tests/integration/test_workflows.py -k "build_dataset or test_build_bug_dataset_records_derives_reporting_fields" -v`
Expected: `PASS`

### Task 3: Lock CSV Output For `bug_master`

**Files:**
- Modify: `D:\3681\Documents\Targetprocess\tests\unit\test_cli.py`
- Modify: `D:\3681\Documents\Targetprocess\src\tp_codex\renderers.py`
- Modify: `D:\3681\Documents\Targetprocess\src\tp_codex\service.py`

- [ ] **Step 1: Write the failing CSV output test**

```python
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

    exit_code = run_cli(
        ["reports", "build-dataset", "--format", "csv"],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    payload = capsys.readouterr().out
    assert "created_week" in payload
    assert "is_customer_feedback" in payload
    assert "quality_bucket" in payload
    assert "default_scope_team" in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_cli.py::test_cli_build_dataset_outputs_csv_with_reporting_columns -v`
Expected: `FAIL` because `render_csv()` still emits the older fixed workflow field list.

- [ ] **Step 3: Write minimal implementation**

```python
def render_csv(result: WorkflowResult) -> str:
    fieldnames = result.metadata.get("csv_fieldnames") or DEFAULT_REVIEW_EXPORT_FIELDNAMES
    ...
```

```python
metadata = self._metadata(entity, dataset_filters or {})
metadata["csv_fieldnames"] = BUG_DATASET_FIELDNAMES
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_cli.py::test_cli_build_dataset_outputs_csv_with_reporting_columns -v`
Expected: `PASS`

### Task 4: Verify Phase 1 End-To-End

**Files:**
- Test: `D:\3681\Documents\Targetprocess\tests\unit\test_cli.py`
- Test: `D:\3681\Documents\Targetprocess\tests\unit\test_datasets.py`
- Test: `D:\3681\Documents\Targetprocess\tests\integration\test_workflows.py`
- Test: `D:\3681\Documents\Targetprocess\tests\unit\test_renderers.py`

- [ ] **Step 1: Run the focused regression set**

Run: `pytest tests/unit/test_cli.py tests/unit/test_datasets.py tests/integration/test_workflows.py tests/unit/test_renderers.py -k "build_dataset or dataset" -v`
Expected: `PASS`

- [ ] **Step 2: Run the full non-live suite**

Run: `pytest -m "not live"`
Expected: `PASS`

- [ ] **Step 3: Review scope before moving to Phase 2**

Confirm this phase only adds:
- the `reports build-dataset` entrypoint
- dataset derivation logic
- dataset CSV export behavior

Confirm it does **not** yet add:
- workbook generation
- weekly report shaping
- monthly audit shaping
- any write-back behavior to Targetprocess

- [ ] **Step 4: Record the no-commit limitation**

Run: `git rev-parse --show-toplevel`
Expected: `fatal: not a git repository (or any of the parent directories): .git`
