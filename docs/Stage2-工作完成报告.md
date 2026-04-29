# Stage 2 工作完成报告

## 1. 阶段信息

| 项目 | 内容 |
| --- | --- |
| 阶段名称 | Stage 2，核心能力实现阶段 |
| 完成日期 | 2026-04-29 |
| 阶段定位 | 在 Stage 1 骨架基础上实现本域核心计算闭环 |
| 主要目标 | 字段映射、主键 / 子键派生、去标识处理、基础算子库、本域任务执行、摘要结果查看 |
| 核心边界 | 数据不出域，且加密数据、哈希数据、去标识数据、派生键、对象级明细均不出域 |

## 2. 阶段目标与完成情况

| 阶段目标 | 完成情况 | 说明 |
| --- | --- | --- |
| 字段映射持久化 | 已完成 | 支持主键字段、子键字段、敏感字段、聚合分组字段配置 |
| 主键 / 子键派生 | 已完成最小实现 | 执行时在本域内存中派生，只输出数量摘要 |
| 去标识处理 | 已完成最小实现 | 执行时在本域内存中生成摘要，只输出处理数量和重复组数量 |
| 基础算子库 | 已完成 | 提供算子清单接口和前端展示 |
| 本域任务执行 | 已完成 | 支持单数据集 CSV 本域任务执行 |
| 执行回执 | 已完成 | 生成不含对象级数据的任务执行状态 |
| 结论声明草稿 | 已完成 | 生成待审核结论草稿，不直接输出正式结论 |
| 聚合统计 | 已完成最小实现 | 支持单维粗粒度分组和最小阈值过滤 |
| 摘要结果查看 | 已完成 | 前端展示摘要指标、聚合统计、结论草稿、安全边界说明 |
| 文档与报告 | 已完成 | 新增 Stage 2 能力说明和本完成报告 |

## 3. 本阶段实现的业务闭环

Stage 2 实现的完整本域链路如下：

```text
导入本域 CSV
  -> 生成字段画像
  -> 保存字段映射
  -> 登记规则包
  -> 审批规则包
  -> 创建本域任务
  -> 执行任务
  -> 生成结果摘要
  -> 前端查看结果
```

该链路只在本域内执行。任务执行过程中会读取本域 CSV，但不会向接口返回原始记录、对象级明细、派生主键、派生子键或去标识摘要。

## 4. 后端实现详情

### 4.1 新增和增强的数据模型

| 模型 | 文件 | 说明 |
| --- | --- | --- |
| `FieldMapping` | `backend/app/models/schemas.py` | 保存字段映射结果 |
| `FieldMappingCreate` | `backend/app/models/schemas.py` | 字段映射保存请求体 |
| `OperatorInfo` | `backend/app/models/schemas.py` | 算子库条目 |
| `TaskResult` | `backend/app/models/schemas.py` | 本域任务执行结果摘要 |
| `Task` 增强 | `backend/app/models/schemas.py` | 增加输出策略、聚合阈值、聚合分组维度 |
| `RulePackage` 增强 | `backend/app/models/schemas.py` | 增加签名引用、审批状态、审批人、审批时间 |

### 4.2 新增存储集合

`backend/app/services/storage.py` 中扩展了本地 JSON 状态集合：

| 集合 | 用途 |
| --- | --- |
| `field_mappings` | 保存数据集字段映射 |
| `results` | 保存任务执行结果摘要 |

完整状态集合包括：

```text
datasets
field_mappings
rule_packages
tasks
results
audit
```

### 4.3 新增后端服务

| 文件 | 说明 |
| --- | --- |
| `backend/app/services/execution.py` | 本域任务执行逻辑，包括 CSV 读取、主键 / 子键派生、去标识摘要、聚合统计 |
| `backend/app/services/operators.py` | 基础算子库清单 |

### 4.4 任务执行逻辑

任务执行步骤：

