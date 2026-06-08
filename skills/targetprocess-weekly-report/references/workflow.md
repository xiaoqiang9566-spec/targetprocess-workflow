# Targetprocess Weekly Report Workflow

## Inputs

Prefer this input order:

1. Existing weekly output bundle
2. Existing `bug_master.json`
3. Existing `bug_master.csv`
4. Live CLI pull

Typical bundle contents:

- `bug_master.json`
- `bug_master.csv`
- `run-metadata.json`
- `send-summary.md`
- `healthcheck.json`
- Existing workbook artifacts

When an existing `bug_master.json` is present, prefer it over a fresh live pull.

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
- The page contains only NG3 sections such as weekly new bugs, yearly effective bugs, customer feedback, and stock reduction.

For this shape, do not blindly use the built-in weekly report generator. The current repo implementation in `src/tp_codex/weekly_reports.py` assumes the multi-product layout and can produce layout mismatches against a 42-row template.
Default to producing a single-sheet `WeekNN` workbook rather than appending a second weekly sheet.

## Scope Pitfalls

### Default team scope is not always enough

The project default scope comes from `config/workflow_rules.yaml` and is limited to:

- `ESW China NG3 Driver`
- `ESW China NG3 Framework`
- `ESW UI Team`

That scope is useful, but it is not automatically the same as the template's report scope.

### Product leakage

When the template is NG3-only, team-level counts may still include records tied to products such as Race, Run, Core, or heart-rate accessories. If counts look inflated, inspect:

- `products`
- `team`
- `created_week`
- `status_raw`
- `severity`

Do not fill an NG3-only template until the scope aligns with the template's sections.

### NG3 platform scope versus NG3 legacy product

The default live pull for this project is usually scoped to the three NG3-platform teams:

- `ESW China NG3 Driver`
- `ESW China NG3 Framework`
- `ESW UI Team`

That scope means "NG3 platform team data". It does not automatically mean the `NG3` product section in the weekly report.

For weekly reporting:

- `Race 3S/Race3` is an NG3-platform new product and must be counted as its own product section.
- `NG3` should mean the NG3 legacy product-model collection.
- Always inspect `products` before reporting a number as `NG3`.
- If a record has empty or unrecognized `products`, keep it in a review bucket or explicitly state that the historical team fallback was used.

The previous mistake was describing a default-scope weekly-new count such as `60` as `NG3 本周新增 60`. The correct wording is either:

- `NG3 平台三团队本周新增 60，需按 Products 继续拆分`
- `NG3 老产品本周新增 N，Race 3S/Race3 本周新增 M`

## Manual Rebuild Guidance For A 42-row NG3 Template

Use the provided template as the only source of layout truth.

Typical mapping:

- `A1`: report title
- `A3`: weekly summary block
- Rows `5:10`: weekly new bug table
- `A12`: yearly effective bug summary
- Rows `14:22`: yearly effective bug tables
- `A24`: customer feedback summary
- Rows `26:35`: customer feedback tables
- `A37`: stock reduction summary
- Rows `39:42`: stock reduction table

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
