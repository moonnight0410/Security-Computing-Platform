import json
import sqlite3
from copy import deepcopy
from typing import Any

from app.core.config import DB_FILE, STATE_FILE, ensure_workspace


DEFAULT_STATE: dict[str, list[dict[str, Any]]] = {
    "datasets": [],
    "field_mappings": [],
    "rule_packages": [],
    "tasks": [],
    "results": [],
    "export_requests": [],
    "export_files": [],
    "audit": [],
}


def normalize_state(state: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    for package in state.get("rule_packages", []):
        package.setdefault("signature_ref", "LEGACY-NO-SIGNATURE")
        if package.get("status") == "imported":
            package["status"] = "pending_review"

    for task in state.get("tasks", []):
        task.setdefault("rule_package_id", None)
        task.setdefault("output_policy", "local_only")
        task.setdefault("aggregate_threshold", None)
        task.setdefault("aggregate_group_by", None)

    for request in state.get("export_requests", []):
        request.setdefault("status", "pending")
        request.setdefault("approver_name", None)
        request.setdefault("approved_at", None)
        request.setdefault("rejection_reason", None)

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