1. 根据任务 ID 查找任务草稿。
2. 校验当前仅支持单数据集任务。
3. 查找任务绑定的数据集。
4. 查找该数据集已保存的字段映射。
5. 读取本域 CSV 文件。
6. 根据字段映射在内存中生成主键材料。
7. 根据字段映射在内存中生成子键材料。
8. 根据敏感字段在内存中生成本域去标识摘要。
9. 统计主键完整数量、重复组数量。
10. 统计子键完整数量、重复组数量。
11. 统计去标识处理数量、重复组数量。
12. 如果任务要求聚合统计，则按单一维度计数并执行阈值过滤。
13. 如果任务要求结论声明，则生成待审核结论草稿。
14. 生成执行回执。
15. 保存结果摘要。
16. 写入审计日志。

### 4.5 主键 / 子键派生方式

当前实现为最小可用方案：

- 用户在前端选择主键字段。
- 用户在前端选择子键字段。
- 后端执行时读取字段值并进行首尾空白清理。
- 字段值为空时不计入完整键数量。
- 多字段组合能力已在服务函数中预留，但前端当前以单字段选择为主。
- 派生材料只用于内存统计，不保存、不返回。

当前返回的主键 / 子键指标：

| 指标 | 含义 |
| --- | --- |
| `primary_key_complete_count` | 主键字段完整的记录数量 |
| `primary_key_duplicate_groups` | 主键重复组数量 |
| `sub_key_complete_count` | 子键字段完整的记录数量 |
| `sub_key_duplicate_groups` | 子键重复组数量 |

### 4.6 去标识处理方式

当前实现为本域内部摘要：

- 使用敏感字段配置作为输入。
- 执行时在内存中拼接敏感字段材料。
- 使用本域命名空间生成 SHA-256 摘要。
- 摘要只用于本域内重复统计。
- 摘要值不保存、不返回、不导出。

当前返回的去标识指标：

| 指标 | 含义 |
| --- | --- |
| `deid_processed_count` | 已完成去标识处理的记录数量 |
| `deid_duplicate_groups` | 去标识摘要重复组数量 |

### 4.7 聚合统计方式

当前实现遵守 `BBB` 选项：

- 只允许单维粗粒度分组。
- 允许的分组维度为 `department`、`matter_type`、`month`。
- 每个分组必须满足最小阈值。
- 默认最小阈值为 `10`。
- 未满足阈值的分组不输出，只计入 `suppressed_groups`。

返回结构示例：

```json
{
  "dimension": "department",
  "group": "民政",
  "count": 10
}
```

### 4.8 结果摘要结构

`TaskResult` 包含：

| 字段 | 含义 |
| --- | --- |
| `id` | 结果 ID |
| `task_id` | 任务 ID |
| `status` | 执行状态 |
| `summary` | 数量摘要 |
| `receipt` | 执行回执 |
| `assertion` | 待审核结论草稿 |
| `aggregate_summary` | 阈值过滤后的聚合统计 |
| `suppressed_groups` | 被阈值抑制的分组数量 |
| `local_security_notes` | 本域安全边界说明 |

## 5. 后端接口清单

### 5.1 Stage 1 已有接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/domain-policy` | 本域策略 |
| GET | `/api/datasets` | 数据集列表 |
| POST | `/api/datasets/import` | 数据导入 |
| GET | `/api/datasets/{dataset_id}` | 数据集详情 |
| GET | `/api/rule-packages` | 规则包列表 |
| POST | `/api/rule-packages` | 规则包登记 |
| POST | `/api/rule-packages/{package_id}/approve` | 规则包审批 |
| GET | `/api/tasks` | 任务列表 |
| POST | `/api/tasks` | 创建任务 |
| GET | `/api/audit` | 审计记录 |

### 5.2 Stage 2 新增接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/operators` | 查询基础算子库 |
| GET | `/api/datasets/{dataset_id}/field-mapping` | 查询字段映射 |
| PUT | `/api/datasets/{dataset_id}/field-mapping` | 保存字段映射 |
| POST | `/api/tasks/{task_id}/execute` | 执行本域任务 |
| GET | `/api/results` | 查询结果摘要列表 |
| GET | `/api/tasks/{task_id}/result` | 查询指定任务结果摘要 |

## 6. 前端实现详情

### 6.1 页面结构

`frontend/src/App.tsx` 当前包含以下页面区域：

