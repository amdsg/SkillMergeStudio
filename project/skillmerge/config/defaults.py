from __future__ import annotations

from typing import Dict, List, Tuple

APP_NAME = "Skill Merge Studio"
CONFIG_VERSION = 2

DEFAULT_SCAN_DEPTH = 10
DEFAULT_SCAN_LIMIT = 4000
DEFAULT_SCAN_TIME_LIMIT = 150
CANCEL_CHECK_EVERY = 200
BATCH_SIZE = 500

MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_LIST_LIMIT = 500
DEFAULT_PAGE_SIZE = 50

PROBE_PLATFORMS: Tuple[Dict[str, object], ...] = (
    {"platform": "agents", "paths": (".agents", ".agents/skills")},
    {"platform": "claude", "paths": (".claude", ".claude/skills")},
    {"platform": "codex", "paths": (".codex", ".codex/skills")},
    {"platform": "copilot", "paths": (".copilot", ".github/copilot")},
    {"platform": "cursor", "paths": (".cursor", ".cursor/skills")},
    {"platform": "gemini", "paths": (".gemini", ".gemini/skills")},
    {"platform": "opencode", "paths": (".opencode", ".config/opencode")},
    {"platform": "trae", "paths": (".trae", ".trae/skills")},
    {"platform": "qwen", "paths": (".qwen", ".qwen/skills")},
    {"platform": "kimi-code", "paths": (".kimi-code", ".kimi")},
    {"platform": "workbuddy", "paths": (".workbuddy", "WorkBuddy", "Documents/WorkBuddy")},
    {"platform": "roo", "paths": (".roo", ".roo/skills")},
    {"platform": "cline", "paths": (".cline", ".cline/skills")},
    {"platform": "goose", "paths": (".goose", ".config/goose")},
    {"platform": "codebuddy", "paths": (".codebuddy", ".codebuddy/skills")},
    {"platform": "iflow", "paths": (".iflow", ".iflow/skills")},
    {"platform": "qoder", "paths": (".qoder", ".qoder/skills")},
    {"platform": "windsurf", "paths": (".windsurf", ".codeium/windsurf")},
    {"platform": "agent", "paths": (".agent", ".agent/skills")},
    {"platform": "doubao", "paths": ("Doubao", "Documents/Doubao", "AppData/Roaming/Doubao")},
)

PLATFORM_PRIORITY: Tuple[str, ...] = tuple(str(item["platform"]) for item in PROBE_PLATFORMS) + ("unknown",)

PRUNE_NAMES = frozenset(
    {
        "node_modules",
        "site-packages",
        ".git",
        ".hg",
        ".svn",
        "venv",
        ".venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".cache",
        "Cache",
        "caches",
        ".npm",
        ".yarn",
        ".pnpm-store",
        ".gradle",
        ".m2",
        "Pods",
        "DerivedData",
        "Library/Caches",
    }
)

SKIP_FILE_NAMES = frozenset({".DS_Store"})
SKIP_FILE_SUFFIXES = (".pyc", ".pyo")

DEFAULT_IGNORE_RULES: Tuple[str, ...] = (
    "**/node_modules/**",
    "**/site-packages/**",
    "**/.git/**",
    "**/venv/**",
    "**/.venv/**",
    "**/__pycache__/**",
    "**/.cache/**",
)

QUALITY_DEDUCTIONS: Tuple[Dict[str, object], ...] = (
    {"code": "PARSE_FAILED", "delta": 40, "reason": "frontmatter 解析失败或文档不可读"},
    {"code": "BODY_EMPTY", "delta": 30, "reason": "正文为空"},
    {"code": "FM_MISSING", "delta": 25, "reason": "缺少 frontmatter"},
    {"code": "NAME_MISSING", "delta": 25, "reason": "frontmatter 缺少 name"},
    {"code": "DESC_MISSING", "delta": 20, "reason": "frontmatter 缺少 description"},
    {"code": "ENCODING_SUSPECT", "delta": 15, "reason": "编码异常或含零字节"},
    {"code": "NAME_MISMATCH", "delta": 10, "reason": "name 与目录名不一致"},
    {"code": "TOO_LONG", "delta": 10, "reason": "正文超过 5000 行或文件超过 200KB"},
    {"code": "BINARY_RESOURCE", "delta": 10, "reason": "存在可疑二进制资源"},
    {"code": "DUP_HEADING", "delta": 5, "reason": "存在重复标题"},
    {"code": "DUP_KEY", "delta": 5, "reason": "frontmatter 存在重复键"},
    {"code": "FENCE_UNCLOSED", "delta": 5, "reason": "代码围栏未闭合"},
)

