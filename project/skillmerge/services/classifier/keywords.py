from __future__ import annotations

from typing import Dict, Tuple

KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "数据分析": ("统计", "数据", "图表", "报告", "分析", "报表", "指标", "data analysis", "analytics"),
    "数据可视化": ("可视化", "仪表盘", "图表", "dashboard", "chart", "plot", "matplotlib", "echarts"),
    "学术写作": ("论文", "摘要", "文献", "引用", "学术", "paper", "abstract", "citation", "latex"),
    "科研": ("研究", "实验", "假设", "科研", "research", "experiment", "hypothesis"),
    "文档处理": ("文档", "排版", "格式", "word", "pdf", "docx", "markdown"),
    "表格处理": ("表格", "excel", "csv", "sheet", "spreadsheet", "数据表"),
    "演示文稿": ("演示", "幻灯片", "汇报", "pptx", "slides", "presentation"),
    "图片处理": ("图片", "图像", "修图", "ocr", "photoshop", "image"),
    "音视频": ("音频", "视频", "剪辑", "字幕", "audio", "video", "ffmpeg"),
    "代码开发": ("代码", "编程", "函数", "重构", "code", "programming", "refactor", "debug"),
    "网站开发": ("网站", "前端", "后端", "html", "css", "react", "web"),
    "金融投资": ("金融", "股票", "投资", "财报", "基金", "finance", "stock", "investment"),
    "医疗健康": ("医疗", "健康", "诊断", "病历", "医生", "health", "medical"),
    "法律": ("法律", "合同", "诉讼", "合规", "legal", "contract"),
    "市场营销": ("营销", "市场", "品牌", "广告", "推广", "marketing", "brand"),
    "办公效率": ("办公", "效率", "日程", "邮件", "会议", "office", "productivity"),
    "教育学习": ("教育", "学习", "课程", "教学", "考试", "education", "learning"),
    "工程": ("工程", "机械", "建筑", "施工", "engineering"),
    "物理": ("物理", "力学", "电磁", "量子", "physics"),
    "心理学": ("心理", "情绪", "认知", "psychology"),
    "人力资源": ("人力资源", "招聘", "绩效", "薪酬", "hr", "recruit"),
    "产品管理": ("产品", "需求", "用户", "prd", "roadmap", "product"),
    "电商": ("电商", "商品", "订单", "店铺", "ecommerce", "shop"),
    "翻译": ("翻译", "中英", "localization", "translate"),
    "安全": ("安全", "漏洞", "攻击", "加密", "security", "vulnerability"),
    "运维": ("运维", "部署", "服务器", "监控", "devops", "deploy"),
    "测试": ("测试", "用例", "pytest", "qa", "testing"),
    "爬虫": ("爬虫", "抓取", "scrape", "crawler", "spider"),
    "知识管理": ("知识", "笔记", "知识库", "notion", "obsidian", "knowledge"),
    "生活": ("生活", "旅行", "美食", "life"),
    "提示词工程": ("提示词", "prompt", "提示工程"),
    "写作": ("写作", "文案", "润色", "writing"),
    "项目管理": ("项目", "计划", "风险", "进度", "project", "management"),
    "客户服务": ("客服", "客户", "工单", "service", "support"),
    "销售": ("销售", "线索", "sales"),
    "供应链": ("供应链", "库存", "物流", "采购", "supply chain"),
    "游戏开发": ("游戏", "unity", "unreal", "game"),
    "移动开发": ("移动", "android", "ios", "app"),
    "数据库": ("数据库", "sql", "sqlite", "mysql", "database"),
    "人工智能": ("人工智能", "模型", "训练", "ai", "machine learning", "llm"),
    "数学": ("数学", "公式", "计算", "math"),
    "化学": ("化学", "分子", "反应", "chemistry"),
    "生物": ("生物", "基因", "细胞", "biology"),
    "地理": ("地理", "地图", "气候", "geography"),
    "历史": ("历史", "朝代", "史料", "history"),
    "哲学": ("哲学", "伦理", "思辨", "philosophy"),
    "旅行": ("旅行", "旅游", "行程", "travel"),
    "美食": ("美食", "菜谱", "烹饪", "food", "recipe"),
}


def for_category(name: str) -> Tuple[str, ...]:
    values = KEYWORDS.get(str(name), ())
    return tuple(dict.fromkeys([str(name), *values]))