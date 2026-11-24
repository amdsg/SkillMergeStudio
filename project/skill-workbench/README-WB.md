# Skill Workbench 工作区

本目录是统一 Skill 工作站的实现工作区（新增，不是既有 Studio 代码）。

## 硬约束

- Python 3.11+，仅标准库，零第三方运行时依赖。
- 扩展为 Chrome/Edge Manifest V3 原生 JS，无构建链、无 React/Vue。
- Agent 承担全部本地副作用；扩展不得直接读写用户目录。
- 真实写入、替换式升级、官方兼容声明、二进制转换、自动检查更新默认全部关闭。
- 默认安全路径：检索/下载/合并/转换/配置预览均为 dry-run。

## 目录

- `agent/`：本地 Agent（HTTP 127.0.0.1:8788，标准库）。
- `extension/`：MV3 扩展（原生 JS）。
- `tools/`：门禁脚本与验证工具。
- `tests_wb/`：工作站测试。
- `docs/`：证据与平台实跑记录。

## 当前状态

门禁与工程骨架构建中。业务功能未完成，不得表述为已可用。

## 验证

工作目录为 `project/`：

```bash
python skill-workbench/tools/gate_all.py --check
python -m pytest skill-workbench/tests_wb/unit -q -o addopts=""
```