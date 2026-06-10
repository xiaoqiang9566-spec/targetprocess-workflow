# Targetprocess Weekly Report Workflow

## Inputs

Prefer this input order:

1. Existing weekly output bundle
2. Existing `bug_master.json`
3. Existing `bug_master.csv`
4. Live CLI pull
5. Layout reference from `docs/weekNN-template.xlsx` when the user does not provide a newer replacement template

Typical bundle contents:

- `bug_master.json`
- `bug_master.csv`
- `run-metadata.json`
- `send-summary.md`
- `healthcheck.json`
- Existing workbook artifacts

When an existing `bug_master.json` is present, prefer it over a fresh live pull.

Default workbook-layout rule:

- Use `docs/weekNN-template.xlsx` as the canonical weekly report template reference for generation, repair, and validation unless the user explicitly provides a different replacement workbook.
- When the generated workbook and `docs/weekNN-template.xlsx` disagree on visual shape, trust `docs/weekNN-template.xlsx`.

## NG3 Single-Sheet Weekly Report Formal Specification

Treat this section as the source of truth for the single-sheet NG3 weekly report unless the user provides a newer template or an explicit replacement rule.

### Global rules

- The NG3 single-sheet weekly report is composed of exactly four business tables:
  1. `2026年NG3固件每周新增Bug`
  2. `NG3项目2026年固件有效bug检出&修复情况`
  3. `2026年NG3固件售后问题`
  4. `NG3存量Bug消减情况`
- Use `docs/weekNN-template.xlsx` as the default workbook skeleton and formatting reference for this four-table NG3 weekly report unless the user explicitly provides a newer replacement workbook.
- Prefer existing local bundle files over live pulls. Reuse `bug_master.json`, `bug_master.csv`, weekly output bundles, or workbook-side artifacts when they already contain the required scope.
- Keep the workflow read-only. If live data is required, run `python -m tp_codex.cli healthcheck --format json` before large pulls.
- For this weekly report, use the four-team scope:
  - `ESW China NG3 Driver`
  - `ESW China NG3 Framework`
  - `ESW UI Team`
  - `ESW WUI`
- Do not split or exclude by `Products`. All `Products` values in this report belong to the NG3 platform. Treat `Products` as descriptive metadata only.
- Write a concise 3-5 point summary before each table. Base the summary on source data, template notes, or explicit user instruction. Do not invent owners, targets, dashboard links, or issue highlights.
- Trust the workbook template over the built-in generator when layout, merged ranges, or section meaning conflict.

## Template Shapes

### Multi-product workbook

Treat the template as compatible with the built-in weekly report generator when most of these cues are true:

- It already contains a weekly sheet named like `固件质量数据概览-WeekNN`.
- The weekly sheet is a long multi-section page with NG3, Dilu, 心率带2, Core 2, Run 2, and Race sections.
- The weekly sheet is roughly the same shape expected by `src/tp_codex/weekly_reports.py`.
- The intended output is to append a new weekly sheet while keeping older weekly sheets and helper sheets.

For this shape, prefer:

```bash
python -m tp_codex.cli reports weekly-report --week-label Week23 --template <template.xlsx> --output <output.xlsx>
```

### Single-sheet NG3 workbook

Treat the template as a manual rebuild target when most of these cues are true:

- The workbook has a single sheet or a single relevant weekly sheet.
- The sheet is roughly a 42-row NG3-only page.
- Merged blocks look like `A1:G1`, `A3:G3`, `A12:G12`, `A24:G24`, and `A37:G37`.
- The page is composed of four fixed tables:
  - `2026年NG3固件每周新增Bug`
  - `NG3项目2026年固件有效bug检出&修复情况`
  - `2026年NG3固件售后问题`
  - `NG3存量Bug消减情况`

For this shape, do not blindly use the built-in weekly report generator. The current repo implementation in `src/tp_codex/weekly_reports.py` assumes the multi-product layout and can produce layout mismatches against a 42-row template.
Default to producing a single-sheet `WeekNN` workbook rather than appending a second weekly sheet.
When the user does not provide another workbook, assume this shape is defined by `docs/weekNN-template.xlsx`.

## Scope Pitfalls

### Scope differs by report purpose

Start from `config/workflow_rules.yaml` for generic project workflows, but do not assume that the generic default scope is always the report scope.

For the NG3 weekly report tables in this single-sheet workbook, use this four-team scope:

