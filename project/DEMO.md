# Demo 快速说明

本目录是 Skill Merge Studio 的可运行副本，运行时不依赖任何第三方 Python 包。

## 启动

```bat
start.bat
```

或：

```bat
python server.py
```

macOS / Linux：

```bash
bash start.sh
```

访问 `http://127.0.0.1:8765`。

## 内置演示数据

`demo-skills/` 下有 3 个合成技能：

- `a/`：描述“三源 A”，含“公共步骤：校验输入”
- `b/`：描述“三源 B”，与 A 有重复段落，也有独立步骤
- `c/`：描述“三源 C”，含独立步骤

演示时把扫描根目录指向本目录的**绝对路径**，即可观察：

1. 扫描与索引；
2. 分类与置信度；
3. 合并篮选择；
4. 预览中的章节对齐、重复段落与冲突；
5. 合并产物 `SKILL.md`、`merge_plan.json`、`manifest.json`；
6. 导出 `generic` + `zip`；
7. 历史面板的撤销与重建。

## 测试

```bat
python -m pytest -q
```

本次提交包副本实测：262 passed, 3 skipped, 3 deselected。

## 数据与隐私

- 默认数据目录 `./data/`，首次启动自动创建。
- 本包不附带任何真实用户 Skill 或真实索引库；`data/` 由评委运行时生成。
- 程序不会修改或删除源 Skill；撤销产物进入 `data/.trash/`，不自动清理。
- `reports/` 中的历史验证报告已把本机用户路径脱敏为 `<USER_HOME>`，未改动任何验证结论。

## 目录说明

详见 `README.txt`（项目完整说明）与 `docs/`（DoD、需求追溯、里程碑汇报）。