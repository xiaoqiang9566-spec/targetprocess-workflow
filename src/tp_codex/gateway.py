from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tp_codex.auth import build_auth
from tp_codex.errors import AuthFailedError, ForbiddenError, QuerySchemaError, UpstreamOrTimeoutError
from tp_codex.logging_utils import sanitize_url
from tp_codex.settings import Settings


@dataclass
class QueryResult:
    items: List[dict]
    total_count: int
    pages_completed: int = 1
    partial: bool = False


class MemoryGateway:
    def __init__(
        self,
        entities: Optional[Dict[str, List[dict]]] = None,
        history: Optional[Dict[str, List[dict]]] = None,
        schemas: Optional[Dict[str, dict]] = None,
        partial_history_ids: Optional[set] = None,
    ) -> None:
        self.entities = entities or {}
        self.history = history or {}
        self.schemas = schemas or {}
        self.partial_history_ids = partial_history_ids or set()

    def healthcheck(self) -> dict:
        return {"status": "ok", "mode": "memory"}

    def snapshot_schema(self, entity: str) -> dict:
        sample = self.entities.get(entity, [])
        return self.schemas.get(entity) or {
            "entity": entity,
            "fields": sorted(sample[0].keys()) if sample else [],
        }

    def list_entities(self, entity: str, filters: Optional[dict] = None, limit: Optional[int] = None) -> QueryResult:
        items = list(self.entities.get(entity, []))
        if limit is not None:
            items = items[:limit]
        return QueryResult(items=items, total_count=len(items))

    def bug_history(self, bug_id: str) -> tuple[list, bool]:
        return list(self.history.get(str(bug_id), [])), str(bug_id) in self.partial_history_ids


@dataclass
class HttpGateway:
    settings: Settings
    api_path_v1: str = "/api/v1"
    api_path_v2: str = "/api/v2"
    _auth: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._auth = build_auth(self.settings.auth.mode, self.settings.auth.secret)

    def _request_json(self, path: str, query: Optional[dict] = None) -> dict:
        query = {**self._auth.query_params, **(query or {})}
        if path.startswith(self.api_path_v1):
            query.setdefault("format", "json")
        url = f"{self.settings.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        request = Request(url, headers=self._auth.headers, method="GET")
        try:
            with urlopen(request, timeout=self.settings.timeout_sec) as response:
                status = getattr(response, "status", 200)
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:  # pragma: no cover - network behavior
            if exc.code == 401:
                raise AuthFailedError() from exc
            if exc.code == 403:
                raise ForbiddenError() from exc
            raise QuerySchemaError(f"request failed for {sanitize_url(url)}") from exc
        except Exception as exc:  # pragma: no cover - network behavior
            raise UpstreamOrTimeoutError(f"request failed for {sanitize_url(url)}") from exc
        if status == 401:
            raise AuthFailedError()
        if status == 403:
            raise ForbiddenError()
        if status >= 400:
            raise QuerySchemaError(f"request failed for {sanitize_url(url)}")
        return payload

    def healthcheck(self) -> dict:
        return self._request_json(f"{self.api_path_v1}/Context")

    def snapshot_schema(self, entity: str) -> dict:
        return self._request_json(f"{self.api_path_v1}/{entity}/meta")

    def list_entities(self, entity: str, filters: Optional[dict] = None, limit: Optional[int] = None) -> QueryResult:
        filters = filters or {}
        items: list[dict] = []
        total_count: Optional[int] = None
        pages_completed = 0
        skip = 0

        while True:
            remaining = None if limit is None else max(limit - len(items), 0)
            if remaining == 0:
                break

            take = min(self.settings.page_size, remaining) if remaining is not None else self.settings.page_size
            query = {"take": take, "skip": skip}
            query.update(filters)
            try:
                payload = self._request_json(f"{self.api_path_v2}/{entity}", query)
            except UpstreamOrTimeoutError:
                if pages_completed == 0:
                    raise
                return QueryResult(
                    items=items,
                    total_count=total_count or len(items),
                    pages_completed=pages_completed,
                    partial=True,
                )

            page_items = payload.get("Items") or payload.get("items") or []
            total_raw = payload.get("TotalCount")
            if total_raw is None:
                total_raw = payload.get("totalCount")
            if total_raw is not None:
                total_count = total_raw
            items.extend(page_items)
            pages_completed += 1
            skip += len(page_items)

            if not page_items:
                break
            if total_count is not None and len(items) >= total_count:
                break
            if limit is not None and len(items) >= limit:
                break
            if len(page_items) < take:
                break

        return QueryResult(items=items, total_count=total_count or len(items), pages_completed=pages_completed)

    def bug_history(self, bug_id: str) -> tuple[list, bool]:
        payload = self._request_json(f"{self.api_path_v1}/Bugs/{bug_id}/History")
        items = payload.get("Items") or payload.get("items") or payload
        return items, False
