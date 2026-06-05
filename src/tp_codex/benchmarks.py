from __future__ import annotations


def build_history_mode_benchmark_matrix(limit: int) -> list[dict]:
    matrix: list[dict] = []
    for workflow in ["triage-view", "risk-scan", "review-export"]:
        for history_mode in ["off", "full"]:
            matrix.append(
                {
                    "workflow": workflow,
                    "history_mode": history_mode,
                    "argv": [
                        "bugs",
                        workflow,
                        "--limit",
                        str(limit),
                        "--history-mode",
                        history_mode,
                        "--format",
                        "json",
                    ],
                }
            )
    return matrix


def summarize_benchmark_result(
    *,
    workflow: str,
    history_mode: str,
    limit: int,
    elapsed_seconds: float,
    payload: dict,
) -> dict:
    records = payload.get("records") or []
    return {
        "workflow": workflow,
        "history_mode": history_mode,
        "limit": limit,
        "elapsed_ms": int(round(elapsed_seconds * 1000)),
        "total_records": int((payload.get("summary") or {}).get("total_records") or 0),
        "warnings": list(payload.get("warnings") or []),
        "records_with_history": sum(1 for record in records if "history" in record),
    }


def build_history_mode_benchmark_markdown(summaries: list[dict]) -> str:
    lines: list[str] = []
    for summary in summaries:
        warning_text = ", ".join(summary["warnings"]) if summary["warnings"] else "none"
        lines.append(
            f"- `{summary['workflow']} --history-mode {summary['history_mode']} --limit {summary['limit']}`: "
            f"about `{summary['elapsed_ms'] / 1000:.2f}s` "
            f"(`{summary['total_records']}` records, "
            f"`{summary['records_with_history']}` with embedded history, "
            f"warnings: `{warning_text}`)"
        )
    return "\n".join(lines)


def build_history_mode_benchmark_doc_section(summaries: list[dict]) -> str:
    return "\n".join(
        [
            "## History Mode Benchmark Refresh",
            "",
            build_history_mode_benchmark_markdown(summaries),
            "",
            "Interpretation:",
            "",
            "- `off` mode skips embedded history fan-out and should be the default path for routine workflow usage.",
            "- `full` mode remains available for callers that explicitly need per-bug history in workflow output.",
        ]
    )
