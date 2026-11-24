from __future__ import annotations

from ..services.classifier.taxonomy import merge_categories
from .schemas import page_args, skill_list_filters


def _list_payload(skill, repo) -> dict:
    return {
        "id": skill.id,
        "path": skill.path,
        "real_path": skill.real_path,
        "name": skill.name,
        "description": skill.description,
        "category": skill.category,
        "category_source": skill.category_source,
        "confidence": skill.confidence,
        "platform_origin": skill.platform_origin,
        "size_bytes": skill.size_bytes,
        "lines": skill.lines,
        "chars": skill.chars,
        "mtime": skill.mtime,
        "quality_score": skill.quality_score,
        "parse_error": skill.parse_error,
        "missing": skill.missing,
        "first_seen": skill.first_seen,
        "last_seen": skill.last_seen,
        "locations_count": max(1, len(repo.locations(skill.id))),
    }


def list_skills(ctx, request):
    filters = skill_list_filters(request)
    limit, offset = page_args(request)
    items, total = ctx.skills_repo.list(filters, limit, offset)
    return 200, {
        "items": items,
        "page": {"limit": limit, "offset": offset, "total": total},
    }


def get_skill(ctx, request):
    from ..util.errors import DomainError
    from ..services.classifier.rules import classify_text

    skill = ctx.skills_repo.get(request.params.get("id", ""))
    if skill is None:
        raise DomainError("NOT_FOUND", "技能不存在", "重新扫描或刷新列表后重试", 404)
    data = _list_payload(skill, ctx.skills_repo)
    data.update(
        {
            "frontmatter": skill.frontmatter(),
            "headings": skill.headings(),
            "resources": skill.resources(),
            "dependencies": skill.dependencies(),
            "warnings": skill.warnings(),
            "quality": skill.quality_json,
            "body_preview": skill.body_preview,
            "locations": ctx.skills_repo.locations(skill.id),
            "keyword": classify_text(skill.name, skill.description, ctx.config),
        }
    )
    return 200, data


def categories(ctx, request):
    counts = {item["name"]: int(item["count"]) for item in ctx.skills_repo.categories_with_counts()}
    items = []
    for item in merge_categories(ctx.config):
        name = item["name"]
        items.append(
            {
                "name": name,
                "slug": item.get("slug") or (ctx.config.slug_map or {}).get(name, ""),
                "count": counts.get(name, 0),
                "builtin": bool(item.get("builtin")),
                "index": int(item.get("index", 0)),
            }
        )
    if counts.get("未分类", 0) and not any(item["name"] == "未分类" for item in items):
        items.append({"name": "未分类", "slug": "uncategorized", "count": counts["未分类"], "builtin": True, "index": 9999})
    items.sort(key=lambda item: (-item["count"], item["name"]))
    return 200, {"items": items, "total": len(items)}


def duplicates(ctx, request):
    groups = ctx.skills_repo.duplicate_groups()
    return 200, {"items": groups, "total": len(groups)}