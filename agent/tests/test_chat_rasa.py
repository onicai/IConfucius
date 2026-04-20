"""Tests for iconfucius.cli.chat_rasa — SSE client + Rasa subprocess manager."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from iconfucius.cli.chat_rasa import (
    _find_rasa_dir,
    _send_sse_message,
    _sse_stream,
    _start_rasa_server,
    _wait_for_rasa_ready,
)


# ------------------------------------------------------------------
# _find_rasa_dir
# ------------------------------------------------------------------

class TestFindRasaDir:
    """Tests for Rasa project directory discovery."""

    def _patch_pkg_paths(self, monkeypatch, tmp_path):
        """Patch module-level candidate paths so only cwd-based ones are live."""
        bogus = tmp_path / "nonexistent"
        monkeypatch.setattr("iconfucius.cli.chat_rasa._RASA_DIR_PKG", bogus)
        monkeypatch.setattr("iconfucius.cli.chat_rasa._RASA_DIR_DEV", bogus)

    def test_finds_cwd_rasa(self, tmp_path, monkeypatch):
        """Finds rasa/ under cwd when endpoints.yml exists."""
        self._patch_pkg_paths(monkeypatch, tmp_path)
        rasa_dir = tmp_path / "rasa"
        rasa_dir.mkdir()
        (rasa_dir / "endpoints.yml").write_text("action_endpoint:")
        monkeypatch.chdir(tmp_path)

        result = _find_rasa_dir()
        assert result == rasa_dir

    def test_finds_agent_rasa(self, tmp_path, monkeypatch):
        """Finds agent/rasa/ under cwd."""
        self._patch_pkg_paths(monkeypatch, tmp_path)
        rasa_dir = tmp_path / "agent" / "rasa"
        rasa_dir.mkdir(parents=True)
        (rasa_dir / "endpoints.yml").write_text("action_endpoint:")
        monkeypatch.chdir(tmp_path)

        result = _find_rasa_dir()
        assert result == rasa_dir

    def test_raises_when_not_found(self, tmp_path, monkeypatch):
        """Raises FileNotFoundError when no rasa dir has endpoints.yml."""
        self._patch_pkg_paths(monkeypatch, tmp_path)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError, match="Cannot find Rasa project"):
            _find_rasa_dir()

    def test_ignores_dir_without_endpoints(self, tmp_path, monkeypatch):
        """A rasa/ dir without endpoints.yml is skipped."""
        self._patch_pkg_paths(monkeypatch, tmp_path)
        rasa_dir = tmp_path / "rasa"
        rasa_dir.mkdir()
        # No endpoints.yml
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError):
            _find_rasa_dir()


# ------------------------------------------------------------------
# _start_rasa_server
# ------------------------------------------------------------------

class TestStartRasaServer:
    """Tests for Rasa subprocess launching."""

    @patch("subprocess.Popen")
    def test_command_and_env(self, mock_popen, tmp_path):
        """Verify the subprocess command and environment variables."""
        mock_popen.return_value = MagicMock()

        _start_rasa_server(
            rasa_dir=tmp_path,
            port=5005,
            mcp_url="http://127.0.0.1:5138/mcp",
            llm_provider="anthropic",
            llm_model="claude-opus-4-6",
            reph_provider="anthropic",
            reph_model="claude-sonnet-4-6",
            sub_provider="openai",
            sub_model="gpt-4o",
            debug=False,
        )

        mock_popen.assert_called_once()
        call_kwargs = mock_popen.call_args
        cmd = call_kwargs[0][0]

        assert cmd[:3] == ["rasa", "run", "--enable-api"]
        assert "--port" in cmd
        assert "5005" in cmd
        assert "--credentials" in cmd
        assert "--endpoints" in cmd
        assert "--debug" not in cmd

        env = call_kwargs[1]["env"]
        assert env["ICONFUCIUS_MCP_URL"] == "http://127.0.0.1:5138/mcp"
        assert env["RASA_LLM_PROVIDER"] == "anthropic"
        assert env["RASA_LLM_MODEL"] == "claude-opus-4-6"
        assert env["RASA_REPHRASER_PROVIDER"] == "anthropic"
        assert env["RASA_REPHRASER_MODEL"] == "claude-sonnet-4-6"
        assert env["RASA_SUBAGENT_PROVIDER"] == "openai"
        assert env["RASA_SUBAGENT_MODEL"] == "gpt-4o"
        assert env["LOG_LEVEL"] == "ERROR"

    @patch("subprocess.Popen")
    def test_debug_mode(self, mock_popen, tmp_path, monkeypatch):
        """Debug mode adds --debug flag and doesn't set LOG_LEVEL."""
        # _start_rasa_server copies os.environ, so inherited log-level vars
        # would leak into the assertion. Clear them explicitly.
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("SANIC_LOG_LEVEL", raising=False)
        mock_popen.return_value = MagicMock()

        _start_rasa_server(
            rasa_dir=tmp_path, port=5005,
            mcp_url="http://127.0.0.1:5138/mcp",
            llm_provider="a", llm_model="b",
            reph_provider="c", reph_model="d",
            sub_provider="e", sub_model="f",
            debug=True,
        )

        cmd = mock_popen.call_args[0][0]
        assert "--debug" in cmd

        env = mock_popen.call_args[1]["env"]
        assert "LOG_LEVEL" not in env

    @patch("subprocess.Popen")
    def test_debug_mode_stdout(self, mock_popen, tmp_path):
        """Debug mode passes stdout/stderr to terminal (None)."""
        mock_popen.return_value = MagicMock()

        _start_rasa_server(
            rasa_dir=tmp_path, port=5005,
            mcp_url="http://127.0.0.1:5138/mcp",
            llm_provider="a", llm_model="b",
            reph_provider="c", reph_model="d",
            sub_provider="e", sub_model="f",
            debug=True,
        )

        kwargs = mock_popen.call_args[1]
        assert kwargs["stdout"] is None
        assert kwargs["stderr"] is None

    @patch("subprocess.Popen")
    def test_non_debug_pipes_output(self, mock_popen, tmp_path):
        """Non-debug mode captures stdout/stderr via PIPE."""
        mock_popen.return_value = MagicMock()

        _start_rasa_server(
            rasa_dir=tmp_path, port=5005,
            mcp_url="http://127.0.0.1:5138/mcp",
            llm_provider="a", llm_model="b",
            reph_provider="c", reph_model="d",
            sub_provider="e", sub_model="f",
            debug=False,
        )

        kwargs = mock_popen.call_args[1]
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.PIPE

    @patch("subprocess.Popen")
    def test_cwd_is_rasa_dir(self, mock_popen, tmp_path):
        """Subprocess cwd is set to the rasa directory."""
        mock_popen.return_value = MagicMock()

        _start_rasa_server(
            rasa_dir=tmp_path, port=9999,
            mcp_url="http://127.0.0.1:5138/mcp",
            llm_provider="a", llm_model="b",
            reph_provider="c", reph_model="d",
            sub_provider="e", sub_model="f",
            debug=False,
        )

        assert mock_popen.call_args[1]["cwd"] == str(tmp_path)

    @patch("subprocess.Popen")
    def test_subagent_tool_timeout_from_env(self, mock_popen, tmp_path, monkeypatch):
        """RASA_SUBAGENT_TOOL_TIMEOUT is forwarded from env."""
        monkeypatch.setenv("RASA_SUBAGENT_TOOL_TIMEOUT", "300")
        mock_popen.return_value = MagicMock()

        _start_rasa_server(
            rasa_dir=tmp_path, port=5005,
            mcp_url="http://127.0.0.1:5138/mcp",
            llm_provider="a", llm_model="b",
            reph_provider="c", reph_model="d",
            sub_provider="e", sub_model="f",
            debug=False,
        )

        env = mock_popen.call_args[1]["env"]
        assert env["RASA_SUBAGENT_TOOL_TIMEOUT"] == "300"


