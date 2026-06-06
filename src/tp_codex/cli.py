from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from tp_codex.errors import EXIT_CODES, InvalidArgsError, TpCodexError
from tp_codex.gateway import HttpGateway
from tp_codex.report_delivery import (
    build_run_manifest,
    build_send_markdown,
    default_monthly_output_dir,
    default_weekly_output_dir,
    load_manifest,
)
from tp_codex.renderers import render_output
from tp_codex.service import TargetprocessService
from tp_codex.settings import Settings, load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tp_codex",
        description="Read-only Targetprocess QA automation toolkit",
        epilog="Workflow commands: bugs intake, bugs triage-view, bugs regression-queue, bugs risk-scan, bugs review-export",
    )
    parser.add_argument("--config", default="config/targetprocess.yaml")
    parser.add_argument("--workflow-rules", default="config/workflow_rules.yaml")

    subparsers = parser.add_subparsers(dest="command")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=["json", "markdown", "csv"], default="json")
    common.add_argument("--output")

    subparsers.add_parser("healthcheck", parents=[common])

    schema = subparsers.add_parser("schema")
    schema_sub = schema.add_subparsers(dest="schema_command")
    schema_snapshot = schema_sub.add_parser("snapshot", parents=[common])
    schema_snapshot.add_argument("--entity", required=True)

    entities = subparsers.add_parser("entities")
    entities_sub = entities.add_subparsers(dest="entities_command")
    entities_list = entities_sub.add_parser("list", parents=[common])
    entities_list.add_argument("--entity", required=True)
    entities_list.add_argument("--limit", type=int)

    reports = subparsers.add_parser("reports")
    reports_sub = reports.add_subparsers(dest="reports_command")
    build_dataset = reports_sub.add_parser("build-dataset", parents=[common])
    build_dataset.add_argument("--entity", default="Bug")
    build_dataset.add_argument("--limit", type=int)
    build_workbook = reports_sub.add_parser("build-workbook")
    build_workbook.add_argument("--entity", default="Bug")
    build_workbook.add_argument("--limit", type=int)
    build_workbook.add_argument("--format", choices=["json", "xlsx"], default="xlsx")
    build_workbook.add_argument("--output")
    weekly_report = reports_sub.add_parser("weekly-report")
    weekly_report.add_argument("--entity", default="Bug")
    weekly_report.add_argument("--limit", type=int)
    weekly_report.add_argument("--week-label")
    weekly_report.add_argument("--template")
    weekly_report.add_argument("--format", choices=["json", "xlsx"], default="xlsx")
    weekly_report.add_argument("--output")
    monthly_audit = reports_sub.add_parser("monthly-audit")
    monthly_audit.add_argument("--entity", default="Bug")
    monthly_audit.add_argument("--limit", type=int)
    monthly_audit.add_argument("--month-label")
    monthly_audit.add_argument("--format", choices=["json", "xlsx"], default="xlsx")
    monthly_audit.add_argument("--output")
    send = reports_sub.add_parser("send")
    send.add_argument("--manifest")
    send.add_argument("--format", choices=["markdown", "json"], default="markdown")
    send.add_argument("--output")
    run_weekly = reports_sub.add_parser("run-weekly")
    run_weekly.add_argument("--entity", default="Bug")
    run_weekly.add_argument("--limit", type=int)
    run_weekly.add_argument("--week-label")
    run_weekly.add_argument("--template")
    run_weekly.add_argument("--output-dir")
    run_monthly = reports_sub.add_parser("run-monthly")
    run_monthly.add_argument("--entity", default="Bug")
    run_monthly.add_argument("--limit", type=int)
    run_monthly.add_argument("--month-label")
    run_monthly.add_argument("--output-dir")

    bugs = subparsers.add_parser("bugs")
    bugs_sub = bugs.add_subparsers(dest="bugs_command")
    for name in ["intake", "triage-view", "regression-queue", "risk-scan", "review-export"]:
        cmd = bugs_sub.add_parser(name, parents=[common])
        cmd.add_argument("--entity", default="Bug")
        cmd.add_argument("--limit", type=int)
        if name in {"triage-view", "risk-scan", "review-export"}:
            cmd.add_argument("--history-mode", choices=["off", "full"], default="off")
    history = bugs_sub.add_parser("history", parents=[common])
    history.add_argument("--bug-id", required=True)

    return parser


def _resolve_service(
    settings: Optional[Settings],
    gateway,
    config_path: str,
    workflow_rules_path: str,
) -> TargetprocessService:
    if settings is None:
        settings = load_settings(Path(config_path), Path(workflow_rules_path))
    if gateway is None:
        gateway = HttpGateway(settings)
    return TargetprocessService(settings=settings, gateway=gateway)


