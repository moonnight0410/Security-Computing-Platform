import unittest

from app.models.schemas import RulePackageApprove, RulePackageCreate, RulePackageDraftSave
from app.services.rule_packages import (
    approve_revision,
    build_rule_package_usage_report,
    compare_rule_package_revisions,
    create_edit_revision,
    create_rule_package_entities,
    package_can_be_deleted,
    save_rule_package_revision,
)


def sample_create_payload() -> RulePackageCreate:
    return RulePackageCreate(
        name="民政补贴资格复核规则包",
        version="0.1.0",
        purpose="用于本域内补贴资格复核筛查",
        signer_name="市级规则中心",
        signature_ref="SIG-CENTER-RSA-001",
        signature="BASE64-SIGNATURE",
        rules=[{"field": "benefit_status", "operator": "eq", "value": "正常"}],
        editor_name="经办员A",
        change_summary="创建首版草稿",
    )


class RulePackageRevisionTests(unittest.TestCase):
    def test_create_rule_package_entities_creates_initial_revision(self) -> None:
        package, revision = create_rule_package_entities(sample_create_payload())

        self.assertEqual(package.current_revision_no, 1)
        self.assertEqual(package.current_revision_id, revision.id)
        self.assertEqual(revision.rule_package_id, package.id)
        self.assertEqual(revision.rules_count, 1)
        self.assertTrue(revision.signature_outdated is False)

    def test_save_rule_package_revision_creates_next_snapshot(self) -> None:
        package, revision = create_rule_package_entities(sample_create_payload())
        saved = save_rule_package_revision(
            package,
            [revision],
            RulePackageDraftSave(
                name=package.name,
                version=package.version,
                purpose=package.purpose,
                signer_name=package.signer_name,
                signature_ref=package.signature_ref,
                signature="",
                rules=[
                    {"field": "benefit_status", "operator": "eq", "value": "正常"},
                    {"field": "department", "operator": "eq", "value": "民政"},
                ],
                editor_name="经办员A",
                change_summary="新增部门条件",
            ),
        )

        self.assertEqual(saved.revision_no, 2)
        self.assertEqual(saved.based_on_revision_id, revision.id)
        self.assertEqual(saved.rules_count, 2)
        self.assertTrue(saved.signature_outdated)
        self.assertEqual(saved.status, "draft")

    def test_editing_approved_package_creates_new_draft_revision(self) -> None:
        package, revision = create_rule_package_entities(sample_create_payload())
        revision.verification_status = "verified"
        revision.status = "approved"
        package.status = "approved"

        next_revision = create_edit_revision(package, [revision], editor_name="经办员B")

        self.assertEqual(next_revision.revision_no, 2)
        self.assertEqual(next_revision.status, "draft")
        self.assertEqual(next_revision.based_on_revision_id, revision.id)
        self.assertEqual(next_revision.signature, "")
        self.assertTrue(next_revision.signature_outdated)

    def test_approve_revision_requires_verified_status(self) -> None:
        package, revision = create_rule_package_entities(sample_create_payload())

        with self.assertRaisesRegex(ValueError, "尚未通过本域签名验签"):
            approve_revision(revision, RulePackageApprove(approver_name="审核员B"))

    def test_delete_only_allows_unapproved_unreferenced_packages(self) -> None:
        package, _ = create_rule_package_entities(sample_create_payload())
        package.status = "draft"
        package.approved_at = None

        allowed, reason = package_can_be_deleted(package, [])
        self.assertTrue(allowed)
        self.assertIsNone(reason)

        blocked, blocked_reason = package_can_be_deleted(
            package,
            [{"rule_package_id": package.id, "rule_package_revision_id": package.current_revision_id}],
        )
        self.assertFalse(blocked)
        self.assertIn("任务引用", blocked_reason or "")


    def test_compare_revisions_reports_field_and_rule_changes(self) -> None:
        package, revision = create_rule_package_entities(sample_create_payload())
        updated = save_rule_package_revision(
            package,
            [revision],
            RulePackageDraftSave(
                name="民政补贴资格复核规则包",
                version="0.2.0",
                purpose="用于本域内补贴资格复核筛查",
                signer_name=package.signer_name,
                signature_ref=package.signature_ref,
                signature="",
                rules=[
                    {"field": "benefit_status", "operator": "eq", "value": "异常"},
                    {"field": "department", "operator": "eq", "value": "民政"},
                ],
                notes="补充部门限定",
                editor_name="经办员A",
                change_summary="更新口径并增加部门条件",
            ),
        )

        diff = compare_rule_package_revisions(package, revision, updated)

        self.assertEqual(diff.from_revision_no, 1)
        self.assertEqual(diff.to_revision_no, 2)
        self.assertTrue(any(change.field == "version" for change in diff.field_changes))
        self.assertTrue(any(change.change_type == "modified" for change in diff.rule_changes))
        self.assertTrue(any(change.change_type == "added" for change in diff.rule_changes))
        self.assertEqual(diff.summary["rule_change_count"], 2)
        self.assertTrue(diff.based_on_match)

    def test_usage_report_groups_current_and_historical_references(self) -> None:
        package, revision1 = create_rule_package_entities(sample_create_payload())
        revision1.verification_status = "verified"
        revision1.status = "approved"
        package.status = "approved"
        package.current_revision_id = revision1.id
        package.current_revision_no = revision1.revision_no

        revision2 = create_edit_revision(package, [revision1], editor_name="经办员B")
        revision2.verification_status = "verified"
        revision2.status = "approved"
        package.current_revision_id = revision2.id
        package.current_revision_no = revision2.revision_no

        report = build_rule_package_usage_report(
            package,
            [revision1, revision2],
            [
                {
                    "id": "task-current",
                    "name": "当前版任务",
                    "status": "completed",
                    "created_at": "2026-05-10T09:00:00Z",
                    "output_policy": "aggregate_summary",
                    "rule_package_id": package.id,
                    "rule_package_revision_id": revision2.id,
                },
                {
                    "id": "task-history",
                    "name": "历史版任务",
                    "status": "completed",
                    "created_at": "2026-05-08T09:00:00Z",
                    "output_policy": "execution_receipt",
                    "rule_package_id": package.id,
                    "rule_package_revision_id": revision1.id,
                },
            ],
        )

        self.assertEqual(report.total_task_count, 2)
        self.assertEqual(report.current_revision_task_count, 1)
        self.assertEqual(report.historical_revision_task_count, 1)
        self.assertEqual(report.revision_summaries[0].task_count, 1)
        self.assertEqual(report.revision_summaries[1].task_count, 1)
        self.assertEqual(report.tasks[0].task_id, "task-current")
        self.assertTrue(report.tasks[0].is_current_revision)


if __name__ == "__main__":
    unittest.main()
