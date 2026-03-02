"""Tests for iconfucius ui command and client.server module."""

import json
import os
import re
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

from iconfucius.cli import app
from iconfucius.client.server import (
    _resolve_static,
    _save_resume_snapshot,
    _read_resume_file,
    _STATIC_DIR,
    UIHandler,
    run_server,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# CLI: iconfucius ui
# ---------------------------------------------------------------------------

class TestUiCommand:
    def test_ui_help(self):
        """Verify 'iconfucius ui --help' shows expected options."""
        result = runner.invoke(app, ["ui", "--help"])
        assert result.exit_code == 0
        output = _ANSI_RE.sub("", result.output)
        assert "Launch the web UI" in output
        assert "--port" in output
        assert "--no-browser" in output

    def test_ui_listed_in_main_help(self):
        """Verify 'ui' appears in the top-level help output."""
        result = runner.invoke(app, ["--help"])
        assert "ui" in result.output

    def test_ui_default_port(self):
        """Verify default port is 55129."""
        result = runner.invoke(app, ["ui", "--help"])
        assert "55129" in result.output

    @patch("iconfucius.client.server.run_server")
    def test_ui_calls_run_server_defaults(self, mock_run):
        """Verify 'iconfucius ui' calls run_server with default args."""
        result = runner.invoke(app, ["ui"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(port=55129, open_browser=True)

    @patch("iconfucius.client.server.run_server")
    def test_ui_custom_port(self, mock_run):
        """Verify --port is forwarded to run_server."""
        result = runner.invoke(app, ["ui", "--port", "8080"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(port=8080, open_browser=True)

    @patch("iconfucius.client.server.run_server")
    def test_ui_no_browser(self, mock_run):
        """Verify --no-browser sets open_browser=False."""
        result = runner.invoke(app, ["ui", "--no-browser"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(port=55129, open_browser=False)

    @patch("iconfucius.client.server.run_server")
    def test_ui_combined_options(self, mock_run):
        """Verify --port and --no-browser work together."""
        result = runner.invoke(app, ["ui", "-p", "9999", "--no-browser"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(port=9999, open_browser=False)


# ---------------------------------------------------------------------------
# _resolve_static
# ---------------------------------------------------------------------------

class TestResolveStatic:
    @pytest.fixture()
    def static_dir(self, tmp_path, monkeypatch):
        """Create a temporary static directory with test files."""
        static = tmp_path / "static"
        static.mkdir()
        (static / "index.html").write_text("<html>hi</html>")
        (static / "app.js").write_text("console.log('hi')")
        assets = static / "assets"
        assets.mkdir()
        (assets / "style.css").write_text("body{}")
        monkeypatch.setattr(
            "iconfucius.client.server._STATIC_DIR", static
        )
        return static

    def test_root_resolves_to_index(self, static_dir):  # noqa: ARG002
        """GET / should resolve to index.html."""
        result = _resolve_static("/")
        assert result is not None
        assert result.name == "index.html"

    def test_empty_path_resolves_to_index(self, static_dir):  # noqa: ARG002
        """Empty path should resolve to index.html."""
        result = _resolve_static("")
        assert result is not None
        assert result.name == "index.html"

    def test_existing_file(self, static_dir):  # noqa: ARG002
        """Known file path should resolve to that file."""
        result = _resolve_static("/app.js")
        assert result is not None
        assert result.name == "app.js"

    def test_nested_file(self, static_dir):  # noqa: ARG002
        """Nested file path should resolve correctly."""
        result = _resolve_static("/assets/style.css")
        assert result is not None
        assert result.name == "style.css"

    def test_spa_fallback(self, static_dir):  # noqa: ARG002
        """Unknown path should fall back to index.html (SPA routing)."""
        result = _resolve_static("/wallet")
        assert result is not None
        assert result.name == "index.html"

    def test_spa_fallback_nested(self, static_dir):  # noqa: ARG002
        """Deeply nested unknown path should fall back to index.html."""
        result = _resolve_static("/some/deep/route")
        assert result is not None
        assert result.name == "index.html"

    def test_directory_traversal_blocked(self, static_dir):  # noqa: ARG002
        """Directory traversal attempts must return None."""
        result = _resolve_static("/../../../etc/passwd")
        assert result is None

    def test_no_static_dir(self, tmp_path, monkeypatch):
        """Returns None when static directory doesn't exist."""
        monkeypatch.setattr(
            "iconfucius.client.server._STATIC_DIR",
            tmp_path / "nonexistent",
        )
        result = _resolve_static("/")
        assert result is None

    def test_no_index_html(self, tmp_path, monkeypatch):
        """Returns None for SPA fallback when index.html is missing."""
        static = tmp_path / "static"
        static.mkdir()
        (static / "app.js").write_text("x")
        monkeypatch.setattr("iconfucius.client.server._STATIC_DIR", static)
        # Existing file still works
        assert _resolve_static("/app.js") is not None
        # SPA fallback returns None (no index.html)
        assert _resolve_static("/unknown") is None


# ---------------------------------------------------------------------------
# run_server
# ---------------------------------------------------------------------------

class TestRunServer:
    @patch("iconfucius.client.server.ThreadingHTTPServer")
    @patch("iconfucius.client.server.threading.Timer")
    @patch("iconfucius.client.server.webbrowser")
    @patch("iconfucius.client.server._warm_cache")
    def test_run_server_opens_browser(
        self, _mock_cache, mock_wb, mock_timer, mock_srv
    ):
        """Verify run_server opens browser when open_browser=True."""
        mock_instance = MagicMock()
        mock_srv.return_value = mock_instance
        mock_instance.serve_forever.side_effect = KeyboardInterrupt

        run_server(port=55199, open_browser=True)

        mock_srv.assert_called_once_with(("127.0.0.1", 55199), UIHandler)
        mock_instance.serve_forever.assert_called_once()
        mock_instance.server_close.assert_called_once()
        mock_timer.assert_called_once_with(
            0.5, mock_wb.open, args=("http://localhost:55199",)
        )

    @patch("iconfucius.client.server.ThreadingHTTPServer")
    @patch("iconfucius.client.server.threading.Timer")
    @patch("iconfucius.client.server.webbrowser")
    @patch("iconfucius.client.server._warm_cache")
    def test_run_server_no_browser(
        self, _mock_cache, _mock_wb, mock_timer, mock_srv
    ):
        """Verify run_server skips browser when open_browser=False."""
        mock_instance = MagicMock()
        mock_srv.return_value = mock_instance
        mock_instance.serve_forever.side_effect = KeyboardInterrupt

        run_server(port=55199, open_browser=False)

        # Timer should not be created when browser is disabled
        mock_timer.assert_not_called()

    @patch("iconfucius.client.server.ThreadingHTTPServer")
    @patch("iconfucius.client.server.webbrowser")
    @patch("iconfucius.client.server._warm_cache")
    def test_run_server_port_in_use(self, _mock_cache, _mock_wb, mock_srv, capsys):
        """Verify port-in-use gives a helpful error and exits."""
        mock_srv.side_effect = OSError("Address already in use")

        with pytest.raises(SystemExit) as exc_info:
            run_server(port=55129)
        assert exc_info.value.code == 1

        output = capsys.readouterr().out
        assert "Port 55129 is already in use" in output
        assert "Another iconfucius ui is probably running" in output
        assert "--port 55130" in output
        assert "Each project folder needs its own port" in output

    @patch("iconfucius.client.server.ThreadingHTTPServer")
    @patch("iconfucius.client.server.webbrowser")
    @patch("iconfucius.client.server._warm_cache")
    def test_run_server_other_oserror_propagates(self, _mock_cache, _mock_wb, mock_srv):
        """Verify non-port OSErrors are re-raised, not swallowed."""
        mock_srv.side_effect = OSError("Permission denied")

        with pytest.raises(OSError, match="Permission denied"):
            run_server(port=55129)


# ---------------------------------------------------------------------------
# Module import & structure
# ---------------------------------------------------------------------------

class TestModuleStructure:
    def test_client_package_importable(self):
        """Verify iconfucius.client is a proper Python package."""
        import iconfucius.client
        assert hasattr(iconfucius.client, "__doc__")

    def test_server_module_importable(self):
        """Verify iconfucius.client.server imports without error."""
        from iconfucius.client import server
        assert hasattr(server, "run_server")
        assert hasattr(server, "UIHandler")

    def test_handler_is_renamed(self):
        """Verify the handler class is UIHandler, not the old names."""
        from iconfucius.client import server
        assert hasattr(server, "UIHandler")
        assert not hasattr(server, "ProxyHandler")
        assert not hasattr(server, "DashboardHandler")


# ---------------------------------------------------------------------------
# _save_resume_snapshot
# ---------------------------------------------------------------------------

class TestSaveResumeSnapshot:
    def _make_session(self, tmp_path):
        """Create a minimal session dict with a ConversationLogger."""
        from iconfucius.conversation_log import ConversationLogger
        conv_logger = ConversationLogger(stamp="test-resume", base_dir=tmp_path)
        return {
            "messages": [],
            "conv_logger": conv_logger,
        }

    def test_writes_incremental_messages(self, tmp_path):
        """First snapshot writes all messages, second writes only new ones."""
        session = self._make_session(tmp_path)
        session["messages"] = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        _save_resume_snapshot(session)

        session["messages"].append({"role": "user", "content": "how are you?"})
        session["messages"].append({"role": "assistant", "content": "fine"})
        _save_resume_snapshot(session)

        path = session["conv_logger"].path_resume
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert len(first["new_messages"]) == 2
        assert first["new_messages"][0]["content"] == "hello"

        second = json.loads(lines[1])
        assert len(second["new_messages"]) == 2
        assert second["new_messages"][0]["content"] == "how are you?"

        session["conv_logger"].close()

    def test_no_op_when_no_new_messages(self, tmp_path):
        """Snapshot with no new messages writes nothing."""
        session = self._make_session(tmp_path)
        session["messages"] = [{"role": "user", "content": "hello"}]
        _save_resume_snapshot(session)

        # Call again with no changes
        _save_resume_snapshot(session)

        path = session["conv_logger"].path_resume
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        session["conv_logger"].close()

    def test_no_op_without_conv_logger(self):
        """Snapshot does nothing if session has no conv_logger."""
        session = {"messages": [{"role": "user", "content": "hi"}]}
        _save_resume_snapshot(session)  # should not raise

    def test_tracks_resume_msg_count(self, tmp_path):
        """Verify _resume_msg_count is updated after each snapshot."""
        session = self._make_session(tmp_path)
        session["messages"] = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        _save_resume_snapshot(session)
        assert session["_resume_msg_count"] == 2

        session["messages"].append({"role": "user", "content": "c"})
        _save_resume_snapshot(session)
        assert session["_resume_msg_count"] == 3
        session["conv_logger"].close()


# ---------------------------------------------------------------------------
# _read_resume_file
# ---------------------------------------------------------------------------

class TestReadResumeFile:
    def test_reads_concatenated_messages(self, tmp_path):
        """Read a resume file with multiple incremental lines."""
        path = tmp_path / "test-ai-for-resume.jsonl"
        line1 = json.dumps({"new_messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "balance", "input": {}},
            ]},
        ]})
        line2 = json.dumps({"new_messages": [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "100"},
            ]},
            {"role": "assistant", "content": "You have 100 sats."},
        ]})
        path.write_text(line1 + "\n" + line2 + "\n")

        api_messages, display = _read_resume_file(path)

        assert len(api_messages) == 4
        assert api_messages[0] == {"role": "user", "content": "hello"}
        assert api_messages[3] == {"role": "assistant", "content": "You have 100 sats."}

        # Display should only include user/assistant with string content
        assert len(display) == 2
        assert display[0] == {"role": "user", "text": "hello"}
        assert display[1] == {"role": "assistant", "text": "You have 100 sats."}

    def test_empty_file_returns_empty(self, tmp_path):
        """Empty resume file returns empty lists."""
        path = tmp_path / "empty-ai-for-resume.jsonl"
        path.write_text("")
        api_messages, display = _read_resume_file(path)
        assert api_messages == []
        assert display == []

    def test_skips_blank_lines(self, tmp_path):
        """Blank lines in the resume file are skipped."""
        path = tmp_path / "test-ai-for-resume.jsonl"
        line = json.dumps({"new_messages": [
            {"role": "user", "content": "hi"},
        ]})
        path.write_text("\n" + line + "\n\n")
        api_messages, display = _read_resume_file(path)
        assert len(api_messages) == 1
        assert len(display) == 1

    def test_tool_use_messages_excluded_from_display(self, tmp_path):
        """Messages with list content (tool_use/tool_result) not in display."""
        path = tmp_path / "test-ai-for-resume.jsonl"
        line = json.dumps({"new_messages": [
            {"role": "user", "content": "check balance"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "balance", "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "50000"},
            ]},
            {"role": "assistant", "content": "Your balance is 50000 sats."},
        ]})
        path.write_text(line + "\n")

        api_messages, display = _read_resume_file(path)
        assert len(api_messages) == 4
        assert len(display) == 2
        assert display[0]["text"] == "check balance"
        assert display[1]["text"] == "Your balance is 50000 sats."

    def test_roundtrip_snapshot_then_read(self, tmp_path):
        """Snapshot + read roundtrip produces correct api_messages."""
        from iconfucius.conversation_log import ConversationLogger
        conv_logger = ConversationLogger(stamp="rt-test", base_dir=tmp_path)
        session = {"messages": [], "conv_logger": conv_logger}

        # Simulate a conversation with tool calls
        session["messages"] = [
            {"role": "user", "content": "what's my balance?"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Let me check."},
                {"type": "tool_use", "id": "tu_1", "name": "wallet_balance", "input": {}},
            ]},
        ]
        _save_resume_snapshot(session)

        session["messages"].extend([
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": '{"sats": 1000}'},
            ]},
            {"role": "assistant", "content": "You have 1000 sats."},
        ])
        _save_resume_snapshot(session)
        conv_logger.close()

        api_messages, display = _read_resume_file(conv_logger.path_resume)

        # All 4 messages should be present
        assert len(api_messages) == 4
        assert api_messages[0]["role"] == "user"
        assert api_messages[0]["content"] == "what's my balance?"
        assert api_messages[1]["role"] == "assistant"
        assert isinstance(api_messages[1]["content"], list)  # tool_use content
        assert api_messages[3]["content"] == "You have 1000 sats."

        # Display: only string-content user/assistant messages
        assert len(display) == 2
        assert display[0]["text"] == "what's my balance?"
        assert display[1]["text"] == "You have 1000 sats."