- `ESW China NG3 Driver`
- `ESW China NG3 Framework`
- `ESW UI Team`
- `ESW WUI`

If `config/workflow_rules.yaml` or older project docs still mention only three teams, treat the four-team scope above as the specific rule for this weekly report workbook unless the user provides a newer template or rule.

### NG3 product scope

Iron rule: for NG3 weekly reports, do not split or exclude by `Products`. All `Products` values in the NG3 report data belong to the NG3 platform.

`Products` is descriptive metadata only. It must not drive product-level bug counts, must not create separate Race/Core/Run/etc. sections for a single-sheet NG3 report, and must not cause records to be excluded from NG3 tables.

`weekly_new_bug_master.csv` is already the weekly new NG3 bug dataset. Treat every record in that file as an NG3 bug.

If counts still look inflated, inspect these fields to confirm whether the data file itself has the intended report scope:

- `team`
- `created_week`
- `status_raw`
- `severity`

Only treat records as out of scope when the source data clearly belongs outside the NG3 report team/data scope. Do not use `Products` for that decision.

## Table 1: 2026年NG3固件每周新增Bug

Use this rule set for the first table, `2026年NG3固件每周新增Bug`.

### Data filter

- Count bugs whose `CreateDate` falls in the previous calendar week.
- Define `Previous week` as Monday through Sunday before the current week. For example, if today is 2026-06-09, use 2026-06-01 through 2026-06-07.
- Prefer existing weekly bundle data or `bug_master.json` when it already contains the required previous-week records. Do not re-pull live data just to regenerate this table.
- If live data is required, run `healthcheck` first and keep the command read-only.

### Scope

Filter to the four weekly-report teams:

- `ESW China NG3 Driver`
- `ESW China NG3 Framework`
- `ESW UI Team`
- `ESW WUI`

### Status buckets

Summarize status columns exactly as follows:

- `待分析`: `New`
- `处理中`: `In progress` + `In review`
- `已解决`: `In testing`
- `已验证`: `Verified` + `Fixed`
- `异常闭环`: `Invalid` + `Duplicate` + `Wont fix`

When a source status is unmapped, inspect the raw status before assigning it. Do not silently drop unmapped statuses from `Bug总数`.

### Table layout and calculations

- Preserve the template's visual style and table shape.
- Use severity rows in this order when present: `Blocking`, `Critical`, `Major`, `Normal`, `总计`, `各状态问题占比`.
- Columns should be: `等级`, `Bug总数`, `待分析`, `处理中`, `已解决`, `已验证`, `异常闭环`.
- `Bug总数` is the row total across all status buckets for that severity.
- The `总计` row sums each numeric column across severities.
- The `各状态问题占比` row divides each status bucket total by the overall `Bug总数`; use percentages and keep Excel percentage formatting intact.

### Summary text

Before the table, write a concise 3-5 point analysis of the previous week's new bugs.

The summary should usually cover:

- Total new bug count and high-severity focus such as `Blocking` + `Critical` counts.
- Distribution by team or group, such as Driver, Framework, UI, and WUI, when the data supports it.
- Status distribution using the same buckets as the table, including percentages for major buckets.
- Key unresolved or risky issues that need continued attention.

Do not invent issue owner names, highlighted problem titles, or @mentions. Only include them when they are present in the source data, template notes, or explicit user instruction.

## Table 2: NG3项目2026年固件有效bug检出&修复情况

Use this rule set for the second table, `NG3项目2026年固件有效bug检出&修复情况`.

### Data filter

- Count 2026 firmware effective bugs whose `CreateDate` falls from 2026-01-01 through 2026-12-31.
- Exclude bugs whose `Name` contains `Customer feedback`.
- Count only bugs whose `State` is one of `New`, `In Progress`, `In Review`, `In Testing`, `Reproduce`, `Verified`, `Wont fix`, `Fixed`, `Expired`, `Later`, or `Planned`.
- Exclude `Duplicate` and `Invalid` from the effective bug population.
- Treat `Wont fix`, `Expired`, and `Later` as abnormal closure inside this table, not as exclusions. Treat `Verified` and `Fixed` as normal closed bugs.
- Prefer existing local data files, weekly bundle data, or `bug_master.json` when they already contain the required 2026 records. Do not re-pull live data just to regenerate this table.
- If live data is required, run `healthcheck` first and keep the command read-only.

