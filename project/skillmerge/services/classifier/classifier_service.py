from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from ...util.errors import CancelledError, DomainError
from ..ai_client import AIClient
from .ai_review import review
from .rules import classify_text
from .taxonomy import merge_categories


class ClassifierService:
    def __init__(self, db, config) -> None:
        self.db = db
        self.config = config

    def _rows(self, skill_ids: Optional[List[str]]) -> List[Dict[str, Any]]:
        rows = [dict(row) for row in self.db.query_all("SELECT * FROM skills WHERE missing=0")]
        if not skill_ids:
            return rows
        wanted = {str(item) for item in skill_ids}
        selected = [row for row in rows if str(row["id"]) in wanted]
        if not selected:
            raise DomainError("INVALID_ARGUMENT", "skill_ids 全部不存在", "先扫描并选择有效技能", 400)
        return selected

    def _update(self, updates: List[tuple]) -> None:
        if not updates:
            return
        with self.db.write_tx() as conn:
            conn.executemany(
                "UPDATE skills SET category=?, category_source=?, confidence=? "
                "WHERE id=? AND category_source != 'manual'",
                updates,
            )

    def classify(
        self,
        skill_ids: Optional[List[str]] = None,
        use_ai: bool = False,
        confirm_ai: bool = False,
        ai_client=None,
        progress=None,
        cancel_token=None,
    ) -> Dict[str, Any]:
        if use_ai and not confirm_ai:
            raise DomainError("AI_NOT_CONFIRMED", "发送技能文本给 AI 前必须确认", "传 confirm_ai=true", 400)
        rows = self._rows(skill_ids)
        manual = [row for row in rows if str(row["category_source"]) == "manual"]
        targets = [row for row in rows if str(row["category_source"]) != "manual"]
        categories = merge_categories(self.config)
        keyword_updates = []
        keyword_results = {}
        for index, row in enumerate(targets):
            if cancel_token is not None and cancel_token.is_set():
                raise CancelledError()
            result = classify_text(str(row.get("name", "")), str(row.get("description", "")), self.config)
            keyword_results[str(row["id"])] = result
            keyword_updates.append(
                (result["category"], "keyword", float(result["confidence"]), str(row["id"]))
            )
            if progress and (index % 100 == 0 or index == len(targets) - 1):
                progress("classify", index + 1, len(targets), "关键词分类")
        self._update(keyword_updates)
        ai_result = {"results": {}, "fallback_ids": [str(row["id"]) for row in targets], "errors": [], "batches": 0}
        if use_ai:
            client = ai_client
            if client is None:
                ai = self.config.ai
                client = AIClient(ai.base_url, ai.api_key, ai.model, ai.timeout) if ai.enabled else None
            items = [
                {"id": str(row["id"]), "name": str(row.get("name", "")), "description": str(row.get("description", ""))}
                for row in targets
            ]
            ai_result = review(items, [item["name"] for item in categories], client)
            ai_updates = []
            for skill_id, value in ai_result["results"].items():
                if value["category"] not in {item["name"] for item in categories} | {"未分类"}:
                    continue
                ai_updates.append((value["category"], "ai", float(value["confidence"]), skill_id))
            self._update(ai_updates)
        return {
            "classified": len(targets),
            "skipped_manual": len(manual),
            "fallback_count": len(ai_result["fallback_ids"]) if use_ai else 0,
            "ai_batches": ai_result.get("batches", 0),
            "ai_errors": ai_result.get("errors", []),
            "keyword_results": keyword_results,
        }