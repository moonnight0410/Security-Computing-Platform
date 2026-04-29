import csv
import tempfile
import unittest
from pathlib import Path

from app.models.schemas import Dataset, FieldMapping, Task
from app.services.audit import utc_now
from app.services.execution import execute_local_task, read_csv_rows


FIELDNAMES = [
    "person_id",
    "record_id",
    "department",
    "matter_type",
    "month",
    "benefit_status",
    "amount",
]


def realistic_joint_query_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for index in range(1, 13):
        rows.append(
            {
                "person_id": f"P{index:04d}",
                "record_id": f"MZ-BT-{index:04d}",
                "department": "民政",
                "matter_type": "补贴资格核验",
                "month": "2026-04",
                "benefit_status": "正常",
                "amount": "800",
            }
        )

    for index in range(13, 19):
        rows.append(
            {
                "person_id": f"P{index:04d}",
                "record_id": f"RS-JY-{index:04d}",
                "department": "人社",
                "matter_type": "就业状态核验",
                "month": "2026-04",
                "benefit_status": "正常",
                "amount": "0",
            }
        )

    for index in range(19, 25):
        rows.append(
            {
                "person_id": f"P{index:04d}",
                "record_id": f"YB-CB-{index:04d}",
                "department": "医保",
                "matter_type": "参保状态核验",
                "month": "2026-05",
                "benefit_status": "正常",
                "amount": "0",
            }
        )

    rows.append(
        {
            "person_id": "P0001",
            "record_id": "MZ-BT-DUP-0001",
            "department": "民政",
            "matter_type": "补贴资格核验",
            "month": "2026-04",
            "benefit_status": "重复记录",
            "amount": "800",
        }
    )
    rows.append(
        {
            "person_id": "",
            "record_id": "MZ-BT-MISSING-0001",
            "department": "民政",
            "matter_type": "补贴资格核验",
            "month": "2026-04",
            "benefit_status": "缺失主键",
            "amount": "800",
        }
    )

    return rows