### Scope

Filter to the four weekly-report teams:

- `ESW China NG3 Driver`
- `ESW China NG3 Framework`
- `ESW UI Team`
- `ESW WUI`

### Status categories

Use these columns for the status and team summary tables:

- `总有效bug数` or `B&C有效bug数`: all bugs after the table's date, text, state, and scope filters.
- `待解决`: bugs not yet in a resolved or closed bucket. At minimum include `New`, `Planned`, `In progress`, and `In review` unless source workflow rules provide a more specific unresolved grouping.
- `待验证`: bugs in `In testing`.
- `异常规划闭单`: bugs closed through non-standard planning or closure states that remain relevant to this table, such as `Wont fix`, `Expired`, and `Later`. Do not include `Duplicate` or `Invalid` because they are excluded before counting effective bugs.
- Closed normal bugs: `Verified` + `Fixed`.

When a source status is unmapped, inspect `status_raw` before assigning it. Do not silently drop unmapped statuses from `总有效bug数`.

### 按状态 table

- Preserve the template's visual style and table shape.
- Use severity rows in this order when present: `Blocking`, `Critical`, `Major`, `Normal`, `总计`.
- Columns should be: `等级`, `总有效bug数`, `待解决`, `待验证`, `异常规划闭单`, `关闭率`, `验证率`.
- `总计` sums each numeric count column across severities.

### 按Team table

- Preserve the template's visual style and table shape.
- Use team rows in the template's order. Typical display names are `驱动`, `框架`, `UI`, and `WUI`.
- Map teams as:
  - `驱动`: `ESW China NG3 Driver`
  - `框架`: `ESW China NG3 Framework`
  - `UI`: `ESW UI Team`
  - `WUI`: `ESW WUI`
- Columns should be: `工作组`, `B&C有效bug数`, `待解决`, `待验证`, `异常规划闭单`, `关闭率`, `验证率`.
- If the template only shows B&C team rows, filter the team table to `Blocking` + `Critical`; otherwise follow the template's row labels.

### Rate formulas

- `关闭率` = (`总有效bug数` - `待解决`) / `总有效bug数`.
- `验证率` = (`总有效bug数` - `待解决` - `待验证` - `异常规划闭单`) / (`总有效bug数` - `待解决` - `异常规划闭单`).
- If the denominator is zero, leave the rate blank or use the template's existing zero-value convention.
- Keep rates as numeric percentage values so Excel formatting remains intact.
- Highlight or color rates only by preserving existing template formatting; do not invent a new color rule unless the user asks.

### Summary text

Before the table, write a concise 3-5 point analysis of 2026 firmware effective bugs.

The summary should usually cover:

- Total effective bug count for 2026 and the current unresolved count.
- Overall closure rate and target gap when the template or user provides a target, such as 65%.
- B&C closure rates for `Blocking` and `Critical`.
- B&C or team-level closure rates for Driver, Framework, UI, and WUI when the data supports it.
- Verification progress, especially remaining B&C bugs awaiting verification.

Do not invent issue owner names, highlighted problem titles, targets, or @mentions. Only include them when they are present in the source data, template notes, or explicit user instruction.

## Table 3: 2026年NG3固件售后问题

Use this rule set for the third table, `2026年NG3固件售后问题`.

### Data filter

- Count 2026 firmware after-sales bugs whose `CreateDate` falls from 2026-01-01 through 2026-12-31.
- Include only bugs whose `Name` contains `Customer feedback`.
- Do not exclude `Duplicate`, `Invalid`, or refused issues before counting unless the user explicitly changes the after-sales definition. The template tracks abnormal closure separately.
- Prefer existing local data files, weekly bundle data, or `bug_master.json` when they already contain the required 2026 after-sales records. Do not re-pull live data just to regenerate this table.
- If live data is required, run `healthcheck` first and keep the command read-only.

### Scope

Filter to the four weekly-report teams:

- `ESW China NG3 Driver`
- `ESW China NG3 Framework`
- `ESW UI Team`
- `ESW WUI`

### Status categories

Use these columns for the severity summary:

- `售后问题总数`: all bugs after the table's date, `Customer feedback`, and scope filters.
- `已关闭`: closed after-sales bugs, including normal closure and abnormal closure when the source status is closed.
- `待关闭`: bugs not yet closed. At minimum include `New`, `Planned`, `In progress`, `In review`, and other active unresolved states.
- `待验证`: bugs in `In testing`.
- `非常规闭环`: after-sales bugs closed through abnormal or non-standard states, such as `Duplicate`, `Invalid`, or `Wont fix`.
- `关闭率`: `已关闭` / `售后问题总数`.

