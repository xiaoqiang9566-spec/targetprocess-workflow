# History Mode Design

## Implementation Status

Status as of `2026-06-03`:

- Phase 1 code changes are implemented locally.
- Non-live coverage is in place for CLI parsing, service behavior, renderer-visible output shape, benchmark helpers, and live-test entry points.
- Remaining work is live-only verification in an environment where `TP_RUN_LIVE_TESTS=1` is explicitly enabled.

## Goal

Reduce runtime cost for `bugs triage-view`, `bugs risk-scan`, and `bugs review-export` in live Targetprocess usage without removing access to full bug history when it is explicitly needed.

## Problem

The current implementation always fetches bug history for `triage-view`, `risk-scan`, and `review-export`.

In the validated live environment:

- `triage-view --limit 5` took about `21.4s`
- `triage-view --limit 10` took about `32.6s`
- `risk-scan --limit 5` took about `17.6s`
- `review-export --limit 5` took about `30.5s`
- Larger fan-out runs timed out inside the current execution window

The dominant cost is one additional history request per candidate bug.

## Decision

Add a `--history-mode` option to history-backed bug workflow commands.

- Supported values in phase 1: `off`, `full`
- Default value: `off`

Behavior:

- `off`: do not fetch per-bug history
- `full`: preserve current behavior and fetch full per-bug history for each record

This keeps the feature set intact while moving the expensive behavior behind an explicit request.

## Scope

Commands affected:

- `python -m tp_codex.cli bugs triage-view`
- `python -m tp_codex.cli bugs risk-scan`
- `python -m tp_codex.cli bugs review-export`

Commands not changed:

- `bugs intake`
- `bugs regression-queue`
- `bugs history`
- `healthcheck`
- `schema snapshot`
- `entities list`

## CLI Design

Add `--history-mode` to the three history-backed workflow subcommands only.

Allowed values:

- `off`
- `full`

Default:

- `off`

Examples:

```text
python -m tp_codex.cli bugs triage-view --format json
python -m tp_codex.cli bugs triage-view --history-mode full --format json
python -m tp_codex.cli bugs risk-scan --history-mode full --format markdown
python -m tp_codex.cli bugs review-export --history-mode off --format csv
```

## Service Design

Extend `TargetprocessService.run_workflow()` with an optional `history_mode` argument.

Rules:

- `triage-view`, `risk-scan`, and `review-export` accept `history_mode`
- other workflows ignore it
- default service behavior for history-backed workflows is `off`

In `_workflow_bugs()`:

- fetch history only when `history_mode == "full"`
- attach `record["history"]` only in `full` mode
- emit `partial_history` warnings only in `full` mode

## Output Design

When `history_mode=off`:

- records do not include `history`
- summary and signals continue to work from bug entity data
- output shape remains otherwise unchanged

When `history_mode=full`:

- records include `history`
- warnings may include `partial_history`
- behavior matches the current live-validated implementation

## Compatibility Impact

This is a behavior change for callers that currently expect `history` to always be present in these three workflows.

Mitigation:

- keep `bugs history` as the explicit single-bug detail path
- provide `--history-mode full` for callers that need the old behavior
- document the default change in README and live validation notes

## Testing Plan

Unit and integration coverage:

- parser accepts `--history-mode` for the three targeted commands
- parser does not add it to unrelated commands
- default mode is `off`
- `off` does not call history retrieval
- `full` does call history retrieval
- `partial_history` warning is only possible in `full` mode
- rendered output for `off` mode omits `history`

Live verification:

- rerun `triage-view`, `risk-scan`, and `review-export` with default mode and confirm materially lower latency
- rerun the same commands with `--history-mode full` and confirm current behavior remains available

## Alternatives Considered

### 1. Always fetch full history

Rejected because live measurements already show it does not scale acceptably for default usage.

### 2. Add separate `*-lite` commands

Rejected because it duplicates command surface and creates avoidable confusion.

### 3. Add `summary` mode in the first implementation

Deferred. It may be useful later, but `off` plus `full` solves the current performance problem with less implementation risk.

## Risks

- Existing consumers may rely on `history` always being present.
- Some downstream logic may implicitly treat missing `history` as an error.
- Documentation must clearly state the new default.

## Rollout Recommendation

Phase 1:

- implement `--history-mode off|full`
- default to `off`
- update tests and docs
- rerun live performance checks

Phase 1 local implementation is complete. The remaining rollout gate is the live rerun and documentation refresh captured in:

- `docs/live-validation-notes-2026-06-03.md`
- `docs/integration-readiness-checklist.md`

Phase 2 if needed:

- add `summary` mode
- consider caching or batching strategies if Targetprocess exposes a viable history bulk path
