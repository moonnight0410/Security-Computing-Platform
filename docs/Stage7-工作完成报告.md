# Stage 7 工作完成报告

## 1. 阶段信息

| 项目 | 内容 |
| --- | --- |
| 阶段名称 | Stage 7，规则包验签与结论声明正式审核阶段 |
| 完成日期 | 2026-05-04 |
| 阶段目标 | 让规则包必须通过本域验签后才能审批入用，并让结论声明必须正式审核通过后才能输出 |
| 阶段边界 | 不导出原始数据、加密数据、哈希数据、去标识摘要、派生键、对象级明细 |

## 2. 本阶段完成内容

### 2.1 规则包真实验签

新增能力：

- 规则包创建时记录签名人、签名引用和签名值。
- 系统在本域对规则包内容执行 HMAC-SHA256 验签。
- 验签失败的规则包自动标记为 `invalid`。
- 未通过验签的规则包不能审批通过，不能绑定到任务执行。
- 支持对已有规则包重新执行验签。

新增模型与字段：

- `TrustedSignerInfo`
- `RulePackage.signer_name`
- `RulePackage.signature`
- `RulePackage.verification_status`
- `RulePackage.verification_message`
- `RulePackage.verified_at`

新增接口：

- `GET /api/rule-signers`
- `POST /api/rule-packages/{package_id}/verify`

新增脚本：

- `scripts/generate-rule-package-signature.ps1`

### 2.2 结论声明正式审核流

新增能力：

- 任务执行生成的结论声明草稿使用明确状态对象保存。
- 结论声明支持正式审核通过或驳回。
- 审核通过时可覆盖为正式结论文本。
- 审核驳回时记录审核意见和驳回原因。
- 只有 `approved` 状态的结论声明才能申请输出和生成输出包。

新增模型与字段：

- `AssertionReviewState`
- `AssertionReviewRequest`
- `TaskResult.assertion` 从普通字典升级为结构化审核状态对象

新增接口：

- `POST /api/results/{result_id}/assertion/review`

### 2.3 前端增强

新增页面能力：

- 规则包登记支持选择签名人、录入签名值。
- 规则包列表显示验签状态和验签信息。
- 规则包支持重新验签与审批通过操作分离。
- 结果摘要区新增结论声明审核表单。
- 结论声明支持“审核通过”和“驳回结论”操作。
- 当结论声明未正式审核通过时，后端会拒绝结论声明类输出申请。

### 2.4 测试增强

本阶段将后端单元测试从 23 个扩展到 32 个。

新增测试覆盖：

- 合法规则包签名可以通过验签。
- 修改规则内容后原签名失效。
- 未知签名人会被拒绝。
- 验签失败规则包会被标记为 `invalid`。
- 结论声明审核通过可替换正式结论文本。
- 结论声明驳回会记录驳回原因。
- 已审核结论不能重复审核。
- 未正式审核通过的结论声明不能生成输出包。
- 已正式审核通过的结论声明才能进入输出包。

## 3. 修改文件

| 文件 | 说明 |
| --- | --- |
| `backend/app/models/schemas.py` | 增加规则包验签、结论声明审核相关模型与字段 |
| `backend/app/services/storage.py` | 兼容旧状态，补默认验签字段和结论声明审核字段 |
| `backend/app/services/rule_signatures.py` | 新增规则包验签服务 |
| `backend/app/services/assertions.py` | 新增结论声明审核服务 |
| `backend/app/services/execution.py` | 结论声明输出改为结构化审核状态 |
| `backend/app/services/exports.py` | 结论声明导出要求先完成正式审核 |
| `backend/app/main.py` | 新增规则签名人、验签、结论审核接口，更新阶段版本 |
| `backend/tests/test_rule_signatures.py` | 新增规则包验签测试 |
| `backend/tests/test_assertions.py` | 新增结论声明审核测试 |
| `backend/tests/test_exports.py` | 增加结论声明正式审核后导出测试 |
| `backend/tests/test_execution.py` | 适配结论声明结构化对象 |
| `frontend/src/types.ts` | 增加验签和结论审核类型 |
| `frontend/src/api.ts` | 增加验签、签名人、结论审核 API |
| `frontend/src/App.tsx` | 增加规则包验签和结论审核 UI |
| `frontend/package.json` | 阶段版本更新为 `0.7.0-stage7` |
| `frontend/package-lock.json` | 阶段版本同步为 `0.7.0-stage7` |
| `README.md` | 当前阶段和 Stage 7 能力说明更新 |
| `scripts/generate-rule-package-signature.ps1` | 新增本地签名脚本 |
| `scripts/run-stage7-checks.ps1` | 新增 Stage 7 本地验证脚本 |

## 4. 数据不出域复核

Stage 7 没有增加任何新的出域数据能力。

新增能力仍然只处理：

- 不含数据的规则包元数据与签名。
- 不含对象级明细的结论声明文本。
- 本域验签结果。
- 本域审核记录。

仍然禁止：

- 原始数据。
- 加密数据。
- 哈希数据。
- 去标识摘要。
- 派生主键 / 子键。
- 对象级明细。
- 可反推对象存在性的细粒度统计。

## 5. 验证方式

```powershell
.\scripts\run-stage7-checks.ps1
```

## 6. 验证结果

验证日期：2026-05-04

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 后端编译 | 通过 | `python -m compileall backend\app` 正常完成 |
| 后端单元测试 | 通过 | `python -m unittest discover -s tests`，共 32 个测试通过 |
| 前端生产构建 | 通过 | `npm run build` 正常完成，Vite 生成 `frontend/dist` |

补充说明：

- 首次在沙箱内运行 `.\scripts\run-stage7-checks.ps1` 时，前端构建仍出现 `spawn EPERM`。
- 按执行环境规则提升权限后重跑同一 Stage 7 检查脚本，完整验证通过。
- 新增的规则包演示签名使用本域离线共享验签密钥，仅用于当前离线原型环境，不等同于正式 PKI 体系。

## 7. 阶段结论

当前阶段：Stage 7，规则包验签与结论声明正式审核阶段。

阶段状态：已完成并通过本地验证。

本轮产出：完成规则包本域验签、结论声明正式审核、导出前审核约束、前端操作入口和 32 个后端单元测试。

下一阶段建议：进入输出文件归档封存与验签报告、规则包批量管理，或将演示签名机制升级为正式公私钥验签。
