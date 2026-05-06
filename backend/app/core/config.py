from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

IMPORTS_DIR = WORKSPACE_ROOT / "imports"
CONFIG_DIR = WORKSPACE_ROOT / "config"
AUDIT_DIR = WORKSPACE_ROOT / "audit"
EXPORTS_DIR = WORKSPACE_ROOT / "exports"
ARCHIVES_DIR = WORKSPACE_ROOT / "archives"
KEYS_DIR = CONFIG_DIR / "keys"
PUBLIC_KEYS_DIR = KEYS_DIR / "public"
PRIVATE_KEYS_DIR = KEYS_DIR / "private"

STATE_FILE = CONFIG_DIR / "app-state.json"
DB_FILE = CONFIG_DIR / "app-state.sqlite3"
TRUSTED_SIGNERS_FILE = CONFIG_DIR / "trusted-signers.json"
ARCHIVE_SIGNER_FILE = CONFIG_DIR / "archive-signer.json"


def ensure_workspace() -> None:
    for path in [
        WORKSPACE_ROOT,
        IMPORTS_DIR,
        WORKSPACE_ROOT / "parsed",
        WORKSPACE_ROOT / "results",
        EXPORTS_DIR,
        WORKSPACE_ROOT / "logs",
        AUDIT_DIR,
        CONFIG_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
