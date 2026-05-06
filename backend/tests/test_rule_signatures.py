import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.models.schemas import RulePackage, RulePackageCreate
from app.services import rule_signatures
from app.services.audit import utc_now
from app.services.rule_signatures import (
    apply_rule_package_verification,
    canonical_rule_package_payload,
    sign_payload_with_private_key,
    verify_rule_package_signature,
)


def generate_rsa_keypair(private_key_path: Path, public_key_path: Path) -> None:
    subprocess.run(["openssl", "genrsa", "-out", str(private_key_path), "2048"], check=True, capture_output=True, text=True)
    subprocess.run(
        ["openssl", "rsa", "-in", str(private_key_path), "-pubout", "-out", str(public_key_path)],
        check=True,
        capture_output=True,
        text=True,
    )


class RuleSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        private_key_path = Path(self.temp_dir.name) / "signer-private.pem"
        public_key_path = Path(self.temp_dir.name) / "signer-public.pem"
        generate_rsa_keypair(private_key_path, public_key_path)
        self.private_key_path = private_key_path
        self.public_key_path = public_key_path

        self.original_file = rule_signatures.TRUSTED_SIGNERS_FILE
        rule_signatures.TRUSTED_SIGNERS_FILE = Path(self.temp_dir.name) / "trusted-signers.json"
        rule_signatures.TRUSTED_SIGNERS_FILE.write_text(
            json.dumps(
                [
                    {
                        "signer_name": "市级规则中心",
                        "key_type": "rsa-public-key",
                        "signature_ref": "SIG-CENTER-RSA-001",
                        "status": "active",
                        "public_key_path": str(self.public_key_path),
                        "description": "测试公钥",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.addCleanup(self.restore_signers_file)

    def restore_signers_file(self) -> None:
        rule_signatures.TRUSTED_SIGNERS_FILE = self.original_file

    def sample_payload(self) -> RulePackageCreate:
        payload = canonical_rule_package_payload(
            name="民政补贴资格规则包",
            version="0.1.0",
            purpose="核验补贴资格规则",
            signer_name="市级规则中心",
            signature_ref="SIG-CENTER-RSA-001",
            rules=[{"field": "benefit_status", "operator": "eq", "value": "正常"}],
        )
        signature = sign_payload_with_private_key(payload, str(self.private_key_path))
        return RulePackageCreate(
            name="民政补贴资格规则包",
            version="0.1.0",
            purpose="核验补贴资格规则",
            signer_name="市级规则中心",
            signature_ref="SIG-CENTER-RSA-001",
            signature=signature,
            rules=[{"field": "benefit_status", "operator": "eq", "value": "正常"}],
        )

    def test_valid_signature_is_verified(self) -> None:
        is_valid, message = verify_rule_package_signature(self.sample_payload())

        self.assertTrue(is_valid)
        self.assertEqual(message, "签名校验通过")

    def test_modified_rule_breaks_signature(self) -> None:
        payload = self.sample_payload()
        payload.rules = [{"field": "benefit_status", "operator": "eq", "value": "异常"}]

        is_valid, message = verify_rule_package_signature(payload)

        self.assertFalse(is_valid)
        self.assertIn("Verification Failure", message)

    def test_unknown_signer_is_rejected(self) -> None:
        payload = self.sample_payload()
        payload.signer_name = "未知签名人"

        is_valid, message = verify_rule_package_signature(payload)

        self.assertFalse(is_valid)
        self.assertIn("不在本域受信任签名人名单", message)

    def test_apply_verification_marks_rule_package_invalid(self) -> None:
        package = RulePackage(
            id="package-1",
            name="民政补贴资格规则包",
            version="0.1.0",
            purpose="核验补贴资格规则",
            signer_name="市级规则中心",
            signature_ref="SIG-CENTER-RSA-001",
            signature="invalid-base64",
            rules=[{"field": "benefit_status", "operator": "eq", "value": "正常"}],
            rules_count=1,
            created_at=utc_now(),
        )

        package = apply_rule_package_verification(package)

        self.assertEqual(package.status, "invalid")
        self.assertEqual(package.verification_status, "failed")
        self.assertIsNotNone(package.verified_at)


if __name__ == "__main__":
    unittest.main()