When a source status is unmapped, inspect `status_raw` before assigning it. Do not silently drop unmapped statuses from `售后问题总数`.

### 按严重程度 table

- Preserve the template's visual style and table shape.
- Use severity rows in this order when present: `Blocking`, `Critical`, `Major`, `Normal`, `总计`.
- Columns should be: `等级`, `售后问题总数`, `已关闭`, `待关闭`, `待验证`, `非常规闭环`, `关闭率`.
- `总计` sums each numeric count column across severities.
- `关闭率` = `已关闭` / `售后问题总数` for each row.
- Keep rates as numeric percentage values so Excel formatting remains intact.

### 按Team table

- Preserve the template's visual style and table shape.
- Use team rows in the template's order. Typical display names are `驱动`, `框架`, `UI`, and `WUI`, followed by `总计`.
- Map teams as:
  - `驱动`: `ESW China NG3 Driver`
  - `框架`: `ESW China NG3 Framework`
  - `UI`: `ESW UI Team`
  - `WUI`: `ESW WUI`
- Build the team table from the template's actual row and column labels.
- At minimum, keep the team dimension aligned to the four-team NG3 report scope and preserve the template's existing counting logic, formulas, and display labels.
- If a specific team-table business rule is not explicitly confirmed by the user or template, do not invent additional SLA thresholds, response-cycle metrics, or manual narrative fields.

### Summary text

Before the table, write a concise 3-5 point analysis of 2026 firmware after-sales bugs.

The summary should usually cover:

- Total after-sales bug count for 2026 and distribution by team when the data supports it.
- Closed count and overall closure rate, plus target gap when the template or user provides a target such as 65%.
- Abnormal closure count and share among closed issues.
- Team-level concentration of high-severity or unresolved after-sales bugs when the data supports it.
- Customer satisfaction or rejection-reason follow-up only when supported by source data or explicit user instruction.

Do not invent issue owner names, highlighted problem titles, customer satisfaction statements, targets, or @mentions. Only include them when they are present in the source data, template notes, or explicit user instruction.

## Table 4: NG3存量Bug消减情况

Use this rule set for the fourth table, NG3存量Bug消减情况.

### Data filter

- Stock bugs are defined as bugs created before the report year: CreateDate >= 2021-01-01 AND CreateDate <= 2025-12-31.
- This table covers four derived dimensions from the stock bug population. All derived dimensions share the same CreateDate range [2021-01-01, 2025-12-31].
- Do not use is_open or status_group as the stock bug filter. The stock definition is based solely on CreateDate range and the column-specific state and owner filters.
- Prefer existing local data files, weekly bundle data, or ug_master.json when they already contain the required stock records. Do not re-pull live data just to regenerate this table.
- If live data is required, run healthcheck first and keep the command read-only.

### Scope

Filter to the four weekly-report teams:

- ESW China NG3 Driver
- ESW China NG3 Framework
- ESW UI Team
- ESW WUI

### Column filter definitions

Each column in the table has its own filter. The stock CreateDate range [2021-01-01, 2025-12-31] applies to all columns.

**Bug存量** = 待研发处理 + 待复现 + 待验证 (sum of the three sub-columns).

**2026年关闭量**:

- CreateDate >= 2021-01-01 AND CreateDate <= 2025-12-31
- LastStateChangeDate >= 2026-01-01 AND LastStateChangeDate <= 2026-12-31
- State in Duplicate, Expired, Fixed, Invalid, Later, Verified, Wont fix
- No creator exclusion for this column.

**待研发处理**:

- CreateDate >= 2021-01-01 AND CreateDate <= 2025-12-31
- State in Blocked, Design review, In Progress, In Review, New, Planned, Waiting for design
- Owner NOT IN Lena Bergendahl, Sami Järvinen, Valtteri Mäki

**待验证**:

- CreateDate >= 2021-01-01 AND CreateDate <= 2025-12-31
- State in In Testing
- Owner NOT IN Lena Bergendahl, Sami Järvinen, Valtteri Mäki

**待复现**:

