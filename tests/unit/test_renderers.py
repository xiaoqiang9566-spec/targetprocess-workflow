import csv
import io

from tp_codex.renderers import render_csv, render_markdown, render_output
from tp_codex.service import WorkflowArtifact, WorkflowResult


def test_render_csv_includes_review_export_business_columns():
    result = WorkflowResult(
        workflow="review-export",
        metadata={"entity": "Bug", "format_version": "1.0"},
        records=[
            {
                "bug_id": 101,
                "name": "Crash on launch",
                "status_raw": "Ready for QA",
                "status_group": "ready_for_qa",
                "severity": "High",
                "owner": "QA User",
                "updated_at": "2026-06-03T00:00:00+00:00",
                "team": "ESW UI Team",
                "suunto_app_version": "2.0.1",
                "suunto_app_platform": "Android",
                "products": ["Watch A", "Watch B"],
                "firmware_version": "FW-9.8.7",
                "reproducibility": "Always",
                "bug_category": "Regression",
                "linked_feature_ids": [501, 502],
            }
        ],
        signals=[],
        summary={"total_records": 1},
    )

    payload = render_csv(result)
    rows = list(csv.DictReader(io.StringIO(payload)))

    assert rows == [
        {
            "bug_id": "101",
            "name": "Crash on launch",
            "status_raw": "Ready for QA",
            "status_group": "ready_for_qa",
            "severity": "High",
            "owner": "QA User",
            "updated_at": "2026-06-03T00:00:00+00:00",
            "team": "ESW UI Team",
            "suunto_app_version": "2.0.1",
            "suunto_app_platform": "Android",
            "products": "Watch A; Watch B",
            "firmware_version": "FW-9.8.7",
            "reproducibility": "Always",
            "bug_category": "Regression",
            "linked_feature_ids": "501; 502",
        }
    ]


def test_render_markdown_includes_business_fields_and_risk_signals():
    result = WorkflowResult(
        workflow="risk-scan",
        metadata={"entity": "Bug", "format_version": "1.0"},
        records=[
            {
                "bug_id": 101,
                "name": "Crash on launch",
                "status_raw": "Ready for QA",
                "status_group": "ready_for_qa",
                "severity": "High",
                "owner": "QA User",
                "team": "ESW UI Team",
                "reproducibility": "Always",
                "bug_category": "Regression",
                "products": ["Watch A", "Watch B"],
                "firmware_version": "FW-9.8.7",
                "suunto_app_platform": "Android",
                "suunto_app_version": "2.0.1",
                "linked_feature_ids": [501, 502],
                "risk_signals": [
                    {"code": "high_severity", "message": "Bug severity is in the high-risk list"},
                    {"code": "missing_owner", "message": "Bug has no assigned owner"},
                ],
            }
        ],
        signals=[],
        summary={"total_records": 1},
        warnings=["partial_entities"],
    )

    payload = render_markdown(result)

    assert "# risk-scan" in payload
    assert "## Warnings" in payload
    assert "- partial_entities" in payload
    assert "### `101` Crash on launch [ready_for_qa]" in payload
    assert "- Team: ESW UI Team" in payload
    assert "- Severity: High" in payload
    assert "- Owner: QA User" in payload
    assert "- Reproducibility: Always" in payload
    assert "- Bug Category: Regression" in payload
    assert "- Products: Watch A, Watch B" in payload
    assert "- Firmware Version: FW-9.8.7" in payload
    assert "- App Platform: Android" in payload
    assert "- App Version: 2.0.1" in payload
    assert "- Linked Features: 501, 502" in payload
    assert "#### Risk Signals" in payload
    assert "- `high_severity`: Bug severity is in the high-risk list" in payload
    assert "- `missing_owner`: Bug has no assigned owner" in payload


def test_render_output_returns_xlsx_bytes_from_workflow_artifact():
    result = WorkflowResult(
        workflow="build-workbook",
        metadata={"entity": "Bug", "format_version": "1.0"},
        records=[],
        signals=[],
        summary={"total_records": 0},
        artifacts=[
            WorkflowArtifact(
                filename="quality-analysis-workbook.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                content=b"PK\x03\x04xlsx",
            )
        ],
    )

    payload = render_output(result, "xlsx")

    assert payload == b"PK\x03\x04xlsx"
