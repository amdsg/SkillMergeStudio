from __future__ import annotations

from typing import Any, Dict, Iterable, List

BATCH_SIZE = 30
MAX_ATTEMPTS = 3


def review(
    items: List[Dict[str, Any]],
    categories: Iterable[str],
    client,
) -> Dict[str, Any]:
    results: Dict[str, Dict[str, Any]] = {}
    fallback_ids: List[str] = []
    errors: List[Dict[str, str]] = []
    batches = 0
    if client is None or not getattr(client, "available", False):
        return {
            "results": results,
            "fallback_ids": [str(item["id"]) for item in items],
            "errors": [{"code": "AI_UNAVAILABLE", "message": "AI 未配置或不可用"}],
            "batches": 0,
        }
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        batches += 1
        last_error = ""
        for _attempt in range(MAX_ATTEMPTS):
            try:
                batch_result = client.classify(batch, categories)
                results.update(batch_result)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)[:500]
        else:
            fallback_ids.extend(str(item["id"]) for item in batch)
            errors.append({"code": "AI_BATCH_FAILED", "message": last_error or "AI 分类失败"})
    return {"results": results, "fallback_ids": fallback_ids, "errors": errors, "batches": batches}