- CreateDate >= 2021-01-01 AND CreateDate <= 2025-12-31
- State in Needs info, Reproduce
- Owner NOT IN Lena Bergendahl, Sami Järvinen, Valtteri Mäki

### Excluded owners

The following owners are excluded from 待研发处理, 待验证, and 待复现, but NOT from 2026年关闭量:

- Lena Bergendahl
- Sami Järvinen
- Valtteri Mäki

### Team mapping

Use the template display rows. Typical display names are 驱动, 框架, UI, and 总计.

Map teams as:

- 驱动: ESW China NG3 Driver
- 框架: ESW China NG3 Framework + ESW WUI
- UI: ESW UI Team

Do not add a separate WUI row unless the template explicitly contains one. In this stock-reduction table, WUI rolls into the 框架 row.

### Table layout and calculations

- Preserve the template visual style and table shape.
- Columns: 工作组, Bug存量, 2026年关闭量, 待研发处理, 待复现, 待验证, 消减率.
- Bug存量 = 待研发处理 + 待复现 + 待验证 per team row. This is a derived sum, not an independent count.
- 2026年关闭量, 待研发处理, 待复现, and 待验证 are the filtered counts from the column definitions above.
- 总计 sums each numeric count column across the displayed team rows.
- 消减率 = 2026年关闭量 / (Bug存量 + 2026年关闭量).
- If the denominator is zero, leave the rate blank or use the template existing zero-value convention.
- Keep rates as numeric percentage values so Excel formatting remains intact.

### Summary text

Before the table, write a concise 3-5 point analysis of the NG3 stock bug situation.

The summary should usually cover:

- Current NG3 stock bug total (Bug存量) and the team distribution across 驱动, 框架, and UI.
- Total 2026 closed volume and the team distribution across the displayed rows.
- Current stock composition across 待研发处理, 待复现, and 待验证.
- Overall stock reduction rate and the highest or lowest team reduction rate when the data supports it.
- Dashboard or tracking-link references only when the template already contains them or the user explicitly provides them.

Do not invent issue owner names, highlighted problem titles, dashboard URLs, targets, or @mentions. Only include them when they are present in the source data, template notes, or explicit user instruction.
## Manual Rebuild Guidance For A 42-row NG3 Template

Use `docs/weekNN-template.xlsx` as the default source of layout truth unless the user explicitly provides a newer replacement workbook.

The weekly report contains exactly these four business tables. Preserve their names and order unless the user explicitly provides a different template:

1. `2026年NG3固件每周新增Bug`
2. `NG3项目2026年固件有效bug检出&修复情况`
3. `2026年NG3固件售后问题`
4. `NG3存量Bug消减情况`

Typical area mapping:

- `A1`: report title
- `A3`: weekly summary block
- Rows `5:10`: `2026年NG3固件每周新增Bug`
- `A12`: yearly effective bug summary
- Rows `14:22`: `NG3项目2026年固件有效bug检出&修复情况`
- `A24`: customer feedback summary
- Rows `26:35`: `2026年NG3固件售后问题`
- `A37`: stock reduction summary
- Rows `39:42`: `NG3存量Bug消减情况`

When rebuilding:

- Rename the sheet to the requested week label.
- Preserve merged cells, styles, column widths, row heights, and formatting.
- Update only the values that belong to the requested week.
- Keep percentages as numeric values so Excel formatting remains intact.

## Live Pull Rules

When a live pull is actually needed:

1. Run:

```bash
python -m tp_codex.cli healthcheck --format json
```

2. Prefer workflow commands over ad hoc entity pulls.

3. Prefer:

```bash
python -m tp_codex.cli bugs review-export --format csv --output <path>
```

or:

```bash
python -m tp_codex.cli reports build-dataset --format json --output <path>
```

4. Keep the flow read-only.

## Validation Checklist

Before handoff, verify:

- Output file exists at the expected path.
- Sheet count matches the intended template pattern.
- Weekly sheet name matches the requested `WeekNN`.
- Row count still matches the template shape.
- Merged ranges are unchanged unless the user requested layout edits.
- Key cells such as title, summaries, totals, and percentages contain current-week values.
- Product-scope language distinguishes `NG3 platform scope`, `NG3 legacy product`, and `Race 3S/Race3`.
- No stale prior-week summary text remains in manually curated sections.

If the user says the workbook is "错乱" or "格式不对", compare the template and output first. In this workflow, structural mismatch is often more likely than bad arithmetic.
