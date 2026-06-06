# Targetprocess QA Automation Agent Notes

- Before working in this project, read and follow these project documents:
  `/Users/xiaoqiang/Documents/targetprocess/docs/codex-project-experience-playbook.md`
  `/Users/xiaoqiang/Documents/targetprocess/docs/codex-retrospective-profile.md`

- Use `python -m tp_codex.cli` as the stable entrypoint.
- Keep all workflows read-only. Do not add create, update, or transition commands.
- Prefer workflow commands for QA tasks and foundation commands for debugging and schema discovery.
- Treat `config/workflow_rules.yaml` as the source of truth for status grouping and risk thresholds.
- Live tests must remain opt-in behind `TP_RUN_LIVE_TESTS=1`.

## Project Experience

- For "pull all current bugs" or "full bug list" requests, prefer `python -m tp_codex.cli bugs review-export`. In this project, "full" means all bug records across all statuses within the configured default scope only.
- In this project, the "full bug" scope is limited to the three default teams in `config/workflow_rules.yaml`: `ESW China NG3 Driver`, `ESW China NG3 Framework`, and `ESW UI Team`.
- For "after-sales bugs" requests, use the same three-team default scope and filter to bugs tagged `customer feedback`.
- Run `python -m tp_codex.cli healthcheck --format json` before large live pulls. It confirms authentication, connectivity, and the active workflow-rule context.
- Environment variables override `config/targetprocess.yaml`. If a live command suddenly fails with `authentication failed`, check for a stale `TP_ACCESS_TOKEN` in the current session before assuming the repo config is wrong.
- Workflow commands and foundation commands behave differently. `bugs intake`, `triage-view`, `regression-queue`, `risk-scan`, and `review-export` auto-apply `default_scope` and `default_select`; `entities list` does not.
- Do not equate "all current bugs" with "only open bugs" unless the user says so. `review-export` does not filter by status, so "full bug" pulls include all statuses in the three-team default scope, and statuses not mapped in `config/workflow_rules.yaml` show up as `unmapped`.
- If the output needs to be handed back to a user, prefer CSV export with `--output` over dumping giant JSON into the conversation. The JSON payload for full review export can be extremely large.
- `bugs review-export` and direct `reports build-dataset` exports should show first-entered status timestamps by default. Their default implementation should batch-query `BugSimpleHistory` snapshots and derive those columns without exposing raw `history`.
- Only use `--history-mode full` when the caller explicitly needs embedded per-bug history details, such as sample analysis or a direct request to keep the raw history payload.
- Keep `--history-mode off` by default for `triage-view` and `risk-scan`. Their default mode should remain history-free unless the caller explicitly requests `full`.
