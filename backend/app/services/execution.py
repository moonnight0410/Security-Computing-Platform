import csv
import hashlib
from collections import Counter
from pathlib import Path
from uuid import uuid4

from typing import Any

from app.models.schemas import AssertionReviewState, Dataset, FieldMapping, Task, TaskResult
from app.services.audit import utc_now


LOCAL_DEID_NAMESPACE = "domain-local-stage2"


def read_csv_rows(file_path: Path) -> list[dict[str, str]]:
    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError("CSV 文件缺少表头，无法执行任务")
        return [dict(row) for row in reader]


def normalize(value: object) -> str:
    return str(value or "").strip()


def complete_key_material(row: dict[str, str], fields: list[str]) -> str | None:
    if not fields:
        return None
    values = [normalize(row.get(field)) for field in fields]
    if any(not value for value in values):
        return None
    return "|".join(values)


def local_digest(material: str) -> str:
    return hashlib.sha256(f"{LOCAL_DEID_NAMESPACE}|{material}".encode("utf-8")).hexdigest()


def compare_rule_value(actual: str, operator: str, expected: Any) -> bool | None:
    if operator == "exists":
        return bool(actual)
    if operator == "not_empty":
        return bool(actual)
    if not actual:
        return None
    if operator == "eq":
        return actual == str(expected)
    if operator == "neq":
        return actual != str(expected)
    if operator == "in":
        if not isinstance(expected, list):
            return None
        return actual in {str(item) for item in expected}
    if operator in {"gte", "lte"}:
        try:
            actual_num = float(actual)
            expected_num = float(expected)
        except (TypeError, ValueError):
            return None
        if operator == "gte":
            return actual_num >= expected_num
        return actual_num <= expected_num
    return None


def evaluate_rules(rows: list[dict[str, str]], rules: list[dict[str, Any]]) -> dict[str, Any]:
    if not rules:
        return {
            "rule_count": 0,
            "rule_evaluated_count": 0,
            "rule_pass_count": 0,
            "rule_fail_count": 0,
            "rule_unknown_count": 0,
        }

    pass_count = 0
    fail_count = 0
    unknown_count = 0

    for row in rows:
        row_results: list[bool | None] = []
        for rule in rules:
            field = str(rule.get("field", "")).strip()
            operator = str(rule.get("operator", "")).strip()
            expected = rule.get("value")
            if not field or not operator:
                row_results.append(None)
                continue
            row_results.append(compare_rule_value(normalize(row.get(field)), operator, expected))

        if any(result is False for result in row_results):
            fail_count += 1
        elif any(result is None for result in row_results):
            unknown_count += 1
        else:
            pass_count += 1

    return {
        "rule_count": len(rules),
        "rule_evaluated_count": len(rows),
        "rule_pass_count": pass_count,
        "rule_fail_count": fail_count,
        "rule_unknown_count": unknown_count,
    }


def execute_local_task(
    task: Task,
    dataset: Dataset,
    mapping: FieldMapping,
    rules: list[dict[str, Any]] | None = None,
) -> TaskResult:
    rows = read_csv_rows(Path(dataset.stored_path))
    primary_materials: list[str] = []
    sub_materials: list[str] = []
    deid_digests: list[str] = []

    for row in rows:
        primary_material = complete_key_material(row, mapping.primary_key_fields)
        if primary_material:
            primary_materials.append(primary_material)

        sub_material = complete_key_material(row, mapping.sub_key_fields)
        if sub_material:
            sub_materials.append(sub_material)

        sensitive_material = complete_key_material(row, mapping.sensitive_fields)
        if sensitive_material:
            deid_digests.append(local_digest(sensitive_material))

    primary_counts = Counter(primary_materials)
    sub_counts = Counter(sub_materials)
    deid_counts = Counter(deid_digests)

    aggregate_summary: list[dict[str, object]] = []
    suppressed_groups = 0
    if task.output_policy == "aggregate_summary" and task.aggregate_group_by:
        group_field = mapping.group_fields.get(task.aggregate_group_by)
        threshold = task.aggregate_threshold or 10
        if not group_field:
            raise ValueError(f"聚合分组字段未映射：{task.aggregate_group_by}")

        grouped = Counter(normalize(row.get(group_field)) or "未填" for row in rows)
        for group_name, count in sorted(grouped.items()):
            if count >= threshold:
                aggregate_summary.append(
                    {
                        "dimension": task.aggregate_group_by,
                        "group": group_name,
                        "count": count,
                    }
                )
            else:
                suppressed_groups += 1

    assertion = None
    if task.output_policy == "manual_assertion":
        assertion = AssertionReviewState(
            status="pending_review",
            statement="结论声明草稿已生成，需审核人与执行人分离审批后方可输出。",
            created_at=utc_now(),
        )

    summary = {
        "dataset_count": 1,
        "row_count": len(rows),
        "primary_key_complete_count": len(primary_materials),
        "primary_key_duplicate_groups": sum(1 for count in primary_counts.values() if count > 1),
        "sub_key_complete_count": len(sub_materials),
        "sub_key_duplicate_groups": sum(1 for count in sub_counts.values() if count > 1),
        "deid_processed_count": len(deid_digests),
        "deid_duplicate_groups": sum(1 for count in deid_counts.values() if count > 1),
    }
    summary.update(evaluate_rules(rows, rules or []))

    receipt = {
        "task_id": task.id,
        "rule_package_id": task.rule_package_id,
        "rule_package_revision_id": task.rule_package_revision_id,
        "status": "completed",
        "executed_at": utc_now(),
        "output_policy": task.output_policy,
    }

    return TaskResult(
        id=str(uuid4()),
        task_id=task.id,
        status="completed",
        created_at=utc_now(),
        summary=summary,
        receipt=receipt,
        assertion=assertion,
        aggregate_summary=aggregate_summary,
        suppressed_groups=suppressed_groups,
        local_security_notes=[
            "未保存或返回原始主键、子键、去标识摘要。",
            "对象级明细结果仅参与本域内内存计算，本接口只返回摘要。",
            "聚合统计仅输出满足最小阈值的单维粗粒度分组。",
            "规则表达式只输出通过、失败、未知数量，不返回对象级命中明细。",
        ],
    )
