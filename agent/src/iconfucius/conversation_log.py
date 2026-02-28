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
        """Initialize the conversation logger and open a new JSONL log file for this session."""
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
        """Return the file path of the cached conversation log."""
        return self._path_cached


# ---------------------------------------------------------------------------
# Reader — parse a *-ai-cached.jsonl log back into structured records
# ---------------------------------------------------------------------------

def read_conversation_log(path: str | Path) -> list[dict]:
    """Read and parse a ``*-ai-cached.jsonl`` conversation log.

    Each returned dict has the keys written by :meth:`ConversationLogger.log_interaction`:

    * **seq** — 1-based sequence number
    * **timestamp** — ISO-8601 UTC timestamp
    * **call_type** — e.g. ``"chat"``
    * **model** — model id
    * **system** — system prompt (or ``"[cached]"``)
    * **new_messages** — only the messages added since the previous call
      (the ``[cached N messages]`` prefix is stripped)
    * **tools** — tool definitions (or ``"[cached]"`` / ``None``)
    * **response** — the raw API response object
    * **duration_ms** — round-trip time
    * **error** — error string or ``None``
    * **tool_calls** — convenience list of ``{name, input}`` dicts extracted
      from the response (empty if the response has no tool_use blocks)
    * **tool_results** — convenience list of ``{tool_use_id, content}`` dicts
      extracted from the new messages (empty if no tool_result blocks)
    * **assistant_text** — concatenated text blocks from the response
      (empty string if the response has no text blocks)

    Args:
        path: File path to the ``*-ai-cached.jsonl`` file.

    Returns:
        Ordered list of interaction records, one per JSONL line.
    """
    path = Path(path)
    records: list[dict] = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)

            # Extract new messages (skip the "[cached N messages]" sentinel)
            messages = entry.get("messages", [])
            new_messages = []
            for m in messages:
                if isinstance(m, str) and m.startswith("[cached"):
                    continue
                new_messages.append(m)

            # Extract tool_use blocks from the response
            response = entry.get("response", {})
            tool_calls = []
            assistant_text_parts = []
            resp_content = response.get("content", []) if isinstance(response, dict) else []
            for block in resp_content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "input": block.get("input", {}),
                    })
                elif block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        assistant_text_parts.append(text)

            # Extract tool_result blocks from new messages
            tool_results = []
            for m in new_messages:
                if not isinstance(m, dict):
                    continue
                content = m.get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        result_content = block.get("content", "")
                        if isinstance(result_content, list):
                            # Extract text from content blocks
                            texts = [b.get("text", "") for b in result_content
                                     if isinstance(b, dict) and b.get("type") == "text"]
                            result_content = "\n".join(texts)
                        tool_results.append({
                            "tool_use_id": block.get("tool_use_id", ""),
                            "content": result_content,
                        })

            records.append({
                "seq": entry.get("sequence", 0),
                "timestamp": entry.get("timestamp", ""),
                "call_type": entry.get("call_type", ""),
                "model": entry.get("model", ""),
                "system": entry.get("system", ""),
                "new_messages": new_messages,
                "tools": entry.get("tools"),
                "response": response,
                "duration_ms": entry.get("duration_ms", 0),
                "error": entry.get("error"),
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                "assistant_text": "\n".join(assistant_text_parts),
            })

    return records


def format_conversation_log(path: str | Path, max_text: int = 200) -> str:
    """Return a human-readable summary of a conversation log.

    Args:
        path: File path to the ``*-ai-cached.jsonl`` file.
        max_text: Maximum characters to show for text content.

    Returns:
        Multi-line string summarizing each interaction.
    """
    records = read_conversation_log(path)
    lines: list[str] = []

    for r in records:
        seq = r["seq"]
        lines.append(f"--- SEQ {seq} [{r['call_type']}] {r['timestamp']} "
                      f"({r['duration_ms']}ms) ---")

        # Show tool results fed into this call (user→assistant feedback)
        for tr in r["tool_results"]:
            content_preview = tr["content"][:max_text]
            lines.append(f"  TOOL_RESULT [{tr['tool_use_id'][:12]}]: "
                         f"{content_preview}")

        # Show user messages (non-tool-result)
        for m in r["new_messages"]:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "?")
            content = m.get("content", "")
            if isinstance(content, str):
                lines.append(f"  {role.upper()}: {content[:max_text]}")
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        lines.append(f"  {role.upper()}: "
                                     f"{block.get('text', '')[:max_text]}")
                    elif block.get("type") != "tool_result":
                        lines.append(f"  {role.upper()} [{block.get('type')}]")

        # Show assistant response
        if r["assistant_text"]:
            lines.append(f"  ASSISTANT: {r['assistant_text'][:max_text]}")

        for tc in r["tool_calls"]:
            input_str = json.dumps(tc["input"], default=str)
            lines.append(f"  TOOL_CALL: {tc['name']}({input_str[:max_text]})")

        if r["error"]:
            lines.append(f"  ERROR: {r['error'][:max_text]}")

        lines.append("")

    return "\n".join(lines)
