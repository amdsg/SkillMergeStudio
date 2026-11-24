from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ...config import defaults
from .keywords import for_category, KEYWORDS

BUILTIN_NAMES = tuple(item["name"] for item in defaults.DEFAULT_CATEGORIES)
REQUIRED_DIRECTIONS = {
    "学术": "学术写作",
    "数据": "数据分析",
    "文档": "文档处理",
    "表格": "表格处理",
    "演示": "演示文稿",
    "图片": "图片处理",
    "音视频": "音视频",
    "代码": "代码开发",
    "网站": "网站开发",
    "金融": "金融投资",
    "医疗": "医疗健康",
    "法律": "法律",
    "营销": "市场营销",
    "办公": "办公效率",
    "教育": "教育学习",
    "科研": "科研",
    "工程": "工程",
    "物理": "物理",
    "心理": "心理学",
    "HR": "人力资源",
    "产品": "产品管理",
    "电商": "电商",
    "翻译": "翻译",
    "安全": "安全",
    "运维": "运维",
    "测试": "测试",
    "爬虫": "爬虫",
    "知识管理": "知识管理",
    "生活": "生活",
}


def builtin_categories() -> List[Dict[str, Any]]:
    return [
        {"name": name, "slug": defaults.DEFAULT_SLUG_MAP.get(name, ""), "index": index, "builtin": True, "keywords": for_category(name)}
        for index, name in enumerate(BUILTIN_NAMES)
    ]


def merge_categories(config) -> List[Dict[str, Any]]:
    custom = []
    for item in getattr(config, "categories", ()):
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        slug = str(item.get("slug", "")).strip()
        if name in BUILTIN_NAMES:
            continue
        custom.append({"name": name, "slug": slug, "builtin": False, "keywords": for_category(name)})
    result = builtin_categories()
    start = len(result)
    for offset, item in enumerate(custom):
        item["index"] = start + offset
        result.append(item)
    return result


def all_names(config) -> List[str]:
    return [item["name"] for item in merge_categories(config)]


def category_index(config) -> Dict[str, int]:
    return {item["name"]: int(item["index"]) for item in merge_categories(config)}


def builtin_names() -> Tuple[str, ...]:
    return BUILTIN_NAMES


def has_keyword_table(name: str) -> bool:
    return name in KEYWORDS