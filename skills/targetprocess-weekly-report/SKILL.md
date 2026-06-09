---
name: targetprocess-weekly-report
description: Build, repair, or validate weekly QA report workbooks for this Targetprocess project from existing bug snapshot bundles and Excel templates. Use when Codex is asked to generate `WeekNN` weekly reports, reuse `bug_master.json/csv` from `outputs/reports/weekly/...`, fix formatting or content mismatches in `weekly-report-WeekNN.xlsx`, align a report strictly to a provided `.xlsx` template, or decide whether to use `python -m tp_codex.cli reports weekly-report` versus a manual template-driven rebuild.
---

# Targetprocess Weekly Report

## Overview

Create or repair weekly QA report workbooks for this repo while preserving the user's template shape. Prefer reusing an existing weekly output bundle over re-pulling live data.

## Workflow

1. Load the repo rules first.

- Read `AGENTS.md`.
- Read `docs/codex-project-experience-playbook.md`.
- Read `docs/codex-retrospective-profile.md`.
- Use `python -m tp_codex.cli` as the stable entrypoint.
- Keep the flow read-only. Treat live pulls as opt-in and run `healthcheck` before large live commands.

2. Inspect the available inputs before generating anything.

- Confirm the week label, template path, and requested output path.
- Inspect the bundle directory for `bug_master.json`, `bug_master.csv`, `run-metadata.json`, `send-summary.md`, and `healthcheck.json`.
- Prefer `bug_master.json` because it already contains normalized `records`.
- Use `bug_master.csv` for quick inspection or delivery, not as the primary reconstruction source.

3. Classify the template before choosing a generation path.

- Open the workbook and inspect sheet names, sheet count, row count, and merged ranges.
- If the template matches the repo's multi-product weekly workbook pattern, use the built-in weekly report flow.
- If the template is a single-sheet NG3 weekly workbook, rebuild directly from that template instead of blindly using the built-in generator.
- Treat the NG3 weekly report page as four fixed tables: `2026年NG3固件每周新增Bug`, `NG3项目2026年固件有效bug检出&修复情况`, `2026年NG3固件售后问题`, and `NG3存量Bug消减情况`.
- For `2026年NG3固件每周新增Bug`, apply the previous-week `CreateDate` filter, four-team weekly report scope, summary bullets, and status buckets defined in `references/workflow.md`.
- For `NG3项目2026年固件有效bug检出&修复情况`, apply the 2026 `CreateDate` filter, effective-bug exclusions, four-team weekly report scope, status summary table, team summary table, and rate formulas defined in `references/workflow.md`.
- For `2026年NG3固件售后问题`, apply the 2026 `CreateDate` filter, `Customer feedback` name inclusion, four-team weekly report scope, severity summary table, team summary table, and closure-rate rules defined in `references/workflow.md`.
- For `NG3存量Bug消减情况`, apply the 2026 full-bug `CreateDate` filter, the creator exclusion rule, the four derived state buckets, and the stock-reduction formula defined in `references/workflow.md`.
- When the template and the existing generator disagree, trust the template.

4. Choose the data scope that matches the template, not just the team scope.

- Start from the project default scope in `config/workflow_rules.yaml` when live data is needed.
- Do not assume the three default teams always equal the product scope required by the report.
- Check whether the template is asking for a multi-product workbook or an NG3-only page before counting records.
- For NG3 weekly reports, do not split or exclude by `Products`. All `Products` values in the NG3 report data belong to the NG3 platform; `Products` is descriptive metadata only and must not drive product-level bug counts.
- If totals look too large or UI-heavy, inspect product distribution and status mix before filling cells.

5. Generate the workbook in the least risky way.

- Reuse `bug_master.json` when it already exists.
- Use `python -m tp_codex.cli reports weekly-report` only when the template shape is compatible with `src/tp_codex/weekly_reports.py`.
- For template-driven rebuilds, preserve styles, merged cells, row heights, formulas, and existing layout; change only sheet names and cell values.
- Do not append extra sheets unless the template pattern clearly expects historical weekly sheets.
- If the template is a single-sheet weekly page, default to rewriting that page into the requested week instead of appending another sheet.
- Replace manual-only sections with explicit placeholders or leave them untouched on purpose; never copy stale prior-week text by accident.

6. Validate the workbook before handing it back.

- Verify the expected sheet count and sheet names.
- Verify that row count and merged ranges still match the intended template shape.
- Spot-check key cells such as the title, summary blocks, totals, and output filename.
- Confirm that no unexpected extra sheet was added and no section was shifted.

## Reference Files

- Read `references/workflow.md` for the four-table NG3 report structure, template-shape heuristics, scope pitfalls, manual rebuild guidance, and a validation checklist.
