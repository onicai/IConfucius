"""Conversation logging for AI interactions — JSONL files with JWT scrubbing.

One file per session:
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

    One file per chat session under .logs/conversations/:
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

        self._path_cached = conv_dir / f"{stamp}-ai-cached.jsonl"

        fd_cached = os.open(self._path_cached,
                            os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        self._file_cached = os.fdopen(fd_cached, "w")

        self._seq = 0
        self._prev_cache_key: str | None = None
        self._prev_msg_count = 0
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
        raw_openai_response: dict | None = None,
    ) -> None:
        """Append one interaction record to the JSONL log file."""
        self._seq += 1
        ts = datetime.now(timezone.utc).isoformat()

        # system+tools → "[cached]" when unchanged from previous call
        current_key = _cache_key(system, tools)
        if self._prev_cache_key is not None and current_key == self._prev_cache_key:
            cached_system = "[cached]"
            cached_tools = "[cached]" if tools is not None else None
        else:
            cached_system = system
            cached_tools = tools
        self._prev_cache_key = current_key

        # Only log new messages since the last call
        prev = self._prev_msg_count
        if prev > 0 and len(messages) > prev:
            cached_messages = [f"[cached {prev} messages]"] + messages[prev:]
        else:
            cached_messages = messages
        self._prev_msg_count = len(messages)

        entry: dict = {
            "timestamp": ts,
            "sequence": self._seq,
            "call_type": call_type,
            "model": model,
            "system": cached_system,
            "messages": cached_messages,
        }
        if cached_tools is not None:
            entry["tools"] = cached_tools
        entry["response"] = response
        entry["duration_ms"] = duration_ms
        entry["error"] = error
        if raw_openai_response is not None:
            entry["raw_openai_response"] = raw_openai_response

        line = json.dumps(entry, default=str)
        line = _JWT_PATTERN.sub("[JWT-REDACTED]", line)
        self._file_cached.write(line + "\n")
        self._file_cached.flush()

    @staticmethod
    def _cleanup(conv_dir: Path) -> None:
        """Delete oldest conversation logs beyond _MAX_LOG_FILES."""
        files = sorted(conv_dir.glob("*-ai-cached.jsonl"))
        for old in files[:-_MAX_LOG_FILES]:
            old.unlink()

    def close(self) -> None:
        """Flush and close the log file."""
        self._file_cached.close()

    @property
    def path_cached(self) -> Path:
        return self._path_cached
