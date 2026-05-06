# Stage 8 工作完成报告

## 1. 阶段信息

| 项目 | 内容 |
| --- | --- |
| 阶段名称 | Stage 8，输出文件归档封存、批量管理与正式公私钥验签阶段 |
| 完成日期 | 2026-05-04 |
| 阶段目标 | 实现输出文件归档封存与验签报告、规则包批量管理，并将规则包验签升级为正式 RSA 公私钥验签 |
| 阶段边界 | 不导出原始数据、加密数据、哈希数据、去标识摘要、派生键、对象级明细 |

## 2. 本阶段完成内容

### 2.1 正式公私钥验签

新增能力：

- 规则包签名从 HMAC 演示机制升级为 RSA 私钥签名、RSA 公钥验签。
- 受信任签名人配置从内存常量升级为 `workspace/config/trusted-signers.json`。
- 验签逻辑使用 OpenSSL 执行 SHA-256 + RSA 验签。
- 新增本地 RSA 密钥引导脚本和规则包签名脚本。

新增脚本：

- `scripts/bootstrap-stage8-keys.ps1`
- `scripts/generate-rule-package-signature.ps1`

### 2.2 规则包批量管理

新增能力：

- 支持批量规则包验签。
- 支持批量规则包审批。
- 返回逐包处理结果，包含成功状态、当前状态和说明消息。

新增模型：

- `RulePackageBatchAction`
- `RulePackageBatchResult`

新增接口：

- `POST /api/rule-packages/batch-verify`
- `POST /api/rule-packages/batch-approve`

### 2.3 输出文件归档封存与验签报告

新增能力：

- 选择多个本域输出文件执行归档封存。
- 复制输出文件到 `workspace/archives/<archive_id>/files`
- 生成归档清单 `archive-manifest.json`
- 使用归档封存中心私钥生成 `archive-manifest.sig`
- 生成归档报告 `archive-report.json`
- 支持重新验签归档报告

新增模型：

- `ExportArchiveCreate`
- `ExportArchiveVerification`
- `ExportArchive`

新增接口：

- `GET /api/export-archives`
- `POST /api/export-archives`
- `GET /api/export-archives/{archive_id}/verify`

### 2.4 前端增强

新增页面能力：

- 规则包支持复选框批量选择。
- 规则包支持批量验签和批量审批。
- 输出文件支持复选框批量归档。
- 归档员和归档用途可录入。
- 归档记录支持重新验签报告。
- 页面阶段提示升级为 Stage 8。

### 2.5 测试增强

本阶段将后端单元测试从 32 个扩展到 34 个。

新增测试覆盖：

- RSA 公私钥规则包签名可通过验签。
- 修改规则内容后原签名立即失效。
- 归档封存可生成签名清单与验签报告。
- 篡改归档 manifest 后验签报告失败。

## 3. 系统累计已实现功能总览

截至 Stage 8，系统已实现的全部功能如下。

### 3.1 本域数据导入与画像

- 支持导入 `CSV`、`XLSX`、`XLS` 文件到本域 `workspace/imports`。
- 对 CSV 执行字段画像，输出字段名、类型、空值数、非空数、重复数和样例值。
- 对空文件、错误文件类型、CSV 编码异常和缺失表头执行失败关闭。

### 3.2 字段映射与本地存储

- 支持保存主键字段、子键字段、敏感字段和聚合分组字段映射。
- 本地状态持久化使用 SQLite：`workspace/config/app-state.sqlite3`。
- 兼容旧 JSON 状态，支持自动迁移与旧字段补默认值。

### 3.3 本域任务执行与结果摘要

- 支持基于单数据集执行本域联查任务。
- 在内存中完成主键材料拼接、子键材料拼接和去标识摘要计算。
- 输出结果只包含摘要计数、重复组数量、执行回执、结论声明和阈值后聚合统计。
- 不返回原始值、派生键、去标识摘要和对象级明细。

### 3.4 聚合统计与规则表达式

- 支持 `department`、`matter_type`、`month` 三个单维粗粒度分组。
- 支持最小阈值控制，默认阈值为 `10`。
- 对低于阈值的分组执行抑制，不在结果和输出中暴露组名。
- 支持最小规则表达式：字段、操作符、值。
- 已支持操作符：`eq`、`neq`、`exists`、`not_empty`、`in`、`gte`、`lte`。
- 规则表达式仅输出通过、失败、未知数量，不输出命中明细。

### 3.5 规则包治理

- 支持规则包登记、查看、单个验签、单个审批。
- 支持规则包批量验签和批量审批。
- 规则包包含名称、用途、版本、规则列表、签名人、签名引用、签名值和验签状态。
- 未通过验签的规则包会标记为 `invalid`，不能审批通过，也不能绑定任务执行。

### 3.6 规则包签名与验签

- Stage 7 引入规则包验签流。
- Stage 8 已升级为 RSA 私钥签名与公钥验签。
- 受信任签名人配置存放于 `workspace/config/trusted-signers.json`。
- 新增本地密钥引导脚本 `scripts/bootstrap-stage8-keys.ps1`。
- 新增本地规则包签名脚本 `scripts/generate-rule-package-signature.ps1`。

### 3.7 结论声明审核

- `manual_assertion` 任务会生成待审核结论声明草稿。
- 结论声明支持 `pending_review`、`approved`、`rejected` 三种状态。
- 支持填写正式结论文本、审核意见和驳回原因。
- 未正式审核通过的结论声明不能申请输出，也不能生成输出包。

