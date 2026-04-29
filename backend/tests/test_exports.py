import json
import tempfile
import unittest
from pathlib import Path

from app.models.schemas import ExportRequestCreate, TaskResult
from app.services.audit import utc_now
from app.services import exports
from app.services.exports import approve_export_request, build_export_package, create_export_request, persist_export_package


def sample_result() -> TaskResult:
    return TaskResult(
        id="result-1",
        task_id="task-1",
        status="completed",
        created_at=utc_now(),
        summary={
            "row_count": 10,
            "primary_key_complete_count": 10,
        },
        receipt={
            "task_id": "task-1",
            "status": "completed",
            "output_policy": "aggregate_summary",
        },
        assertion={
            "status": "pending_review",
            "statement": "结论声明草稿已生成，需审核人与执行人分离审批后方可输出。",
        },
        aggregate_summary=[
            {
                "dimension": "department",
                "group": "民政",
                "count": 10,
            }
        ],
        suppressed_groups=0,
    )


class ExportApprovalTests(unittest.TestCase):
    def make_request(self, export_type: str = "receipt"):
        return create_export_request(
            ExportRequestCreate(
                result_id="result-1",
                export_type=export_type,  # type: ignore[arg-type]
                requester_name="经办人A",
                purpose="事项办理结果反馈",
            )
        )

    def test_unapproved_request_cannot_build_package(self) -> None:
        request = self.make_request("receipt")

        with self.assertRaisesRegex(ValueError, "尚未审批"):
            build_export_package(request, sample_result())

    def test_approver_must_be_different_from_requester(self) -> None:
        request = self.make_request("receipt")

        with self.assertRaisesRegex(ValueError, "不能相同"):
            approve_export_request(request, "经办人A")

    def test_receipt_package_contains_only_receipt(self) -> None:
        request = approve_export_request(self.make_request("receipt"), "审核员B")
        package = build_export_package(request, sample_result())

        self.assertEqual(package.export_type, "receipt")
        self.assertEqual(set(package.payload.keys()), {"receipt"})
        self.assertNotIn("primary_key_complete_count", str(package.payload))
        self.assertNotIn("P0001", str(package.model_dump()))

    def test_aggregate_package_contains_thresholded_summary_only(self) -> None:
        request = approve_export_request(self.make_request("aggregate_summary"), "审核员B")
        package = build_export_package(request, sample_result())

        self.assertEqual(package.export_type, "aggregate_summary")
        self.assertEqual(set(package.payload.keys()), {"aggregate_summary", "suppressed_groups"})
        self.assertIn("民政", str(package.payload))
        self.assertNotIn("P0001", str(package.model_dump()))

    def test_assertion_package_requires_assertion(self) -> None:
        request = approve_export_request(self.make_request("assertion"), "审核员B")
        result = sample_result()
        result.assertion = None

        with self.assertRaisesRegex(ValueError, "没有可输出的结论声明"):
            build_export_package(request, result)

    def test_persisted_export_file_contains_only_approved_safe_payload(self) -> None:
        request = approve_export_request(self.make_request("aggregate_summary"), "审核员B")
        package = build_export_package(request, sample_result())

        with tempfile.TemporaryDirectory() as directory:
            original_exports_dir = exports.EXPORTS_DIR
            exports.EXPORTS_DIR = Path(directory)
            try:
                export_file = persist_export_package(package)
                stored_content = Path(export_file.stored_path).read_text(encoding="utf-8")
            finally:
                exports.EXPORTS_DIR = original_exports_dir

        stored_package = json.loads(stored_content)
        self.assertEqual(export_file.export_type, "aggregate_summary")
        self.assertEqual(export_file.byte_size, len(stored_content.encode("utf-8")))
        self.assertEqual(len(export_file.sha256), 64)
        self.assertEqual(set(stored_package["payload"].keys()), {"aggregate_summary", "suppressed_groups"})
        self.assertIn("民政", stored_content)
        self.assertNotIn("citizen_name", stored_content)
        self.assertNotIn("id_card", stored_content)
        self.assertNotIn("derived_primary_key", stored_content)
        self.assertNotIn("deidentified_digest", stored_content)

    def test_persisted_receipt_file_excludes_aggregate_and_assertion_content(self) -> None:
        request = approve_export_request(self.make_request("receipt"), "审核员B")
        package = build_export_package(request, sample_result())

        with tempfile.TemporaryDirectory() as directory:
            original_exports_dir = exports.EXPORTS_DIR
            exports.EXPORTS_DIR = Path(directory)
            try:
                export_file = persist_export_package(package)
                stored_content = Path(export_file.stored_path).read_text(encoding="utf-8")
            finally:
                exports.EXPORTS_DIR = original_exports_dir

        stored_package = json.loads(stored_content)
        self.assertEqual(set(stored_package["payload"].keys()), {"receipt"})
        self.assertIn("output_policy", stored_content)
        self.assertNotIn("民政", stored_content)
        self.assertNotIn("suppressed_groups", stored_content)
        self.assertNotIn("结论声明草稿", stored_content)


if __name__ == "__main__":
    unittest.main()