| 区域 | 功能 |
| --- | --- |
| 顶部说明区 | 展示系统处于本域不出域模式 |
| 边界策略区 | 展示禁止出域项、允许输出项、阈值和审批策略 |
| 本域数据导入 | 上传本域文件并生成画像 |
| 规则包登记 | 登记规则包名称、用途、签名引用 |
| 规则包审批 | 输入审批人并将规则包审批为可用 |
| 字段画像 | 查看数据集字段统计 |
| 本域任务草稿 | 创建本域任务，选择输出策略和聚合配置 |
| 字段映射 | 配置主键、子键、敏感字段和聚合分组字段 |
| 边界审计 | 查看导入、审批、执行等审计记录 |
| 执行与结果 | 触发任务执行 |
| 摘要结果 | 查看任务执行摘要 |
| 算子库 | 查看当前可用基础算子 |

### 6.2 前端状态

前端维护的主要状态：

| 状态 | 用途 |
| --- | --- |
| `datasets` | 数据集列表 |
| `fieldMapping` | 当前数据集字段映射 |
| `rulePackages` | 规则包列表 |
| `tasks` | 任务列表 |
| `results` | 结果摘要列表 |
| `operators` | 算子库列表 |
| `audit` | 审计记录 |
| `selectedDatasetId` | 当前选中的数据集 |
| `selectedRulePackageId` | 当前选中的规则包 |
| `outputPolicy` | 当前任务输出策略 |
| `aggregateThreshold` | 聚合统计阈值 |
| `aggregateGroupBy` | 聚合分组维度 |

### 6.3 前端 API 封装

`frontend/src/api.ts` 新增：

| 函数 | 说明 |
| --- | --- |
| `getFieldMapping` | 获取字段映射 |
| `saveFieldMapping` | 保存字段映射 |
| `executeTask` | 执行任务 |
| `getResults` | 获取结果摘要 |
| `getOperators` | 获取算子库 |

### 6.4 前端类型

`frontend/src/types.ts` 新增：

| 类型 | 说明 |
| --- | --- |
| `FieldMapping` | 字段映射类型 |
| `TaskResult` | 任务结果摘要类型 |
| `OperatorInfo` | 算子信息类型 |

## 7. 数据不出域控制

### 7.1 明确禁止返回的内容

Stage 2 后端执行逻辑不返回：

- 原始字段值。
- 原始记录行。
- 派生主键。
- 派生子键。
- 去标识摘要。
- 对象级命中明细。
- 阈值以下的聚合分组。

### 7.2 允许返回的内容

当前仅允许返回：

- 总行数。
- 主键完整数量。
- 主键重复组数量。
- 子键完整数量。
- 子键重复组数量。
- 去标识处理数量。
- 去标识重复组数量。
- 执行回执。
- 待审核结论声明草稿。
- 满足阈值的单维聚合统计。
- 被抑制分组数量。
- 安全边界说明。

### 7.3 聚合统计保护

聚合统计保护规则：

- 只允许单维分组。
- 分组维度必须是预定义维度。
- 每个分组计数必须大于等于阈值。
- 不满足阈值的分组不输出名称和数量。
- 只返回被抑制分组的数量。

## 8. 算子库清单

当前基础算子包括：

| 算子编码 | 名称 | 分类 | 输出边界 |
| --- | --- | --- | --- |
| `standardize.trim` | 去除首尾空白 | standardize | 本域内部 |
| `key.primary.derive` | 主键派生 | key | 本域内部 |
| `key.sub.derive` | 子键派生 | key | 本域内部 |
| `deid.digest.local` | 本域去标识摘要 | deid | 本域内部 |
| `aggregate.threshold` | 聚合阈值过滤 | aggregate | 安全摘要 |
| `receipt.execution` | 执行回执生成 | receipt | 安全摘要 |

## 9. 验证记录

### 9.1 编译检查

执行命令：

```powershell
python -m compileall backend\app
```

验证结果：通过。

### 9.2 前端构建

执行命令：

```powershell
npm run build
```

验证结果：通过。

### 9.3 API 烟测

执行过完整烟测链路：

```text
导入 CSV
  -> 保存字段映射
  -> 登记规则包
  -> 审批规则包
  -> 创建聚合统计任务
  -> 执行任务
  -> 获取摘要结果
```

烟测使用字段：

