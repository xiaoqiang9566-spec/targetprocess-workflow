# Targetprocess End-User Export Experience Design

Last updated: 2026-06-06

## Summary

This design targets end-user-facing bug export requests such as:

- "导出 2026 年新增的 bug"
- "导出 2026 年有变更记录的 bug"
- "导出 Driver 组 2026 年所有的 bug"
- "导出 2026 年状态未闭环的 bug"

The recommended architecture is a two-layer design:

1. A stable CLI execution layer that owns read-only querying, workflow-rule merging, structured filtering, and export.
2. A skill-based user semantic layer that translates natural-language export intents into structured CLI filters.

This avoids pushing raw Targetprocess `where` syntax onto end users while keeping core business definitions in code and tests instead of prompt text alone.

## Current State

The current repository already provides the following foundations:

- `python -m tp_codex.cli bugs review-export` for broad bug export within configured workflow scope.
- `python -m tp_codex.cli reports build-dataset` for standardized `bug_master` export.
- Workflow commands automatically merge `default_scope` and `default_select` from `config/workflow_rules.yaml`.
- `review-export` and `build-dataset` now accept raw `--where` for additional narrowing on top of the configured scope.
- Default exports avoid per-bug history fan-out and use batch `BugSimpleHistory` lookups only for status timestamp summarization.

These foundations are enough to support an end-user export experience without creating a new query engine.

## Approaches Considered

### Approach A: CLI-first business semantics

Add many business-level CLI parameters and expect users or wrappers to call them directly.

Examples:

- `--created-from`, `--created-to`
- `--updated-from`, `--updated-to`
- `--team`
- `--is-open`
- `--status-group`

Pros:

- Clear code ownership and testability
- Short execution path
- Low ambiguity once implemented

Cons:

- CLI becomes a business DSL
- Natural-language UX remains poor
- Every new user phrase pressures the CLI surface to expand

### Approach B: Skill-first freeform translation

Keep CLI almost unchanged and let the skill translate user requests mainly into raw `--where`.

Pros:

- Fastest user-facing rollout
- Most natural interaction for end users

Cons:

- Business definitions drift into prompt logic
- Regression coverage weakens
- Performance and scope guarantees become harder to enforce consistently

### Approach C: Hybrid structured semantics

Keep CLI as the stable execution substrate, add a small structured filter surface for high-frequency semantics, and let the skill translate natural language into those structured filters. Use raw `--where` only as a fallback for long-tail requests.

Pros:

- Best end-user experience
- Core semantics stay testable in code
- Query performance remains predictable
- Long-tail flexibility still exists

Cons:

- Slightly more design work than a pure skill wrapper
- Requires careful boundary management between structured filters and raw fallback

### Recommendation

Adopt Approach C.

It matches the current codebase, preserves execution efficiency, and gives end users natural-language access without making the CLI absorb every business phrase directly.

## Business Semantics for the First Release

The first release should explicitly support these initial high-frequency semantics and their combinations:

- "新增" = `CreateDate`
- "有变更记录" = `ModifyDate`
- "Driver 组" = `Team.Name == "ESW China NG3 Driver"`
- "未闭环" = bug state not mapped into `workflow_rules.closed`

These are the initial seed semantics, not the final complete catalog.

These definitions are chosen because they are already derivable from the main bug query and current workflow rules, which avoids extra history fan-out.

## Semantic Expansion Policy

The skill must be designed to support more than the initial four examples.

The architecture should treat export semantics as an extensible catalog with two classes:

1. **Structured high-frequency semantics**
   - Common user intents that are stable, repeated, and performance-sensitive
   - Implemented through dedicated CLI structured filters plus skill translation
   - Example: created time, updated time, team alias, open/closed state

2. **Long-tail freeform semantics**
   - Less common, more complex, or field-specific requests
   - Implemented through skill translation to raw `--where`
   - Example: product/version/feature-specific boolean expressions

New semantics must be evaluated against this rule:

- If the semantic is common, stable, and can be derived from the main bug query without extra fan-out, promote it into the structured CLI surface.
- If the semantic is rare, ambiguous, or requires flexible field logic, keep it in the skill layer and translate it to raw `--where`.
- If the semantic would require per-bug history fan-out for routine use, do not promote it into the default structured path without a separate performance review.

This keeps the architecture open for growth without forcing every new phrase into the CLI.

### Semantics intentionally not included in v1

Do not make v1 depend on per-bug history inspection for filtering. In particular:

- "有变更记录" does not mean "history contains any event in the requested period"
- "未闭环" does not mean "ever reopened" or "ever failed closure"

Those richer meanings can be added later only if there is a proven user need and the performance trade-off is accepted.

## CLI Design

### Execution commands

Keep the export entrypoints limited to:

- `bugs review-export`
- `reports build-dataset`

Do not extend the rest of the bug workflows or report bundle commands in the first release.

### Structured filter surface

Add the following structured filters to the two export commands:

- `--created-from YYYY-MM-DD`
- `--created-to YYYY-MM-DD`
- `--updated-from YYYY-MM-DD`
- `--updated-to YYYY-MM-DD`
- `--team <name-or-alias>`
- `--is-open true|false`

Do not add `--status-group` in v1. The example requests are already covered by `--is-open` plus date and team filters, and `--status-group` would push the CLI deeper into business DSL territory prematurely.

### Filter compilation rules

