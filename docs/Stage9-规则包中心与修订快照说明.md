# Stage 9 规则包中心与修订快照说明

## 1. 当前阶段

当前阶段：Stage 9，规则包中心、修订快照与编辑治理阶段。

本阶段承接 Stage 8，在不改变“数据不得出域”总边界的前提下，把规则包从“登记对象”升级为“核心治理模块”。

## 2. 本阶段目标

本阶段重点实现以下能力：

- 独立规则包中心。
- 规则包草稿创建。
- 规则包修订快照保存。
- 已审批规则包点击“编辑”时自动派生修订草稿。
- 草稿允许无签名保存。
- 每次保存形成新修订快照。
- 提交验签、审批通过、废弃、删除受限。
- 任务绑定具体规则包修订 ID。

## 3. 后端模型调整

### 3.1 规则包主对象

`RulePackage` 新增：

- `current_revision_id`
- `current_revision_no`
- `latest_editor_name`
- `latest_edited_at`
- `signature_outdated`
- `updated_at`
- `deprecated_at`
- `deprecated_by`
- `deprecation_reason`

状态扩展为：

- `draft`
- `pending_review`
- `approved`
- `invalid`
- `deprecated`
- `deleted`

验签状态扩展为：

- `not_signed`
- `verified`
- `failed`
- `legacy_unverified`

### 3.2 修订快照对象

新增 `RulePackageRevision`，用于保存每次草稿保存后的不可变快照。

核心字段包括：

- `rule_package_id`
- `revision_no`
- `rules`
- `change_summary`
- `editor_name`
- `saved_by_auto`
- `based_on_revision_id`
- `content_hash`
- `signature_outdated`

### 3.3 任务模型

`Task` / `TaskCreate` 新增：

- `rule_package_revision_id`

这样本域任务执行绑定的是“具体修订”，不是模糊的规则包名称。

## 4. 存储与迁移

### 4.1 新增集合

本地状态新增：

- `rule_package_revisions`

### 4.2 旧状态迁移

对旧阶段已有规则包执行兼容迁移：

- 若旧规则包没有修订记录，则自动补生成首条迁移修订。
- 若旧任务没有 `rule_package_revision_id`，则自动补绑定到当前规则包主对象的当前修订。

这样现有 Stage 1 至 Stage 8 数据不会因 Stage 9 升级而失效。

## 5. 新增规则包中心接口

### 5.1 查询接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/rule-package-center/packages` | 获取规则包中心列表 |
| GET | `/api/rule-package-center/packages/{package_id}` | 获取单个规则包主对象 |
| GET | `/api/rule-package-center/packages/{package_id}/revisions` | 获取修订快照列表 |

### 5.2 编辑接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/rule-package-center/packages` | 创建规则包草稿 |
| POST | `/api/rule-package-center/packages/{package_id}/edit` | 进入编辑；对已审批规则包自动派生修订草稿 |
| POST | `/api/rule-package-center/packages/{package_id}/draft-save` | 保存草稿并生成修订快照 |
| POST | `/api/rule-package-center/packages/{package_id}/submit-verification` | 提交当前修订验签 |
| POST | `/api/rule-package-center/packages/{package_id}/approve` | 审批当前修订 |
| POST | `/api/rule-package-center/packages/{package_id}/deprecate` | 废弃已审批规则包 |
| DELETE | `/api/rule-package-center/packages/{package_id}` | 删除草稿或失败规则包 |

## 6. 编辑行为约束

### 6.1 可直接编辑

- 草稿
- 待验签对象
- 验签失败对象

### 6.2 不直接覆盖

对以下对象点击“编辑”时，不原地改内容：

- 已审批规则包
- 已废弃规则包
- 已删除对象

系统会自动：

- 复制当前生效内容
- 创建新修订草稿
- 清空旧签名
- 标记 `signature_outdated=true`

## 7. 验签与审批联动

### 7.1 草稿保存

- 允许无签名保存。
- 保存后修订状态保持 `draft`。
- 保存后主对象状态回到 `draft`。

### 7.2 提交验签

- 只有当前修订参与验签。
- 验签通过后状态变为 `pending_review`。
- 验签失败后状态变为 `invalid`。

### 7.3 审批通过

- 只有 `verified` 的当前修订才能审批通过。
- 审批通过后主对象状态更新为 `approved`。
- 当前修订成为任务可绑定版本。

## 8. 删除与废弃策略

### 8.1 删除

仅允许删除：

- 草稿
- 验签失败规则包
- 且从未审批
- 且从未被任务引用

### 8.2 废弃

本阶段新增规则包废弃能力：

- 仅允许废弃已审批规则包。
- 废弃后不允许新任务继续绑定。
- 历史修订和历史任务仍保留可查。

## 9. 前端规则包中心

前端新增独立 `RulePackageCenter` 组件。

### 9.1 页面入口

- 首页新增视图切换：
  - 本域工作台
  - 规则包中心

### 9.2 页面结构

规则包中心分三列：

- 规则包列表区
- 编辑区
- 修订与治理区

### 9.3 已实现交互

- 新建规则包草稿。
- 查看规则包列表。
- 点击“编辑”进入草稿或自动派生修订。
- 多条平铺规则增删改。
- 手动保存草稿。
- 页面离开时自动保存。
- 提交验签。
- 审批当前修订。
- 废弃当前规则包。
- 删除草稿。
- 查看修订历史。

## 10. 审计留痕

本阶段新增或强化审计动作：

- `rule_package.create`
- `rule_package.edit.start`
- `rule_package.draft_save`
- `rule_package.verify`
- `rule_package.approve`
- `rule_package.deprecate`
- `rule_package.delete`

## 11. 验证方式

```powershell
.\scripts\run-stage9-checks.ps1
```

脚本内容包括：

- 后端编译检查
- 后端单元测试
- 前端 TypeScript 类型检查
- 前端生产构建

## 12. 本阶段边界

本阶段仍然不实现：

- 规则差异对比界面
- AND / OR 嵌套树形规则编排
- 多角色独立视图
- 跨域规则包协同

