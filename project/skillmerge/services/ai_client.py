from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List

from ..util.logging import redact

MAX_RESPONSE = 2 * 1024 * 1024


def _strip_fence(text: str) -> str:
    value = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", value, re.S | re.I)
    return match.group(1).strip() if match else value


class AIClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 90) -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.api_key = str(api_key or "")
        self.model = str(model or "")
        self.timeout = max(1, int(timeout or 90))

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.model)

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base_url + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self.api_key:
            request.add_header("Authorization", "Bearer " + self.api_key)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ValueError(redact(str(exc))[:500])
        if len(raw) > MAX_RESPONSE:
            raise ValueError("AI 响应超过 2MB")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError(f"AI 响应不是 JSON：{exc}")

    def ping(self) -> None:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": "ping"}],
        }
        self._request(payload)

    def suggest_merge(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        body = self._request(payload)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError("AI 响应缺少 choices[0].message.content")
        usage = body.get("usage") if isinstance(body, dict) else None
        tokens = 0
        if isinstance(usage, dict):
            try:
                tokens = int(usage.get("total_tokens", 0) or 0)
            except (TypeError, ValueError):
                tokens = 0
        return {"content": str(content), "tokens": tokens, "model": self.model}

    def classify(self, items: List[Dict[str, Any]], categories: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        category_list = sorted({str(item) for item in categories})
        prompt = (
            "你是技能分类器。只返回严格 JSON，不要 Markdown。格式："
            '{"items":[{"id":"技能id","category":"分类名","confidence":0.0}]}。'
            f"可选分类：{json.dumps(category_list, ensure_ascii=False)}。"
            "只能选择可选分类；不确定时选择“未分类”并给低置信度。"
            f"技能：{json.dumps([{'id': item['id'], 'name': item.get('name', ''), 'description': item.get('description', '')} for item in items], ensure_ascii=False)}"
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        body = self._request(payload)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError("AI 响应缺少 choices[0].message.content")
        try:
            parsed = json.loads(_strip_fence(str(content)))
        except ValueError as exc:
            raise ValueError(f"AI 内容不是 JSON：{exc}")
        rows = parsed.get("items") if isinstance(parsed, dict) else None
        if not isinstance(rows, list):
            raise ValueError("AI JSON 缺少 items 数组")
        allowed = set(category_list) | {"未分类"}
        result = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("AI items 项不是对象")
            skill_id = str(row.get("id", ""))
            category = str(row.get("category", ""))
            if not skill_id or category not in allowed:
                raise ValueError("AI 返回了非法 id 或 category")
            try:
                confidence = float(row.get("confidence", 0))
            except (TypeError, ValueError):
                raise ValueError("AI confidence 非法")
            result[skill_id] = {"category": category, "confidence": max(0.0, min(1.0, confidence))}
        return result