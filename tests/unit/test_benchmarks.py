from tp_codex.benchmarks import (
    build_history_mode_benchmark_markdown,
    build_history_mode_benchmark_matrix,
    summarize_benchmark_result,
)


def test_history_mode_benchmark_matrix_covers_targeted_workflows_and_modes():
    matrix = build_history_mode_benchmark_matrix(limit=5)

    assert matrix == [
        {
            "workflow": "triage-view",
            "history_mode": "off",
            "argv": ["bugs", "triage-view", "--limit", "5", "--history-mode", "off", "--format", "json"],
        },
        {
            "workflow": "triage-view",
            "history_mode": "full",
            "argv": ["bugs", "triage-view", "--limit", "5", "--history-mode", "full", "--format", "json"],
        },
        {
            "workflow": "risk-scan",
            "history_mode": "off",
            "argv": ["bugs", "risk-scan", "--limit", "5", "--history-mode", "off", "--format", "json"],
        },
        {
            "workflow": "risk-scan",
            "history_mode": "full",
            "argv": ["bugs", "risk-scan", "--limit", "5", "--history-mode", "full", "--format", "json"],
        },
        {
            "workflow": "review-export",
            "history_mode": "off",
            "argv": ["bugs", "review-export", "--limit", "5", "--history-mode", "off", "--format", "json"],
        },
        {
            "workflow": "review-export",
            "history_mode": "full",
            "argv": ["bugs", "review-export", "--limit", "5", "--history-mode", "full", "--format", "json"],
        },
    ]


def test_summarize_benchmark_result_reports_history_presence_and_elapsed_ms():
    summary = summarize_benchmark_result(
        workflow="triage-view",
        history_mode="full",
        limit=5,
        elapsed_seconds=1.234,
        payload={
            "summary": {"total_records": 2},
            "warnings": ["partial_history"],
            "records": [
                {"bug_id": 101, "history": []},
                {"bug_id": 102, "history": [{"event_type": "unknown"}]},
            ],
        },
    )

    assert summary == {
        "workflow": "triage-view",
        "history_mode": "full",
        "limit": 5,
        "elapsed_ms": 1234,
        "total_records": 2,
        "warnings": ["partial_history"],
        "records_with_history": 2,
    }


def test_summarize_benchmark_result_counts_zero_history_records_in_off_mode():
    summary = summarize_benchmark_result(
        workflow="risk-scan",
        history_mode="off",
        limit=3,
        elapsed_seconds=0.5,
        payload={
            "summary": {"total_records": 1},
            "warnings": [],
            "records": [{"bug_id": 101}],
        },
    )

    assert summary == {
        "workflow": "risk-scan",
        "history_mode": "off",
        "limit": 3,
        "elapsed_ms": 500,
        "total_records": 1,
        "warnings": [],
        "records_with_history": 0,
    }


def test_build_history_mode_benchmark_markdown_formats_results_for_docs():
    markdown = build_history_mode_benchmark_markdown(
        [
            {
                "workflow": "triage-view",
                "history_mode": "off",
                "limit": 3,
                "elapsed_ms": 840,
                "total_records": 5,
                "warnings": [],
                "records_with_history": 0,
            },
            {
                "workflow": "triage-view",
                "history_mode": "full",
                "limit": 10,
                "elapsed_ms": 21400,
                "total_records": 5,
                "warnings": ["partial_history"],
                "records_with_history": 5,
            },
        ]
    )

    assert markdown == "\n".join(
        [
            "- `triage-view --history-mode off --limit 3`: about `0.84s` (`5` records, `0` with embedded history, warnings: `none`)",
            "- `triage-view --history-mode full --limit 10`: about `21.40s` (`5` records, `5` with embedded history, warnings: `partial_history`)",
        ]
    )


def test_build_history_mode_benchmark_doc_section_wraps_markdown_for_live_notes():
    from tp_codex.benchmarks import build_history_mode_benchmark_doc_section

    section = build_history_mode_benchmark_doc_section(
        [
            {
                "workflow": "triage-view",
                "history_mode": "off",
                "limit": 5,
                "elapsed_ms": 840,
                "total_records": 5,
                "warnings": [],
                "records_with_history": 0,
            }
        ]
    )

    assert section == "\n".join(
        [
            "## History Mode Benchmark Refresh",
            "",
            "- `triage-view --history-mode off --limit 5`: about `0.84s` (`5` records, `0` with embedded history, warnings: `none`)",
            "",
            "Interpretation:",
            "",
            "- `off` mode skips embedded history fan-out and should be the default path for routine workflow usage.",
            "- `full` mode remains available for callers that explicitly need per-bug history in workflow output.",
        ]
    )
