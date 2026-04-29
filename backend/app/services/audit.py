from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from app.core.config import AUDIT_DIR, ensure_workspace
from app.models.schemas import AuditChainVerification, AuditEntry
from app.services.app_logging import get_logger
from app.services.storage import add_record

logger = get_logger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def last_audit_hash() -> str:
    audit_file = AUDIT_DIR / "audit-log.jsonl"
    if not audit_file.exists():
        return "GENESIS"

    last_hash = "GENESIS"
    with audit_file.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            last_hash = item.get("entry_hash") or last_hash
    return last_hash


def chain_audit_entry(entry: AuditEntry) -> dict[str, Any]:
    previous_hash = last_audit_hash()
    payload = entry.model_dump()
    return {
        **payload,
        "previous_hash": previous_hash,
        "entry_hash": compute_entry_hash(previous_hash, payload),
    }


def compute_entry_hash(previous_hash: str, entry_payload: dict[str, Any]) -> str:
    hash_input = json.dumps(
        {"previous_hash": previous_hash, "entry": entry_payload},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


def verify_audit_chain() -> AuditChainVerification:
    ensure_workspace()
    audit_file = AUDIT_DIR / "audit-log.jsonl"
    if not audit_file.exists():
        return AuditChainVerification(
            valid=True,
            total_entries=0,
            checked_entries=0,
            head_hash="GENESIS",
        )

    errors: list[str] = []
    previous_hash = "GENESIS"
    first_invalid_index: int | None = None
    checked_entries = 0
    total_entries = 0

    with audit_file.open("r", encoding="utf-8") as file:
        for index, line in enumerate(file, start=1):
            if not line.strip():
                continue

            total_entries += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                first_invalid_index = first_invalid_index or index
                errors.append(f"第 {index} 行不是合法 JSON")
                break

            actual_previous_hash = item.get("previous_hash")
            actual_entry_hash = item.get("entry_hash")
            entry_payload = {
                key: value
                for key, value in item.items()
                if key not in {"previous_hash", "entry_hash"}
            }

            if actual_previous_hash != previous_hash:
                first_invalid_index = first_invalid_index or index
                errors.append(f"第 {index} 行 previous_hash 与上一条记录不一致")
                break

            expected_entry_hash = compute_entry_hash(previous_hash, entry_payload)
            if actual_entry_hash != expected_entry_hash:
                first_invalid_index = first_invalid_index or index
                errors.append(f"第 {index} 行 entry_hash 校验失败")
                break

            previous_hash = expected_entry_hash
            checked_entries += 1

    return AuditChainVerification(
        valid=not errors,
        total_entries=total_entries,
        checked_entries=checked_entries,
        first_invalid_index=first_invalid_index,
        head_hash=previous_hash,
        errors=errors,
    )


def write_audit(
    *,
    action: str,
    object_type: str,
    summary: str,
    object_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEntry:
    entry = AuditEntry(
        id=str(uuid4()),
        action=action,
        object_type=object_type,
        object_id=object_id,
        summary=summary,
        created_at=utc_now(),
        metadata=metadata or {},
    )
    add_record("audit", entry.model_dump())
    ensure_workspace()
    audit_file = AUDIT_DIR / "audit-log.jsonl"
    with audit_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(chain_audit_entry(entry), ensure_ascii=False) + "\n")
    logger.info("audit action=%s object_type=%s object_id=%s", action, object_type, object_id)
    return entry
