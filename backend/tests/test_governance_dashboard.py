import unittest

from app.services.governance_dashboard import build_governance_dashboard


class GovernanceDashboardTests(unittest.TestCase):
    def test_dashboard_summarizes_tasks_outputs_and_audit(self) -> None:
        dashboard = build_governance_dashboard(
            {
                "datasets": [],
                "field_mappings": [],
                "rule_templates": [],
                "rule_snippets": [],
                "rule_packages": [
                    {
                        "id": "pkg-1",
                        "name": "规则包",
                        "version": "0.1.0",
                        "purpose": "测试",
                        "signer_name": "",
                        "signature_ref": "",
                        "signature": "",
                        "rules": [],
                        "rules_count": 0,
                        "status": "approved",
                        "verification_status": "verified",
                        "created_at": "2026-05-13T08:00:00Z",
                        "current_revision_no": 1,
                        "signature_outdated": False,
                    }
                ],
                "rule_package_revisions": [],
                "tasks": [
                    {
                        "id": "task-1",
                        "name": "任务一",
                        "dataset_ids": [],
                        "output_policy": "aggregate_summary",
                        "status": "completed",
                        "created_at": "2026-05-13T08:00:00Z",
                    },
                    {
                        "id": "task-2",
                        "name": "任务二",
                        "dataset_ids": [],
                        "output_policy": "execution_receipt",
                        "status": "draft",
                        "created_at": "2026-05-13T09:00:00Z",
                    },
                ],
                "results": [
                    {
                        "id": "result-1",
                        "task_id": "task-1",
                        "status": "completed",
                        "created_at": "2026-05-13T08:10:00Z",
                        "summary": {},
                        "receipt": {},
                        "aggregate_summary": [],
                        "suppressed_groups": 0,
                        "local_security_notes": [],
                        "assertion": {
                            "status": "pending_review",
                            "statement": "待审",
                            "created_at": "2026-05-13T08:10:00Z",
                        },
                    }
                ],
                "export_requests": [
                    {
                        "id": "req-1",
                        "result_id": "result-1",
                        "export_type": "receipt",
                        "requester_name": "甲",
                        "purpose": "反馈",
                        "status": "pending",
                        "requested_at": "2026-05-13T08:20:00Z",
                    }
                ],
                "export_files": [
                    {
                        "id": "file-1",
                        "request_id": "req-1",
                        "result_id": "result-1",
                        "export_type": "receipt",
                        "stored_path": "workspace/exports/a.json",
                        "file_name": "a.json",
                        "sha256": "1234",
                        "byte_size": 10,
                        "generated_at": "2026-05-13T08:30:00Z",
                        "safety_notes": [],
                    }
                ],
                "export_archives": [
                    {
                        "id": "arc-1",
                        "export_file_ids": ["file-1"],
                        "archived_by": "归档员A",
                        "purpose": "归档",
                        "archived_at": "2026-05-13T08:40:00Z",
                        "archive_dir": "workspace/archives/arc-1",
                        "manifest_path": "manifest.json",
                        "report_path": "report.json",
                        "signature_path": "signature.sig",
                        "signer_name": "归档中心",
                        "signer_key_ref": "ARCH-1",
                        "manifest_hash": "abcd",
                        "file_count": 1,
                        "verification": {
                            "valid": True,
                            "manifest_hash": "abcd",
                            "signature_verified": True,
                            "audit_chain_valid": True,
                            "errors": [],
                        },
                    }
                ],
                "audit": [{"id": "audit-1", "action": "task.create", "object_type": "task", "summary": "创建任务", "created_at": "2026-05-13T08:00:00Z"}],
            }
        )

        self.assertEqual(dashboard.task_counts["completed"], 1)
        self.assertEqual(dashboard.task_counts["draft"], 1)
        self.assertEqual(dashboard.output_counts["pending"], 1)
        self.assertEqual(dashboard.output_counts["files"], 1)
        self.assertEqual(dashboard.output_counts["archives"], 1)
        self.assertEqual(dashboard.rule_package_counts["approved"], 1)
        self.assertEqual(dashboard.pending_assertion_count, 1)
        self.assertEqual(dashboard.audit_total_entries, 1)
        self.assertEqual(dashboard.recent_tasks[0].id, "task-2")


if __name__ == "__main__":
    unittest.main()
