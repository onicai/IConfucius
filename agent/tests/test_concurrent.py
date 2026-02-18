"""Tests for iconfucius.cli.concurrent — run_per_bot() helper."""

import time

import pytest

from iconfucius.cli.concurrent import run_per_bot


class TestRunPerBot:
    """Tests for the run_per_bot() concurrent helper."""

    def test_returns_results_in_order(self):
        """Results preserve original bot_names order."""
        results = run_per_bot(str.upper, ["bot-3", "bot-1", "bot-2"])
        assert results == [
            ("bot-3", "BOT-3"),
            ("bot-1", "BOT-1"),
            ("bot-2", "BOT-2"),
        ]

    def test_handles_exceptions(self):
        """Per-bot exceptions are caught; other bots still succeed."""
        def _maybe_fail(name):
            if name == "bot-2":
                raise ValueError("boom")
            return f"ok-{name}"

        results = run_per_bot(_maybe_fail, ["bot-1", "bot-2", "bot-3"])

        assert results[0] == ("bot-1", "ok-bot-1")
        assert results[0][0] == "bot-1"

        assert results[1][0] == "bot-2"
        assert isinstance(results[1][1], ValueError)
        assert str(results[1][1]) == "boom"

        assert results[2] == ("bot-3", "ok-bot-3")

    def test_single_bot(self):
        """Works with a single-element list."""
        results = run_per_bot(lambda n: n * 2, ["only"])
        assert results == [("only", "onlyonly")]

    def test_empty_list(self):
        """Returns empty list for empty bot_names."""
        results = run_per_bot(lambda n: n, [])
        assert results == []

    def test_runs_concurrently(self):
        """Multiple bots run concurrently (not sequentially).

        Each bot sleeps 0.2s. With 3 bots running concurrently, total
        time should be ~0.2s, not ~0.6s.
        """
        def _sleep(name):
            time.sleep(0.2)
            return name

        start = time.monotonic()
        results = run_per_bot(_sleep, ["a", "b", "c"], max_workers=3)
        elapsed = time.monotonic() - start

        assert len(results) == 3
        # Should complete in well under 0.6s (sequential would take 0.6s)
        assert elapsed < 0.5

    def test_max_workers_limits_concurrency(self):
        """max_workers=1 forces sequential execution."""
        order = []

        def _track(name):
            order.append(f"start-{name}")
            time.sleep(0.05)
            order.append(f"end-{name}")
            return name

        results = run_per_bot(_track, ["a", "b"], max_workers=1)
        assert len(results) == 2
        # With max_workers=1, operations run sequentially
        assert order == ["start-a", "end-a", "start-b", "end-b"]

    def test_all_fail(self):
        """All bots failing returns all exceptions."""
        def _fail(name):
            raise RuntimeError(f"fail-{name}")

        results = run_per_bot(_fail, ["bot-1", "bot-2"])
        for name, result in results:
            assert isinstance(result, RuntimeError)
            assert f"fail-{name}" in str(result)

    def test_return_types_preserved(self):
        """Complex return values (dicts, lists) are preserved."""
        def _complex(name):
            return {"name": name, "items": [1, 2, 3]}

        results = run_per_bot(_complex, ["bot-1"])
        assert results[0][1] == {"name": "bot-1", "items": [1, 2, 3]}
