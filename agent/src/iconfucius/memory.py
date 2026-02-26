"""Markdown-first memory store for trading personas.

Memory is per-persona, per-project. Files live in .memory/<persona>/ under
the project root. File locking via filelock prevents race conditions when
multiple bots share a persona.

Phase 1: append-only Markdown files (no SQLite/embeddings yet).
"""

import json
import re
from datetime import datetime, timezone
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


def append_trade(persona_name: str, entry: dict) -> None:
    """Append a trade entry (dict) to trades.jsonl with file locking."""
    memory_dir = get_memory_dir(persona_name)
    jsonl_path = memory_dir / "trades.jsonl"
    md_path = memory_dir / "trades.md"
    with FileLock(_lock_path(persona_name), timeout=30):
        if md_path.exists():
            _migrate_trades_md_to_jsonl_locked(memory_dir)
        with open(jsonl_path, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def read_trades(persona_name: str, last_n: int = 10) -> list[dict]:
    """Read last N trade entries from trades.jsonl.

    Returns list of trade dicts (newest last). Returns [] if no file.
    Auto-migrates trades.md → trades.jsonl on first access.
    """
    memory_dir = get_memory_dir(persona_name)
    jsonl_path = memory_dir / "trades.jsonl"
    md_path = memory_dir / "trades.md"

    with FileLock(_lock_path(persona_name), timeout=30):
        if md_path.exists():
            _migrate_trades_md_to_jsonl_locked(memory_dir)

        if not jsonl_path.exists():
            return []

        trades: list[dict] = []
        with open(jsonl_path, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        trades.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        continue
    return trades[-last_n:]


def migrate_trades_md_to_jsonl(persona_name: str) -> int:
    """Migrate trades.md → trades.jsonl, then delete trades.md.

    Returns count of trades migrated. Safe to call if trades.md doesn't exist.
    """
    memory_dir = get_memory_dir(persona_name)
    with FileLock(_lock_path(persona_name), timeout=30):
        return _migrate_trades_md_to_jsonl_locked(memory_dir)


def _migrate_trades_md_to_jsonl_locked(memory_dir: Path) -> int:
    """Inner migration — caller must hold the lock."""
    md_path = memory_dir / "trades.md"
    jsonl_path = memory_dir / "trades.jsonl"

    if not md_path.exists():
        return 0

    content = md_path.read_text()
    blocks = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    blocks = [b.strip() for b in blocks if b.strip().startswith("## ")]

    trades: list[dict] = []
    for block in blocks:
        parsed = _parse_trade_block(block)
        if parsed:
            trades.append(parsed)

    if trades:
        with open(jsonl_path, "a") as f:
            for t in trades:
                f.write(json.dumps(t, separators=(",", ":")) + "\n")

    md_path.unlink()
    return len(trades)


def _parse_trade_block(block: str) -> dict | None:
    """Parse a single ## trade block from trades.md into a dict.

    Returns None if the heading can't be parsed at all.
    """
    lines = block.splitlines()
    if not lines:
        return None

    heading = lines[0]  # e.g. "## BUY — 2026-02-18 21:12 UTC"
    m = re.match(r"^## (BUY|SELL) — (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC", heading)
    if not m:
        return None

    action = m.group(1)
    ts_str = m.group(2)
    try:
        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None

    entry: dict = {"ts": ts.isoformat(), "action": action}

    body = "\n".join(lines[1:])

    # Token: <id> (<ticker>)
    tm = re.search(r"- Token:\s*(\S+)\s*\(([^)]+)\)", body)
    if tm:
        entry["token_id"] = tm.group(1)
        entry["ticker"] = tm.group(2)

    # Spent: N sats  (BUY)
    sm = re.search(r"- Spent:\s*([\d,]+)\s*sats", body)
    if sm:
        entry["amount_sats"] = int(sm.group(1).replace(",", ""))

    # Est. tokens: ~N
    et = re.search(r"- Est\. tokens:\s*~?([\d,.]+)", body)
    if et:
        entry["est_tokens"] = float(et.group(1).replace(",", ""))

    # Sold: N tokens / ALL tokens
    sd = re.search(r"- Sold:\s*ALL\s+tokens", body)
    if sd:
        entry["tokens_sold"] = "all"
    else:
        sd2 = re.search(r"- Sold:\s*([\d,.]+)\s*tokens", body)
        if sd2:
            entry["tokens_sold"] = float(sd2.group(1).replace(",", ""))

    # Est. received: ~N sats
    er = re.search(r"- Est\. received:\s*~?([\d,.]+)\s*sats", body)
    if er:
        entry["est_sats_received"] = float(er.group(1).replace(",", ""))

    # Price: N sats/token
    pm = re.search(r"- Price:\s*([\d,]+)\s*sats/token", body)
    if pm:
        entry["price_sats"] = int(pm.group(1).replace(",", ""))

    # BTC/USD from price line: ($X.XX)
    um = re.search(r"- Price:.*\(\$([\d,.]+)\)", body)
    if um:
        entry["btc_usd_rate"] = None  # can't recover from per-token USD

    # Bots: bot-1, bot-2
    bm = re.search(r"- Bots:\s*(.+)", body)
    if bm:
        entry["bots"] = [b.strip() for b in bm.group(1).split(",")]

    return entry


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


# ---------------------------------------------------------------------------
# Balance snapshots (JSONL)
# ---------------------------------------------------------------------------

_SNAPSHOT_INTERVAL_SECS = 3600  # 1 hour


def append_balance_snapshot(persona_name: str, snapshot: dict) -> None:
    """Append a balance snapshot to balances.jsonl.

    Skips if last snapshot is < 1 hour old OR portfolio_sats is unchanged.
    """
    memory_dir = get_memory_dir(persona_name)
    path = memory_dir / "balances.jsonl"

    with FileLock(_lock_path(persona_name), timeout=30):
        # Read last line to check dedup
        if path.exists():
            last_line = ""
            with open(path, "r") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        last_line = stripped
            if last_line:
                try:
                    last = json.loads(last_line)
                    last_ts = datetime.fromisoformat(last["ts"])
                    now = datetime.now(timezone.utc)
                    elapsed = (now - last_ts).total_seconds()
                    if elapsed < _SNAPSHOT_INTERVAL_SECS and last.get("portfolio_sats") == snapshot.get("portfolio_sats"):
                        return  # skip — too recent and unchanged
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass  # corrupted line — just append

        with open(path, "a") as f:
            f.write(json.dumps(snapshot, separators=(",", ":")) + "\n")


def read_balance_snapshots(persona_name: str, last_n: int = 50) -> list[dict]:
    """Read last N balance snapshots from balances.jsonl."""
    memory_dir = get_memory_dir(persona_name)
    path = memory_dir / "balances.jsonl"
    if not path.exists():
        return []

    snapshots = []
    with open(path, "r") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                try:
                    snapshots.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
    return snapshots[-last_n:]


def archive_balance_snapshots(persona_name: str, keep_days: int = 90) -> int:
    """Move snapshots older than keep_days to balances-archive.jsonl.

    Returns count archived. Data is never deleted — just moved out of
    the active file to limit what gets sent to the AI.
    """
    memory_dir = get_memory_dir(persona_name)
    path = memory_dir / "balances.jsonl"
    archive_path = memory_dir / "balances-archive.jsonl"

    if not path.exists():
        return 0

    cutoff = datetime.now(timezone.utc).timestamp() - (keep_days * 86400)
    keep: list[str] = []
    archive: list[str] = []

    with FileLock(_lock_path(persona_name), timeout=30):
        with open(path, "r") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    snap = json.loads(stripped)
                    ts = datetime.fromisoformat(snap["ts"]).timestamp()
                    if ts < cutoff:
                        archive.append(stripped)
                    else:
                        keep.append(stripped)
                except (json.JSONDecodeError, KeyError, ValueError):
                    keep.append(stripped)  # keep unparseable lines

        if not archive:
            return 0

        # Append to archive file
        with open(archive_path, "a") as f:
            for line in archive:
                f.write(line + "\n")

        # Rewrite active file with only recent entries
        with open(path, "w") as f:
            for line in keep:
                f.write(line + "\n")

    return len(archive)
