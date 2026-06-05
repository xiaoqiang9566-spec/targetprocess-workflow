# Live Validation Notes (2026-06-03)

This note records the first successful live validation run against the Suunto Targetprocess environment.

## Scope

- Environment: `https://suunto.tpondemand.com`
- Auth mode: `access_token`
- Live bug history smoke target: `209881`
- Record expectation: `TP_LIVE_REQUIRE_RECORDS=1`

## Commands Verified

- `pytest -m "not live"`
- `TP_RUN_LIVE_TESTS=1 pytest -m live -v`
- `TP_RUN_LIVE_TESTS=1 pytest tests/live/test_live_cli.py -v` with `TP_PAGE_SIZE=10`
- `TP_RUN_LIVE_TESTS=1 python -m pytest tests/live/test_live_cli.py -q`
- `python scripts/tp_history_mode_benchmark.py --limit 5`

## Results

- Non-live suite passed: `31 passed, 5 deselected`
- Live suite passed: `5 passed, 31 deselected`
- Live suite after pagination coverage passed: `6 passed`
- Live suite after history-mode coverage passed: `8 passed in 51.45s`
- Benchmark refresh completed for `triage-view`, `risk-scan`, and `review-export` in both `off` and `full` modes

## Important Integration Finding

- The Targetprocess `api/v1` endpoints in this environment return XML by default.
- `tp-codex` must request `format=json` for `api/v1` calls.
- `api/v2/Bug` already returns JSON without extra formatting parameters.
- `api/v2/Bug` pagination can omit `TotalCount`; page iteration must continue until a short or empty page is returned.

## Live Endpoints Confirmed

- `healthcheck`
- `schema snapshot --entity Bug`
- `entities list --entity Bug`
- `bugs history --bug-id 209881`
- `bugs intake`
- `bugs intake` with forced multi-page retrieval (`TP_PAGE_SIZE=10`, `--limit 25`)

## Workflow Calibration Snapshot

- Scope filter in active config resolves to project `Suunto work` and teams `ESW China NG3 Driver`, `ESW China NG3 Framework`, `ESW UI Team`.
- A 100-record `bugs intake` sample returned only those three teams:
  - `ESW China NG3 Driver`: 49
  - `ESW China NG3 Framework`: 39
  - `ESW UI Team`: 12
- Observed status values in that same sample:
  - `New`: 61
  - `Reproduce`: 5
  - `In Progress`: 10
  - `In Review`: 1
  - `In Testing`: 10
  - `Invalid`: 8
  - `Verified`: 1
  - `Wont fix`: 4
- Active status group mapping now aligns to those observed values:
  - `triage`: `New`, `Reproduce`
  - `in_progress`: `In Progress`, `In Review`
  - `ready_for_qa`: `In Testing`
  - `closed`: `Verified`, `Invalid`, `Wont fix`
- Custom field population in the 100-record sample:
  - `suunto_app_version`: 18
  - `suunto_app_platform`: 15
  - `firmware_version`: 40
  - `bug_category`: 13
  - `products`: 57
  - `linked_feature_ids`: 15

## History Fan-Out Measurements

- `triage-view --limit 3`: about `10.5s`
- `triage-view --limit 5`: about `21.4s`
- `triage-view --limit 10`: about `32.6s`
- `risk-scan --limit 5`: about `17.6s`
- `review-export --limit 5`: about `30.5s`
- Larger fan-out runs (`limit 20`) timed out within the current 120s execution window.

Interpretation:

- History-backed workflows are functionally correct in the live environment.
- Runtime cost grows materially with record count because each candidate bug triggers an additional history request.
- Pagination for the base bug list is verified, but history fan-out throughput still needs a product decision:
  either accept this latency, reduce default result sizes, or optimize history retrieval.

## History Mode Follow-Up

- As of `2026-06-03`, `bugs triage-view`, `bugs risk-scan`, and `bugs review-export` now support `--history-mode off|full`.
- The default mode is now `off`, which skips per-bug history fan-out for those three workflows.
- `--history-mode full` preserves the previous behavior for callers that explicitly need embedded history records.
- The live measurements above were collected before that default change, so they remain the baseline for `full` mode rather than the new default path.

