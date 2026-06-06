from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from tp_codex.artifacts import WorkflowArtifact
from tp_codex.datasets import (
    BUG_DATASET_SELECT_FIELDS,
    build_bug_dataset_fieldnames,
    build_bug_dataset_records,
    build_review_export_fieldnames,
    format_bug_report_timestamps,
    summarize_bug_history,
)
from tp_codex.errors import UpstreamOrTimeoutError
from tp_codex.history import get_bug_history, get_bug_simple_history_batch
from tp_codex.monthly_audits import (
    MONTHLY_AUDIT_SHEET_NAMES,
    build_monthly_audit_candidates,
    build_monthly_audit_summary,
    build_monthly_audit_workbook_artifact,
    resolve_month_label,
)
from tp_codex.normalizers import normalize_bug
from tp_codex.queries import list_entities
from tp_codex.rules import WorkflowRulesEngine
from tp_codex.schema import snapshot_entity_schema
from tp_codex.settings import Settings
from tp_codex.weekly_reports import build_weekly_report_artifact, build_weekly_report_summary
from tp_codex.workbooks import QUALITY_WORKBOOK_SHEET_NAMES, build_quality_workbook_artifact


@dataclass
class WorkflowResult:
    workflow: str
    metadata: Dict[str, object]
    records: List[dict]
    signals: List[dict]
    summary: Dict[str, object]
    warnings: List[str] = field(default_factory=list)
    artifacts: List[WorkflowArtifact] = field(default_factory=list)


