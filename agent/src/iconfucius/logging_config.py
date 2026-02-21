"""File-only logging for iconfucius. Thread-safe by design.

Security properties:
- Log file created with 0600 (owner read/write only)
- Log directory created with 0700 (owner access only)
- Default level: INFO (debug detail requires --verbose or ICONFUCIUS_VERBOSE=1)
- JWT tokens are NEVER logged (scrubbed by filter)
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# JWT pattern: three base64url-encoded segments separated by dots
_JWT_PATTERN = re.compile(
    r'eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'
)

_MAX_SESSION_LOGS = 100

_session_stamp: str | None = None


def get_session_stamp() -> str:
    """Return the session timestamp (YYYYMMDD-HHMMSS), generated once."""
    global _session_stamp
    if _session_stamp is None:
        _session_stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return _session_stamp


def _reset_session_stamp() -> None:
    """Reset the cached session stamp (for tests only)."""
    global _session_stamp
    _session_stamp = None


class _JwtScrubFilter(logging.Filter):
    """Safety net: redact any JWT token that appears in a log message."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _JWT_PATTERN.sub("[JWT-REDACTED]", record.msg)
        return True


def _cleanup_session_logs(conv_dir: Path) -> None:
    """Delete oldest session logs beyond _MAX_SESSION_LOGS."""
    files = sorted(conv_dir.glob("*-iconfucius.log"))
    for old in files[:-_MAX_SESSION_LOGS]:
        old.unlink()


def get_logger() -> logging.Logger:
    """Return the iconfucius logger (file-only, no StreamHandler)."""
    logger = logging.getLogger("iconfucius")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    conv_dir = (
        Path(os.environ.get("ICONFUCIUS_ROOT", ".")) / ".logs" / "conversations"
    )
    conv_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(conv_dir, 0o700)
    os.chmod(conv_dir.parent, 0o700)

    log_path = conv_dir / f"{get_session_stamp()}-iconfucius.log"
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    fh = logging.StreamHandler(os.fdopen(fd, "w"))

    # Default: INFO only. DEBUG requires --verbose or ICONFUCIUS_VERBOSE=1.
    if os.environ.get("ICONFUCIUS_VERBOSE", "").strip() in ("1", "true", "yes"):
        fh.setLevel(logging.DEBUG)
    else:
        fh.setLevel(logging.INFO)

    fh.setFormatter(
        logging.Formatter("%(asctime)s %(threadName)s %(levelname)s %(message)s")
    )
    fh.addFilter(_JwtScrubFilter())
    logger.addHandler(fh)

    _cleanup_session_logs(conv_dir)

    return logger


def set_debug(enabled: bool) -> None:
    """Switch file handler between DEBUG and INFO level."""
    logger = get_logger()
    level = logging.DEBUG if enabled else logging.INFO
    for handler in logger.handlers:
        handler.setLevel(level)
