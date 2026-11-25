Skill Merge Studio
==================

把散落在电脑各处的 Agent Skill 找出来、建立索引、自动分类、按策略安全合并，
再按目标平台或聊天模型导出，并保留可撤销、可重建的产物历史。当前进度：
M0（扫描与索引）+ M2（选择与合并）+ M3（导出与平台）+ M3b（平台治理）+
M1（分类体系）+ M4（历史/撤销/重建）+ M5（打磨与收口）。另内置 GitHub 只读客户端：
按项目名搜索、本周/本月热门推荐、zipball 下载与更新检测（手动触发）。运行时不依赖任何
第三方 Python 包；前端无框架与构建链。

一、安装
--------
1. 需要 Python 3.9 或更高版本（Windows / macOS / Linux）。
2. 不需要 pip install 任何运行时依赖。
3. 开发与测试依赖（可选）：
   python -m pip install -r requirements-dev.txt
4. 首次启动创建 data/，可用环境变量改位置：
   SKILLMERGE_DATA_DIR=D:\SkillMergeData

二、启动
--------
   python server.py
   python -m skillmerge serve
   Windows: start.bat ／ macOS: ./start.command ／ Linux: ./start.sh

启动后只监听 127.0.0.1，端口 8765 起自动探测；data/port.txt 与 pid.txt
记录运行信息，退出时清理。

三、目录
--------
server.py                 仅入口
skillmerge/
  app.py                  装配、路由、生命周期
  config/                 默认值、加载、迁移
  http/                   HTTP 准入、静态资源、SSE、文件下载响应
  api/                    scan / classify / preview / merge / export / history /
                          artifacts undo·rebuild / download
  services/classifier/    48 类关键词表、加权打分、置信度、slug、AI 复核、人工保护
  services/history/       manifest 校验、历史六列、撤销（.trash）、章节级重建 diff、
                          trash_usage.py 只读统计
  services/ai_client.py   唯一出站网络模块（OpenAI 兼容，默认关闭，密钥不落盘）
  services/scanner/       探测、DFS、增量索引
  services/parser/        YAML 子集、frontmatter、Markdown、资源、质量分
  services/merger/        对齐、冲突、段落去重、资源/依赖、组装、merge_plan
  services/exporter/      平台注册表、命名/描述、15 项校验、builder、zip、
                          installer、manifest、prompt_pack、export_service
  services/fsops.py       staging / .trash / 命名锁 / 路径边界
  jobs/                   任务队列、取消、进度事件、SSE
  storage/                SQLite 七表、仓储、迁移
  cli/                    命令行
platforms/                平台规则 JSON + schema.json + discovery/（数量以核验结果为准）
web/                      原生 ESM 前端（分类筛选、合并篮、预览、冲突决策、
                          导出面板、历史、设置、i18n 中英切换）
tests/                    unit / integration / security / reliability / performance /
                          golden / platform_matrix / a11y / e2e（默认 deselect）
tools/                    check_lines / check_imports / check_golden /
                          check_platforms / check_wording / check_i18n /
                          check_coverage / check_wrappers / check_no_auto_delete /
                          check_req_trace / ai_quality_probe / verify_platform /
                          check_install_isolated / check_openbox / selftest /
                          validate_discovery / grade_evidence
docs/                     DoD、需求追溯与映射、抽检记录、可访问性/浏览器手工清单、
                          AI 质量协议、平台实跑说明、里程碑汇报
reports/                  机器生成：verification-summary.json、platform-*.json、
                          collect-*.txt（运行产物）
pytest.ini / .coveragerc  测试与覆盖率配置

数据目录：
data/config.json          配置（api_key 永不回显）
data/index.db             SQLite 索引（WAL）
data/artifacts/           合并产物与 exports/ 导出产物
data/.trash/              失败或撤销产物（不直接删除）
data/port.txt / pid.txt   运行期文件

四、演示
--------
合并：
1. python server.py
2. 扫描 → 勾选技能 → 预览 → 冲突决策 → 合并。
3. 产物含 SKILL.md、merge_plan.json、manifest.json。

导出：
1. 在预览弹窗底部选择平台与模式（dir / zip / download / install）。
2. 点击“导出”；成功后可看到产物路径或“下载 zip”。
3. prompt-only 平台会生成 prompt.md、manifest.json、README.txt。

GitHub 搜索 / 下载：
1. 点击顶部“GitHub 下载”，选择“热门推荐”（本周/本月）或“搜索”。
2. 下载 zipball 解压到 data/downloads/<sha 前缀>，阻断路径穿越并识别 SKILL.md。
3. 重新扫描该目录即可入索引；再次打开弹窗时检查更新（手动触发）。

