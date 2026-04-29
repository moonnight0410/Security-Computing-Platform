import json
import tempfile
import unittest
from pathlib import Path

from app.models.schemas import AuditEntry
from app.services import audit
from app.services.audit import chain_audit_entry, compute_entry_hash, verify_audit_chain


class AuditChainTests(unittest.TestCase):
    def test_chain_entry_adds_hash_fields(self) -> None:
        entry = AuditEntry(
            id="audit-1",
            action="test.action",
            object_type="test",
            object_id="object-1",
            summary="测试审计",
            created_at="2026-04-29T00:00:00+00:00",
            metadata={"count": 1},
        )

        chained = chain_audit_entry(entry)

        self.assertIn("previous_hash", chained)
        self.assertIn("entry_hash", chained)
        self.assertEqual(len(chained["entry_hash"]), 64)

    def test_verify_audit_chain_accepts_intact_realistic_chain(self) -> None:
        entries = [
            {
                "id": "audit-1",
                "action": "dataset.import",
                "object_type": "dataset",
                "object_id": "dataset-1",
                "summary": "本域导入数据集：民政救助事项.csv",
                "created_at": "2026-04-29T01:00:00+00:00",
                "metadata": {"row_count": 31, "field_count": 8, "export_policy": "local_only"},
            },
            {
                "id": "audit-2",
                "action": "export.file.persist",
                "object_type": "export_file",
                "object_id": "export-file-1",
                "summary": "安全输出包写入本域文件：export-aggregate_summary.json",
                "created_at": "2026-04-29T01:05:00+00:00",
                "metadata": {"export_type": "aggregate_summary", "sha256": "a" * 64, "byte_size": 512},
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            original_audit_dir = audit.AUDIT_DIR
            audit.AUDIT_DIR = Path(directory)
            try:
                previous_hash = "GENESIS"
                audit_file = Path(directory) / "audit-log.jsonl"
                with audit_file.open("w", encoding="utf-8") as file:
                    for entry in entries:
                        entry_hash = compute_entry_hash(previous_hash, entry)
                        file.write(
                            json.dumps(
                                {**entry, "previous_hash": previous_hash, "entry_hash": entry_hash},
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        previous_hash = entry_hash

                result = verify_audit_chain()
            finally:
                audit.AUDIT_DIR = original_audit_dir

        self.assertTrue(result.valid)
        self.assertEqual(result.total_entries, 2)
        self.assertEqual(result.checked_entries, 2)
        self.assertEqual(result.head_hash, previous_hash)
        self.assertEqual(result.errors, [])

    def test_verify_audit_chain_detects_tampered_summary(self) -> None:
        entry = {
            "id": "audit-1",
            "action": "export.file.persist",
            "object_type": "export_file",
            "object_id": "export-file-1",
            "summary": "安全输出包写入本域文件：export-receipt.json",
            "created_at": "2026-04-29T01:05:00+00:00",
            "metadata": {"export_type": "receipt", "sha256": "b" * 64, "byte_size": 300},
        }
        chained = {
            **entry,
            "previous_hash": "GENESIS",
            "entry_hash": compute_entry_hash("GENESIS", entry),
        }
        chained["summary"] = "被篡改的导出记录"

        with tempfile.TemporaryDirectory() as directory:
            original_audit_dir = audit.AUDIT_DIR
            audit.AUDIT_DIR = Path(directory)
            try:
                audit_file = Path(directory) / "audit-log.jsonl"
                audit_file.write_text(json.dumps(chained, ensure_ascii=False) + "\n", encoding="utf-8")
                result = verify_audit_chain()
            finally:
                audit.AUDIT_DIR = original_audit_dir

        self.assertFalse(result.valid)
        self.assertEqual(result.first_invalid_index, 1)
        self.assertEqual(result.checked_entries, 0)
        self.assertIn("entry_hash 校验失败", result.errors[0])

    def test_verify_audit_chain_detects_previous_hash_break(self) -> None:
        first_entry = {
            "id": "audit-1",
            "action": "task.execute",
            "object_type": "task",
            "object_id": "task-1",
            "summary": "执行本域任务：救助资格核验",
            "created_at": "2026-04-29T02:00:00+00:00",
            "metadata": {"row_count": 31, "suppressed_groups": 2},
        }
        second_entry = {
            "id": "audit-2",
            "action": "export.request",
            "object_type": "export_request",
            "object_id": "request-1",
            "summary": "创建安全输出申请：receipt",
            "created_at": "2026-04-29T02:02:00+00:00",
            "metadata": {"export_type": "receipt", "requester_name": "经办人A"},
        }
        first_hash = compute_entry_hash("GENESIS", first_entry)
        second_hash = compute_entry_hash("BROKEN", second_entry)

        with tempfile.TemporaryDirectory() as directory:
            original_audit_dir = audit.AUDIT_DIR
            audit.AUDIT_DIR = Path(directory)
            try:
                audit_file = Path(directory) / "audit-log.jsonl"
                audit_file.write_text(
                    "\n".join(
                        [
                            json.dumps(
                                {**first_entry, "previous_hash": "GENESIS", "entry_hash": first_hash},
                                ensure_ascii=False,
                            ),
                            json.dumps(
                                {**second_entry, "previous_hash": "BROKEN", "entry_hash": second_hash},
                                ensure_ascii=False,
                            ),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                result = verify_audit_chain()
            finally:
                audit.AUDIT_DIR = original_audit_dir

        self.assertFalse(result.valid)
        self.assertEqual(result.first_invalid_index, 2)
        self.assertEqual(result.checked_entries, 1)
        self.assertIn("previous_hash", result.errors[0])


if __name__ == "__main__":
    unittest.main()
