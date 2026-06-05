from __future__ import annotations

import csv
import io
import json
from tp_codex.service import WorkflowResult


def render_json(result: WorkflowResult) -> str:
    return json.dumps(_result_payload(result), ensure_ascii=False, indent=2)


def render_markdown(result: WorkflowResult) -> str:
    lines = [
        f"# {result.workflow}",
        "",
        f"- Records: {result.summary['total_records']}",
        f"- Entity: {result.metadata['entity']}",
        f"- Format version: {result.metadata['format_version']}",
        "",
    ]
    if result.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend([f"- {warning}" for warning in result.warnings])
        lines.append("")
    lines.extend(["## Records", ""])
    for record in result.records:
        lines.append(f"### `{record['bug_id']}` {record['name']} [{record['status_group']}]")
        lines.append("")
        lines.extend(_markdown_record_lines(record))
        risk_signals = record.get("risk_signals") or []
        if risk_signals:
            lines.extend(["", "#### Risk Signals", ""])
            for signal in risk_signals:
                lines.append(f"- `{signal['code']}`: {signal['message']}")
        lines.append("")
    return "\n".join(lines)


def render_csv(result: WorkflowResult) -> str:
    output = io.StringIO()
    fieldnames = result.metadata.get("csv_fieldnames") or [
        "bug_id",
        "name",
        "status_raw",
        "status_group",
        "severity",
        "owner",
        "updated_at",
        "team",
        "suunto_app_version",
        "suunto_app_platform",
        "products",
        "firmware_version",
        "reproducibility",
        "bug_category",
        "linked_feature_ids",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for record in result.records:
        writer.writerow({name: _csv_value(record.get(name)) for name in fieldnames})
    return output.getvalue()


def render_output(result: WorkflowResult, output_format: str) -> str | bytes:
    if output_format == "json":
        return render_json(result)
    if output_format == "markdown":
        return render_markdown(result)
    if output_format == "csv":
        return render_csv(result)
    if output_format == "xlsx":
        return render_xlsx(result)
    raise ValueError(f"unsupported output format: {output_format}")


def _csv_value(value):
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _markdown_record_lines(record: dict) -> list[str]:
    fields = [
        ("Team", record.get("team")),
        ("Severity", record.get("severity")),
        ("Owner", record.get("owner")),
        ("Reproducibility", record.get("reproducibility")),
        ("Bug Category", record.get("bug_category")),
        ("Products", _markdown_value(record.get("products"))),
        ("Firmware Version", record.get("firmware_version")),
        ("App Platform", record.get("suunto_app_platform")),
        ("App Version", record.get("suunto_app_version")),
        ("Linked Features", _markdown_value(record.get("linked_feature_ids"))),
    ]
    return [f"- {label}: {value}" for label, value in fields if value not in (None, "", [])]


def _markdown_value(value):
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return value


def render_xlsx(result: WorkflowResult) -> bytes:
    for artifact in result.artifacts:
        if artifact.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            return artifact.content
    raise ValueError("no xlsx artifact available")


def _result_payload(result: WorkflowResult) -> dict:
    return {
        "workflow": result.workflow,
        "metadata": result.metadata,
        "records": result.records,
        "signals": result.signals,
        "summary": result.summary,
        "warnings": result.warnings,
        "artifacts": [
            {
                "filename": artifact.filename,
                "media_type": artifact.media_type,
                "size_bytes": len(artifact.content),
            }
            for artifact in result.artifacts
        ],
    }
