import json
import sqlite3
from copy import deepcopy
from typing import Any

from app.core.config import DB_FILE, STATE_FILE, ensure_workspace


DEFAULT_STATE: dict[str, list[dict[str, Any]]] = {
    "datasets": [],
    "field_mappings": [],
    "rule_packages": [],
    "rule_package_revisions": [],
    "tasks": [],
    "results": [],
    "export_requests": [],
    "export_files": [],
    "export_archives": [],
    "audit": [],
}


def normalize_rule_packages(state: dict[str, list[dict[str, Any]]]) -> None:
    revisions = state.setdefault("rule_package_revisions", [])
    revisions_by_package: dict[str, list[dict[str, Any]]] = {}
    for revision in revisions:
        package_id = str(revision.get("rule_package_id") or "")
        if package_id:
            revisions_by_package.setdefault(package_id, []).append(revision)

    for package in state.get("rule_packages", []):
        package.setdefault("signer_name", "")
        package.setdefault("signature_ref", "")
        package.setdefault("signature", "")
        package.setdefault("verification_status", "legacy_unverified")
        package.setdefault("verification_message", None)
        package.setdefault("verified_at", None)
        if package.get("status") in {"imported", "rejected"}:
            package["status"] = "draft"
        package.setdefault("updated_at", package.get("created_at"))
        package.setdefault("latest_editor_name", package.get("approved_by"))
        package.setdefault("latest_edited_at", package.get("updated_at"))
        package.setdefault("signature_outdated", package.get("verification_status") != "verified")
        package.setdefault("deleted_at", None)
        package.setdefault("deprecated_at", None)
        package.setdefault("deprecated_by", None)
        package.setdefault("deprecation_reason", None)

        package_revisions = revisions_by_package.get(str(package.get("id")), [])
        if not package_revisions:
            revision_id = f"{package['id']}-rev-1"
            revision_status = package["status"]
            revision = {
                "id": revision_id,
                "rule_package_id": package["id"],
                "revision_no": 1,
                "name": package.get("name"),
                "version": package.get("version", "0.1.0"),
                "purpose": package.get("purpose"),
                "signer_name": package.get("signer_name", ""),
                "signature_ref": package.get("signature_ref", ""),
                "signature": package.get("signature", ""),
                "rules": package.get("rules", []),
                "rules_count": package.get("rules_count", len(package.get("rules", []))),
                "status": revision_status,
                "verification_status": package.get("verification_status", "legacy_unverified"),
                "verification_message": package.get("verification_message"),
                "verified_at": package.get("verified_at"),
                "approved_by": package.get("approved_by"),
                "approved_at": package.get("approved_at"),
                "notes": package.get("notes"),
                "change_summary": "Migrated existing rule package into Stage 9 revision history",
                "editor_name": package.get("latest_editor_name") or package.get("approved_by"),
                "saved_by_auto": False,
                "signature_outdated": package.get("verification_status") != "verified",
                "based_on_revision_id": None,
                "content_hash": f"legacy-{package['id']}",
                "created_at": package.get("created_at"),
            }
            revisions.append(revision)
            package_revisions = [revision]
            revisions_by_package[str(package["id"])] = package_revisions

        package_revisions.sort(key=lambda item: (int(item.get("revision_no", 0)), str(item.get("created_at", ""))))
        current_revision = package_revisions[-1]
        package.setdefault("current_revision_id", current_revision.get("id"))
        package.setdefault("current_revision_no", int(current_revision.get("revision_no", 1)))
        package["rules"] = current_revision.get("rules", package.get("rules", []))
        package["rules_count"] = current_revision.get("rules_count", len(package["rules"]))
        package["signer_name"] = current_revision.get("signer_name", package.get("signer_name", ""))
        package["signature_ref"] = current_revision.get("signature_ref", package.get("signature_ref", ""))
        package["signature"] = current_revision.get("signature", package.get("signature", ""))
        package["verification_status"] = current_revision.get(
            "verification_status",
            package.get("verification_status", "legacy_unverified"),
        )
        package["verification_message"] = current_revision.get("verification_message")
        package["verified_at"] = current_revision.get("verified_at")
        package["approved_by"] = current_revision.get("approved_by")
        package["approved_at"] = current_revision.get("approved_at")
        package["notes"] = current_revision.get("notes")
        package["latest_editor_name"] = current_revision.get("editor_name") or package.get("latest_editor_name")
        package["latest_edited_at"] = current_revision.get("created_at") or package.get("latest_edited_at")
        package["signature_outdated"] = current_revision.get("signature_outdated", package.get("signature_outdated", True))


