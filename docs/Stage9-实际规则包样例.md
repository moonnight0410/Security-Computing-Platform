# Stage 9 实际规则包样例

## 1. 样例用途

这份样例用于说明：

- 当前项目里“规则包”到底长什么样。
- 一个真实可落地的规则包应该包含哪些内容。
- Stage 9 做“创建与编辑核心模块”后，这个对象会如何演进。

本样例严格遵守当前项目边界：

- 不包含任何业务对象明细数据。
- 不包含任何原始数据、加密数据、哈希数据、去标识数据。
- 只描述规则条件、用途、签名、审批和审计所需元信息。

## 2. 业务场景

这里给一个真实感较强的场景：

- 规则包名称：`民政补贴资格复核规则包`
- 目标：在本域内对已导入数据集做资格复核筛查
- 输出目标：仅允许本域执行结果、执行回执、经审批结论声明、满足阈值的聚合统计

这个规则包本身不带任何人、任何对象、任何命中名单，只带“怎么查”的规则。

## 3. 当前项目可直接使用的创建样例

当前后端 `RulePackageCreate` 结构如下：

- `name`
- `version`
- `purpose`
- `signer_name`
- `signature_ref`
- `signature`
- `rules`
- `notes`

下面这份 JSON 就是贴近当前项目接口的实际样例。

```json
{
  "name": "民政补贴资格复核规则包",
  "version": "0.1.0",
  "purpose": "用于本域内筛查补贴资格复核对象，仅输出执行回执、结论声明或满足阈值的聚合统计，不返回对象级明细",
  "signer_name": "市级规则中心",
  "signature_ref": "SIG-MZBT-20260504-001",
  "signature": "BASE64_RSA_SIGNATURE_PLACEHOLDER",
  "rules": [
    {
      "field": "benefit_status",
      "operator": "eq",
      "value": "正常"
    },
    {
      "field": "review_flag",
      "operator": "eq",
      "value": "待复核"
    },
    {
      "field": "household_income_level",
      "operator": "lte",
      "value": "2"
    },
    {
      "field": "department",
      "operator": "eq",
      "value": "民政"
    }
  ],
  "notes": "不含数据，仅含复核逻辑。适用于民政补贴资格年度复核任务。"
}
```

## 4. 这份规则包是什么意思

上面那 4 条规则的业务含义可以翻译成：

1. 补贴状态必须是“正常”。
2. 当前复核标记必须是“待复核”。
3. 家庭收入等级必须不高于 2。
4. 记录所属部门必须是“民政”。

这就是一个典型的“规则包”：

- 它定义筛查条件。
- 它不携带命中的对象。
- 它不携带任何名单或结果。
- 它只描述本域内怎么执行。

## 5. 在当前系统中创建后，后台对象大致会变成什么样

规则包创建后，系统里保存的对象会更完整，通常会多出状态和时间字段。

一个贴近当前系统 `RulePackage` 的保存态样例如下：

```json
{
  "id": "rp_20260504_0001",
  "name": "民政补贴资格复核规则包",
  "version": "0.1.0",
  "purpose": "用于本域内筛查补贴资格复核对象，仅输出执行回执、结论声明或满足阈值的聚合统计，不返回对象级明细",
  "signer_name": "市级规则中心",
  "signature_ref": "SIG-MZBT-20260504-001",
  "signature": "BASE64_RSA_SIGNATURE_PLACEHOLDER",
  "rules": [
    {
      "field": "benefit_status",
      "operator": "eq",
      "value": "正常"
    },
    {
      "field": "review_flag",
      "operator": "eq",
      "value": "待复核"
    },
    {
      "field": "household_income_level",
      "operator": "lte",
      "value": "2"
    },
    {
      "field": "department",
      "operator": "eq",
      "value": "民政"
    }
  ],
  "rules_count": 4,
  "status": "pending_review",
  "verification_status": "verified",
  "verification_message": "RSA signature verified",
  "verified_at": "2026-05-04T14:10:00+08:00",
  "approved_by": null,
  "approved_at": null,
  "created_at": "2026-05-04T14:08:31+08:00",
  "notes": "不含数据，仅含复核逻辑。适用于民政补贴资格年度复核任务。"
}
```

这个状态表示：

- 规则包已经创建。
- 签名已经通过本域验签。
- 但还没有审批通过。
- 所以它还不能正式被任务使用。

## 6. 审批通过后的样子

审批通过后，规则包才会变成可绑定任务的正式对象。

