"""File-only logging for iconfucius. Thread-safe by design.

Security properties:
- Log file created with 0600 (owner read/write only)
- Log directory created with 0700 (owner access only)
- Default level: INFO (debug detail requires --verbose or ICONFUCIUS_VERBOSE=1)
- JWT tokens are NEVER logged (scrubbed by filter)

In ``chat`` mode (one process = one session), ``get_logger()`` returns the
global logger which writes to a single ``*-iconfucius.log``.

In ``ui`` mode (one process = many sessions), each chat session calls
``create_session_logger`` + ``set_session_logger`` so that ``get_logger()``
returns a per-session file logger on the current thread.  The global logger
is used for server-level events (startup, requests, cache warming).
"""

import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

# JWT pattern: three base64url-encoded segments separated by dots
_JWT_PATTERN = re.compile(
    r'eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'
)

_MAX_SESSION_LOGS = 100

_session_stamp: str | None = None

# Thread-local storage for per-session loggers (used in ``ui`` mode).
_thread_local = threading.local()


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
        """Scrub JWT tokens from log messages and allow the record to pass."""
        if isinstance(record.msg, str):
            record.msg = _JWT_PATTERN.sub("[JWT-REDACTED]", record.msg)
        return True


def _cleanup_session_logs(conv_dir: Path) -> None:
    """Delete oldest session logs beyond _MAX_SESSION_LOGS."""
    files = sorted(conv_dir.glob("*-iconfucius.log"))
    for old in files[:-_MAX_SESSION_LOGS]:
        old.unlink()


def _get_log_dir(base_dir: str | Path | None = None) -> Path:
    """Return (and create) the ``.logs/conversations/`` directory."""
    root = Path(base_dir) if base_dir else Path(
        os.environ.get("ICONFUCIUS_ROOT", ".")
    )
    conv_dir = root / ".logs" / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(conv_dir, 0o700)
    os.chmod(conv_dir.parent, 0o700)
    return conv_dir


def _make_file_handler(log_path: Path) -> logging.StreamHandler:
    """Create a file handler with 0600 perms, JWT scrubbing, and formatter."""
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    fh = logging.StreamHandler(os.fdopen(fd, "w"))
    if os.environ.get("ICONFUCIUS_VERBOSE", "").strip() in ("1", "true", "yes"):
        fh.setLevel(logging.DEBUG)
    else:
        fh.setLevel(logging.INFO)
    fh.setFormatter(
        logging.Formatter("%(asctime)s %(threadName)s %(levelname)s %(message)s")
    )
    fh.addFilter(_JwtScrubFilter())
    return fh


# ---- Global logger (one per process) --------------------------------------

def _get_global_logger() -> logging.Logger:
    """Return the global iconfucius logger (file-only, no StreamHandler)."""
    logger = logging.getLogger("iconfucius")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    conv_dir = _get_log_dir()
    log_path = conv_dir / f"{get_session_stamp()}-iconfucius.log"
    logger.addHandler(_make_file_handler(log_path))

    _cleanup_session_logs(conv_dir)

    return logger


# ---- Thread-local session logger (for ``ui`` mode) ------------------------

def set_session_logger(logger: logging.Logger) -> None:
    """Set a per-session logger for the current thread."""
    _thread_local.logger = logger


def clear_session_logger() -> None:
    """Remove the per-session logger from the current thread."""
    _thread_local.logger = None


def create_session_logger(
    stamp: str,
    base_dir: str | Path | None = None,
    suffix: str = "-iconfucius.log",
) -> logging.Logger:
    """Create a new logger that writes to ``{stamp}{suffix}``.

    Each call creates an independent ``logging.Logger`` with its own file
    handler — safe to use from any thread.
    """
    conv_dir = _get_log_dir(base_dir)
    log_path = conv_dir / f"{stamp}{suffix}"

    logger = logging.getLogger(f"iconfucius.session.{stamp}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(_make_file_handler(log_path))

    _cleanup_session_logs(conv_dir)
    return logger


# ---- Public API ------------------------------------------------------------

def get_logger() -> logging.Logger:
    """Return the session logger (thread-local) or the global fallback."""
    session_logger = getattr(_thread_local, "logger", None)
    if session_logger is not None:
        return session_logger
    return _get_global_logger()


def set_debug(enabled: bool) -> None:
    """Switch file handler between DEBUG and INFO level."""
    logger = get_logger()
    level = logging.DEBUG if enabled else logging.INFO
    for handler in logger.handlers:
        handler.setLevel(level)