class LocalExecutionTests(unittest.TestCase):
    def make_dataset(
        self,
        rows: list[dict[str, str]],
        *,
        include_header: bool = True,
    ) -> tuple[tempfile.TemporaryDirectory[str], Dataset]:
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "dataset.csv"
        with path.open("w", encoding="utf-8", newline="") as file:
            if include_header:
                writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(rows)
            else:
                file.write("")

        dataset = Dataset(
            id="dataset-1",
            name="dataset",
            source_filename="dataset.csv",
            stored_path=str(path),
            status="imported",
            row_count=len(rows),
            field_count=len(FIELDNAMES),
            fields=[],
            created_at=utc_now(),
        )
        return temp_dir, dataset

    def mapping(self) -> FieldMapping:
        return FieldMapping(
            dataset_id="dataset-1",
            primary_key_fields=["person_id"],
            sub_key_fields=["record_id"],
            sensitive_fields=["person_id"],
            group_fields={
                "department": "department",
                "matter_type": "matter_type",
                "month": "month",
            },
            updated_at=utc_now(),
        )

    def aggregate_task(self, *, group_by: str = "department", threshold: int = 10) -> Task:
        return Task(
            id="task-aggregate",
            name="aggregate",
            dataset_ids=["dataset-1"],
            output_policy="aggregate_summary",
            aggregate_threshold=threshold,
            aggregate_group_by=group_by,  # type: ignore[arg-type]
            created_at=utc_now(),
        )

    def test_realistic_department_aggregate_suppresses_small_groups(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)

        result = execute_local_task(self.aggregate_task(group_by="department", threshold=10), dataset, self.mapping())

        self.assertEqual(result.summary["row_count"], 26)
        self.assertEqual(result.summary["primary_key_complete_count"], 25)
        self.assertEqual(result.summary["primary_key_duplicate_groups"], 1)
        self.assertEqual(result.summary["sub_key_complete_count"], 26)
        self.assertEqual(result.summary["sub_key_duplicate_groups"], 0)
        self.assertEqual(result.summary["deid_processed_count"], 25)
        self.assertEqual(result.summary["deid_duplicate_groups"], 1)
        self.assertEqual(result.suppressed_groups, 2)
        self.assertEqual(
            result.aggregate_summary,
            [{"dimension": "department", "group": "民政", "count": 14}],
        )

    def test_month_aggregate_outputs_only_threshold_month(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)

        result = execute_local_task(self.aggregate_task(group_by="month", threshold=10), dataset, self.mapping())

        self.assertEqual(result.aggregate_summary, [{"dimension": "month", "group": "2026-04", "count": 20}])
        self.assertEqual(result.suppressed_groups, 1)

    def test_matter_type_aggregate_suppresses_two_small_categories(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)

        result = execute_local_task(self.aggregate_task(group_by="matter_type", threshold=10), dataset, self.mapping())

        self.assertEqual(
            result.aggregate_summary,
            [{"dimension": "matter_type", "group": "补贴资格核验", "count": 14}],
        )
        self.assertEqual(result.suppressed_groups, 2)

    def test_result_does_not_leak_object_identifiers_or_deid_digests(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)

        result = execute_local_task(self.aggregate_task(group_by="department", threshold=10), dataset, self.mapping())
        dumped = str(result.model_dump())

        self.assertNotIn("P0001", dumped)
        self.assertNotIn("MZ-BT-0001", dumped)
        self.assertNotIn("MZ-BT-DUP-0001", dumped)
        self.assertNotIn("sha256", dumped.lower())
        self.assertIn("未保存或返回原始主键", dumped)

    def test_manual_assertion_creates_pending_review_statement(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)
        task = Task(
            id="task-assertion",
            name="assertion",
            dataset_ids=["dataset-1"],
            output_policy="manual_assertion",
            created_at=utc_now(),
        )

        result = execute_local_task(task, dataset, self.mapping())

        self.assertIsNotNone(result.assertion)
        self.assertEqual(result.assertion["status"], "pending_review")
        self.assertEqual(result.receipt["output_policy"], "manual_assertion")

    def test_execution_receipt_contains_no_dataset_values(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)
        task = Task(
            id="task-receipt",
            name="receipt",
            dataset_ids=["dataset-1"],
            output_policy="execution_receipt",
            created_at=utc_now(),
        )

        result = execute_local_task(task, dataset, self.mapping())
        dumped_receipt = str(result.receipt)

        self.assertEqual(result.receipt["status"], "completed")
        self.assertNotIn("P0001", dumped_receipt)
        self.assertNotIn("民政", dumped_receipt)

    def test_unmapped_aggregate_dimension_fails_closed(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)
        mapping = self.mapping()
        mapping.group_fields.pop("department")

        with self.assertRaisesRegex(ValueError, "聚合分组字段未映射"):
            execute_local_task(self.aggregate_task(group_by="department", threshold=10), dataset, mapping)

    def test_csv_without_header_fails_closed(self) -> None:
        temp_dir, dataset = self.make_dataset([], include_header=False)
        self.addCleanup(temp_dir.cleanup)

        with self.assertRaisesRegex(ValueError, "CSV 文件缺少表头"):
            read_csv_rows(Path(dataset.stored_path))

    def test_small_group_is_suppressed_without_group_name_leak(self) -> None:
        rows = [
            {
                "person_id": f"T{index:04d}",
                "record_id": f"TEST-{index:04d}",
                "department": "测试小组",
                "matter_type": "小样本事项",
                "month": "2026-06",
                "benefit_status": "正常",
                "amount": "0",
            }
            for index in range(1, 10)
        ]
        temp_dir, dataset = self.make_dataset(rows)
        self.addCleanup(temp_dir.cleanup)

        result = execute_local_task(self.aggregate_task(group_by="department", threshold=10), dataset, self.mapping())

        self.assertEqual(len(result.aggregate_summary), 0)
        self.assertEqual(result.suppressed_groups, 1)
        self.assertNotIn("测试小组", str(result.model_dump()))

    def test_rule_expression_counts_pass_and_fail_without_row_details(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)
        task = Task(
            id="task-rule",
            name="rule",
            dataset_ids=["dataset-1"],
            output_policy="local_only",
            created_at=utc_now(),
        )
        rules = [{"field": "benefit_status", "operator": "eq", "value": "正常"}]

        result = execute_local_task(task, dataset, self.mapping(), rules)

        self.assertEqual(result.summary["rule_count"], 1)
        self.assertEqual(result.summary["rule_evaluated_count"], 26)
        self.assertEqual(result.summary["rule_pass_count"], 24)
        self.assertEqual(result.summary["rule_fail_count"], 2)
        self.assertEqual(result.summary["rule_unknown_count"], 0)
        self.assertNotIn("重复记录", str(result.model_dump()))
        self.assertNotIn("缺失主键", str(result.model_dump()))

    def test_numeric_rule_expression_counts_failures(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)
        task = Task(
            id="task-numeric-rule",
            name="numeric-rule",
            dataset_ids=["dataset-1"],
            output_policy="local_only",
            created_at=utc_now(),
        )
        rules = [{"field": "amount", "operator": "gte", "value": 1}]

        result = execute_local_task(task, dataset, self.mapping(), rules)

        self.assertEqual(result.summary["rule_pass_count"], 14)
        self.assertEqual(result.summary["rule_fail_count"], 12)
        self.assertEqual(result.summary["rule_unknown_count"], 0)

    def test_invalid_rule_field_counts_unknown_without_values(self) -> None:
        temp_dir, dataset = self.make_dataset(realistic_joint_query_rows())
        self.addCleanup(temp_dir.cleanup)
        task = Task(
            id="task-unknown-rule",
            name="unknown-rule",
            dataset_ids=["dataset-1"],
            output_policy="local_only",
            created_at=utc_now(),
        )
        rules = [{"field": "unknown_field", "operator": "eq", "value": "正常"}]

        result = execute_local_task(task, dataset, self.mapping(), rules)

        self.assertEqual(result.summary["rule_unknown_count"], 26)
        self.assertEqual(result.summary["rule_pass_count"], 0)
        self.assertEqual(result.summary["rule_fail_count"], 0)


if __name__ == "__main__":
    unittest.main()