### 3.8 安全输出审批与输出包

- 支持创建安全输出申请。
- 支持审批输出申请，且审批人与申请人必须分离。
- 支持三类输出：执行回执、结论声明、聚合统计。
- 支持预览安全输出包。
- 输出包明确不包含原始数据、派生键、去标识摘要和对象级明细。

### 3.9 输出文件落盘、归档封存与验签报告

- 已审批安全输出包可写入本域 `workspace/exports`。
- 输出文件记录包含文件名、路径、字节数、SHA-256 哈希和安全说明。
- 支持多文件归档封存到 `workspace/archives/<archive_id>`。
- 归档封存会生成 `archive-manifest.json`、`archive-manifest.sig` 和 `archive-report.json`。
- 支持对归档报告重新执行验签复核。

### 3.10 审计与日志

- 系统操作会写入本地审计记录和 `workspace/audit/audit-log.jsonl`。
- 审计 JSONL 包含 `previous_hash` 与 `entry_hash` 链式哈希。
- 支持校验审计链完整性，识别内容篡改和断链。
- 应用日志写入 `workspace/logs/app.log`，支持滚动日志。

### 3.11 前端工作台

- 已提供完整前端工作台，覆盖数据导入、字段映射、规则包管理、任务执行、结果摘要、安全输出、审计校验、归档封存。
- 支持规则包验签状态展示、批量选择、批量验签、批量审批。
- 支持结论声明审核通过与驳回。
- 支持输出文件多选归档和归档报告重新验签。

### 3.12 脚本与验证

- 已提供后端启动、前端启动、停止服务脚本。
- 已提供 `run-stage3-checks.ps1` 至 `run-stage8-checks.ps1` 阶段检查脚本。
- 已提供本地密钥初始化和规则包签名脚本。
- 后端当前累计单元测试 34 个，覆盖执行、规则表达式、输出审批、审计链、结论审核、RSA 验签和归档封存。

## 4. 修改文件

| 文件 | 说明 |
| --- | --- |
| `backend/app/core/config.py` | 增加归档目录、密钥目录和配置文件路径 |
| `backend/app/models/schemas.py` | 增加批量管理、归档封存与验签报告模型 |
| `backend/app/services/rule_signatures.py` | 将规则包验签升级为 RSA 公钥验签 |
| `backend/app/services/archives.py` | 新增输出文件归档封存与验签报告服务 |
| `backend/app/services/storage.py` | 增加 `export_archives` 本地状态集合 |
| `backend/app/main.py` | 新增规则包批量接口、归档封存接口和 Stage 8 版本信息 |
| `backend/tests/test_rule_signatures.py` | 改为真实 RSA 签名验签测试 |
| `backend/tests/test_archives.py` | 新增归档封存与验签报告测试 |
| `frontend/src/types.ts` | 增加批量管理与归档封存类型 |
| `frontend/src/api.ts` | 增加批量验签、批量审批、归档封存 API |
| `frontend/src/App.tsx` | 增加批量管理与归档操作 UI |
| `.gitignore` | 忽略归档文件、密钥与本地签名配置 |
| `workspace/archives/.gitkeep` | 增加归档目录占位 |
| `workspace/config/keys/.../.gitkeep` | 增加密钥目录占位 |
| `frontend/package.json` | 阶段版本更新为 `0.8.0-stage8` |
| `frontend/package-lock.json` | 阶段版本同步为 `0.8.0-stage8` |
| `README.md` | 当前阶段和 Stage 8 能力说明更新 |
| `scripts/run-stage8-checks.ps1` | 新增 Stage 8 检查脚本 |
| `docs/Stage8-归档封存与正式公私钥验签说明.md` | 新增 Stage 8 说明文档 |

## 5. 数据不出域复核

本阶段虽然增加了归档封存和本地密钥，但仍然只在本域内处理数据与密钥材料。

仍然禁止：

- 原始数据出域。
- 加密数据出域。
- 哈希数据出域。
- 去标识摘要出域。
- 派生主键 / 子键出域。
- 对象级明细出域。
- 低于阈值的聚合分组出域。

归档封存只复制已经符合安全边界的输出文件，不扩大输出范围。

## 6. 验证方式

```powershell
.\scripts\run-stage8-checks.ps1
```

## 7. 验证结果

验证日期：2026-05-04

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 后端编译 | 通过 | `python -m compileall backend\app` 正常完成 |
| 后端单元测试 | 通过 | `python -m unittest discover -s tests`，共 34 个测试通过 |
| 前端生产构建 | 通过 | `npm run build` 正常完成，Vite 生成 `frontend/dist` |

补充说明：

- 单独运行 `npm run build` 可以通过，但统一检查脚本首次在沙箱内仍可能触发 `spawn EPERM`。
- 按执行环境规则提升权限后重跑同一 Stage 8 检查脚本，完整验证通过。
- 当前 RSA 验签依赖本机 OpenSSL，可满足离线原型需求；若进入正式生产，应切换到稳定的应用内密码库和证书生命周期管理。

## 8. 阶段结论

当前阶段：Stage 8，输出文件归档封存、批量管理与正式公私钥验签阶段。

阶段状态：已完成并通过本地验证。

本轮产出：完成 RSA 规则包验签、批量规则包管理、输出文件归档封存、归档验签报告和 34 个后端单元测试。

下一阶段建议：进入正式证书管理、规则包版本对比与批量导入、归档报告检索与封存策略管理。
