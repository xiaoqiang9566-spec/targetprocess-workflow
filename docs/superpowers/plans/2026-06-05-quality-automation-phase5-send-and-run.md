# Send And Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `reports send`、`reports run-weekly`、`reports run-monthly`，把现有 `build-dataset / build-workbook / weekly-report / monthly-audit` 串成可落盘、可人工发送的完整运行闭环。
**Architecture:** 保持 Targetprocess 读取和分析逻辑继续由现有 service workflow 负责；将“发送摘要生成”“运行目录产物清单”和“运行元数据 manifest”封装到独立模块；CLI 负责编排原子 workflow、写入输出目录和对现有产物做 send-ready 摘要渲染。默认不接入真实外部发送渠道，只生成可人工发送的摘要和附件目录。
**Tech Stack:** Python 3.9、现有 `tp_codex` CLI/service/renderers、最小 OOXML 工作簿产物、JSON/CSV/Markdown 文件输出。

---

## Files

- Create: `src/tp_codex/report_delivery.py`
- Modify: `src/tp_codex/cli.py`
- Modify: `src/tp_codex/__init__.py`
- Modify: `src/tp_codex/renderers.py`
- Modify: `tests/unit/test_cli.py`
- Create: `tests/unit/test_report_delivery.py`
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-06-05-quality-automation-phase5-send-and-run.md`

## Task 1: 锁定 CLI 契约

**Files:**
- Modify: `tests/unit/test_cli.py`
- Modify: `src/tp_codex/cli.py`

- [ ] **Step 1: 先写失败测试，锁定 parser 和参数约束**

覆盖：

- `reports send --manifest <run-metadata.json>`
- `reports run-weekly --week-label Week23 --template <template.xlsx> [--output-dir <dir>]`
- `reports run-monthly --month-label 2026-06 [--output-dir <dir>]`
- `send` 必须要求 `--manifest`
- `run-weekly` 的 `xlsx` 运行必须要求 `--template`、`--week-label`
- `run-monthly` 必须要求 `--month-label`

- [ ] **Step 2: 跑聚焦测试并确认失败**

Run:

```powershell
python -m pytest tests/unit/test_cli.py -k "send or run_weekly or run_monthly" -v
```

Expected:

- parser 未包含新命令
- 或参数约束断言失败

- [ ] **Step 3: 最小实现 parser 与 CLI 校验**

要求：

- `send` 默认 `--format markdown`
- `send` 支持 `--output`
- `run-weekly/run-monthly` 支持 `--output-dir`
- 当未显式指定 `--output-dir` 时，CLI 使用规范默认目录

- [ ] **Step 4: 重跑测试并通过**

## Task 2: 锁定发送摘要生成

**Files:**
- Create: `tests/unit/test_report_delivery.py`
- Create: `src/tp_codex/report_delivery.py`

- [ ] **Step 1: 写失败测试，锁定 weekly/monthly send-ready 摘要**

要求：

- 周报摘要包含 `week_label`、总记录数、本周新增、高风险、售后问题、产品拆分
- 月审摘要包含 `month_label`、总记录数、当月新增、候选风险、高风险、售后、未映射状态
- 如果 `warnings` 含 `partial_entities` 或 `partial_history`，摘要必须显式写出“本次数据不完整”
- 摘要必须列出建议附件文件名

- [ ] **Step 2: 跑单测并确认失败**

Run:

```powershell
python -m pytest tests/unit/test_report_delivery.py -v
```

- [ ] **Step 3: 实现摘要渲染与 manifest 帮助函数**

要求：

- 提供 `build_send_markdown(manifest)` 或等价接口
- 提供 `build_run_manifest(...)` 或等价接口
- 输出保持中文、适合人工直接复制发送

- [ ] **Step 4: 重跑单测并通过**

## Task 3: 跑通 `run-weekly`

**Files:**
- Modify: `tests/unit/test_cli.py`
- Modify: `src/tp_codex/cli.py`
- Create/Modify: `src/tp_codex/report_delivery.py`
- Modify: `src/tp_codex/renderers.py`

- [ ] **Step 1: 写失败测试，锁定 `run-weekly` 目录产物**

输出目录至少包含：

- `healthcheck.json`
- `bug_master.json`
- `bug_master.csv`
- `quality-analysis-workbook.xlsx`
- `weekly-report-Week23.xlsx`
- `send-summary.md`
- `run-metadata.json`

- [ ] **Step 2: 跑测试并确认失败**

- [ ] **Step 3: 在 CLI 中编排 `healthcheck -> build-dataset -> build-workbook -> weekly-report -> send-summary`**

要求：

- 不重复拉取外部模板外的其它文件
- 复用现有 workflow 结果，不新写第二套统计逻辑
- manifest 中保留摘要、warnings、附件文件名和输出目录

- [ ] **Step 4: 重跑测试并通过**

## Task 4: 跑通 `run-monthly` 与 `send`

**Files:**
- Modify: `tests/unit/test_cli.py`
- Modify: `src/tp_codex/cli.py`
- Create/Modify: `src/tp_codex/report_delivery.py`

- [ ] **Step 1: 写失败测试，锁定 `run-monthly` 和 `send`**

覆盖：

- `run-monthly` 输出目录至少包含：
  - `healthcheck.json`
  - `bug_master.json`
  - `bug_master.csv`
  - `quality-analysis-workbook.xlsx`
  - `monthly-audit-2026-06.xlsx`
  - `send-summary.md`
  - `run-metadata.json`
- `send --manifest <path> --output <summary.md>` 能从既有 manifest 重新渲染发送摘要

- [ ] **Step 2: 跑测试并确认失败**

- [ ] **Step 3: 实现 `run-monthly` 和 `send`**

要求：

- `send` 不拉数、不分析、不依赖 Targetprocess 连接
- `send` 只读取既有 manifest 并输出摘要
- `run-monthly` 复用 `monthly-audit` 工作流，不额外创建第二套月审逻辑

- [ ] **Step 4: 重跑测试并通过**

## Task 5: 文档与回归验证

**Files:**
- Modify: `README.md`
- Modify: `tests/unit/test_cli.py`
- Modify: `tests/unit/test_report_delivery.py`
- Modify: `src/tp_codex/cli.py`
- Modify: `src/tp_codex/report_delivery.py`

- [ ] **Step 1: 更新 README 命令示例**

至少补充：

- `reports build-dataset`
- `reports build-workbook`
- `reports weekly-report`
- `reports monthly-audit`
- `reports send`
- `reports run-weekly`
- `reports run-monthly`

- [ ] **Step 2: 跑新增聚焦测试**

Run:

```powershell
python -m pytest tests/unit/test_cli.py tests/unit/test_report_delivery.py -k "send or run_weekly or run_monthly" -v
```

- [ ] **Step 3: 跑报表全链路回归**

Run:

```powershell
python -m pytest tests/unit/test_cli.py tests/unit/test_renderers.py tests/unit/test_report_delivery.py tests/integration/test_workflows.py -k "build_dataset or build_workbook or weekly_report or monthly_audit or send or run_weekly or run_monthly or xlsx" -v
```

- [ ] **Step 4: 跑非 live 全量验证**

Run:

```powershell
python -m pytest -m "not live"
```

- [ ] **Step 5: 最终说明中明确验证边界**

必须说明：

- 已验证：发送摘要渲染、周/月运行目录产物、已有报表 workflow 回归、非 live 全量测试
- 未验证：真实外部邮件/Teams/钉钉/企业微信发送、真实 Targetprocess live 数据运行