API：
   POST /api/scan           {"roots":["D:\\skills"],"depth":10}
   POST /api/classify       {"use_ai":false}（人工分类不会被覆盖）
   GET  /api/categories     内置 + 自定义分类与每类计数
   GET  /api/config         配置（api_key 仅返回 api_key_set）
   POST /api/config         保存配置（分类 slug 冲突 → 400）
   POST /api/ai/test        连通性测试（不可达仍 200 + reachable:false）
   GET  /api/audit          审计日志（时间/动作/对象/结果）
   POST /api/preview
   {"sources":["id1","id2"],"name":"demo","platform":"generic","strategy":"keep-all"}
   POST /api/merge
   {"sources":["id1","id2"],"name":"demo","platform":"generic"}
   POST /api/export
   {"artifact_id":"<id>","platform":"claude","mode":"zip"}
   GET  /api/history        产物历史（含 status / source_updated）
   GET  /api/artifacts/{id} manifest + 逐文件 sha256 校验结果
   POST /api/artifacts/{id}/undo     改 1 字节即 409 ARTIFACT_MODIFIED
   POST /api/artifacts/{id}/rebuild  用当前源重建，返回 job_id
   POST /api/artifacts/{id}/ai-apply 应用已确认的 AI 建议（仅确认的 key）
   GET  /api/skills/{id}/artifacts   引用该技能的产物
   GET  /api/artifacts/{id}/download
   GET  /api/github/health  GitHub 客户端状态
   POST /api/github/search  {"query":"skill","sort":"relevance","page":1}
   POST /api/github/trending {"window":"week"|"month","page":1}
   POST /api/github/download {"repo_full_name":"owner/repo","ref":""}
   POST /api/github/check-update {"repo_full_name":"owner/repo","local_ref":{...}}

合并规则：
- 默认 keep-all，只删除空白归一化后完全相同的段落。
- sim >=0.72 建议合并，0.35–0.72 提示复核，<0.35 冲突并保留双方。
- 资源 sha256 去重；同名不同内容 _2/_3；跳过符号链接。
- 超限只给裁剪建议，禁止静默截断。
- 相同输入 + 相同 merge_plan 的 SKILL.md / merge_plan.json 字节级一致。

五、测试
--------
   python -m pytest -q                     # 默认跳过 perf 与 e2e
   python -m pytest -m perf -q             # 性能门槛
   python -m pytest -m e2e -q              # 未批准依赖 → skipped（exit 0）
   python -m pytest -m e2e -o addopts="" -q
   python tools/check_lines.py
   python tools/check_imports.py
   python tools/check_imports.py --forbidden-net
   python tools/check_golden.py
   python tools/check_platforms.py
   python tools/check_wording.py
   python tools/check_i18n.py
   python tools/check_wrappers.py
   python tools/check_no_auto_delete.py
   python tools/check_req_trace.py --check
   python tools/check_req_trace.py --summary --audit-out reports/closure-audit-<date>.json
   python tools/check_openbox.py --check
   python tools/verify_platform.py --record
   python tools/check_install_isolated.py  # 缺 --root → exit 2（默认不写真实目录）
   python tools/ai_quality_probe.py --dry-run
   python tools/selftest.py                # 无 pytest 环境亦可自证
   # 工作站门禁（实现后启用）
   python skill-workbench/tools/check_i18n_wb.py --check
   python skill-workbench/tools/check_adapter_registry.py --check
   python tools/check_req_trace.py --trace-out reports/req-trace.md

覆盖率（需要开发依赖 pytest-cov）：
   python -m pip install -r requirements-dev.txt
   python -m pytest -q --cov=skillmerge --cov-report=json
   python tools/check_coverage.py

当前覆盖：
- M0：解析兼容、深层发现、剪枝、副本归并、增量复扫、SQLite 迁移、HTTP 安全。
- M2：归一化/相似度/冲突、段落去重、资源与依赖、四策略、并发同名、
  写入失败回滚、10 源性能、5 组 golden。
- M3：5 平台端到端、27 Skill 平台矩阵、15 项校验、命名/描述重写、
  zip 确定性、安装不覆盖、manifest、API 导出/下载、提示词三档/八段/token。
- M3b：schema v2 迁移、证据分级、平台清单/详情、候选确认、计数等式与门禁。
- M1：48 类分类目录、关键词加权（描述 2 : 名称 1）、置信度、人工分类保护、
  AI 复核分批与失败回退（默认关闭）、七类筛选、虚拟滚动、键盘全键位、
  四态、详情分类依据、i18n 203 键。