## History Mode Benchmark Refresh

- `triage-view --history-mode off --limit 5`: about `3.96s` (`5` records, `0` with embedded history, warnings: `none`)
- `triage-view --history-mode full --limit 5`: about `16.19s` (`5` records, `5` with embedded history, warnings: `none`)
- `risk-scan --history-mode off --limit 5`: about `2.57s` (`3` records, `0` with embedded history, warnings: `none`)
- `risk-scan --history-mode full --limit 5`: about `28.33s` (`3` records, `3` with embedded history, warnings: `none`)
- `review-export --history-mode off --limit 5`: about `3.62s` (`5` records, `0` with embedded history, warnings: `none`)
- `review-export --history-mode full --limit 5`: about `18.33s` (`5` records, `5` with embedded history, warnings: `none`)

Interpretation:

- `off` mode skips embedded history fan-out and is materially faster for routine workflow usage.
- `full` mode remains available for callers that explicitly need per-bug history in workflow output.
- Current `full` mode timings are below the earlier pre-change baseline at `limit 5`, but still materially slower than `off`.

## History Mode Benchmark Refresh (`limit 10`)

- `triage-view --history-mode off --limit 10`: about `2.89s` (`10` records, `0` with embedded history, warnings: `none`)
- `triage-view --history-mode full --limit 10`: about `37.98s` (`10` records, `10` with embedded history, warnings: `none`)
- `risk-scan --history-mode off --limit 10`: about `2.55s` (`7` records, `0` with embedded history, warnings: `none`)
- `risk-scan --history-mode full --limit 10`: about `31.70s` (`7` records, `7` with embedded history, warnings: `none`)
- `review-export --history-mode off --limit 10`: about `2.62s` (`10` records, `0` with embedded history, warnings: `none`)
- `review-export --history-mode full --limit 10`: about `42.39s` (`10` records, `10` with embedded history, warnings: `none`)

Interpretation:

- `off` mode stays comfortably in the low-single-digit-second range even as the limit increases to `10`.
- `full` mode remains functionally correct at `limit 10`, but its latency increases into the `31s` to `42s` range.
- This is acceptable only for explicit, on-demand use where callers need embedded history and can tolerate materially slower completion.
- This is not acceptable as a default path for routine QA workflow usage.

## History Mode Benchmark Refresh (`limit 20`)

- `triage-view --history-mode off --limit 20`: about `3.33s` (`20` records, `0` with embedded history, warnings: `none`)
- `triage-view --history-mode full --limit 20`: about `67.90s` (`20` records, `20` with embedded history, warnings: `none`)
- `risk-scan --history-mode off --limit 20`: about `2.90s` (`13` records, `0` with embedded history, warnings: `none`)
- `risk-scan --history-mode full --limit 20`: about `59.60s` (`13` records, `13` with embedded history, warnings: `none`)
- `review-export --history-mode off --limit 20`: about `2.83s` (`20` records, `0` with embedded history, warnings: `none`)
- `review-export --history-mode full --limit 20`: about `68.82s` (`20` records, `20` with embedded history, warnings: `none`)

Interpretation:

- `off` mode remains effectively flat at around `3s` even when the limit increases to `20`.
- `full` mode remains within the current execution window at `limit 20`, but settles into a roughly `60s` to `69s` range.
- This confirms current timeout settings are adequate for explicit small-to-medium batch diagnostic use of `full` mode.
- This still does not make `full` suitable as a routine default path, and larger bulk use should be re-measured before adoption.

## Remaining Follow-Up

- Measure pagination and history fan-out behavior with larger live result sets only if `full` mode is expected to grow beyond small-to-medium batch diagnostics.

## Failure-Path Verification

- Automated non-live coverage now verifies that later-page entity retrieval failures surface `partial_entities`.
- Automated non-live coverage now verifies that embedded history timeouts in `--history-mode full` preserve already-fetched records and surface `partial_history`.

## Closure Status

- The previously open history-mode rerun and document backfill are now complete.
- The remaining open items are broader follow-up checks, not blockers for this phase-1 live validation refresh.
