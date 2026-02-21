"""Conversation logging for AI interactions — JSONL files with JWT scrubbing.

Two files per session:
  {stamp}-ai-full.jsonl    — complete API payload + response, for replay
  {stamp}-ai-cached.jsonl  — system+tools replaced with "[cached]" when
                             unchanged, for quick reading & cache review
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from iconfucius.logging_config import _JWT_PATTERN, get_session_stamp

_MAX_LOG_FILES = 100


def _cache_key(system, tools) -> str:
    """Return a deterministic string for system+tools to detect changes."""
    return json.dumps({"system": system, "tools": tools}, sort_keys=True,
                      default=str)


class ConversationLogger:
    """Logs AI interactions to timestamped JSONL files.

    Two files per chat session under .logs/conversations/:
      - ai-full:   every field, every call
      - ai-cached: system+tools replaced with "[cached]" when unchanged
    """

    def __init__(self, base_dir: str | Path | None = None):
        root = Path(base_dir) if base_dir else Path(
            os.environ.get("ICONFUCIUS_ROOT", ".")
        )
        conv_dir = root / ".logs" / "conversations"
        conv_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(conv_dir, 0o700)
        os.chmod(conv_dir.parent, 0o700)

        stamp = get_session_stamp()

        self._path_full = conv_dir / f"{stamp}-ai-full.jsonl"
        self._path_cached = conv_dir / f"{stamp}-ai-cached.jsonl"

        fd_full = os.open(self._path_full,
                          os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        self._file_full = os.fdopen(fd_full, "w")

        fd_cached = os.open(self._path_cached,
                            os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        self._file_cached = os.fdopen(fd_cached, "w")

        self._seq = 0
        self._prev_cache_key: str | None = None
        self._cleanup(conv_dir)

    def log_interaction(
        self,
        *,
        call_type: str,
        model: str,
        system,
        messages: list[dict],
        tools: list[dict] | None = None,
        response,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        """Append one interaction record to both JSONL files."""
        self._seq += 1
        ts = datetime.now(timezone.utc).isoformat()

        # --- full entry (always complete) ---
        full_entry: dict = {
            "timestamp": ts,
            "sequence": self._seq,
            "call_type": call_type,
            "model": model,
            "system": system,
            "messages": messages,
        }
        if tools is not None:
            full_entry["tools"] = tools
        full_entry["response"] = response
        full_entry["duration_ms"] = duration_ms
        full_entry["error"] = error

        full_line = json.dumps(full_entry, default=str)
        full_line = _JWT_PATTERN.sub("[JWT-REDACTED]", full_line)
        self._file_full.write(full_line + "\n")
        self._file_full.flush()

        # --- cached entry (system+tools → "[cached]" when unchanged) ---
        current_key = _cache_key(system, tools)
        if self._prev_cache_key is not None and current_key == self._prev_cache_key:
            cached_system = "[cached]"
            cached_tools = "[cached]" if tools is not None else None
        else:
            cached_system = system
            cached_tools = tools
        self._prev_cache_key = current_key

        cached_entry: dict = {
            "timestamp": ts,
            "sequence": self._seq,
            "call_type": call_type,
            "model": model,
            "system": cached_system,
            "messages": messages,
        }
        if cached_tools is not None:
            cached_entry["tools"] = cached_tools
        cached_entry["response"] = response
        cached_entry["duration_ms"] = duration_ms
        cached_entry["error"] = error

        cached_line = json.dumps(cached_entry, default=str)
        cached_line = _JWT_PATTERN.sub("[JWT-REDACTED]", cached_line)
        self._file_cached.write(cached_line + "\n")
        self._file_cached.flush()

    @staticmethod
    def _cleanup(conv_dir: Path) -> None:
        """Delete oldest conversation logs beyond _MAX_LOG_FILES (per suffix)."""
        for suffix in ("ai-full", "ai-cached"):
            files = sorted(conv_dir.glob(f"*-{suffix}.jsonl"))
            for old in files[:-_MAX_LOG_FILES]:
                old.unlink()

    def close(self) -> None:
        """Flush and close both log files."""
        self._file_full.close()
        self._file_cached.close()

    @property
    def path_full(self) -> Path:
        return self._path_full

    @property
    def path_cached(self) -> Path:
        return self._path_cached
