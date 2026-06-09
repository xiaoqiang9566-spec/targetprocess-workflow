import json

from tp_codex.report_delivery import build_run_manifest, build_send_markdown


def test_build_send_markdown_renders_weekly_summary_with_partial_warning():
    manifest = build_run_manifest(
        workflow="run-weekly",
        report_kind="weekly",
        report_label="Week23",
        generated_at="2026-06-05T08:00:00+00:00",
        warnings=["partial_entities", "partial_history"],
        healthcheck={"status": "ok"},
        dataset_summary={"total_records": 10},
        report_summary={
            "week_label": "Week23",
            "total_records": 10,
            "weekly_new_records": 3,
            "by_product": {
                "NG3": {
                    "total_records": 4,
                    "weekly_new_records": 2,
                    "customer_feedback_records": 1,
                    "high_risk_records": 1,
                },
                "Dilu": {
                    "total_records": 2,
                    "weekly_new_records": 1,
                    "customer_feedback_records": 0,
                    "high_risk_records": 1,
                },
            },
        },
        attachments=[
            {"filename": "weekly_new_bug_master.csv"},
            {"filename": "full_bug_snapshot.csv"},
            {"filename": "质量周报-Week23(2026.6.1-2026.6.7).xlsx"},
        ],
        output_dir="outputs/reports/weekly/2026-W23",
    )

    payload = build_send_markdown(manifest)

    assert "Week23" in payload
    assert "本次数据不完整" in payload
    assert "总记录数：10" in payload
    assert "本周新增：3" in payload
    assert "NG3" in payload
    assert "Dilu" in payload
    assert "质量周报-Week23(2026.6.1-2026.6.7).xlsx" in payload


def test_build_send_markdown_renders_monthly_summary():
    manifest = build_run_manifest(
        workflow="run-monthly",
        report_kind="monthly",
        report_label="2026-06",
        generated_at="2026-06-30T10:00:00+00:00",
        warnings=[],
        healthcheck={"status": "ok"},
        dataset_summary={"total_records": 20},
        report_summary={
            "month_label": "2026-06",
            "total_records": 20,
            "created_count": 5,
            "candidate_risk_records": 4,
            "high_risk_records": 3,
            "customer_feedback_records": 2,
            "unmapped_status_records": 1,
            "aging_60_plus_records": 2,
        },
        attachments=[
            {"filename": "bug_master.csv"},
            {"filename": "monthly-audit-2026-06.xlsx"},
        ],
        output_dir="outputs/reports/monthly/2026-06",
    )

    payload = build_send_markdown(manifest)

    assert "2026-06" in payload
    assert "当月新增：5" in payload
    assert "候选风险：4" in payload
    assert "高风险：3" in payload
    assert "售后问题：2" in payload
    assert "未映射状态：1" in payload
    assert "monthly-audit-2026-06.xlsx" in payload


def test_build_run_manifest_keeps_core_fields():
    manifest = build_run_manifest(
        workflow="run-weekly",
        report_kind="weekly",
        report_label="Week23",
        generated_at="2026-06-05T08:00:00+00:00",
        warnings=["partial_entities"],
        healthcheck={"status": "ok"},
        dataset_summary={"total_records": 10},
        report_summary={"week_label": "Week23"},
        attachments=[{"filename": "bug_master.csv"}],
        output_dir="outputs/reports/weekly/2026-06-05",
    )

    payload = json.loads(json.dumps(manifest, ensure_ascii=False))

    assert payload["workflow"] == "run-weekly"
    assert payload["report_kind"] == "weekly"
    assert payload["report_label"] == "Week23"
    assert payload["warnings"] == ["partial_entities"]
    assert payload["attachments"][0]["filename"] == "bug_master.csv"
