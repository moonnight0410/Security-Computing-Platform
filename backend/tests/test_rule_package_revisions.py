import unittest

from app.models.schemas import RulePackageApprove, RulePackageCreate, RulePackageDraftSave
from app.services.rule_packages import (
    approve_revision,
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


if __name__ == "__main__":
    unittest.main()
