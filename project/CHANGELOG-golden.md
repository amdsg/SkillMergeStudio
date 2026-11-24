# Golden 变更记录

## 2026-11-22 M2 初始 golden

- g1_single：单源合并。
- g2_three_sources：三源同名章节与完全重复段落。
- g3_conflicts：同名章节内容差异大，冲突注释保留双方。
- g4_resources：资源按 sha256 去重、同名不同内容重命名。
- g5_aliases：标题别名（工作流程 → 工作流）对齐。

## 2026-11-22 M2 合并计划补充 omitted

- `merge_plan.json` 新增 `omitted` 数组，记录 prefer-first/prefer-largest/manual 下被省略的源章节。
- 5 组 golden 因 plan 结构新增字段而重建；正文与资源未变化。

说明：
- 初始内容由 `python tools/make_golden.py` 生成，生成后冻结。
- `merge_plan.json` 比对时将 `sources[].path` 归一化为 `<source>`，避免绝对路径影响字节级一致性。
- `manifest.json` 含 `created_at` 与临时源路径，不参与字节比对，仅校验结构与关键字段。
- 任何修改算法导致 golden 变化，必须在本文件新增条目并说明差异，禁止静默改写。