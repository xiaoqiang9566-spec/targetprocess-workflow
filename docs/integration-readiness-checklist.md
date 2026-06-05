# Integration Readiness Checklist

This checklist defines the minimum entry conditions for connecting `tp-codex` to real Targetprocess data for read-only QA workflow validation.

## 1. Blocking Preconditions

- [x] A read-only Targetprocess credential is available for the target environment.
- [x] The target `TP_BASE_URL` is confirmed.
- [x] The authentication mode is confirmed and works with current code paths.
- [x] Local environment variables are populated from `.env.example`.
- [x] `TP_RUN_LIVE_TESTS=1` is enabled only for explicit live validation runs.

## 2. Targetprocess Baseline Validation

- [x] `python -m tp_codex.cli healthcheck --format json` succeeds against the real environment.
- [x] `python -m tp_codex.cli schema snapshot --entity Bug --format json` succeeds.
- [x] `python -m tp_codex.cli entities list --entity Bug --limit 10 --format json` succeeds.
- [x] `python -m tp_codex.cli bugs history --bug-id <real_bug_id> --format json` succeeds.
- [x] The `/api/v2/Bug` query path accepts current filter and select usage.

## 3. Workflow Rules Alignment

- [x] Real workflow state names match `status_groups` in `config/workflow_rules.yaml`.
- [x] Real severity values match `high_risk_severities`.
- [ ] `stale_days` reflects current QA expectations.
- [ ] `reopen_threshold` reflects current QA expectations.
- [x] `default_scope.project` values exist in the target instance.
- [x] `default_scope.team` values exist in the target instance.
- [x] Every field in `default_select` exists and is readable in the target instance.

## 4. Real Data Shape Validation

- [x] Real `Bug` payloads include fields needed by the normalizer: `Id`, `Name`, `EntityState` or `Status`, `Project`, `Team`, `Owner`, `Severity`, `CreateDate`, `ModifyDate`.
- [x] Real history payloads match the current normalization assumptions.
- [x] Custom fields such as `Suuntoappversion`, `Suuntoappplatform`, `Firmwareversion`, and `BugCategory` are present if they remain part of workflow output.
- [x] Linked data for `Feature`, `Products`, and `UserStory` is returned in a shape the current normalizer can consume.

## 5. Code Gaps To Close Before Live Validation Is Trusted

- [x] Replace the live placeholder test with real live coverage.
- [x] Add a live test for `healthcheck`.
- [x] Add a live test for `schema snapshot --entity Bug`.
- [x] Add a live test for `entities list --entity Bug`.
- [x] Add a live test for `bugs history --bug-id`.
- [x] Add at least one live workflow test for `bugs intake` or `bugs triage-view`.
- [x] Tighten HTTP error handling so auth failures, permission failures, query errors, and timeouts are distinguishable.

## 6. Runtime Risk Checks

- [x] Pagination is verified against a data set larger than one page.
- [x] Partial-result warnings are verified under real failure conditions.
- [x] Default `--history-mode off` latency is verified for `triage-view`, `risk-scan`, and `review-export`.
- [x] `--history-mode full` latency and behavior are explicitly accepted for callers that need embedded history.
- [x] Timeout settings are sufficient for the expected record volume.

## 7. Exit Criteria

- [x] Non-live tests pass with `pytest -m "not live"`.
- [x] Live tests pass with `TP_RUN_LIVE_TESTS=1 pytest -m live`.
- [x] At least one real workflow command returns usable QA records.
- [x] Known warnings and expected data gaps are documented.

## Recommended Execution Order

1. Obtain target environment access and read-only credentials.
2. Validate connectivity and export the real `Bug` schema.
3. Align `config/workflow_rules.yaml` to real status, scope, and field names.
4. Replace placeholder live coverage with real live tests.
5. Run non-live and live validation before using workflow outputs for QA decisions.

## History Mode Closure Command Set

Executed for the `2026-06-03` live refresh:

1. `pytest -m "not live"`
2. `TP_RUN_LIVE_TESTS=1 pytest -m live -q`
3. `python scripts/tp_history_mode_benchmark.py --limit 5`
4. Copy the generated `Doc section:` block into `docs/live-validation-notes-2026-06-03.md`
5. Mark the runtime risk items above based on the measured `off` and `full` mode results

Measured results at `--limit 5`:

- `triage-view --history-mode off`: about `3.96s`
- `triage-view --history-mode full`: about `16.19s`
- `risk-scan --history-mode off`: about `2.57s`
- `risk-scan --history-mode full`: about `28.33s`
- `review-export --history-mode off`: about `3.62s`
- `review-export --history-mode full`: about `18.33s`

Measured results at `--limit 10`:

- `triage-view --history-mode off`: about `2.89s`
- `triage-view --history-mode full`: about `37.98s`
- `risk-scan --history-mode off`: about `2.55s`
- `risk-scan --history-mode full`: about `31.70s`
- `review-export --history-mode off`: about `2.62s`
- `review-export --history-mode full`: about `42.39s`

Measured results at `--limit 20`:

- `triage-view --history-mode off`: about `3.33s`
- `triage-view --history-mode full`: about `67.90s`
- `risk-scan --history-mode off`: about `2.90s`
- `risk-scan --history-mode full`: about `59.60s`
- `review-export --history-mode off`: about `2.83s`
- `review-export --history-mode full`: about `68.82s`

Acceptance decision:

- `--history-mode full` is accepted only as an explicit, on-demand path for callers that need embedded per-bug history.
- `--history-mode off` remains the only acceptable default for routine workflow usage.
- Current timeout headroom is acceptable through `limit 20` for the intended on-demand `full` mode use case.
- This does not justify broader operational use of `full` mode for larger bulk exports without additional measurement.

Failure-path verification:

- Later-page entity retrieval timeout is covered by automated gateway tests and surfaces `partial_entities`.
- Embedded history timeout during `--history-mode full` is covered by automated workflow tests and preserves records while surfacing `partial_history`.
