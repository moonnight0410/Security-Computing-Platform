from app.models.schemas import AssertionReviewRequest, AssertionReviewState, TaskResult
from app.services.audit import utc_now


def review_assertion(result: TaskResult, payload: AssertionReviewRequest) -> TaskResult:
    assertion = result.assertion
    if assertion is None:
        raise ValueError("该结果没有可审核的结论声明")
    if assertion.status != "pending_review":
        raise ValueError("结论声明当前不处于待审核状态")

    reviewed_statement = payload.final_statement.strip() if payload.final_statement else assertion.statement
    review_comment = payload.comment.strip() if payload.comment else None

    if payload.decision == "approved":
        assertion = AssertionReviewState(
            status="approved",
            statement=reviewed_statement,
            created_at=assertion.created_at,
            reviewer_name=payload.reviewer_name,
            reviewed_at=utc_now(),
            review_comment=review_comment,
            rejection_reason=None,
        )
    else:
        assertion = AssertionReviewState(
            status="rejected",
            statement=reviewed_statement,
            created_at=assertion.created_at,
            reviewer_name=payload.reviewer_name,
            reviewed_at=utc_now(),
            review_comment=review_comment,
            rejection_reason=review_comment or "审核驳回",
        )

    result.assertion = assertion
    return result
