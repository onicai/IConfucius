"""Tests for iconfucius.memory — Markdown-first memory store."""

import json
from datetime import datetime, timezone, timedelta

import iconfucius.config as cfg
from iconfucius.memory import (
    append_balance_snapshot,
    append_trade,
    archive_balance_snapshots,
    get_memory_dir,
    migrate_trades_md_to_jsonl,
    read_balance_snapshots,
    read_learnings,
    read_strategy,
    read_trades,
    write_learnings,
    write_strategy,
)


class TestMemoryDir:
    def test_creates_memory_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        d = get_memory_dir("test-persona")
        assert d.exists()
        assert d == tmp_path / ".memory" / "test-persona"

    def test_idempotent_creation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        d1 = get_memory_dir("test-persona")
        d2 = get_memory_dir("test-persona")
        assert d1 == d2


class TestTrades:
    def test_read_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        assert read_trades("test-persona") == []

    def test_append_and_read(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        trade = {"ts": "2026-02-17T21:00:00+00:00", "action": "BUY", "token_id": "29m8", "amount_sats": 1000}
        append_trade("test-persona", trade)
        result = read_trades("test-persona")
        assert len(result) == 1
        assert result[0]["token_id"] == "29m8"
        assert result[0]["amount_sats"] == 1000

    def test_read_last_n(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        for i in range(5):
            append_trade("test-persona", {"ts": f"2026-02-1{i}T00:00:00+00:00", "action": "BUY", "index": i})
        result = read_trades("test-persona", last_n=2)
        assert len(result) == 2
        assert result[0]["index"] == 3
        assert result[1]["index"] == 4

    def test_migrate_trades_md_to_jsonl(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        # Write a trades.md with two entries
        memory_dir = tmp_path / ".memory" / "test-persona"
        memory_dir.mkdir(parents=True)
        md_content = (
            "# Trade Log\n"
            "\n"
            "## BUY — 2026-02-18 21:12 UTC\n"
            "- Token: 29m8 (ICONFUCIUS)\n"
            "- Spent: 7,555 sats ($7.290)\n"
            "- Est. tokens: ~4,683,818.970\n"
            "- Price: 1,613 sats/token ($0.016)\n"
            "- Bots: bot-45\n"
            "\n"
            "## SELL — 2026-02-19 10:30 UTC\n"
            "- Token: 29m8 (ICONFUCIUS)\n"
            "- Sold: ALL tokens\n"
            "- Price: 2,000 sats/token ($0.020)\n"
            "- Bots: bot-45, bot-46\n"
        )
        (memory_dir / "trades.md").write_text(md_content)

        # read_trades auto-migrates
        result = read_trades("test-persona")
        assert len(result) == 2
        assert not (memory_dir / "trades.md").exists()
        assert (memory_dir / "trades.jsonl").exists()

        # Verify parsed fields
        buy = result[0]
        assert buy["action"] == "BUY"
        assert buy["token_id"] == "29m8"
        assert buy["ticker"] == "ICONFUCIUS"
        assert buy["amount_sats"] == 7555
        assert buy["est_tokens"] == 4683818.970
        assert buy["price_sats"] == 1613
        assert buy["bots"] == ["bot-45"]

        sell = result[1]
        assert sell["action"] == "SELL"
        assert sell["tokens_sold"] == "all"
        assert sell["bots"] == ["bot-45", "bot-46"]


class TestStrategy:
    def test_read_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        assert read_strategy("test-persona") == ""

    def test_write_and_read(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        write_strategy("test-persona", "# Strategy\n\n1. Buy low, sell high")
        result = read_strategy("test-persona")
        assert "Buy low" in result


class TestLearnings:
    def test_read_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        assert read_learnings("test-persona") == ""

    def test_write_and_read(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        write_learnings("test-persona", "# Learnings\n\n## Volume spikes")
        result = read_learnings("test-persona")
        assert "Volume spikes" in result


def _make_snapshot(ts: datetime, portfolio_sats: int = 100000) -> dict:
    """Helper to create a balance snapshot dict."""
    return {
        "ts": ts.isoformat(),
        "wallet_sats": 50000,
        "odin_sats": 25000,
        "token_value_sats": 25000,
        "portfolio_sats": portfolio_sats,
        "btc_usd_rate": 96500.0,
        "portfolio_usd": round((portfolio_sats / 100_000_000) * 96500.0, 2),
        "bot_count": 3,
    }


class TestBalanceSnapshots:
    def test_read_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        assert read_balance_snapshots("test-persona") == []

    def test_append_and_read(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        snap = _make_snapshot(datetime.now(timezone.utc))
        append_balance_snapshot("test-persona", snap)
        result = read_balance_snapshots("test-persona")
        assert len(result) == 1
        assert result[0]["portfolio_sats"] == 100000

    def test_skips_within_one_hour(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        now = datetime.now(timezone.utc)
        snap1 = _make_snapshot(now - timedelta(minutes=30))
        snap2 = _make_snapshot(now)  # same portfolio_sats, within 1h
        append_balance_snapshot("test-persona", snap1)
        append_balance_snapshot("test-persona", snap2)
        result = read_balance_snapshots("test-persona")
        assert len(result) == 1  # second was skipped

    def test_records_if_portfolio_changed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        now = datetime.now(timezone.utc)
        snap1 = _make_snapshot(now - timedelta(minutes=30), portfolio_sats=100000)
        snap2 = _make_snapshot(now, portfolio_sats=120000)  # different portfolio
        append_balance_snapshot("test-persona", snap1)
        append_balance_snapshot("test-persona", snap2)
        result = read_balance_snapshots("test-persona")
        assert len(result) == 2

    def test_archive_moves_old(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        now = datetime.now(timezone.utc)
        old_snap = _make_snapshot(now - timedelta(days=100))
        new_snap = _make_snapshot(now, portfolio_sats=200000)
        append_balance_snapshot("test-persona", old_snap)
        # Force-write the new snapshot (bypass dedup since >1h apart)
        append_balance_snapshot("test-persona", new_snap)
        count = archive_balance_snapshots("test-persona", keep_days=90)
        assert count == 1
        # Active file should only have the recent entry
        remaining = read_balance_snapshots("test-persona")
        assert len(remaining) == 1
        assert remaining[0]["portfolio_sats"] == 200000

    def test_archive_keeps_recent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(now)
        append_balance_snapshot("test-persona", snap)
        count = archive_balance_snapshots("test-persona", keep_days=90)
        assert count == 0
        remaining = read_balance_snapshots("test-persona")
        assert len(remaining) == 1

    def test_archive_appends_to_existing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        now = datetime.now(timezone.utc)
        # Write two old snapshots with different timestamps & portfolio values
        snap1 = _make_snapshot(now - timedelta(days=200), portfolio_sats=80000)
        snap2 = _make_snapshot(now - timedelta(days=150), portfolio_sats=90000)
        snap3 = _make_snapshot(now, portfolio_sats=100000)
        append_balance_snapshot("test-persona", snap1)
        append_balance_snapshot("test-persona", snap2)
        append_balance_snapshot("test-persona", snap3)
        # First archive run
        count1 = archive_balance_snapshots("test-persona", keep_days=90)
        assert count1 == 2
        # Add another old entry and archive again
        memory_dir = get_memory_dir("test-persona")
        old_snap = _make_snapshot(now - timedelta(days=120), portfolio_sats=70000)
        with open(memory_dir / "balances.jsonl", "a") as f:
            f.write(json.dumps(old_snap) + "\n")
        count2 = archive_balance_snapshots("test-persona", keep_days=90)
        assert count2 == 1
        # Archive file should have all 3 archived entries
        archive_path = memory_dir / "balances-archive.jsonl"
        lines = [l for l in archive_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 3