def normalize_state(state: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    normalize_rule_packages(state)

    for task in state.get("tasks", []):
        task.setdefault("rule_package_id", None)
        if not task.get("rule_package_revision_id") and task.get("rule_package_id"):
            package = next(
                (item for item in state.get("rule_packages", []) if item.get("id") == task.get("rule_package_id")),
                None,
            )
            if package:
                task["rule_package_revision_id"] = package.get("current_revision_id")
        task.setdefault("rule_package_revision_id", None)
        task.setdefault("output_policy", "local_only")
        task.setdefault("aggregate_threshold", None)
        task.setdefault("aggregate_group_by", None)

    for request in state.get("export_requests", []):
        request.setdefault("status", "pending")
        request.setdefault("approver_name", None)
        request.setdefault("approved_at", None)
        request.setdefault("rejection_reason", None)

    for result in state.get("results", []):
        assertion = result.get("assertion")
        if isinstance(assertion, dict):
            assertion.setdefault("created_at", result.get("created_at"))
            assertion.setdefault("reviewer_name", None)
            assertion.setdefault("reviewed_at", None)
            assertion.setdefault("review_comment", None)
            assertion.setdefault("rejection_reason", None)

    return state


def connect() -> sqlite3.Connection:
    ensure_workspace()
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            collection TEXT NOT NULL,
            record_key TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (collection, record_key)
        )
        """
    )
    connection.commit()
    return connection


def record_key(collection: str, record: dict[str, Any], index: int) -> str:
    if collection == "field_mappings" and record.get("dataset_id"):
        return str(record["dataset_id"])
    if collection == "results" and record.get("task_id"):
        return str(record["task_id"])
    if record.get("id"):
        return str(record["id"])
    return f"{collection}-{index}"


def existing_record_count(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS count FROM records").fetchone()
    return int(row["count"])


def load_json_state_file() -> dict[str, list[dict[str, Any]]]:
    if not STATE_FILE.exists():
        return deepcopy(DEFAULT_STATE)

    with STATE_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    state = deepcopy(DEFAULT_STATE)
    for key in DEFAULT_STATE:
        value = data.get(key)
        if isinstance(value, list):
            state[key] = value
    return normalize_state(state)


def migrate_json_state_if_needed(connection: sqlite3.Connection) -> None:
    if existing_record_count(connection) > 0 or not STATE_FILE.exists():
        return

    state = load_json_state_file()
    for collection, records in state.items():
        for index, record in enumerate(records):
            upsert_record(connection, collection, record_key(collection, record, index), record)
    connection.commit()


def upsert_record(
    connection: sqlite3.Connection,
    collection: str,
    key: str,
    record: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO records (collection, record_key, payload, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(collection, record_key)
        DO UPDATE SET payload = excluded.payload, updated_at = CURRENT_TIMESTAMP
        """,
        (collection, key, json.dumps(record, ensure_ascii=False)),
    )


def load_state() -> dict[str, list[dict[str, Any]]]:
    with connect() as connection:
        migrate_json_state_if_needed(connection)
        rows = connection.execute(
            "SELECT collection, payload FROM records ORDER BY created_at, rowid"
        ).fetchall()

    state = deepcopy(DEFAULT_STATE)
    for row in rows:
        collection = row["collection"]
        if collection not in state:
            continue
        state[collection].append(json.loads(row["payload"]))
    return normalize_state(state)


def save_state(state: dict[str, list[dict[str, Any]]]) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM records")
        for collection, records in normalize_state(state).items():
            for index, record in enumerate(records):
                upsert_record(connection, collection, record_key(collection, record, index), record)
        connection.commit()


def add_record(collection: str, record: dict[str, Any]) -> None:
    if collection not in DEFAULT_STATE:
        raise ValueError(f"Unknown collection: {collection}")

    with connect() as connection:
        migrate_json_state_if_needed(connection)
        key = record_key(collection, record, existing_record_count(connection))
        upsert_record(connection, collection, key, record)
        connection.commit()


def replace_collection(collection: str, records: list[dict[str, Any]]) -> None:
    if collection not in DEFAULT_STATE:
        raise ValueError(f"Unknown collection: {collection}")

    with connect() as connection:
        migrate_json_state_if_needed(connection)
        connection.execute("DELETE FROM records WHERE collection = ?", (collection,))
        for index, record in enumerate(records):
            upsert_record(connection, collection, record_key(collection, record, index), record)
        connection.commit()
