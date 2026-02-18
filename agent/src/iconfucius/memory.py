"""Markdown-first memory store for trading personas.

Memory is per-persona, per-project. Files live in .memory/<persona>/ under
the project root. File locking via filelock prevents race conditions when
multiple bots share a persona.

Phase 1: append-only Markdown files (no SQLite/embeddings yet).
"""

import re
from pathlib import Path

from filelock import FileLock

from iconfucius.config import _project_root


def get_memory_dir(persona_name: str) -> Path:
    """Return .memory/<persona_name>/ under project root. Create if missing."""
    memory_dir = Path(_project_root()) / ".memory" / persona_name
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def _lock_path(persona_name: str) -> Path:
    """Return the lock file path for a persona's memory."""
    return get_memory_dir(persona_name) / ".lock"


def append_trade(persona_name: str, entry: str) -> None:
    """Append a trade entry to trades.md with file locking."""
    memory_dir = get_memory_dir(persona_name)
    trades_path = memory_dir / "trades.md"
    with FileLock(_lock_path(persona_name), timeout=30):
        # Create header if file doesn't exist
        if not trades_path.exists():
            trades_path.write_text("# Trade Log\n")
        with open(trades_path, "a") as f:
            f.write(f"\n{entry}\n")


def read_trades(persona_name: str, last_n: int = 10) -> str:
    """Read last N trade entries from trades.md.

    Each entry starts with '## ' (h2 heading). Returns empty string
    if no trades file exists.
    """
    memory_dir = get_memory_dir(persona_name)
    trades_path = memory_dir / "trades.md"
    if not trades_path.exists():
        return ""

    content = trades_path.read_text()
    # Split on h2 headings to get individual entries
    entries = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    # Filter out the header (first element is usually "# Trade Log\n")
    entries = [e.strip() for e in entries if e.strip().startswith("## ")]
    if not entries:
        return ""
    return "\n\n".join(entries[-last_n:])


def read_strategy(persona_name: str) -> str:
    """Read strategy.md contents. Returns empty string if not yet created."""
    path = get_memory_dir(persona_name) / "strategy.md"
    if not path.exists():
        return ""
    return path.read_text()


def write_strategy(persona_name: str, content: str) -> None:
    """Write strategy.md with file locking."""
    memory_dir = get_memory_dir(persona_name)
    with FileLock(_lock_path(persona_name), timeout=30):
        (memory_dir / "strategy.md").write_text(content)


def read_learnings(persona_name: str) -> str:
    """Read learnings.md contents. Returns empty string if not yet created."""
    path = get_memory_dir(persona_name) / "learnings.md"
    if not path.exists():
        return ""
    return path.read_text()


def write_learnings(persona_name: str, content: str) -> None:
    """Write learnings.md with file locking."""
    memory_dir = get_memory_dir(persona_name)
    with FileLock(_lock_path(persona_name), timeout=30):
        (memory_dir / "learnings.md").write_text(content)