```json
{
  "id": "rp_20260504_0001",
  "name": "民政补贴资格复核规则包",
  "version": "0.1.0",
  "purpose": "用于本域内筛查补贴资格复核对象，仅输出执行回执、结论声明或满足阈值的聚合统计，不返回对象级明细",
  "signer_name": "市级规则中心",
  "signature_ref": "SIG-MZBT-20260504-001",
  "signature": "BASE64_RSA_SIGNATURE_PLACEHOLDER",
  "rules": [
    {
      "field": "benefit_status",
      "operator": "eq",
      "value": "正常"
    },
    {
      "field": "review_flag",
      "operator": "eq",
      "value": "待复核"
    },
    {
      "field": "household_income_level",
      "operator": "lte",
      "value": "2"
    },
    {
      "field": "department",
      "operator": "eq",
      "value": "民政"
    }
  ],
  "rules_count": 4,
  "status": "approved",
  "verification_status": "verified",
  "verification_message": "RSA signature verified",
  "verified_at": "2026-05-04T14:10:00+08:00",
  "approved_by": "审核员B",
  "approved_at": "2026-05-04T14:15:42+08:00",
  "created_at": "2026-05-04T14:08:31+08:00",
  "notes": "不含数据，仅含复核逻辑。适用于民政补贴资格年度复核任务。"
}
```

## 7. 如果按 Stage 9 做“创建与编辑核心模块”，这个规则包会怎么演进

你刚刚确认的 Stage 9 方向不是只做“创建”，而是把它做成核心模块。

所以它会从“一个规则包对象”演进成：

- 一个主规则包对象
- 多个修订快照
- 每次保存都会形成历史修订
- 已审批规则包点击“编辑”时，系统自动转成新修订草稿

## 8. Stage 9 下的主对象样例

这是建议中的主对象结构，不是当前接口原样，但会是下一阶段核心模块的目标形态。

```json
{
  "rule_package_id": "rp_20260504_0001",
  "current_revision_id": "rpr_20260504_0003",
  "current_revision_no": 3,
  "name": "民政补贴资格复核规则包",
  "purpose": "用于本域内筛查补贴资格复核对象，仅输出执行回执、结论声明或满足阈值的聚合统计，不返回对象级明细",
  "status": "approved",
  "verification_status": "verified",
  "latest_editor_name": "经办员A",
  "latest_edited_at": "2026-05-04T15:22:10+08:00",
  "signature_outdated": false,
  "is_deprecated": false,
  "created_at": "2026-05-04T14:08:31+08:00",
  "updated_at": "2026-05-04T15:22:10+08:00"
}
```

## 9. Stage 9 下的修订快照样例

### 9.1 修订 1：首版草稿

```json
{
  "revision_id": "rpr_20260504_0001",
  "rule_package_id": "rp_20260504_0001",
  "revision_no": 1,
  "name": "民政补贴资格复核规则包",
  "purpose": "用于本域内筛查补贴资格复核对象，仅输出执行回执、结论声明或满足阈值的聚合统计，不返回对象级明细",
  "rules": [
    {
      "field": "benefit_status",
      "operator": "eq",
      "value": "正常"
    },
    {
      "field": "review_flag",
      "operator": "eq",
      "value": "待复核"
    }
  ],
  "signer_name": "",
  "signature_ref": "",
  "signature": "",
  "signature_outdated": true,
  "verification_status": "draft",
  "status": "draft",
  "change_summary": "创建首版草稿",
  "editor_name": "经办员A",
  "saved_by_auto": false,
  "created_at": "2026-05-04T14:08:31+08:00",
  "content_hash": "sha256:placeholder-v1",
  "based_on_revision_id": null
}
```

### 9.2 修订 2：补充完整规则后保存

```json
{
  "revision_id": "rpr_20260504_0002",
  "rule_package_id": "rp_20260504_0001",
  "revision_no": 2,
  "name": "民政补贴资格复核规则包",
  "purpose": "用于本域内筛查补贴资格复核对象，仅输出执行回执、结论声明或满足阈值的聚合统计，不返回对象级明细",
  "rules": [
    {
      "field": "benefit_status",
      "operator": "eq",
      "value": "正常"
    },
    {
      "field": "review_flag",
      "operator": "eq",
      "value": "待复核"
    },
    {
      "field": "household_income_level",
      "operator": "lte",
      "value": "2"
    },
    {
      "field": "department",
      "operator": "eq",
      "value": "民政"
    }
  ],
  "signer_name": "",
  "signature_ref": "",
  "signature": "",
  "signature_outdated": true,
  "verification_status": "draft",
  "status": "draft",
  "change_summary": "补充资格复核完整规则",
  "editor_name": "经办员A",
  "saved_by_auto": false,
  "created_at": "2026-05-04T14:20:05+08:00",
  "content_hash": "sha256:placeholder-v2",
  "based_on_revision_id": "rpr_20260504_0001"
}
```

