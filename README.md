# tp-codex

Read-only Targetprocess automation toolkit for QA-oriented bug workflows.

## Capabilities

- Read-only connectivity and auth selection
- Schema snapshot export for `Bug`, `Feature`, and `UserStory`
- Entity listing and Bug history retrieval
- QA workflow commands for intake, triage view, regression queue, risk scan, and review export
- Reporting workflows for dataset export, quality workbook, weekly report, monthly audit, and run bundles
- JSON, Markdown, CSV, and XLSX output
- Redacted diagnostics and explicit live-test opt-in

## Quick Start

1. Copy `.env.example` values into your local environment or config files.
2. Adjust `config/workflow_rules.yaml` to match your Targetprocess workflow names.
3. Run `python -m tp_codex.cli healthcheck --format json` to confirm connectivity and see the active workflow rule summary.

## Commands

```text
python -m tp_codex.cli healthcheck --format json
python -m tp_codex.cli schema snapshot --entity Bug --format json
python -m tp_codex.cli entities list --entity Bug --limit 100 --format json
python -m tp_codex.cli bugs intake --format markdown
python -m tp_codex.cli bugs triage-view --format json
python -m tp_codex.cli bugs triage-view --history-mode full --format json
python -m tp_codex.cli bugs regression-queue --format json
python -m tp_codex.cli bugs risk-scan --format markdown
python -m tp_codex.cli bugs risk-scan --history-mode full --format markdown
python -m tp_codex.cli bugs review-export --format csv
python -m tp_codex.cli bugs review-export --history-mode full --format csv
python -m tp_codex.cli bugs history --bug-id 12345 --format json
python -m tp_codex.cli reports build-dataset --format csv --output outputs/datasets/bug_master.csv
python -m tp_codex.cli reports build-workbook --output outputs/datasets/quality-analysis-workbook.xlsx
python -m tp_codex.cli reports weekly-report --week-label Week23 --template weekly-template.xlsx --output outputs/reports/weekly/2026-06-05/weekly-report-Week23.xlsx
python -m tp_codex.cli reports monthly-audit --month-label 2026-06 --output outputs/reports/monthly/2026-06/monthly-audit-2026-06.xlsx
python -m tp_codex.cli reports run-weekly --week-label Week23 --template weekly-template.xlsx --output-dir outputs/reports/weekly/2026-06-05
python -m tp_codex.cli reports run-monthly --month-label 2026-06 --output-dir outputs/reports/monthly/2026-06
python -m tp_codex.cli reports send --manifest outputs/reports/weekly/2026-06-05/run-metadata.json --output outputs/reports/weekly/2026-06-05/send-summary.md
python scripts/tp_history_mode_benchmark.py --limit 5
```

## Reporting Outputs

- `reports build-dataset` 生成标准化 `bug_master` 数据集，可输出 `json` 或 `csv`
- `reports build-workbook` 生成质量分析工作簿 `.xlsx`
- `reports weekly-report` 基于累计周报模板追加新的周报 sheet
- `reports monthly-audit` 生成月审工作簿 `.xlsx`
- `reports run-weekly` 默认输出到 `outputs/reports/weekly/YYYY-MM-DD/`
- `reports run-monthly` 默认输出到 `outputs/reports/monthly/YYYY-MM/`
- `reports send` 只基于既有 `run-metadata.json` 生成可人工发送的摘要，不会重新拉取 Targetprocess 数据

## Workflow Defaults

`bugs intake`, `bugs triage-view`, `bugs regression-queue`, `bugs risk-scan`, and `bugs review-export` automatically apply the defaults from `config/workflow_rules.yaml`.

`bugs triage-view`, `bugs risk-scan`, and `bugs review-export` default to `--history-mode off`. Use `--history-mode full` when the caller explicitly needs per-bug history in those workflow results.

Current defaults:

- `default_scope.project`: `Suunto work`
- `default_scope.team`: `ESW China NG3 Driver`, `ESW China NG3 Framework`, `ESW UI Team`
- `status_groups.triage`: `New`, `Reproduce`
- `status_groups.in_progress`: `In Progress`, `In Review`
- `status_groups.ready_for_qa`: `In Testing`
- `status_groups.closed`: `Verified`, `Invalid`, `Wont fix`
- `default_select`: `Id`, `Name`, `CreateDate`, `ModifyDate`, `LastStateChangeDate`, `Team`, `Project`, `Severity`, `EntityState`, `Owner`, `Suuntoappversion`, `Suuntoappplatform`, `Products`, `Firmwareversion`, `Reproducibility`, `Feature`, `BugCategory`

`entities list` stays a foundation/debug command and does not automatically apply `default_scope` or `default_select`.

## Testing

```text
pytest -m "not live"
TP_RUN_LIVE_TESTS=1 pytest -m live
```

For the live bug history test, set `TP_LIVE_BUG_ID` to a real readable bug id in the target Targetprocess instance.
Set `TP_LIVE_REQUIRE_RECORDS=1` if the live environment is expected to return at least one bug record for smoke validation.

For history mode performance follow-up, run `python scripts/tp_history_mode_benchmark.py --limit 5` in a live-enabled environment. It benchmarks `triage-view`, `risk-scan`, and `review-export` in both `off` and `full` modes and prints a JSON summary, a compact Markdown list, and a complete document-ready section that can be pasted into the live validation notes.

## Integration Readiness

Use [docs/integration-readiness-checklist.md](D:/3681/Documents/Targetprocess/docs/integration-readiness-checklist.md) as the gate for real Targetprocess data validation.
The first successful live validation run is recorded in [docs/live-validation-notes-2026-06-03.md](D:/3681/Documents/Targetprocess/docs/live-validation-notes-2026-06-03.md).
The history mode phase-1 design and current implementation status are tracked in [2026-06-03-history-mode-design.md](D:/3681/Documents/Targetprocess/docs/superpowers/specs/2026-06-03-history-mode-design.md).