class TargetprocessService:
    def __init__(self, settings: Settings, gateway) -> None:
        self.settings = settings
        self.gateway = gateway
        self.rules = WorkflowRulesEngine(settings.workflow_rules)

    def healthcheck(self) -> WorkflowResult:
        payload = dict(self.gateway.healthcheck())
        payload["workflow_rules"] = self._workflow_rules_summary()
        return WorkflowResult(
            workflow="healthcheck",
            metadata=self._metadata("Context", {}),
            records=[payload],
            signals=[],
            summary={"total_records": 1},
        )

    def schema_snapshot(self, entity: str) -> WorkflowResult:
        payload = snapshot_entity_schema(self.gateway, entity)
        return WorkflowResult(
            workflow="schema-snapshot",
            metadata=self._metadata(entity, {}),
            records=[payload],
            signals=[],
            summary={"total_records": 1},
        )

    def run_workflow(
        self,
        workflow: str,
        entity: str = "Bug",
        filters: Optional[dict] = None,
        limit: Optional[int] = None,
        history_mode: Optional[str] = None,
    ) -> WorkflowResult:
        if workflow == "entities-list":
            return self._entities_list(entity, filters, limit)
        if workflow == "bug-history":
            bug_id = str(filters["bug_id"])
            return self._bug_history(bug_id)
        if workflow == "build-dataset":
            return self._build_dataset(entity, filters, limit, history_mode=history_mode, include_status_timestamps=True)
        if workflow == "build-workbook":
            return self._build_workbook(entity, filters, limit)
        if workflow == "weekly-report":
            return self._weekly_report(entity, filters, limit)
        if workflow == "monthly-audit":
            return self._monthly_audit(entity, filters, limit)
        if workflow in {"intake", "triage-view", "regression-queue", "risk-scan", "review-export"}:
            return self._workflow_bugs(workflow, entity, filters, limit, history_mode=history_mode)
        raise ValueError(f"unsupported workflow '{workflow}'")

    def _entities_list(self, entity: str, filters: Optional[dict], limit: Optional[int]) -> WorkflowResult:
        query = list_entities(self.gateway, entity, filters=filters, limit=limit)
        records = [normalize_bug(item, self.settings.base_url) for item in query.items]
        records = [self.rules.enrich_record(record) for record in records]
        warnings = ["partial_entities"] if query.partial else []
        return self._result("entities-list", entity, filters, records, warnings, query.total_count)

    def _bug_history(self, bug_id: str) -> WorkflowResult:
        history, partial = get_bug_history(self.gateway, bug_id)
        warnings = ["partial_history"] if partial else []
        return WorkflowResult(
            workflow="bug-history",
            metadata=self._metadata("Bug", {"bug_id": bug_id}),
            records=history,
            signals=[],
            summary={"total_records": len(history)},
            warnings=warnings,
        )

    def _workflow_bugs(
        self,
        workflow: str,
        entity: str,
        filters: Optional[dict],
        limit: Optional[int],
        history_mode: Optional[str] = None,
    ) -> WorkflowResult:
        filters = self._merge_default_bug_filters(filters)
        query = list_entities(self.gateway, entity, filters=filters, limit=limit)
        warnings: list[str] = ["partial_entities"] if query.partial else []
        include_history = workflow in {"triage-view", "risk-scan", "review-export"} and (history_mode or "off") == "full"
        summarize_history = workflow == "review-export"
        records = []
        for item in query.items:
            normalized = self.rules.enrich_record(normalize_bug(item, self.settings.base_url))
            if summarize_history and include_history:
                try:
                    history, partial = get_bug_history(self.gateway, str(normalized["bug_id"]))
                except UpstreamOrTimeoutError:
                    history = []
                    partial = True
                normalized = summarize_bug_history(normalized, history, include_history=include_history)
                if partial:
                    warnings.append("partial_history")
            elif include_history:
                try:
                    history, partial = get_bug_history(self.gateway, str(normalized["bug_id"]))
                except UpstreamOrTimeoutError:
                    history = []
                    partial = True
                normalized["history"] = history
                if partial:
                    warnings.append("partial_history")
            if workflow == "regression-queue" and normalized["status_group"] != "ready_for_qa":
                continue
            if workflow == "risk-scan" and not normalized["risk_signals"]:
                continue
            records.append(normalized)
        if summarize_history and not include_history:
            records, partial = self._summarize_records_with_bug_simple_history(records, recompute_reopen_count=False)
            if partial:
                warnings.append("partial_history")
        if workflow == "review-export":
            records = [format_bug_report_timestamps(record) for record in records]
        result = self._result(workflow, entity, filters, records, warnings, query.total_count)
        if workflow == "review-export":
            result.metadata["csv_fieldnames"] = build_review_export_fieldnames(records)
            result.metadata["history_mode"] = history_mode or "off"
        return result

    def _build_dataset(
        self,
        entity: str,
        filters: Optional[dict],
        limit: Optional[int],
        history_mode: Optional[str] = None,
        include_status_timestamps: bool = False,
    ) -> WorkflowResult:
        dataset_filters = dict(filters or {})
        dataset_filters["select"] = self._format_select(BUG_DATASET_SELECT_FIELDS)
        dataset_filters = self._merge_default_bug_filters(dataset_filters)
        query = list_entities(self.gateway, entity, filters=dataset_filters, limit=limit)
        warnings: list[str] = ["partial_entities"] if query.partial else []
        include_history = (history_mode or "off") == "full"
        base_records = []
        for item in query.items:
            normalized = self.rules.enrich_record(normalize_bug(item, self.settings.base_url))
            if include_status_timestamps:
                if include_history:
                    try:
                        history, partial = get_bug_history(self.gateway, str(normalized["bug_id"]))
                    except UpstreamOrTimeoutError:
                        history = []
                        partial = True
                    normalized["history"] = history
                    if partial:
                        warnings.append("partial_history")
            base_records.append(normalized)
        if include_status_timestamps and not include_history:
            base_records, partial = self._summarize_records_with_bug_simple_history(base_records, recompute_reopen_count=True)
            if partial:
                warnings.append("partial_history")
        records = build_bug_dataset_records(base_records, self.settings.workflow_rules, datetime.now(timezone.utc))
        signals: list[dict] = []
        for record in records:
            signals.extend(record.get("risk_signals", []))
        summary = {
            "total_records": len(records),
            "source_total_records": query.total_count,
            "by_status_group": self._count_by(records, "status_group"),
            "by_severity": self._count_by(records, "severity"),
            "by_risk_level": self._count_by(records, "risk_level"),
            "by_team": self._count_by(records, "team"),
            "customer_feedback_records": sum(1 for record in records if record.get("is_customer_feedback")),
        }
        metadata = self._metadata(entity, dataset_filters or {})
        metadata["csv_fieldnames"] = build_bug_dataset_fieldnames(records)
        metadata["dataset_version"] = "1.1" if include_status_timestamps else "1.0"
        metadata["history_mode"] = history_mode or "off"
        return WorkflowResult(
            workflow="build-dataset",
            metadata=metadata,
            records=records,
            signals=self._dedupe_signals(signals),
            summary=summary,
            warnings=sorted(set(warnings)),
        )

    def _summarize_records_with_bug_simple_history(
        self,
        records: List[dict],
        *,
        recompute_reopen_count: bool,
    ) -> tuple[List[dict], bool]:
        histories_by_bug_id, partial = get_bug_simple_history_batch(
            self.gateway,
            [record.get("bug_id") for record in records],
        )
        summarized_records = [
            summarize_bug_history(
                record,
                histories_by_bug_id.get(str(record.get("bug_id")), []),
                include_history=False,
                recompute_reopen_count=recompute_reopen_count,
            )
            for record in records
        ]
        return summarized_records, partial

    def _build_workbook(self, entity: str, filters: Optional[dict], limit: Optional[int]) -> WorkflowResult:
        dataset_result = self._build_dataset(entity, filters, limit)
        workbook_artifact = build_quality_workbook_artifact(
            dataset_result.records,
            self.settings.workflow_rules,
            metadata=dataset_result.metadata,
            warnings=dataset_result.warnings,
        )
        metadata = dict(dataset_result.metadata)
        metadata["sheet_names"] = list(QUALITY_WORKBOOK_SHEET_NAMES)
        metadata["workbook_filename"] = workbook_artifact.filename
        summary = dict(dataset_result.summary)
        summary["sheet_count"] = len(QUALITY_WORKBOOK_SHEET_NAMES)
        return WorkflowResult(
            workflow="build-workbook",
            metadata=metadata,
            records=[],
            signals=dataset_result.signals,
            summary=summary,
            warnings=dataset_result.warnings,
            artifacts=[workbook_artifact],
        )

    def _weekly_report(self, entity: str, filters: Optional[dict], limit: Optional[int]) -> WorkflowResult:
        filters = dict(filters or {})
        week_label = str(filters.pop("week_label", "") or "")
        template_path = str(filters.pop("template_path", "") or "")
        dataset_result = self._build_dataset(entity, filters or None, limit)
        summary = build_weekly_report_summary(
            dataset_result.records,
            week_label=week_label,
            generated_at=str(dataset_result.metadata["generated_at"]),
        )
        metadata = dict(dataset_result.metadata)
        metadata["week_label"] = summary["week_label"]
        metadata["sheet_name"] = summary["sheet_name"]
        records = [{"product": key, **value} for key, value in summary["by_product"].items()]
        artifacts: list[WorkflowArtifact] = []
        if template_path:
            workbook_artifact = build_weekly_report_artifact(
                dataset_result.records,
                week_label=week_label,
                template_path=template_path,
                generated_at=str(dataset_result.metadata["generated_at"]),
            )
            artifacts.append(workbook_artifact)
            metadata["workbook_filename"] = workbook_artifact.filename
        return WorkflowResult(
            workflow="weekly-report",
            metadata=metadata,
            records=records,
            signals=dataset_result.signals,
            summary=summary,
            warnings=dataset_result.warnings,
            artifacts=artifacts,
        )

    def _monthly_audit(self, entity: str, filters: Optional[dict], limit: Optional[int]) -> WorkflowResult:
        filters = dict(filters or {})
        month_label = resolve_month_label(str(filters.pop("month_label", "") or ""))
        dataset_result = self._build_dataset(entity, filters or None, limit)
        summary = build_monthly_audit_summary(
            dataset_result.records,
            month_label=month_label,
            workflow_rules=self.settings.workflow_rules,
        )
        candidates, candidate_warnings = build_monthly_audit_candidates(
            dataset_result.records,
            workflow_rules=self.settings.workflow_rules,
            history_loader=lambda bug_id: get_bug_history(self.gateway, str(bug_id)),
        )
        warnings = sorted(set(dataset_result.warnings + candidate_warnings))
        workbook_artifact = build_monthly_audit_workbook_artifact(
            dataset_result.records,
            candidates,
            summary,
            month_label=month_label,
            generated_at=str(dataset_result.metadata["generated_at"]),
            workflow_rules=self.settings.workflow_rules,
            warnings=warnings,
        )
        metadata = dict(dataset_result.metadata)
        metadata["month_label"] = month_label
        metadata["sheet_names"] = list(MONTHLY_AUDIT_SHEET_NAMES)
        metadata["workbook_filename"] = workbook_artifact.filename
        return WorkflowResult(
            workflow="monthly-audit",
            metadata=metadata,
            records=candidates,
            signals=dataset_result.signals,
            summary=summary,
            warnings=warnings,
            artifacts=[workbook_artifact],
        )

    def _result(self, workflow: str, entity: str, filters: Optional[dict], records: List[dict], warnings: List[str], total_count: int) -> WorkflowResult:
        warnings = sorted(set(warnings))
        signals = []
        for record in records:
            signals.extend(record.get("risk_signals", []))
        summary = {
            "total_records": len(records),
            "source_total_records": total_count,
            "by_status_group": self._count_by(records, "status_group"),
            "by_severity": self._count_by(records, "severity"),
        }
        return WorkflowResult(
            workflow=workflow,
            metadata=self._metadata(entity, filters or {}),
            records=records,
            signals=self._dedupe_signals(signals),
            summary=summary,
            warnings=warnings,
        )

    def _merge_default_bug_filters(self, filters: Optional[dict]) -> Optional[dict]:
        merged: Dict[str, object] = {}
        scope_where = self._default_scope_where()
        if scope_where:
            merged["where"] = scope_where
        if self.settings.workflow_rules.default_select:
            merged["select"] = self._format_select(self.settings.workflow_rules.default_select)
        if filters:
            filters = dict(filters)
            explicit_where = filters.pop("where", None)
            if explicit_where and merged.get("where"):
                merged["where"] = f'({merged["where"]}) and ({explicit_where})'
            elif explicit_where:
                merged["where"] = explicit_where
            merged.update(filters)
        return merged or None

    @staticmethod
    def _format_select(fields: List[str]) -> str:
        return "{" + ",".join(fields) + "}"

    def _default_scope_where(self) -> Optional[str]:
        clauses: List[str] = []
        for key, values in self.settings.workflow_rules.default_scope.items():
            field = self._scope_field(key)
            if not field or not values:
                continue
            comparisons = [f'{field} == "{self._escape_where_value(value)}"' for value in values]
            if len(comparisons) == 1:
                clauses.append(comparisons[0])
            else:
                clauses.append("(" + " or ".join(comparisons) + ")")
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return " and ".join(f"({clause})" for clause in clauses)

    @staticmethod
    def _scope_field(key: str) -> Optional[str]:
        mapping = {
            "project": "Project.Name",
            "team": "Team.Name",
        }
        return mapping.get(key)

    @staticmethod
    def _escape_where_value(value: str) -> str:
        return str(value).replace('"', '\\"')

    def _metadata(self, entity: str, filters: Dict[str, object]) -> Dict[str, object]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "base_url": self.settings.base_url,
            "entity": entity,
            "filters": filters,
            "format_version": "1.0",
            "auth_mode": self.settings.auth.mode,
            "rules_version": "workflow_rules.yaml",
        }

    def _workflow_rules_summary(self) -> Dict[str, object]:
        return {
            "status_groups": self.settings.workflow_rules.status_groups,
            "high_risk_severities": self.settings.workflow_rules.high_risk_severities,
            "stale_days": self.settings.workflow_rules.stale_days,
            "reopen_threshold": self.settings.workflow_rules.reopen_threshold,
            "default_scope": self.settings.workflow_rules.default_scope,
            "default_select": self.settings.workflow_rules.default_select,
        }

    @staticmethod
    def _count_by(records: List[dict], key: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for record in records:
            value = str(record.get(key) or "null")
            counts[value] = counts.get(value, 0) + 1
        return counts

    @staticmethod
    def _dedupe_signals(signals: List[dict]) -> List[dict]:
        seen = set()
        result = []
        for signal in signals:
            key = signal["code"]
            if key in seen:
                continue
            seen.add(key)
            result.append(signal)
        return result