- M4：SSE 与 Last-Event-ID、任务持久化与重启语义、manifest 校验、历史六列、
  撤销（改 1 字节拒绝）、章节级重建 diff、重建 preflight、审计日志。
- M5：AI 建议稿（未确认不写入）、CLI 七命令、配置/AI 测试接口、
  密钥脱敏、性能门槛、覆盖率门禁、66 项零依赖自测。
- M6：361 条机械提取与文件级映射、50 条抽检记录、闭合汇总（0 已闭合 /
  361 未闭合）、`.trash` 只读统计与禁自动删除门禁、Windows 平台实跑归档、
  AI 质量 blocked 门控、浏览器手工清单、开箱即用五步验收（verdict=pass）。
- 当前全量：262 passed，3 skipped，3 deselected（perf/e2e 默认跳过）；
  覆盖率整体 78.8%，merger/exporter/scanner 均 ≥85%。

六、平台规则核验
----------------
platforms/<id>.json 为唯一规则来源。字段含 id/label/kind/verified_at/source/
name/description/skill_md/bundle/package/frontmatter/install/notes。

当前状态：
- generic / prompt-only：本地规则，verified_at 2026-11-22。
- claude：已核验 https://docs.claude.com/en/docs/claude-code/skills 的目录与
  frontmatter；description≤200、名称禁 claude/anthropic、zip≤30MB 来自本项目需求。
- workbuddy / chatgpt：无可公开核验的完整官方限制，source/verified_at=unknown，
  导出时必有 V-RULE-02 告警。
- 其余 23 个平台：统一标 unknown，采用通用目录与保守限制；导出前请核对官网。
- 27 个 kind=skill 平台 + prompt-only（kind=prompt）= 28 份规则。
- 规则核验日期超过 90 天 / 180 天会分别产生 warn；“unknown”绝不静默使用。

七、常见错误
------------
1. 端口被占用：关闭占用程序，或 python server.py --port 9000。
2. 已有实例：同一 data 目录只允许一个实例。
3. 扫描为空：确认存在 SKILL.md，且不在 node_modules/.git/venv 等剪枝目录。
4. 401：刷新页面获取 Cookie，或携带 X-Skillmerge-Token。
5. 403：Host 必须为本机，POST Origin 必须同源。
6. 合并被拒绝：查看预览“校验”标签的 error 与 fix。
7. 导出被拒绝：preflight/postflight 的 error 会阻止写盘或登记；按 fix 修复。
8. 安装失败：平台未配置安装目录时改用 zip；目标重名自动 _2，不覆盖。
9. 规则未核验：V-RULE-02 为告警；确认官网规则后再用于生产。
10. config.json 损坏：程序备份 .bak 并以默认配置启动。
11. 数据库版本高于程序：拒绝启动，避免降级破坏。

八、当前进度
------------
已完成：
- M0：骨架、配置、SQLite、解析、扫描与增量、HTTP 准入、任务队列、CLI scan。
- M2：合并篮、预览、冲突决策、四策略、资源/依赖、staging/.trash、
  merge_plan、manifest、5 组 golden、前端合并流程。
- M3：平台注册表（首批端到端 + 候选条目）、15+ 校验器、命名/描述重写、
  确定性 zip、安装、导出流水线、API 导出/下载、提示词包与前端导出面板。
- M3b：schema v2、v1 兼容加载与基线迁移、探测记录/证据分级、平台清单/详情 API、
  CLI platforms、候选确认与保守限制。平台数量与证据数均以 API/CLI 的 counts 为准。
- M1：48 类关键词分类（中文子串 / 英文边界匹配）、描述 2 : 名称 1 加权、
  confidence=min(0.95, 0.35+0.15×得分)、仅名称命中封顶 0.60、来源
  keyword/ai/manual、人工分类不被覆盖、AI 复核 30/批 + 3 次重试 + 失败回退、
  分类树筛选、列表虚拟滚动、详情展示来源/置信度/命中词。
- M4：manifest 存在性/集合/逐文件 sha256 三步校验、撤销走 .trash、
  源哈希变化标记、H2 章节级 add/remove/modify diff、重建生成新产物、
  技能详情反查引用产物、历史面板（撤销 / 重建 / 复制路径）、
  SSE 前端订阅与取消按钮、任务持久化与重启语义、审计日志。
- M5：AI 语义合并建议稿（未确认不写入；确认后 ai-apply 只改指定章节）、
  CLI 七命令（scan/classify/merge/export/validate/platforms/serve）、
  配置 API 与 AI 连通性测试、密钥脱敏全链路、i18n 203 键、
  键盘/焦点、性能门槛、覆盖率门禁、66 项零依赖自测、DoD/追溯/里程碑文档。