```text
person_id, record_id, department, matter_type, month
```

烟测结果：

| 指标 | 结果 |
| --- | --- |
| 导入行数 | 10 |
| 主键完整数量 | 10 |
| 去标识处理数量 | 10 |
| 聚合分组输出数量 | 1 |
| 被阈值抑制分组数量 | 0 |

烟测说明：

- 测试 CSV 中 `department=民政` 共 10 条记录。
- 当前聚合阈值为 10，因此该分组允许输出。
- 若该分组低于 10 条，将不会输出该分组名称和数量。

## 10. 文件变更清单

### 10.1 后端文件

| 文件 | 变更说明 |
| --- | --- |
| `backend/app/main.py` | 新增字段映射、算子、任务执行、结果查询接口 |
| `backend/app/models/schemas.py` | 新增字段映射、算子、任务结果模型 |
| `backend/app/services/storage.py` | 增加 `field_mappings` 和 `results` 状态集合 |
| `backend/app/services/execution.py` | 新增本域任务执行服务 |
| `backend/app/services/operators.py` | 新增基础算子库 |

### 10.2 前端文件

| 文件 | 变更说明 |
| --- | --- |
| `frontend/src/App.tsx` | 新增字段映射、执行任务、结果摘要、算子库展示 |
| `frontend/src/api.ts` | 新增字段映射、任务执行、结果、算子 API |
| `frontend/src/types.ts` | 新增 `FieldMapping`、`TaskResult`、`OperatorInfo` 类型 |
| `frontend/src/styles.css` | 新增结果摘要展示样式 |

### 10.3 文档文件

| 文件 | 变更说明 |
| --- | --- |
| `docs/Stage2-核心能力实现说明.md` | 新增 Stage 2 功能说明 |
| `docs/Stage2-工作完成报告.md` | 新增并细化 Stage 2 工作完成报告 |
| `README.md` | 更新当前阶段与 Stage 2 完成内容 |

## 11. 当前限制与风险

| 限制 / 风险 | 说明 | 后续建议 |
| --- | --- | --- |
| 仅支持 CSV 执行 | Excel 文件当前只落盘，不参与执行 | Stage 3 增加 Excel 解析 |
| 仅支持单数据集任务 | 尚未实现多数据集本域内联合计算 | Stage 3 或后续阶段扩展 |
| 规则包未解析规则表达式 | 规则包只是元数据和审批骨架 | Stage 3 实现规则表达式 |
| 去标识摘要算法固定 | 当前使用本域命名空间 + SHA-256 | 后续增加盐值配置与密钥管理 |
| JSON 状态文件 | 适合原型，不适合长期运行 | Stage 3 切换 SQLite |
| 审计日志可篡改 | 当前为普通 JSON 状态记录 | 后续增加链式摘要或签名 |
| 结论声明未完整审批 | 当前只生成待审核草稿 | Stage 3 实现审核流 |
| 未实现导出审批 | 当前不提供结果导出 | Stage 3 增加回执 / 结论 / 统计导出审批 |

## 12. 验证方式

用户可按以下方式验证 Stage 2：

1. 启动后端。
2. 启动前端。
3. 上传包含 `person_id`、`record_id`、`department`、`matter_type`、`month` 的 CSV。
4. 登记规则包。
5. 审批规则包。
6. 保存字段映射。
7. 创建聚合统计任务。
8. 执行任务。
9. 查看摘要结果。

建议测试数据至少包含 10 条同一分组记录，以便观察聚合统计输出。

## 13. 阶段结论

Stage 2 已完成本域核心计算闭环。系统已经从 Stage 1 的“可运行骨架”推进到“可执行本域任务并查看安全摘要结果”的状态。

当前阶段：Stage 2，核心能力实现阶段

本轮产出：字段映射持久化、本域主键 / 子键派生、本域去标识处理、基础算子库、任务执行、执行回执、待审核结论草稿、阈值聚合统计和摘要结果查看。

待确认事项：是否进入 Stage 3；Stage 3 是否优先处理 SQLite、Excel 解析、规则表达式、审核流、导出审批或部署脚本。

下一步建议：进入 Stage 3，完善验证、审计、存储、导出审批和离线部署。
