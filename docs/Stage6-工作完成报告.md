# Stage 6 工作完成报告

## 1. 阶段信息

| 项目 | 内容 |
| --- | --- |
| 阶段名称 | Stage 6，输出包受控落盘与审计链校验阶段 |
| 完成日期 | 2026-04-29 |
| 阶段目标 | 将已审批安全输出包写入本域受控目录，并提供审计链完整性校验 |
| 阶段边界 | 不导出原始数据、加密数据、哈希数据、去标识摘要、派生键、对象级明细 |

## 2. 本阶段完成内容

### 2.1 安全输出包受控落盘

新增能力：

- 已审批输出申请可以生成安全输出包并写入 `workspace/exports`。
- 输出文件使用 JSON 格式保存，内容来自 Stage 5 已审批安全输出包。
- 写入文件后生成本域输出文件记录。
- 输出文件记录包含文件名、路径、字节数、SHA-256 哈希和安全说明。

新增模型：

- `ExportFile`

新增服务函数：

- `persist_export_package`

新增接口：

- `GET /api/export-files`
- `POST /api/export-requests/{request_id}/file`

### 2.2 审计链完整性校验

新增能力：

- 校验 `workspace/audit/audit-log.jsonl` 是否保持链式完整。
- 识别审计记录内容篡改。
- 识别 `previous_hash` 断链。
- 返回首个异常行号和错误说明。

新增模型：

- `AuditChainVerification`

新增服务函数：

- `compute_entry_hash`
- `verify_audit_chain`

新增接口：

- `GET /api/audit/verify`

### 2.3 前端增强

新增页面能力：

- 输出申请审批通过后，支持点击“写入本域文件”。
- 展示最近本域输出文件、文件大小和哈希前缀。
- 边界审计区支持点击“校验审计链完整性”。
- 展示审计链校验结果、检查条数、链头哈希和异常信息。

前端阶段提示已更新为 Stage 6。

### 2.4 测试增强

本阶段将后端单元测试从 18 个扩展到 23 个。

新增测试覆盖：

- 聚合统计输出文件只包含阈值后聚合结果和抑制分组数量。
- 聚合统计输出文件不包含 `citizen_name`、`id_card`、派生主键、去标识摘要等敏感字段。
- 回执输出文件只包含回执 payload，不混入聚合统计内容和结论声明正文。
- 完整审计链可通过校验。
- 审计记录正文被篡改时可识别 `entry_hash` 校验失败。
- 审计记录 `previous_hash` 被破坏时可识别断链。

## 3. 修改文件

| 文件 | 说明 |
| --- | --- |
| `backend/app/core/config.py` | 增加 `EXPORTS_DIR` 常量 |
| `backend/app/models/schemas.py` | 增加 `ExportFile` 和 `AuditChainVerification` 模型 |
| `backend/app/services/storage.py` | 增加 `export_files` 本地状态集合 |
| `backend/app/services/exports.py` | 增加安全输出包本域落盘能力 |
| `backend/app/services/audit.py` | 增加审计链哈希计算和完整性校验 |
| `backend/app/main.py` | 增加输出文件和审计链校验 API |
| `backend/tests/test_exports.py` | 增加输出文件内容边界测试 |
| `backend/tests/test_audit_chain.py` | 增加审计链完整和篡改检测测试 |
| `frontend/src/types.ts` | 增加输出文件和审计链校验类型 |
| `frontend/src/api.ts` | 增加输出文件和审计链校验 API 调用 |
| `frontend/src/App.tsx` | 增加输出落盘和审计链校验 UI |
| `frontend/package.json` | 阶段版本更新为 `0.6.0-stage6` |
| `README.md` | 当前阶段和 Stage 6 能力说明更新 |
| `scripts/run-stage6-checks.ps1` | 新增 Stage 6 本地验证脚本 |

## 4. 数据不出域复核

本阶段只把已审批安全输出包写入本域目录，没有新增任何跨域传输能力。

落盘文件仍然禁止包含：

- 原始数据。
- 加密数据。
- 哈希数据。
- 去标识摘要。
- 派生主键 / 子键。
- 对象级明细。
- 低于阈值的聚合分组。

输出文件哈希 `sha256` 仅用于本域归档核验，不作为可出域联查标识使用。

## 5. 验证方式

```powershell
.\scripts\run-stage6-checks.ps1
```

## 6. 验证结果

验证日期：2026-04-29

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 后端编译 | 通过 | `python -m compileall backend\app` 正常完成 |
| 后端单元测试 | 通过 | `python -m unittest discover -s tests`，共 23 个测试通过 |
| 前端生产构建 | 通过 | `npm run build` 正常完成，Vite 生成 `frontend/dist` |

补充说明：

- 首次在沙箱内运行前端构建时，Vite/esbuild 因子进程启动限制出现 `spawn EPERM`。
- 按执行环境规则提升权限后重跑同一 Stage 6 检查脚本，完整验证通过。
- 本阶段曾修正一个测试断言：回执可包含 `output_policy` 元信息，但不得混入聚合统计内容或结论声明正文。

## 7. 阶段结论

当前阶段：Stage 6，输出包受控落盘与审计链校验阶段。

阶段状态：已完成并通过本地验证。

本轮产出：完成安全输出文件落盘、输出文件记录、审计链完整性校验、前端操作入口和 23 个后端单元测试。

下一阶段建议：进入规则包真实签名验签、结论声明正式审核流，或输出文件归档封存与验签报告生成。
