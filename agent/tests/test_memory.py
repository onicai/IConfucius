"""Tests for iconfucius.memory — Markdown-first memory store."""

import iconfucius.config as cfg
from iconfucius.memory import (
    append_trade,
    get_memory_dir,
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
        assert read_trades("test-persona") == ""

    def test_append_and_read(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        append_trade("test-persona", "## 2026-02-17 — BUY 29m8\n- Amount: 1000 sats")
        result = read_trades("test-persona")
        assert "BUY 29m8" in result

    def test_read_last_n(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        for i in range(5):
            append_trade("test-persona", f"## Trade {i}\n- Details for trade {i}")
        result = read_trades("test-persona", last_n=2)
        assert "Trade 3" in result
        assert "Trade 4" in result
        assert "Trade 0" not in result

    def test_creates_header_on_first_trade(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        append_trade("test-persona", "## First trade\n- Details")
        content = (tmp_path / ".memory" / "test-persona" / "trades.md").read_text()
        assert content.startswith("# Trade Log")


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