def _write_stdout(payload: str) -> None:
    try:
        print(payload)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        text = payload.encode(encoding, errors="replace").decode(encoding)
        print(text)


def _write_output(path: Path, payload: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8")


def _render_json_payload(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _collect_warnings(*warning_groups) -> list[str]:
    merged = set()
    for warnings in warning_groups:
        for warning in warnings or []:
            merged.add(str(warning))
    return sorted(merged)


def _write_weekly_run_bundle(service: TargetprocessService, args) -> None:
    health_result = service.healthcheck()
    dataset_result = service.run_workflow("build-dataset", entity=args.entity, limit=args.limit)
    workbook_result = service.run_workflow("build-workbook", entity=args.entity, limit=args.limit)
    weekly_result = service.run_workflow(
        "weekly-report",
        entity=args.entity,
        limit=args.limit,
        filters={
            "week_label": args.week_label,
            "template_path": args.template,
        },
    )
    generated_at = str(dataset_result.metadata["generated_at"])
    output_dir = Path(args.output_dir) if args.output_dir else default_weekly_output_dir(generated_at)
    report_artifact = weekly_result.artifacts[0]
    workbook_artifact = workbook_result.artifacts[0]
    attachments = [
        {"filename": "bug_master.csv", "path": str(output_dir / "bug_master.csv")},
        {"filename": workbook_artifact.filename, "path": str(output_dir / workbook_artifact.filename)},
        {"filename": report_artifact.filename, "path": str(output_dir / report_artifact.filename)},
    ]
    warnings = _collect_warnings(dataset_result.warnings, workbook_result.warnings, weekly_result.warnings)
    manifest = build_run_manifest(
        workflow="run-weekly",
        report_kind="weekly",
        report_label=str(weekly_result.summary.get("week_label") or args.week_label),
        generated_at=generated_at,
        warnings=warnings,
        healthcheck=dict(health_result.records[0]),
        dataset_summary=dict(dataset_result.summary),
        report_summary=dict(weekly_result.summary),
        attachments=attachments,
        generated_files=[
            "healthcheck.json",
            "bug_master.json",
            "bug_master.csv",
            workbook_artifact.filename,
            report_artifact.filename,
            "send-summary.md",
            "run-metadata.json",
        ],
        output_dir=str(output_dir),
    )
    send_summary = build_send_markdown(manifest)

    _write_output(output_dir / "healthcheck.json", render_output(health_result, "json"))
    _write_output(output_dir / "bug_master.json", render_output(dataset_result, "json"))
    _write_output(output_dir / "bug_master.csv", render_output(dataset_result, "csv"))
    _write_output(output_dir / workbook_artifact.filename, render_output(workbook_result, "xlsx"))
    _write_output(output_dir / report_artifact.filename, render_output(weekly_result, "xlsx"))
    _write_output(output_dir / "send-summary.md", send_summary)
    _write_output(output_dir / "run-metadata.json", _render_json_payload(manifest))


def _write_monthly_run_bundle(service: TargetprocessService, args) -> None:
    health_result = service.healthcheck()
    dataset_result = service.run_workflow("build-dataset", entity=args.entity, limit=args.limit)
    workbook_result = service.run_workflow("build-workbook", entity=args.entity, limit=args.limit)
    monthly_result = service.run_workflow(
        "monthly-audit",
        entity=args.entity,
        limit=args.limit,
        filters={"month_label": args.month_label},
    )
    output_dir = Path(args.output_dir) if args.output_dir else default_monthly_output_dir(args.month_label)
    generated_at = str(dataset_result.metadata["generated_at"])
    report_artifact = monthly_result.artifacts[0]
    workbook_artifact = workbook_result.artifacts[0]
    attachments = [
        {"filename": "bug_master.csv", "path": str(output_dir / "bug_master.csv")},
        {"filename": workbook_artifact.filename, "path": str(output_dir / workbook_artifact.filename)},
        {"filename": report_artifact.filename, "path": str(output_dir / report_artifact.filename)},
    ]
    warnings = _collect_warnings(dataset_result.warnings, workbook_result.warnings, monthly_result.warnings)
    manifest = build_run_manifest(
        workflow="run-monthly",
        report_kind="monthly",
        report_label=str(monthly_result.summary.get("month_label") or args.month_label),
        generated_at=generated_at,
        warnings=warnings,
        healthcheck=dict(health_result.records[0]),
        dataset_summary=dict(dataset_result.summary),
        report_summary=dict(monthly_result.summary),
        attachments=attachments,
        generated_files=[
            "healthcheck.json",
            "bug_master.json",
            "bug_master.csv",
            workbook_artifact.filename,
            report_artifact.filename,
            "send-summary.md",
            "run-metadata.json",
        ],
        output_dir=str(output_dir),
    )
    send_summary = build_send_markdown(manifest)

    _write_output(output_dir / "healthcheck.json", render_output(health_result, "json"))
    _write_output(output_dir / "bug_master.json", render_output(dataset_result, "json"))
    _write_output(output_dir / "bug_master.csv", render_output(dataset_result, "csv"))
    _write_output(output_dir / workbook_artifact.filename, render_output(workbook_result, "xlsx"))
    _write_output(output_dir / report_artifact.filename, render_output(monthly_result, "xlsx"))
    _write_output(output_dir / "send-summary.md", send_summary)
    _write_output(output_dir / "run-metadata.json", _render_json_payload(manifest))


def run_cli(argv: list[str] | None = None, *, settings: Optional[Settings] = None, gateway=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return EXIT_CODES["INVALID_ARGS"]

    try:
        output_format = getattr(args, "format", None) or "json"
        if args.command == "reports" and args.reports_command == "send":
            if not args.manifest:
                raise InvalidArgsError("--manifest is required for send")
            manifest = load_manifest(args.manifest)
            payload = build_send_markdown(manifest) if output_format == "markdown" else _render_json_payload(manifest)
            if args.output:
                _write_output(Path(args.output), payload)
            else:
                _write_stdout(payload)
            return EXIT_CODES["SUCCESS"]

        service = _resolve_service(settings, gateway, args.config, args.workflow_rules)
        if args.command == "healthcheck":
            result = service.healthcheck()
        elif args.command == "schema" and args.schema_command == "snapshot":
            result = service.schema_snapshot(args.entity)
        elif args.command == "entities" and args.entities_command == "list":
            result = service.run_workflow("entities-list", entity=args.entity, limit=args.limit)
        elif args.command == "bugs" and args.bugs_command == "history":
            result = service.run_workflow("bug-history", filters={"bug_id": args.bug_id})
        elif args.command == "bugs":
            if args.bugs_command == "review-export" and output_format == "csv":
                result = service.run_workflow("build-dataset", entity=args.entity, limit=args.limit)
            else:
                result = service.run_workflow(
                    args.bugs_command,
                    entity=args.entity,
                    limit=args.limit,
                    history_mode=getattr(args, "history_mode", None),
                )
        elif args.command == "reports" and args.reports_command == "build-dataset":
            result = service.run_workflow("build-dataset", entity=args.entity, limit=args.limit)
        elif args.command == "reports" and args.reports_command == "build-workbook":
            result = service.run_workflow("build-workbook", entity=args.entity, limit=args.limit)
        elif args.command == "reports" and args.reports_command == "weekly-report":
            result = service.run_workflow(
                "weekly-report",
                entity=args.entity,
                limit=args.limit,
                filters={
                    "week_label": args.week_label,
                    "template_path": args.template,
                },
            )
        elif args.command == "reports" and args.reports_command == "monthly-audit":
            result = service.run_workflow(
                "monthly-audit",
                entity=args.entity,
                limit=args.limit,
                filters={"month_label": args.month_label},
            )
        elif args.command == "reports" and args.reports_command == "run-weekly":
            if not args.template:
                raise InvalidArgsError("--template is required for run-weekly")
            if not args.week_label:
                raise InvalidArgsError("--week-label is required for run-weekly")
            _write_weekly_run_bundle(service, args)
            return EXIT_CODES["SUCCESS"]
        elif args.command == "reports" and args.reports_command == "run-monthly":
            if not args.month_label:
                raise InvalidArgsError("--month-label is required for run-monthly")
            _write_monthly_run_bundle(service, args)
            return EXIT_CODES["SUCCESS"]
        else:
            raise InvalidArgsError("unsupported command")

        if output_format == "xlsx" and not args.output:
            raise InvalidArgsError("--output is required for xlsx")
        if args.command == "reports" and args.reports_command == "weekly-report" and output_format == "xlsx":
            if not args.template:
                raise InvalidArgsError("--template is required for weekly-report xlsx")
            if not args.week_label:
                raise InvalidArgsError("--week-label is required for weekly-report")
        if args.command == "reports" and args.reports_command == "monthly-audit" and output_format == "xlsx":
            if not args.month_label:
                raise InvalidArgsError("--month-label is required for monthly-audit")
        payload = render_output(result, output_format)
        if args.output:
            _write_output(Path(args.output), payload)
        else:
            _write_stdout(payload)
        return EXIT_CODES["SUCCESS"]
    except TpCodexError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code


def main() -> int:
    return run_cli(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
