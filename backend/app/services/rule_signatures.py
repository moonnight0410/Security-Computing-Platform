import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, TRUSTED_SIGNERS_FILE, ensure_workspace
from app.models.schemas import RulePackage, RulePackageCreate, RulePackageRevision, TrustedSignerInfo
from app.services.audit import utc_now


DEFAULT_TRUSTED_SIGNERS = [
    {
        "signer_name": "市级规则中心",
        "key_type": "rsa-public-key",
        "signature_ref": "SIG-CENTER-RSA-001",
        "status": "active",
        "public_key_path": "workspace/config/keys/public/city-rule-center-public.pem",
        "description": "市级规则中心离线 RSA 公钥",
    },
    {
        "signer_name": "数据治理办公室",
        "key_type": "rsa-public-key",
        "signature_ref": "SIG-GOV-RSA-002",
        "status": "active",
        "public_key_path": "workspace/config/keys/public/governance-office-public.pem",
        "description": "数据治理办公室离线 RSA 公钥",
    },
]


def ensure_trusted_signers_config() -> None:
    ensure_workspace()
    if TRUSTED_SIGNERS_FILE.exists():
        return
    TRUSTED_SIGNERS_FILE.write_text(
        json.dumps(DEFAULT_TRUSTED_SIGNERS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_trusted_signers() -> list[TrustedSignerInfo]:
    ensure_trusted_signers_config()
    items = json.loads(TRUSTED_SIGNERS_FILE.read_text(encoding="utf-8"))
    return [TrustedSignerInfo(**item) for item in items]


def list_trusted_signers() -> list[TrustedSignerInfo]:
    return load_trusted_signers()


def find_trusted_signer(signer_name: str) -> TrustedSignerInfo | None:
    return next((item for item in load_trusted_signers() if item.signer_name == signer_name), None)


def resolve_key_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def canonical_rule_package_payload(
    *,
    name: str,
    version: str,
    purpose: str,
    signer_name: str,
    signature_ref: str,
    rules: list[dict[str, Any]],
) -> str:
    return json.dumps(
        {
            "name": name,
            "version": version,
            "purpose": purpose,
            "signer_name": signer_name,
            "signature_ref": signature_ref,
            "rules": rules,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sign_payload_with_private_key(payload: str, private_key_path: str) -> str:
    resolved_private_key_path = resolve_key_path(private_key_path)
    with tempfile.TemporaryDirectory() as directory:
        payload_file = Path(directory) / "payload.json"
        signature_file = Path(directory) / "payload.sig"
        payload_file.write_text(payload, encoding="utf-8")
        completed = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                str(resolved_private_key_path),
                "-out",
                str(signature_file),
                str(payload_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise ValueError((completed.stderr or completed.stdout or "OpenSSL 签名失败").strip())
        return base64.b64encode(signature_file.read_bytes()).decode("ascii")


def verify_signature_with_public_key(payload: str, signature: str, public_key_path: str) -> tuple[bool, str]:
    public_key_file = resolve_key_path(public_key_path)
    if not public_key_file.exists():
        return False, f"公钥文件不存在：{public_key_path}"

    try:
        signature_bytes = base64.b64decode(signature.encode("ascii"), validate=True)
    except Exception:
        return False, "签名值不是合法的 Base64"

    with tempfile.TemporaryDirectory() as directory:
        payload_file = Path(directory) / "payload.json"
        signature_file = Path(directory) / "payload.sig"
        payload_file.write_text(payload, encoding="utf-8")
        signature_file.write_bytes(signature_bytes)
        completed = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(public_key_file),
                "-signature",
                str(signature_file),
                str(payload_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    if completed.returncode == 0:
        return True, "签名校验通过"
    output_parts = [part.strip() for part in [completed.stdout, completed.stderr] if part and part.strip()]
    output = " | ".join(output_parts) if output_parts else "OpenSSL 验签失败"
    return False, output


def verify_rule_package_signature(payload: RulePackageCreate | RulePackage | RulePackageRevision) -> tuple[bool, str]:
    if not payload.signer_name or not payload.signature_ref or not payload.signature:
        return False, "签名字段不完整"

    signer = find_trusted_signer(payload.signer_name)
    if signer is None:
        return False, "签名人不在本域受信任签名人名单中"
    if signer.status != "active":
        return False, "签名人当前不可用"
    if payload.signature_ref != signer.signature_ref:
        return False, "签名引用与受信任签名人配置不一致"

    canonical_payload = canonical_rule_package_payload(
        name=payload.name,
        version=payload.version,
        purpose=payload.purpose,
        signer_name=payload.signer_name,
        signature_ref=payload.signature_ref,
        rules=payload.rules,
    )
    return verify_signature_with_public_key(canonical_payload, payload.signature, signer.public_key_path)


def apply_rule_package_verification(
    package: RulePackage | RulePackageRevision,
) -> RulePackage | RulePackageRevision:
    is_valid, message = verify_rule_package_signature(package)
    package.verification_status = "verified" if is_valid else "failed"
    package.verification_message = message
    package.verified_at = utc_now()
    package.signature_outdated = False
    if not is_valid:
        package.status = "invalid"
    elif package.status in {"invalid", "draft"}:
        package.status = "pending_review"
    return package