- M6（部分交付）：361 条机械提取与文件级映射、50 条抽检记录、三组计数
  （通过 0 / 未执行 361 / 豁免 0）、.trash 只读统计与禁自动删除门禁、
  Windows 平台实跑归档、AI 质量 blocked 门控、浏览器手工清单。

未验证 / 风险（不虚报）：
- 浏览器 5 点未执行：Q-32 未批准开发依赖，只有 manual 清单（未勾选）。
- 真实 AI 端点未执行：Q-33 未提供端点/样本/预算，REQ-VER-006/007 为 blocked。
- macOS / Linux 未实跑：Q-34 未提供环境，REQ-CMP-001 保持 blocked。
- 真实平台目录安装未执行：Q-35 未提供隔离根，REQ-VER-010/011 为 partial。
- 需求映射是文件级锚点（多对多），不是逐条节点级证据；未逐条勾选。

已知限制：
- 未核验平台（含 WorkBuddy/ChatGPT）不能视为官方合规承诺；导出必须确认候选。
- 平台选择器已实现搜索、分组折叠、最近使用、虚拟列表与独立候选池；
  尚未做真实浏览器自动化与 200 条实测性能记录。
- 探测记录目前只有一轮；页面出现 SKILL.md 只算发现证据，不等于规则已核验。
- 前端导出交互尚未做浏览器自动化测试。
- 安装端到端仅在临时目录验证，未对真实平台目录执行。
- 关键词分类基于词表匹配，不做语义理解；命中词是详情页实时重算的“关键词建议”，
  分类权威值仍以 category / category_source / confidence 为准。
- 历史列表的“源已更新”需要逐个产物比对源目录哈希，产物很多时会变慢。
- 撤销/重建/历史面板未做浏览器自动化；已用临时数据目录做 HTTP 冒烟
  （页面、静态资源、history/categories/platforms 均 200）。
- 显式指定超出 8865 的 --port 时，只尝试该端口本身（不再误报“区间均占用”）。
- AI 合并建议必须由用户显式确认；未确认时 SKILL.md 不含 AI 改写内容。
- `.trash` 的 30 天/2GB 只做只读统计与提示；永不自动清理（REQ-VER-016）。
- 抽检比例 0.20 为默认值，Q-36 未确认；不得据此宣称“逐条通过”。
- Q-37 未确认时清理入口不实现；Q-38 未确认时允许带 blocked/exempt 标记发布。
- 英文模式零中文的验收范围为工作站界面（含扩展面板与教程浮层）；README/CLI 语言策略见 Q-17（默认不纳入）。

九、统一 Skill 工作站（规划中）
--------------------------------
- 规格：`.codeartsdoer/specs/skill_workbench/spec.md`（180 条；P0 135 / P1 40 / P2 5）。
- 目标链路：GitHub 搜索/推荐 → 下载 → 升级 → 合并 → 跨模型转换 → 通用导出 → 配置（dry-run）。
- 目标注册表：25 条为**当前注册表快照，非全集**；GPT / 豆包 / 通用仅为示例，实际支持
  以开放注册表为准。当前 verified 3（Claude + 2 个通用契约）/ candidate 0 / unknown 22；
  unknown 只能导出通用文本，不得称“官方兼容”。
- 本轮新增：适用目标三态标注（`CFG-011`）、目标不匹配知悉（`CFG-012`）、升级声明变化
  预览（`UPG-016`）、全屏英文化门禁（`I18N-015/016`）、继承源缺失标 blocked（`ACC-008`）。
- 教程：顶部“教程”按钮 + 七步浮层；英文模式零中文内置文案。
- 默认安全：真实写入、替换式升级、自动检查更新默认关闭；`.trash` 永不自动删除。
- 追溯：Studio 侧 361 条追溯已按域补齐（原 338 口径已消除）；锚点为文件级，通过数仍为 0。
- 继承：上游 `skill-hub-plugin` 规格在本仓库不可达 → 继承关系标 `blocked`
  （`.codeartsdoer/specs/skill-hub-plugin`，检索时间 2026-11-23）；不得称已继承 189 条。
- 当前状态：工作站 9 项门禁全绿；核心链路（注册表/检索/下载/预览/转换/合并/升级检查）
  已在 fixture 模式实现并通过单元/集成/安全测试；真实 GitHub 访问、真实写入、浏览器 15 屏
  证据、macOS/Linux 实跑**尚未执行**，不得表述为已发布可用。