Structured filters are compiled into a Targetprocess `where` clause in code before querying.

The compiled clause is then merged with workflow-rule scope using existing service behavior:

- Existing `default_scope` remains mandatory
- Structured filters only narrow the scope
- Raw `--where` remains available as a fallback

The CLI must never fetch a broad result set and then apply these filters locally.

### Team parameter behavior

`--team` accepts both canonical team names and a small alias set.

For v1, the alias mapping should be local, explicit, and fixed:

- `driver` -> `ESW China NG3 Driver`
- `framework` -> `ESW China NG3 Framework`
- `ui` -> `ESW UI Team`

This avoids live schema exploration and keeps behavior deterministic.

### Open/closed behavior

`--is-open true` means `EntityState` not in the configured `workflow_rules.closed` names.

`--is-open false` means `EntityState` in the configured `workflow_rules.closed` names.

This definition must be implemented from the workflow rules file so the CLI and skill share the same state model.

## Skill Design

### Role

The skill is the end-user entrypoint. Its job is not to execute freeform Targetprocess logic directly. Its job is to:

1. Recognize supported business intents
2. Map them into structured CLI filters when the intent belongs to the structured catalog
3. Fall back to raw `--where` when the request is outside the structured catalog
4. Choose `review-export` or `build-dataset` based on the delivery need

### Command selection

Default selection should be:

- `bugs review-export` for end-user bug list exports and CSV delivery
- `reports build-dataset` only when the downstream consumer explicitly needs the reporting dataset contract

This keeps the common export path lighter and closer to the user's mental model.

### Natural-language mapping examples

- "导出 2026 年新增的 bug"
  - `review-export`
  - `--created-from 2026-01-01`
  - `--created-to 2027-01-01`

- "导出 2026 年有变更记录的 bug"
  - `review-export`
  - `--updated-from 2026-01-01`
  - `--updated-to 2027-01-01`

- "导出 Driver 组 2026 年所有的 bug"
  - `review-export`
  - `--team driver`
  - plus a time filter
  - default time interpretation should be `CreateDate` unless the user explicitly asks for changed/updated bugs

- "导出 2026 年状态未闭环的 bug"
  - `review-export`
  - `--created-from 2026-01-01`
  - `--created-to 2027-01-01`
  - `--is-open true`

### Raw fallback

Use raw `--where` only when the request cannot be expressed by the structured filters, such as:

- multiple custom field combinations
- product/version/feature-specific boolean conditions
- highly specific state or nested field logic

When the fallback is used, the skill should still preserve the same delivery conventions:

- prefer CSV for large handoff outputs
- call out that filtering still happens inside the configured workflow scope

### Adding new semantics later

When a new user-facing export phrase appears, the maintenance process should be:

1. Normalize the phrase into a candidate semantic definition.
2. Decide whether it belongs to the structured catalog or the raw fallback path.
3. If structured:
   - add or reuse a CLI structured filter
   - add skill translation coverage
   - add CLI/service tests for filter compilation
4. If raw fallback:
   - add skill translation coverage only
   - keep the core CLI surface unchanged
5. If the new semantic changes a business definition that users depend on, update the design spec and the project skill documentation.

Examples of future additions that may be promoted later if demand is high:

- customer feedback bugs
- high-risk bugs
- product-specific exports
- severity-scoped exports

## Performance Requirements

The end-user design must preserve the current performance model.

### Query path

- one main `api/v2/Bug` query path per export
- structured filters compiled into upstream `where`
- no broad fetch followed by local filtering

### History behavior

- no extra per-bug `bug_history` calls for the supported high-frequency semantics
- keep current default `BugSimpleHistory` summarization behavior for export columns
- only use `--history-mode full` when explicitly requested

### Scope behavior

- never allow structured filters or skill fallback to bypass `default_scope`
- all end-user exports stay within the project workflow rules unless a future design explicitly changes that policy

## Testing Requirements

### CLI and service

Add tests for:

- structured filter parsing on `review-export` and `build-dataset`
- filter compilation into `where`
- alias mapping for `team`
- `is_open` translation based on `workflow_rules.closed`
- coexistence of structured filters with raw `--where`
- preservation of dataset-specific select fields on `build-dataset`

### Skill behavior

Add deterministic tests or fixtures for the supported natural-language mappings:

- new bugs in year
- updated bugs in year
- driver team plus year
- open bugs in year

The tests should assert command selection and parameter translation, not just text generation.

### Performance guardrails

Add regression coverage that proves the supported high-frequency filters do not trigger per-bug history fan-out in default mode.

## Rollout Plan

### Phase 1

Add structured CLI filters to the two export commands and test them thoroughly.

### Phase 2

Add the skill translation layer for the four high-frequency semantics and their combinations.

### Phase 3

Add raw `--where` fallback routing for long-tail requests and document when fallback was used.

## Out of Scope

This design does not include:

- write or transition operations
- freeform end-user access to all workflow commands
- history-based semantic filtering in the first release
- removing raw `--where`
- cross-team or cross-project scope override beyond the configured workflow rules

## Final Recommendation

Build the end-user experience as a hybrid system:

- code the high-frequency, performance-sensitive filter semantics into the export CLI
- keep natural-language interpretation in a skill layer
- use raw `--where` only as a controlled escape hatch

This is the smallest design that is user-friendly, operationally efficient, and maintainable over time.
