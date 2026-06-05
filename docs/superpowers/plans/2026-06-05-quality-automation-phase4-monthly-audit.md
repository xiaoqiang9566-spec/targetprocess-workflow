# Monthly Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `reports monthly-audit`，基于统一的 `bug_master` 数据集输出月度质量审计摘要和 `.xlsx` 月审工作簿。

**Architecture:** 复用现有 `build-dataset` 作为唯一数据主干，在 service 层新增 `monthly-audit` workflow，并将月审统计、候选异常集筛选、候选 history 补拉和工作簿产物封装到独立模块。月审 workbook 不依赖外部模板，直接使用现有最小 OOXML 写入器输出固定 sheet 集合。

**Tech Stack:** Python 3.9、现有 `tp_codex` CLI/service/gateway/history、最小 OOXML `.xlsx` 生成器。

---

## Files

- Create: `src/tp_codex/monthly_audits.py`
- Modify: `src/tp_codex/cli.py`
- Modify: `src/tp_codex/service.py`
- Modify: `src/tp_codex/__init__.py`
- Modify: `tests/unit/test_cli.py`
- Modify: `tests/integration/test_workflows.py`
- Modify: `docs/superpowers/plans/2026-06-05-quality-automation-phase4-monthly-audit.md`

## Task 1: 定义月审命令契约

**Files:**
- Modify: `tests/unit/test_cli.py`
- Modify: `src/tp_codex/cli.py`

- [ ] **Step 1: 写失败测试，锁定 `reports monthly-audit` parser 和 xlsx 参数约束**

```python
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
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m pytest tests/unit/test_cli.py -k "monthly_audit" -v
```

Expected:

- `monthly-audit` parser 相关测试失败
- 报错显示 `invalid choice: 'monthly-audit'`

- [ ] **Step 3: 最小实现 CLI parser 与参数校验**

```python
monthly_audit = reports_sub.add_parser("monthly-audit")
monthly_audit.add_argument("--entity", default="Bug")
monthly_audit.add_argument("--limit", type=int)
monthly_audit.add_argument("--month-label")
monthly_audit.add_argument("--format", choices=["json", "xlsx"], default="xlsx")
monthly_audit.add_argument("--output")
```

```python
elif args.command == "reports" and args.reports_command == "monthly-audit":
    result = service.run_workflow(
        "monthly-audit",
        entity=args.entity,
        limit=args.limit,
        filters={"month_label": args.month_label},
    )
```

```python
if args.command == "reports" and args.reports_command == "monthly-audit" and output_format == "xlsx":
    if not args.month_label:
        raise InvalidArgsError("--month-label is required for monthly-audit")
```

- [ ] **Step 4: 重跑测试并确认通过**

Run:

```powershell
python -m pytest tests/unit/test_cli.py -k "monthly_audit" -v
```

Expected:

- `PASS`

## Task 2: 锁定月审 workflow 的摘要输出与候选异常集

**Files:**
- Modify: `tests/integration/test_workflows.py`
- Modify: `src/tp_codex/service.py`
- Create: `src/tp_codex/monthly_audits.py`

- [ ] **Step 1: 写失败测试，锁定月审 summary 和候选异常规则**

```python
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
            ]
        },
        history={
            "201": [{"Date": "2026-06-21T00:00:00+00:00"}],
            "202": [{"Date": "2026-06-18T00:00:00+00:00"}],
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

    assert result.workflow == "monthly-audit"
    assert result.summary["month_label"] == "2026-06"
    assert result.summary["created_count"] == 1
    assert result.summary["candidate_risk_records"] == 2
    assert any(record["bug_id"] == 201 for record in result.records)
    assert any(record["bug_id"] == 202 for record in result.records)
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m pytest tests/integration/test_workflows.py -k "monthly_audit_workflow" -v
```

Expected:

- `unsupported workflow 'monthly-audit'`

- [ ] **Step 3: 最小实现月审 summary、候选集筛选和 history 补拉**

```python
if workflow == "monthly-audit":
    return self._monthly_audit(entity, filters, limit)
```

```python
summary = build_monthly_audit_summary(
    dataset_result.records,
    month_label=month_label,
    workflow_rules=self.settings.workflow_rules,
)
candidates, partial_history = build_monthly_audit_candidates(
    dataset_result.records,
    month_label=month_label,
    workflow_rules=self.settings.workflow_rules,
    history_loader=lambda bug_id: get_bug_history(self.gateway, str(bug_id)),
)
```

```python
return WorkflowResult(
    workflow="monthly-audit",
    metadata=metadata,
    records=candidates,
    signals=dataset_result.signals,
    summary=summary,
    warnings=warnings,
    artifacts=[],
)
```

