# Stage 7 规则包验签与结论声明审核说明

## 1. 当前阶段

当前阶段：Stage 7，规则包验签与结论声明正式审核阶段。

本阶段将两条此前尚未闭环的控制链补齐：

- 规则包从“签名引用”升级为“本域真实验签后才能审批入用”。
- 结论声明从“待审核草稿”升级为“正式审核通过后才能申请安全输出”。

## 2. 规则包验签

规则包新增字段：

- `signer_name`
- `signature_ref`
- `signature`
- `verification_status`
- `verification_message`
- `verified_at`

验签规则：

- 签名人必须位于本域受信任签名人名单中。
- 签名引用必须与签名人配置一致。
- 签名值必须能够通过本域 HMAC-SHA256 验签。
- 未通过验签的规则包状态标记为 `invalid`，不能审批通过。

新增接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/rule-signers` | 查询本域受信任签名人 |
| POST | `/api/rule-packages/{package_id}/verify` | 重新执行规则包验签 |

## 3. 结论声明正式审核

结论声明状态对象新增：

- `pending_review`
- `approved`
- `rejected`

审核规则：

- 只有 `pending_review` 状态的结论声明可以审核。
- 审核通过时可填写正式结论文本。
- 审核驳回时记录驳回原因或审核意见。
- 未正式审核通过的结论声明不得申请输出。
- 未正式审核通过的结论声明不得生成安全输出包。

新增接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/results/{result_id}/assertion/review` | 审核通过或驳回结论声明 |

## 4. 本地签名脚本

新增脚本：

```powershell
.\scripts\generate-rule-package-signature.ps1
```

用途：

- 为演示环境中的规则包生成本地签名值。
- 便于离线完成“签发 -> 导入 -> 验签 -> 审批”的完整流程。

## 5. 前端变化

前端新增：

- 规则包签名人、签名值录入。
- 规则包验签结果展示。
- 规则包重新验签按钮。
- 结论声明审核人、正式结论、审核意见录入。
- 结论声明审核通过与驳回操作。

## 6. 验证方式

```powershell
.\scripts\run-stage7-checks.ps1
```

2026-05-04 验证结果：通过。