### 9.3 修订 3：签名、验签、审批后的正式版

```json
{
  "revision_id": "rpr_20260504_0003",
  "rule_package_id": "rp_20260504_0001",
  "revision_no": 3,
  "name": "民政补贴资格复核规则包",
  "purpose": "用于本域内筛查补贴资格复核对象，仅输出执行回执、结论声明或满足阈值的聚合统计，不返回对象级明细",
  "rules": [
    {
      "field": "benefit_status",
      "operator": "eq",
      "value": "正常"
    },
    {
      "field": "review_flag",
      "operator": "eq",
      "value": "待复核"
    },
    {
      "field": "household_income_level",
      "operator": "lte",
      "value": "2"
    },
    {
      "field": "department",
      "operator": "eq",
      "value": "民政"
    }
  ],
  "signer_name": "市级规则中心",
  "signature_ref": "SIG-MZBT-20260504-001",
  "signature": "BASE64_RSA_SIGNATURE_PLACEHOLDER",
  "signature_outdated": false,
  "verification_status": "verified",
  "status": "approved",
  "change_summary": "首版正式发布",
  "editor_name": "经办员A",
  "saved_by_auto": false,
  "created_at": "2026-05-04T15:22:10+08:00",
  "content_hash": "sha256:placeholder-v3",
  "based_on_revision_id": "rpr_20260504_0002"
}
```

## 10. 一个真实的编辑场景

假设后面政策调整，需要新增一条规则：

- `subsidy_year` 必须等于 `2026`

那在 Stage 9 的正确处理方式不是直接改修订 3，而是：

1. 用户点“编辑”
2. 系统自动从已审批修订 3 派生修订 4 草稿
3. 用户新增规则
4. 保存形成新快照
5. 旧签名自动失效
6. 重新签名
7. 重新验签
8. 重新审批

新增后的修订 4 草稿内容可以是：

```json
{
  "revision_id": "rpr_20260510_0004",
  "rule_package_id": "rp_20260504_0001",
  "revision_no": 4,
  "name": "民政补贴资格复核规则包",
  "purpose": "用于本域内筛查补贴资格复核对象，仅输出执行回执、结论声明或满足阈值的聚合统计，不返回对象级明细",
  "rules": [
    {
      "field": "benefit_status",
      "operator": "eq",
      "value": "正常"
    },
    {
      "field": "review_flag",
      "operator": "eq",
      "value": "待复核"
    },
    {
      "field": "household_income_level",
      "operator": "lte",
      "value": "2"
    },
    {
      "field": "department",
      "operator": "eq",
      "value": "民政"
    },
    {
      "field": "subsidy_year",
      "operator": "eq",
      "value": "2026"
    }
  ],
  "signer_name": "市级规则中心",
  "signature_ref": "SIG-MZBT-20260510-002",
  "signature": "",
  "signature_outdated": true,
  "verification_status": "draft",
  "status": "draft",
  "change_summary": "按 2026 年政策口径新增补贴年度条件",
  "editor_name": "经办员A",
  "saved_by_auto": false,
  "created_at": "2026-05-10T09:30:00+08:00",
  "content_hash": "sha256:placeholder-v4",
  "based_on_revision_id": "rpr_20260504_0003"
}
```

## 11. 这个样例为什么算“实际”

它是实际的，不是因为里面有真实数据，而是因为它符合真实系统治理要求：

- 有明确业务目的
- 有具体规则条目
- 有签名和验签位置
- 有审批状态
- 有修订历史
- 有编辑后的重新签名逻辑
- 能和本域任务执行直接对接

如果规则包样例只有一句“查询异常人员”，那不叫实际样例，那只是标题。

## 12. 我对这个核心模块的建议

如果你认这个样例方向，下一步实现时我建议直接按这个样例去驱动：

- 先做规则包中心
- 再做修订快照
- 再做编辑保存和自动保存
- 再把任务绑定从 `rule_package_id` 改到 `rule_package_revision_id`

