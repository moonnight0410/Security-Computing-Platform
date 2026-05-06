import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.models.schemas import ExportArchiveCreate, ExportFile
from app.services import archives
from app.services.archives import archive_export_files, verify_archive_report
from app.services.audit import utc_now


def generate_rsa_keypair(private_key_path: Path, public_key_path: Path) -> None:
    subprocess.run(["openssl", "genrsa", "-out", str(private_key_path), "2048"], check=True, capture_output=True, text=True)
    subprocess.run(
        ["openssl", "rsa", "-in", str(private_key_path), "-pubout", "-out", str(public_key_path)],
        check=True,
        capture_output=True,
        text=True,
    )


def sample_export_file(base_dir: Path) -> ExportFile:
    file_path = base_dir / "export-receipt.json"
    file_path.write_text(
        json.dumps(
            {
                "export_type": "receipt",
                "payload": {"receipt": {"task_id": "task-1", "status": "completed"}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return ExportFile(
        id="file-1",
        request_id="request-1",
        result_id="result-1",
        export_type="receipt",
        stored_path=str(file_path),
        file_name=file_path.name,
        sha256="demo-sha256",
        byte_size=file_path.stat().st_size,
        generated_at=utc_now(),
        safety_notes=["receipt only"],
    )


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        temp_root = Path(self.temp_dir.name)
        private_key_path = temp_root / "archive-private.pem"
        public_key_path = temp_root / "archive-public.pem"
        generate_rsa_keypair(private_key_path, public_key_path)

        self.original_archives_dir = archives.ARCHIVES_DIR
        self.original_archive_signer_file = archives.ARCHIVE_SIGNER_FILE
        archives.ARCHIVES_DIR = temp_root / "archives"
        archives.ARCHIVE_SIGNER_FILE = temp_root / "archive-signer.json"
        archives.ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
        archives.ARCHIVE_SIGNER_FILE.write_text(
            json.dumps(
                {
                    "signer_name": "本域归档封存中心",
                    "signature_ref": "ARCHIVE-SEAL-RSA-001",
                    "private_key_path": str(private_key_path),
                    "public_key_path": str(public_key_path),
                    "status": "active",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.addCleanup(self.restore_archive_globals)
        self.export_file = sample_export_file(temp_root)

    def restore_archive_globals(self) -> None:
        archives.ARCHIVES_DIR = self.original_archives_dir
        archives.ARCHIVE_SIGNER_FILE = self.original_archive_signer_file

    def test_archive_export_files_generates_signed_report(self) -> None:
        archive = archive_export_files(
            ExportArchiveCreate(
                export_file_ids=[self.export_file.id],
                archived_by="归档员A",
                purpose="归档封存与验签报告",
            ),
            [self.export_file],
        )

        self.assertEqual(archive.file_count, 1)
        self.assertTrue(Path(archive.manifest_path).exists())
        self.assertTrue(Path(archive.signature_path).exists())
        self.assertTrue(archive.verification.signature_verified)

    def test_verify_archive_report_detects_tampered_manifest(self) -> None:
        archive = archive_export_files(
            ExportArchiveCreate(
                export_file_ids=[self.export_file.id],
                archived_by="归档员A",
                purpose="归档封存与验签报告",
            ),
            [self.export_file],
        )
        manifest_path = Path(archive.manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["purpose"] = "被篡改的归档用途"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        verification = verify_archive_report(
            archive.manifest_path,
            archive.signature_path,
            json.loads(archives.ARCHIVE_SIGNER_FILE.read_text(encoding="utf-8"))["public_key_path"],
        )

        self.assertFalse(verification.valid)
        self.assertFalse(verification.signature_verified)
        self.assertTrue(verification.errors)


if __name__ == "__main__":
    unittest.main()
