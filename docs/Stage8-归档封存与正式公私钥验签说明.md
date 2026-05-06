# Stage 8 归档封存与正式公私钥验签说明

## 1. 当前阶段

当前阶段：Stage 8，输出文件归档封存、规则包批量管理与正式公私钥验签阶段。

本阶段承接 Stage 7，继续补齐三条能力：

- 输出文件归档封存与验签报告。
- 规则包批量验签与批量审批。
- 规则包验签从演示 HMAC 升级为 RSA 公私钥签名与公钥验签。

## 2. 规则包正式公私钥验签

Stage 8 使用 RSA 私钥签发规则包，使用受信任签名人的 RSA 公钥进行验签。

新增能力：

- 受信任签名人配置文件 `workspace/config/trusted-signers.json`
- 规则包签名脚本 `scripts/generate-rule-package-signature.ps1`
- 密钥引导脚本 `scripts/bootstrap-stage8-keys.ps1`
- 验签失败时返回 OpenSSL 实际验签结果

新增接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/rule-signers` | 查看受信任签名人公钥配置 |
| POST | `/api/rule-packages/{package_id}/verify` | 单个规则包重新验签 |
| POST | `/api/rule-packages/batch-verify` | 批量规则包验签 |
| POST | `/api/rule-packages/batch-approve` | 批量规则包审批 |

## 3. 输出文件归档封存

Stage 8 新增归档封存目录：

- `workspace/archives`

归档封存流程：

```text
已审批安全输出文件
  -> 选择多个输出文件
  -> 复制到归档目录
  -> 生成归档清单 manifest
  -> 使用归档封存中心私钥签名
  -> 生成验签报告 report
  -> 可再次执行验签复核
```

新增接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/export-archives` | 查看归档封存记录 |
| POST | `/api/export-archives` | 对选定输出文件执行归档封存 |
| GET | `/api/export-archives/{archive_id}/verify` | 重新验签归档报告 |

## 4. 本地密钥与配置

新增运行态目录：

- `workspace/config/keys/public`
- `workspace/config/keys/private`

新增运行态配置：

- `workspace/config/trusted-signers.json`
- `workspace/config/archive-signer.json`

这些文件默认只在本域生成和使用，不纳入版本库。

## 5. 前端变化

前端新增：

- 规则包多选复选框。
- 批量验签按钮。
- 批量审批按钮。
- 输出文件多选归档。
- 归档员与归档用途录入。
- 归档报告重新验签按钮。

## 6. 验证方式

```powershell
.\scripts\run-stage8-checks.ps1
```

2026-05-04 验证结果：通过。
