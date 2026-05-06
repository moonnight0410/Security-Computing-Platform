import hashlib
import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import ARCHIVES_DIR, ARCHIVE_SIGNER_FILE, ensure_workspace
from app.models.schemas import ExportArchive, ExportArchiveCreate, ExportArchiveVerification, ExportFile
from app.services.audit import utc_now, verify_audit_chain
from app.services.rule_signatures import resolve_key_path, sign_payload_with_private_key, verify_signature_with_public_key


DEFAULT_ARCHIVE_SIGNER = {
    "signer_name": "本域归档封存中心",
    "key_type": "rsa-key-pair",
    "signature_ref": "ARCHIVE-SEAL-RSA-001",
    "private_key_path": "workspace/config/keys/private/archive-sealer-private.pem",
    "public_key_path": "workspace/config/keys/public/archive-sealer-public.pem",
    "status": "active",
    "description": "本域归档封存中心离线 RSA 密钥对",
}


def ensure_archive_signer_config() -> None:
    ensure_workspace()
    if ARCHIVE_SIGNER_FILE.exists():
        return
    ARCHIVE_SIGNER_FILE.write_text(
        json.dumps(DEFAULT_ARCHIVE_SIGNER, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_archive_signer() -> dict[str, str]:
    ensure_archive_signer_config()
    return json.loads(ARCHIVE_SIGNER_FILE.read_text(encoding="utf-8"))


def build_archive_manifest(
    archive_id: str,
    files: list[ExportFile],
    archived_by: str,
    purpose: str,
) -> dict[str, Any]:
    audit_verification = verify_audit_chain()
    return {
        "archive_id": archive_id,
        "archived_by": archived_by,
        "purpose": purpose,
        "archived_at": utc_now(),
        "audit_chain": {
            "valid": audit_verification.valid,
            "checked_entries": audit_verification.checked_entries,
            "total_entries": audit_verification.total_entries,
            "head_hash": audit_verification.head_hash,
        },
        "files": [
            {
                "id": item.id,
                "export_type": item.export_type,
                "file_name": item.file_name,
                "sha256": item.sha256,
                "byte_size": item.byte_size,
                "generated_at": item.generated_at,
            }
            for item in files
        ],
    }


def hash_manifest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_archive_report(manifest_path: str, signature_path: str, public_key_path: str) -> ExportArchiveVerification:
    manifest_file = Path(manifest_path)
    signature_file = Path(signature_path)
    errors: list[str] = []

    if not manifest_file.exists():
        errors.append(f"归档清单不存在：{manifest_path}")
        return ExportArchiveVerification(
            valid=False,
            manifest_hash="",
            signature_verified=False,
            audit_chain_valid=False,
            errors=errors,
        )
    if not signature_file.exists():
        errors.append(f"归档签名不存在：{signature_path}")
        return ExportArchiveVerification(
            valid=False,
            manifest_hash="",
            signature_verified=False,
            audit_chain_valid=False,
            errors=errors,
        )

    manifest_payload = manifest_file.read_text(encoding="utf-8")
    signature = signature_file.read_text(encoding="utf-8").strip()
    signature_verified, message = verify_signature_with_public_key(manifest_payload, signature, public_key_path)
    if not signature_verified:
        errors.append(message)

    manifest = json.loads(manifest_payload)
    audit_chain_valid = bool(manifest.get("audit_chain", {}).get("valid"))

    return ExportArchiveVerification(
        valid=signature_verified and audit_chain_valid and not errors,
        manifest_hash=hash_manifest(manifest_payload),
        signature_verified=signature_verified,
        audit_chain_valid=audit_chain_valid,
        errors=errors,
    )


def archive_export_files(payload: ExportArchiveCreate, files: list[ExportFile]) -> ExportArchive:
    ensure_workspace()
    if not files:
        raise ValueError("没有可归档的输出文件")

    archive_id = str(uuid4())
    archive_dir = ARCHIVES_DIR / archive_id
    files_dir = archive_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    for export_file in files:
        source = Path(export_file.stored_path)
        if not source.exists():
            raise ValueError(f"输出文件不存在：{export_file.file_name}")
        shutil.copy2(source, files_dir / export_file.file_name)

    manifest = build_archive_manifest(archive_id, files, payload.archived_by, payload.purpose)
    manifest_payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    manifest_path = archive_dir / "archive-manifest.json"
    manifest_path.write_text(manifest_payload, encoding="utf-8")

    signer = load_archive_signer()
    signature = sign_payload_with_private_key(manifest_payload, signer["private_key_path"])
    signature_path = archive_dir / "archive-manifest.sig"
    signature_path.write_text(signature, encoding="utf-8")

    verification = verify_archive_report(
        str(manifest_path),
        str(signature_path),
        str(resolve_key_path(signer["public_key_path"])),
    )

    report_path = archive_dir / "archive-report.json"
    report_path.write_text(
        json.dumps(
            {
                "archive_id": archive_id,
                "signer_name": signer["signer_name"],
                "signer_key_ref": signer["signature_ref"],
                "manifest_path": str(manifest_path),
                "signature_path": str(signature_path),
                "verification": verification.model_dump(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return ExportArchive(
        id=archive_id,
        export_file_ids=[item.id for item in files],
        archived_by=payload.archived_by,
        purpose=payload.purpose,
        archived_at=manifest["archived_at"],
        archive_dir=str(archive_dir),
        manifest_path=str(manifest_path),
        report_path=str(report_path),
        signature_path=str(signature_path),
        signer_name=signer["signer_name"],
        signer_key_ref=signer["signature_ref"],
        manifest_hash=hash_manifest(manifest_payload),
        file_count=len(files),
        verification=verification,
    )
