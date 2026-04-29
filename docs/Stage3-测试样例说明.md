# Stage 3 测试样例说明

## 1. 测试目标

本测试集用于验证“本域数据不出域”约束下，系统在真实联查数据形态中是否能正确完成：

- 主键完整性统计。
- 主键重复组统计。
- 子键完整性统计。
- 去标识处理数量统计。
- 去标识重复组统计。
- 单维粗粒度聚合统计。
- 小样本分组抑制。
- 执行回执生成。
- 结论声明草稿生成。
- 对象级标识不泄露。

## 2. 样例数据形态

测试数据模拟 3 类部门事项：

| 部门 | 事项类型 | 月份 | 记录数 | 预期 |
| --- | --- | --- | --- | --- |
| 民政 | 补贴资格核验 | 2026-04 | 14 | 满足阈值，允许输出聚合统计 |
| 人社 | 就业状态核验 | 2026-04 | 6 | 低于阈值，应被抑制 |
| 医保 | 参保状态核验 | 2026-05 | 6 | 低于阈值，应被抑制 |

特殊记录：

- `P0001` 出现重复，用于验证主键重复组统计。
- 存在 1 条缺失 `person_id` 的记录，用于验证主键完整数量。
- 所有 `record_id` 唯一，用于验证子键重复组为 0。

## 3. 测试用例清单

| 用例 | 验证点 |
| --- | --- |
| `test_realistic_department_aggregate_suppresses_small_groups` | 部门分组下只输出满足阈值的民政分组，抑制人社和医保 |
| `test_month_aggregate_outputs_only_threshold_month` | 月份分组下只输出 2026-04，抑制 2026-05 |
| `test_matter_type_aggregate_suppresses_two_small_categories` | 事项类型分组下只输出补贴资格核验，抑制两个小样本事项 |
| `test_result_does_not_leak_object_identifiers_or_deid_digests` | 结果中不出现人员编号、记录编号或去标识摘要 |
| `test_manual_assertion_creates_pending_review_statement` | 结论声明只生成待审核草稿 |
| `test_execution_receipt_contains_no_dataset_values` | 执行回执不含数据集字段值 |
| `test_unmapped_aggregate_dimension_fails_closed` | 聚合分组字段未映射时失败关闭 |
| `test_csv_without_header_fails_closed` | CSV 无表头时失败关闭 |
| `test_small_group_is_suppressed_without_group_name_leak` | 小样本分组不仅不输出数量，也不泄露分组名称 |

## 4. 预期核心结果

真实样例部门分组任务预期：

| 指标 | 预期值 |
| --- | --- |
| 总行数 | 26 |
| 主键完整数量 | 25 |
| 主键重复组数量 | 1 |
| 子键完整数量 | 26 |
| 子键重复组数量 | 0 |
| 去标识处理数量 | 25 |
| 去标识重复组数量 | 1 |
| 输出聚合分组数量 | 1 |
| 被抑制分组数量 | 2 |

允许输出的聚合统计：

```json
[
  {
    "dimension": "department",
    "group": "民政",
    "count": 14
  }
]
```

不允许输出：

- `P0001`
- `MZ-BT-0001`
- `MZ-BT-DUP-0001`
- 任何去标识摘要
- 低于阈值的 `人社`、`医保` 分组统计

## 5. 运行方式

```powershell
cd D:\demo_opencode\部门计算\backend
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

或运行项目级检查：

```powershell
cd D:\demo_opencode\部门计算
.\scripts\run-stage3-checks.ps1
```
