# Stage 10 规则包差异对比与引用回溯说明

## 1. 本阶段目标

Stage 10 在 Stage 9 规则包中心基础上，继续补强两个核心治理能力：

- 规则包修订差异对比
- 规则包引用关系回溯

两项能力仍然严格遵守“本域数据不出域”约束，只返回规则定义、治理元数据与任务摘要，不返回原始业务数据或对象级明细。

## 2. 新增后端能力

### 2.1 修订差异接口

新增接口：

- `GET /api/rule-package-center/packages/{package_id}/revision-diff`

请求参数：

- `from_revision_id`
- `to_revision_id`

返回内容：

- 包信息
- 起止修订号
- 是否为直接派生关系
- 字段级变化
- 规则级变化
- 统计摘要

### 2.2 引用回溯接口

新增接口：

- `GET /api/rule-package-center/packages/{package_id}/references`

返回内容：

- 当前修订号
- 总引用任务数
- 当前修订引用数
- 历史修订引用数
- 各修订被引用次数
- 关联任务摘要列表

## 3. 差异对比口径

差异对比分两类：

### 3.1 字段级差异

比较以下治理字段：

- `name`
- `version`
- `purpose`
- `signer_name`
- `signature_ref`
- `notes`
- `change_summary`
- `status`
- `verification_status`
- `rules_count`
- `signature_outdated`

### 3.2 规则级差异

按 `field + operator` 作为规则键进行比对，识别：

- 新增规则
- 删除规则
- 同键规则值变更

## 4. 引用回溯口径

引用回溯按任务维度汇总：

- 只统计当前规则包及其修订链相关任务
- 任务只展示名称、状态、输出策略、创建时间和所引用修订号
- 不展示原始数据、计算明细或对象级结果

## 5. 前端展示

规则包中心新增三个治理块：

- 修订历史
- 修订差异对比
- 引用回溯

支持能力：

- 选择两个修订版本做对比
- 查看字段变化与规则变化
- 查看某规则包当前和历史修订的引用任务

## 6. 验证结果

- `python -m compileall backend\app`
- `python -m unittest discover -s tests`
- `npx tsc --noEmit`
- `npm run build`
- `.\scripts\run-stage10-checks.ps1`

全部通过。
