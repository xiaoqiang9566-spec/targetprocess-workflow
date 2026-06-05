# targetprocess-qa

Use the read-only Targetprocess QA toolkit through stable CLI commands.

## Principles

- Never construct REST URLs manually inside the skill.
- Prefer workflow commands over raw entity queries for QA tasks.
- Keep all actions read-only.
- Start from `python -m tp_codex.cli` and let the workflow layer apply default scope and field selection.

## Workflow Map

- `healthcheck`: verify auth, connectivity, active user, and loaded workflow rules.
- `bugs intake`: read the default-scope intake queue quickly.
- `bugs triage-view`: fetch the triage-oriented view; use `--history-mode full` only when embedded bug history is explicitly needed.
- `bugs regression-queue`: fetch only records mapped into `ready_for_qa`.
- `bugs risk-scan`: return only records with risk signals after rule enrichment.
- `bugs review-export`: export the broadest workflow view for the configured scope; use this for "all current bugs" style requests inside the current project/team scope.
- `schema snapshot` and `entities list`: foundation/debug commands for schema discovery, field inspection, and workflow troubleshooting.
- `bugs history`: fetch the timeline for one bug after you already know the bug id.

## Call Chain

For workflow bug queries, the runtime path is:

`python -m tp_codex.cli` -> `src/tp_codex/cli.py` -> `TargetprocessService.run_workflow()` -> `_workflow_bugs()` -> `_merge_default_bug_filters()` -> `list_entities()` -> `HttpGateway.list_entities()` -> Targetprocess `api/v2/Bug`

Important flow details:

- `config/workflow_rules.yaml` supplies `default_scope`, `default_select`, status groups, stale threshold, reopen threshold, and high-risk severities.
- Workflow commands automatically merge `default_scope` into the `where` filter and `default_select` into the `select` projection.
- `review-export` does not narrow by status; it returns all bug records within the configured scope.
- `triage-view`, `risk-scan`, and `review-export` only fan out into per-bug history when `--history-mode full` is requested.
- `risk-scan` filters out records without `risk_signals`.
- `regression-queue` filters to normalized `status_group == ready_for_qa`.

## Recommended Retrieval Flow

When the request is "pull all current bugs" or similar:

1. Run `python -m tp_codex.cli healthcheck --format json` first.
2. Confirm auth succeeds and note the active rules scope from `config/workflow_rules.yaml`.
3. Run `python -m tp_codex.cli bugs review-export --format json` for analysis or `--format csv --output <path>` for delivery.
4. Summarize the returned `summary.total_records`, `by_status_group`, and `by_severity`.
5. Call out that "all current bugs" in this toolkit means "all bugs in the configured workflow scope", not automatically "only open bugs".

## Troubleshooting

- If a workflow command returns `authentication failed`, check whether environment variables such as `TP_ACCESS_TOKEN` are overriding `config/targetprocess.yaml`.
- In this project, environment variables take precedence over the config file. A stale session token can silently override a valid repo token.
- If healthcheck succeeds but workflow output is unexpectedly broad, verify you used a workflow command rather than `entities list`; only workflow commands auto-apply `default_scope`.
- If the user expects only open bugs, inspect `config/workflow_rules.yaml` first. Statuses not mapped into `closed` remain visible and may appear as `unmapped`.
- Expect very large `review-export --format json` payloads. Prefer `--output` with CSV for handoff and provide a compact summary in chat.
- Use `--history-mode off` unless history is explicitly required; `full` materially increases latency because it triggers one extra history request per bug.

## Suggested Commands

- Healthcheck: `python -m tp_codex.cli healthcheck --format json`
- Daily intake: `python -m tp_codex.cli bugs intake --format markdown`
- Triage view: `python -m tp_codex.cli bugs triage-view --format json`
- Regression queue: `python -m tp_codex.cli bugs regression-queue --format json`
- Risk scan: `python -m tp_codex.cli bugs risk-scan --format markdown`
- Review export: `python -m tp_codex.cli bugs review-export --format json`
- Schema snapshot: `python -m tp_codex.cli schema snapshot --entity Bug --format json`
- Bug history: `python -m tp_codex.cli bugs history --bug-id <ID> --format json`
