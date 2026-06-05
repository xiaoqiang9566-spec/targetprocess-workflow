from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Sequence

from tp_codex.errors import OutputIoError


def build_run_manifest(
    *,
    workflow: str,
    report_kind: str,
    report_label: str,
    generated_at: str,
    warnings: Sequence[str],
    healthcheck: dict,
    dataset_summary: dict,
    report_summary: dict,
    attachments: Sequence[dict],
    output_dir: str,
    generated_files: Sequence[str] | None = None,
) -> dict:
    return {
        "workflow": workflow,
        "report_kind": report_kind,
        "report_label": report_label,
        "generated_at": generated_at,
        "warnings": list(warnings),
        "healthcheck": dict(healthcheck),
        "dataset_summary": dict(dataset_summary),
        "report_summary": dict(report_summary),
        "attachments": [dict(item) for item in attachments],
        "generated_files": list(generated_files or []),
        "output_dir": output_dir,
    }


def build_send_markdown(manifest: dict) -> str:
    report_kind = str(manifest.get("report_kind") or "")
    if report_kind == "weekly":
        return _build_weekly_send_markdown(manifest)
    if report_kind == "monthly":
        return _build_monthly_send_markdown(manifest)
    raise ValueError(f"unsupported report kind: {report_kind}")


def load_manifest(path: str | Path) -> dict:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise OutputIoError(f"send manifest not found: {manifest_path}")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OutputIoError(f"send manifest is not valid json: {manifest_path}") from exc


def default_weekly_output_dir(generated_at: str) -> Path:
    generated = datetime.fromisoformat(generated_at)
    return Path("outputs") / "reports" / "weekly" / generated.date().isoformat()


def default_monthly_output_dir(month_label: str) -> Path:
    return Path("outputs") / "reports" / "monthly" / str(month_label)


def _build_weekly_send_markdown(manifest: dict) -> str:
    summary = dict(manifest.get("report_summary") or {})
    by_product = dict(summary.get("by_product") or {})
    lines = [
        f"# 质量周报 {manifest.get('report_label')}",
        "",
        f"- 生成时间：{manifest.get('generated_at')}",
        f"- 总记录数：{summary.get('total_records', manifest.get('dataset_summary', {}).get('total_records', 0))}",
        f"- 本周新增：{summary.get('weekly_new_records', 0)}",
    ]
    if _has_incomplete_warnings(manifest.get("warnings") or []):
        lines.append(f"- 数据完整性：本次数据不完整（{', '.join(manifest.get('warnings') or [])}）")
    if by_product:
        lines.extend(["", "## 产品分布", ""])
        for product, stats in by_product.items():
            lines.append(
                f"- {product}：累计{stats.get('total_records', 0)}，本周新增{stats.get('weekly_new_records', 0)}，售后{stats.get('customer_feedback_records', 0)}，高风险{stats.get('high_risk_records', 0)}"
            )
    lines.extend(_attachment_section(manifest.get("attachments") or []))
    return "\n".join(lines)


def _build_monthly_send_markdown(manifest: dict) -> str:
    summary = dict(manifest.get("report_summary") or {})
    lines = [
        f"# 月度 Bug 审计 {manifest.get('report_label')}",
        "",
        f"- 生成时间：{manifest.get('generated_at')}",
        f"- 总记录数：{summary.get('total_records', manifest.get('dataset_summary', {}).get('total_records', 0))}",
        f"- 当月新增：{summary.get('created_count', 0)}",
        f"- 候选风险：{summary.get('candidate_risk_records', 0)}",
        f"- 高风险：{summary.get('high_risk_records', 0)}",
        f"- 售后问题：{summary.get('customer_feedback_records', 0)}",
        f"- 未映射状态：{summary.get('unmapped_status_records', 0)}",
        f"- 60+ 老化：{summary.get('aging_60_plus_records', 0)}",
    ]
    if _has_incomplete_warnings(manifest.get("warnings") or []):
        lines.append(f"- 数据完整性：本次数据不完整（{', '.join(manifest.get('warnings') or [])}）")
    lines.extend(_attachment_section(manifest.get("attachments") or []))
    return "\n".join(lines)


def _attachment_section(attachments: Sequence[dict]) -> list[str]:
    lines = ["", "## 建议附件", ""]
    if attachments:
        for item in attachments:
            lines.append(f"- {item.get('filename')}")
    else:
        lines.append("- 无")
    return lines


def _has_incomplete_warnings(warnings: Sequence[str]) -> bool:
    codes = set(str(item) for item in warnings)
    return bool({"partial_entities", "partial_history"} & codes)