DEFAULT_CATEGORIES: Tuple[Dict[str, str], ...] = (
    {"name": "数据分析", "slug": "data-analysis"},
    {"name": "数据可视化", "slug": "data-visualization"},
    {"name": "学术写作", "slug": "academic-writing"},
    {"name": "科研", "slug": "research"},
    {"name": "文档处理", "slug": "document-processing"},
    {"name": "表格处理", "slug": "spreadsheet"},
    {"name": "演示文稿", "slug": "presentation"},
    {"name": "图片处理", "slug": "image-processing"},
    {"name": "音视频", "slug": "audio-video"},
    {"name": "代码开发", "slug": "code-development"},
    {"name": "网站开发", "slug": "web-development"},
    {"name": "金融投资", "slug": "finance"},
    {"name": "医疗健康", "slug": "healthcare"},
    {"name": "法律", "slug": "legal"},
    {"name": "市场营销", "slug": "marketing"},
    {"name": "办公效率", "slug": "office-productivity"},
    {"name": "教育学习", "slug": "education"},
    {"name": "工程", "slug": "engineering"},
    {"name": "物理", "slug": "physics"},
    {"name": "心理学", "slug": "psychology"},
    {"name": "人力资源", "slug": "hr"},
    {"name": "产品管理", "slug": "product-management"},
    {"name": "电商", "slug": "e-commerce"},
    {"name": "翻译", "slug": "translation"},
    {"name": "安全", "slug": "security"},
    {"name": "运维", "slug": "devops"},
    {"name": "测试", "slug": "testing"},
    {"name": "爬虫", "slug": "scraping"},
    {"name": "知识管理", "slug": "knowledge-management"},
    {"name": "生活", "slug": "life"},
    {"name": "提示词工程", "slug": "prompt-engineering"},
    {"name": "写作", "slug": "writing"},
    {"name": "项目管理", "slug": "project-management"},
    {"name": "客户服务", "slug": "customer-service"},
    {"name": "销售", "slug": "sales"},
    {"name": "供应链", "slug": "supply-chain"},
    {"name": "游戏开发", "slug": "game-development"},
    {"name": "移动开发", "slug": "mobile-development"},
    {"name": "数据库", "slug": "database"},
    {"name": "人工智能", "slug": "artificial-intelligence"},
    {"name": "数学", "slug": "math"},
    {"name": "化学", "slug": "chemistry"},
    {"name": "生物", "slug": "biology"},
    {"name": "地理", "slug": "geography"},
    {"name": "历史", "slug": "history"},
    {"name": "哲学", "slug": "philosophy"},
    {"name": "旅行", "slug": "travel"},
    {"name": "美食", "slug": "food"},
)

DEFAULT_SLUG_MAP: Dict[str, str] = {item["name"]: item["slug"] for item in DEFAULT_CATEGORIES}

DEFAULT_AI: Dict[str, object] = {
    "enabled": False,
    "base_url": "",
    "model": "",
    "api_key": "",
    "timeout": 90,
}

TRASH_RETAIN_DAYS = 30
TRASH_MAX_GB = 2
DEFAULT_LANGUAGE = "zh"


def default_config_dict() -> Dict[str, object]:
    return {
        "config_version": CONFIG_VERSION,
        "roots": [],
        "save_dir": "",
        "ignore_rules": list(DEFAULT_IGNORE_RULES),
        "categories": [dict(item) for item in DEFAULT_CATEGORIES],
        "slug_map": dict(DEFAULT_SLUG_MAP),
        "scan_depth": DEFAULT_SCAN_DEPTH,
        "scan_limit": DEFAULT_SCAN_LIMIT,
        "scan_time_limit": DEFAULT_SCAN_TIME_LIMIT,
        "ai": dict(DEFAULT_AI),
        "trash": {"retain_days": TRASH_RETAIN_DAYS, "max_gb": TRASH_MAX_GB},
        "language": DEFAULT_LANGUAGE,
    }