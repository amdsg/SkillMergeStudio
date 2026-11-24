# Skill Workbench 执行报告（2026-11-23）

> 证据等级说明：本文只记录实际执行的命令与结果。未执行项一律标 `blocked` 或 `not_started`，不计入通过。

## 一、已完成

| 范围 | 内容 | 证据 |
| --- | --- | --- |
| 独立项 A | `check_req_trace.py` 新增只读 `--trace-out`；338 → 361 按域补齐；`docs/req-trace.md` 落盘；`dod-checklist.md` 旧口径标时效；`check_wording.py` 扩展 361 禁语 | `python tools/check_req_trace.py --summary` → total=361 / passed=0 / identity_ok=True |
| 独立项 B | README 第九章 180 条与三组计数；本轮 6 条新增；361 口径；继承 `blocked`；门禁命令；Q-17 边界 | `python tools/check_readme_counts.py --check` → total=180 P0=135 P1=40 P2=5 issues=0 |
| Stage 0 | 工作区骨架、MV3 扩展骨架、Agent 骨架、9 个门禁 + `gate_all.py` | `python skill-workbench/tools/gate_all.py --check` → 9/9 passed |
| 数据契约 | `target_schema.json`、25 条初始快照、分组/别名、工具声明、引擎映射、未映射备忘、证据历史 25 份、继承记录 | `check_adapter_registry.py --assert-counts --assert-groups --assert-evidence` → 0 errors |
| Agent API | `/health`、`/targets`、`/targets/{id}/tools`、`/applicability/resolve`、`/search`、`/download`、`/install/preview`、`/convert`、`/merge`、`/upgrade/check`、`/records/{name}` | `pytest tests_wb/integration` → 8 passed |
| 安全边界 | zip-slip 拒绝、脚本/二进制零执行、单文件/总量限制、来源引用完整性 | `pytest tests_wb/security` → 4 passed |
| 门禁自测 | 注册表计数等式、重复 id、unknown 带来源、开放集合、默认关闭、i18n 键一致、继承 blocked、适用性三态、工具匹配 | `pytest tests_wb/unit` → 10 passed |
| 引擎隔离 | 目录哈希快照写入与复核 | `snapshot_engine_hash.py --write/--compare` → files=181 changed=0 |
| 英文化数据 | 15 屏清单、动态枚举、reason_code 注册表、白名单结构、zh/en 键集合一致 | `check_i18n_wb.py --check --assert-screens` → 0 errors |

## 二、未完成 / 阻塞（不虚报）

| 项 | 状态 | 原因 |
| --- | --- | --- |
| 真实 GitHub 检索/升级网络调用 | `blocked` | 自动化只使用 fixture；真实网络需只读 Token、稳定网络窗口与配额 |
| 真实目录写入（`/install/apply`） | `not_started` | `real_write` 默认关闭；需隔离根与显式授权 |
| 替换式升级 | `not_started` | `upgrade_replace` 默认关闭；需备份、二次确认与留痕 |
| 浏览器 15 屏英文渲染证据 | `not_started` | 无浏览器自动化依赖；只有静态门禁与 DOM 结构 |
| macOS / Linux 实跑 | `blocked` | 仅 Windows 环境实测 |
| 配对/会话鉴权（一次性码、Bearer、CSRF） | `not_started` | `middleware.py` 只有来源/CSRF 骨架，配对接口未实现 |
| 并发槽与幂等接入 API | `not_started` | `limits.py` 已实现类，但未接入各端点 |
| 诊断导出与脱敏日志 | `not_started` | 仅有 `redact_path` 辅助函数 |
| 记录迁移与 `interrupted` 扫描接入启动流程 | `not_started` | `records.py` 已实现函数，未接入启动 |
| 合并 apply / 转换撤销 / 升级回滚 | `not_started` | 预览与产物生成已实现，写后回滚链未实现 |

## 三、关键验证命令与结果

```bash
cd project/
python skill-workbench/tools/gate_all.py --check
# total=9 passed=9 failed=0

python -m pytest skill-workbench/tests_wb/unit -q -o addopts=""
# 10 passed

python -m pytest skill-workbench/tests_wb/integration -q -o addopts=""
# 8 passed

python -m pytest skill-workbench/tests_wb/security -q -o addopts=""
# 4 passed

python tools/check_req_trace.py --summary
# total=361 passed=0 not_executed=361 exempt=0 identity_ok=True

python tools/check_wording.py
# 文案门禁通过（29 个文件）

python tools/check_readme_counts.py --check
# total=180 P0=135 P1=40 P2=5 issues=0

python skill-workbench/tools/snapshot_engine_hash.py --compare reports/engine-hash-before.json
# baseline=181 current=181 changed=0
```

## 四、口径与风险

1. **361 条追溯不等于通过**：`docs/req-trace.md` 首行固定“通过 0 / 未执行 361 / 豁免 0”，锚点为文件级。
2. **25 个目标是当前快照**：GPT / 豆包 / 通用仅为示例；注册表开放，新增目标不需要改转换核心。
3. **`ACC-008` 持续 `blocked`**：上游 `skill-hub-plugin` 规格不在本仓库，禁止声称“已继承 189 条”。
4. **真实写入未执行**：任何“已配置 / 已写入”表述都不成立；当前只有 dry-run 计划。
5. **英文门禁只覆盖 UI/扩展/教程**：README 与 CLI 中文属 Q-17 默认边界，不计缺陷。
6. **fixture 模式**：检索与升级检查的数据来自 `tests_wb/fixtures/**`，不是真实 GitHub 响应。

## 五、后续计划

1. 接入真实 GitHub 只读客户端与配额错误码（需要 Token 与网络窗口）。
2. 实现配对鉴权、并发槽/幂等接入、诊断导出与启动时 `interrupted` 扫描。
3. 实现 `install/apply`、升级回滚、转换撤销与备份清单。
4. 在批准的浏览器环境中补齐 15 屏 × 必测状态的英文渲染证据。
5. 在隔离根上完成一次真实写入演练与一次失败回滚演练。