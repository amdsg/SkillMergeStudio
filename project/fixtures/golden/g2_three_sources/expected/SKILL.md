---
name: golden-g2
description: 合并 3 个技能（跨领域），涵盖 g2-a、g2-b、g2-c，当任务涉及相关工作流时使用。
version: 1.0.0
author: Skill Merge Studio
merged-from:
  - g2-a (custom)
  - g2-b (custom)
  - g2-c (custom)
merge-plan: ./merge_plan.json
source-hashes:
  - "sha256:1670374d577d51299826ccda0ba62930fc7dbe53dbb7857b411120dc27f631db"
  - "sha256:c581668cc6e304888a548fa4b4aa8e3089d73a6adab91224cc5e4994d34ea211"
  - "sha256:f705b83e6ac5febcd2c2f0cecd2f50d1ae2e57528caf64b6cb37130e2a20a35c"
generator: skillmerge-studio/1.0.0
---

# golden-g2

## 来源说明

本次合并来自 3 个技能：

- g2-a（custom）
- g2-b（custom）
- g2-c（custom）

## 工作流

<!-- conflict: source=a:工作流, sim=0.000 -->


公共步骤：校验输入。

步骤一：读取数据。

<!-- conflict: source=b:工作流, sim=0.000 -->


步骤二：生成报告。

<!-- conflict: source=c:工作流, sim=0.000 -->


步骤三：保存产物。

## 合并报告

- 策略：keep-all
- 源技能：3 个
- 完全相同段落去重：1
- 近重复建议（未删除）：0
- 冲突章节：1
- 建议合并章节：0
- 差异较大需复核：0
- 生成器：skillmerge-studio/1.0.0

### 冲突章节

- 工作流（sim=0.000）：a / b / c