- [ ] **Step 4: 重跑测试并确认通过**

Run:

```powershell
python -m pytest tests/integration/test_workflows.py -k "monthly_audit_workflow" -v
```

Expected:

- `PASS`

## Task 3: 锁定月审工作簿结构

**Files:**
- Modify: `tests/integration/test_workflows.py`
- Create: `src/tp_codex/monthly_audits.py`
- Modify: `src/tp_codex/service.py`

- [ ] **Step 1: 写失败测试，锁定月审 workbook 的 sheet 集合**

```python
def test_monthly_audit_workflow_generates_expected_workbook_sheets():
    result = service.run_workflow("monthly-audit", entity="Bug", filters={"month_label": "2026-06"})

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
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m pytest tests/integration/test_workflows.py -k "expected_workbook_sheets" -v
```

Expected:

- `artifacts` 为空或 sheet 断言失败

- [ ] **Step 3: 最小实现月审 workbook 生成**

```python
artifact = build_monthly_audit_workbook_artifact(
    dataset_result.records,
    candidates,
    summary,
    month_label=month_label,
    warnings=warnings,
)
```

```python
return WorkflowResult(
    workflow="monthly-audit",
    metadata=metadata,
    records=candidates,
    signals=dataset_result.signals,
    summary=summary,
    warnings=warnings,
    artifacts=[artifact],
)
```

- [ ] **Step 4: 重跑测试并确认通过**

Run:

```powershell
python -m pytest tests/integration/test_workflows.py -k "expected_workbook_sheets" -v
```

Expected:

- `PASS`

## Task 4: 跑通 CLI 的 xlsx 输出链路

**Files:**
- Modify: `tests/unit/test_cli.py`
- Modify: `src/tp_codex/cli.py`

- [ ] **Step 1: 写失败测试，锁定 `monthly-audit --output` 能落盘 workbook**

```python
def test_cli_monthly_audit_writes_xlsx_to_output_file(tmp_path, capsys):
    gateway = MemoryGateway(
        entities={"Bug": [sample_bug]}
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
    output_path = tmp_path / "exports" / "monthly-audit.xlsx"

    exit_code = run_cli(
        ["reports", "monthly-audit", "--month-label", "2026-06", "--format", "xlsx", "--output", str(output_path)],
        settings=settings,
        gateway=gateway,
    )

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    with zipfile.ZipFile(output_path) as archive:
        assert "xl/workbook.xml" in archive.namelist()
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m pytest tests/unit/test_cli.py -k "monthly_audit_writes_xlsx" -v
```

Expected:

- CLI 相关断言失败

- [ ] **Step 3: 用现有 xlsx 输出通路接通月审**

```python
elif args.command == "reports" and args.reports_command == "monthly-audit":
    result = service.run_workflow(
        "monthly-audit",
        entity=args.entity,
        limit=args.limit,
        filters={"month_label": args.month_label},
    )
```

月审 workbook 使用已有 `render_output(..., "xlsx")` 和 `Path.write_bytes(...)`，不新增额外写文件逻辑。

- [ ] **Step 4: 重跑测试并确认通过**

Run:

```powershell
python -m pytest tests/unit/test_cli.py -k "monthly_audit" -v
```

Expected:

- `PASS`

## Task 5: 全量验证

**Files:**
- Modify: `src/tp_codex/monthly_audits.py`
- Modify: `src/tp_codex/service.py`
- Modify: `src/tp_codex/cli.py`
- Modify: `tests/unit/test_cli.py`
- Modify: `tests/integration/test_workflows.py`

- [ ] **Step 1: 跑 monthly-audit 聚焦测试**

Run:

```powershell
python -m pytest tests/unit/test_cli.py tests/integration/test_workflows.py -k "monthly_audit" -v
```

Expected:

- 全部 `PASS`

- [ ] **Step 2: 跑更宽的报表回归**

Run:

```powershell
python -m pytest tests/unit/test_cli.py tests/unit/test_renderers.py tests/integration/test_workflows.py -k "build_dataset or build_workbook or weekly_report or monthly_audit or xlsx" -v
```

Expected:

- 全部 `PASS`

- [ ] **Step 3: 跑非 live 全量验证**

Run:

```powershell
python -m pytest -m "not live"
```

Expected:

- 全部 `PASS`

- [ ] **Step 4: 更新计划状态说明**

在最终说明中明确：

- 已验证：月审 CLI、workflow、candidate history、workbook 输出、非 live 全量测试
- 未验证：真实 Targetprocess live 拉数
