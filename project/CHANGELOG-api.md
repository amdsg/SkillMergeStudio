# API 变更记录

## 2026-11-22 M3b api_version 1.0 → 1.1

- `GET /api/platforms` 返回 `items/page/total/counts/evidence/diagnostics/sources`。
- 新增筛选：`kind/group/verified/evidence/q/sort/limit/offset`。
- 新增 `GET /api/platforms/{id}` 详情。
- **破坏点**：candidate 的 `limits` 由对象变为 `null`；同时提供 `legacy_limits_present=true` 与详情中的 `legacy_limits`。
- 新增 `confirm_candidate=true` 才能导出候选平台；未确认返回 400 `PLATFORM_NOT_SELECTABLE`。
- 候选导出校验必须包含 `V-RULE-02` 与 `V-RULE-05`；不可达/发现源对象不可导出。
- 计数口径：`verified` 与 `evidence_*` 分列，禁止相加；`evidence` 缺失显示为 null/—，不显示 0。
## 2026-11-23 增量 api_version 1.1 → 1.2（扫描进度 · 多平台导出）

新增（只增不改）：

- `GET /api/platforms` 与平台详情新增 `format{package_type,wrap,skill_md_path,install_scopes,rule_source,rule_status,requires_confirm,limits_source}`；候选 `limits` 仍为 `null`。
- `POST /api/export` 支持 `platforms[]`（1–28 个、去重保序）：批量响应 `202 {job_id,status,type:"export",batch:true,platforms:[...]}`；单平台 `platform` 请求与响应不变。
- 批量任务结果 `result{batch,source_artifact_id,items[],summary{total,succeeded,failed,cancelled}}`；`items[]` 含 `platform/label/kind/status/dir_path/zip_path/installed_path/size_bytes/sha256/sources_count/format/download_url/error`。
- 新增 `POST /api/export/preview`（只读，零写盘）：`{artifact_id,platform|platforms[],mode,...}` → `{artifact_id,items[],summary{total,verified,candidate,installable}}`。
- manifest 新增顶层 `package_type` 与 `format{wrap,skill_md_path,rule_status,limits_source,install_available}`；既有键名称、类型、含义不变。
- `GET /api/history?platform=` 新增可选筛选；缺省行为不变。
- 新增错误码：`EXPORT_BATCH_EMPTY`、`EXPORT_BATCH_TOO_LARGE`、`EXPORT_PLATFORM_UNKNOWN`、`EXPORT_INSTALL_UNAVAILABLE`；复用 `PLATFORM_NOT_SELECTABLE`。
- SSE `phase` 值域扩展 `export`；事件既有 7 字段不变。
- 批量部分/全部平台失败时任务终态仍为 `succeeded`，失败明细在 `items[].error` 与 `summary.failed`；取消时任务终态为 `cancelled`，已完成平台保留产物。
- `api_version` 1.1 → 1.2。