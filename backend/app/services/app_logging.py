import logging
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import WORKSPACE_ROOT, ensure_workspace


def configure_logging() -> None:
    ensure_workspace()
    log_dir = WORKSPACE_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root_logger = logging.getLogger()
    if any(isinstance(handler, RotatingFileHandler) for handler in root_logger.handlers):
        return

    try:
        handler: logging.Handler = RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.StreamHandler(sys.stderr)

    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