# ------------------------------------------------------------------
# _wait_for_rasa_ready
# ------------------------------------------------------------------

class TestWaitForRasaReady:
    """Tests for Rasa server health check polling."""

    @pytest.mark.asyncio
    async def test_ready_immediately(self):
        """Returns immediately when health check succeeds."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("iconfucius.cli.chat_rasa.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _wait_for_rasa_ready("http://127.0.0.1:5005")

        mock_client.get.assert_called_with("http://127.0.0.1:5005/webhooks/sse/")

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        """Raises RuntimeError when server never becomes ready."""
        with patch("iconfucius.cli.chat_rasa.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RuntimeError, match="not ready after 0s"):
                await _wait_for_rasa_ready(
                    "http://127.0.0.1:5005", timeout=0, interval=0.01,
                )

    @pytest.mark.asyncio
    async def test_retries_on_connect_error(self):
        """Polls past ConnectError until success."""
        mock_fail = MagicMock()
        mock_fail.status_code = 500

        mock_ok = MagicMock()
        mock_ok.status_code = 200

        with patch("iconfucius.cli.chat_rasa.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[
                    httpx.ConnectError("refused"),
                    httpx.ConnectError("refused"),
                    mock_ok,
                ]
            )
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _wait_for_rasa_ready(
                "http://127.0.0.1:5005", timeout=10, interval=0.01,
            )

        assert mock_client.get.call_count == 3


# ------------------------------------------------------------------
# _sse_stream
# ------------------------------------------------------------------

def _make_sse_client(sse_lines):
    """Create a mock httpx.AsyncClient whose .stream() yields the given SSE lines."""
    async def mock_aiter_lines():
        for line in sse_lines:
            yield line

    mock_response = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_response)
    ctx.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=ctx)
    return mock_client


class TestSseStream:
    """Tests for the async SSE event parser."""

    @pytest.mark.asyncio
    async def test_parses_bot_uttered(self):
        """Yields bot_uttered events with text."""
        client = _make_sse_client([
            "event: bot_uttered",
            'data: {"text": "Hello from Rasa"}',
            "",
        ])

        events = [e async for e in _sse_stream(client, "http://x/webhook", "s1", "hi")]

        assert len(events) == 1
        assert events[0]["type"] == "bot_uttered"
        assert events[0]["text"] == "Hello from Rasa"

    @pytest.mark.asyncio
    async def test_parses_tool_status(self):
        """Yields tool_status from custom events."""
        client = _make_sse_client([
            "event: custom",
            'data: {"type": "tool_status", "text": "Checking price..."}',
            "",
        ])

        events = [e async for e in _sse_stream(client, "http://x/webhook", "s1", "hi")]

        assert len(events) == 1
        assert events[0]["type"] == "tool_status"
        assert events[0]["text"] == "Checking price..."

    @pytest.mark.asyncio
    async def test_mixed_events(self):
        """Handles interleaved bot_uttered and custom events."""
        client = _make_sse_client([
            "event: custom",
            'data: {"type": "tool_status", "text": "Looking up..."}',
            "",
            "event: bot_uttered",
            'data: {"text": "The price is 42 sats."}',
            "",
        ])

        events = [e async for e in _sse_stream(client, "http://x/webhook", "s1", "hi")]

        assert len(events) == 2
        assert events[0]["type"] == "tool_status"
        assert events[1]["type"] == "bot_uttered"
        assert events[1]["text"] == "The price is 42 sats."

    @pytest.mark.asyncio
    async def test_ignores_custom_non_tool_status(self):
        """Custom events without type=tool_status are ignored."""
        client = _make_sse_client([
            "event: custom",
            'data: {"type": "other_thing", "value": 42}',
            "",
        ])

        events = [e async for e in _sse_stream(client, "http://x/webhook", "s1", "hi")]
        assert events == []

    @pytest.mark.asyncio
    async def test_ignores_unknown_event_types(self):
        """Unknown SSE event types are silently skipped."""
        client = _make_sse_client([
            "event: unknown_type",
            'data: {"text": "should be ignored"}',
            "",
            "event: bot_uttered",
            'data: {"text": "kept"}',
            "",
        ])

        events = [e async for e in _sse_stream(client, "http://x/webhook", "s1", "hi")]

        assert len(events) == 1
        assert events[0]["text"] == "kept"

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        """Empty stream yields no events."""
        client = _make_sse_client([])

        events = [e async for e in _sse_stream(client, "http://x/webhook", "s1", "hi")]
        assert events == []

    @pytest.mark.asyncio
    async def test_posts_correct_payload(self):
        """Verifies the POST body sent to the SSE endpoint."""
        client = _make_sse_client([])

        _ = [e async for e in _sse_stream(client, "http://x/webhook", "sender-42", "hello world")]

        client.stream.assert_called_once_with(
            "POST", "http://x/webhook",
            json={"message": "hello world", "sender_id": "sender-42"},
        )


# ------------------------------------------------------------------
# _send_sse_message
# ------------------------------------------------------------------

class TestSendSseMessage:
    """Tests for the high-level SSE message sender."""

    @pytest.mark.asyncio
    async def test_collects_bot_responses(self):
        """Collects all bot_uttered text responses."""
        async def fake_stream(*args, **kwargs):
            yield {"type": "bot_uttered", "text": "Response 1"}
            yield {"type": "tool_status", "text": "Working..."}
            yield {"type": "bot_uttered", "text": "Response 2"}

        with patch("iconfucius.cli.chat_rasa._sse_stream", side_effect=fake_stream):
            with patch("iconfucius.cli.chat_rasa._Spinner"):
                client = AsyncMock()
                result = await _send_sse_message(
                    client, "http://x/webhook", "s1", "hi",
                )

        assert result == ["Response 1", "Response 2"]

    @pytest.mark.asyncio
    async def test_skips_empty_text(self):
        """bot_uttered events without text are not collected."""
        async def fake_stream(*args, **kwargs):
            yield {"type": "bot_uttered", "text": ""}
            yield {"type": "bot_uttered"}
            yield {"type": "bot_uttered", "text": "Real response"}

        with patch("iconfucius.cli.chat_rasa._sse_stream", side_effect=fake_stream):
            with patch("iconfucius.cli.chat_rasa._Spinner"):
                client = AsyncMock()
                result = await _send_sse_message(
                    client, "http://x/webhook", "s1", "hi",
                )

        assert result == ["Real response"]

    @pytest.mark.asyncio
    async def test_spinner_updates_on_tool_status(self):
        """Spinner is updated with tool_status text."""
        async def fake_stream(*args, **kwargs):
            yield {"type": "tool_status", "text": "Checking wallet..."}
            yield {"type": "tool_status", "text": "Checking price..."}
            yield {"type": "bot_uttered", "text": "Done"}

        mock_spinner = MagicMock()
        mock_spinner.__enter__ = MagicMock(return_value=mock_spinner)
        mock_spinner.__exit__ = MagicMock(return_value=False)

        with patch("iconfucius.cli.chat_rasa._sse_stream", side_effect=fake_stream):
            with patch("iconfucius.cli.chat_rasa._Spinner", return_value=mock_spinner):
                client = AsyncMock()
                await _send_sse_message(
                    client, "http://x/webhook", "s1", "hi",
                    spinner_label="Thinking...",
                )

        assert mock_spinner.update.call_count == 2
        mock_spinner.update.assert_any_call("Checking wallet...")
        mock_spinner.update.assert_any_call("Checking price...")

    @pytest.mark.asyncio
    async def test_empty_stream_returns_empty_list(self):
        """No events yields empty response list."""
        async def fake_stream(*args, **kwargs):
            return
            yield  # make it a generator

        with patch("iconfucius.cli.chat_rasa._sse_stream", side_effect=fake_stream):
            with patch("iconfucius.cli.chat_rasa._Spinner"):
                client = AsyncMock()
                result = await _send_sse_message(
                    client, "http://x/webhook", "s1", "hi",
                )

        assert result == []
