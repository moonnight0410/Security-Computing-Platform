import unittest

from app.models.schemas import AssertionReviewRequest, AssertionReviewState, TaskResult
from app.services.assertions import review_assertion
from app.services.audit import utc_now


def sample_result() -> TaskResult:
    return TaskResult(
        id="result-1",
        task_id="task-1",
        status="completed",
        created_at=utc_now(),
        summary={"row_count": 10},
        receipt={"task_id": "task-1", "status": "completed"},
        assertion=AssertionReviewState(
            status="pending_review",
            statement="发现 12 条符合补贴资格规则的摘要结论，待正式审核。",
            created_at=utc_now(),
        ),
    )


class AssertionReviewTests(unittest.TestCase):
    def test_approve_assertion_can_replace_final_statement(self) -> None:
        result = review_assertion(
            sample_result(),
            AssertionReviewRequest(
                reviewer_name="审核员B",
                decision="approved",
                final_statement="审核通过：满足条件对象数量达到输出阈值，仅可对外出具摘要性结论。",
                comment="表述已压缩为不含对象级信息的正式结论。",
            ),
        )

        self.assertIsNotNone(result.assertion)
        self.assertEqual(result.assertion.status, "approved")
        self.assertEqual(result.assertion.reviewer_name, "审核员B")
        self.assertIn("审核通过", result.assertion.statement)

    def test_reject_assertion_records_rejection_reason(self) -> None:
        result = review_assertion(
            sample_result(),
            AssertionReviewRequest(
                reviewer_name="审核员B",
                decision="rejected",
                comment="结论措辞仍可能引发对象存在性推断。",
            ),
        )

        self.assertIsNotNone(result.assertion)
        self.assertEqual(result.assertion.status, "rejected")
        self.assertEqual(result.assertion.rejection_reason, "结论措辞仍可能引发对象存在性推断。")

    def test_cannot_review_assertion_twice(self) -> None:
        result = sample_result()
        result.assertion = AssertionReviewState(
            status="approved",
            statement="已审核通过",
            created_at=utc_now(),
            reviewer_name="审核员A",
            reviewed_at=utc_now(),
        )

        with self.assertRaisesRegex(ValueError, "不处于待审核状态"):
            review_assertion(
                result,
                AssertionReviewRequest(
                    reviewer_name="审核员B",
                    decision="approved",
                ),
            )


if __name__ == "__main__":
    unittest.main()
