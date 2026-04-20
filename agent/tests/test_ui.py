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
    _find_resume_files,
    _make_stamp,
    _STATIC_DIR,
    UIHandler,
    run_server,
    _handle_setup_status,
    _handle_action_init,
    _handle_action_wallet_create,
    _handle_action_set_bots,
    _handle_wallet_info,
    _require_sdk,
    _cache_clear,
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
        assert "--network" in output
        assert "--verbose" in output
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
    def test_ui_network_option(self, mock_run):
        """Verify --network is accepted."""
        result = runner.invoke(app, ["ui", "--network", "testing"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(port=55129, open_browser=True)

    @patch("iconfucius.client.server.run_server")
    def test_ui_verbose_option(self, mock_run):
        """Verify --verbose/--quiet is accepted."""
        result = runner.invoke(app, ["ui", "--quiet"])
        assert result.exit_code == 0


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


# ---------------------------------------------------------------------------
# _make_stamp
# ---------------------------------------------------------------------------

class TestMakeStamp:
    def test_prd_no_network_suffix(self, monkeypatch):
        """prd stamps have no network suffix (backward compatible)."""
        monkeypatch.setattr("iconfucius.config.get_network", lambda: "prd")
        stamp = _make_stamp("abcdef1234567890")
        assert stamp.endswith("-web-abcdef12")
        assert "-prd" not in stamp

    def test_testing_suffix(self, monkeypatch):
        """testing stamps end with -testing."""
        monkeypatch.setattr("iconfucius.config.get_network", lambda: "testing")
        stamp = _make_stamp("abcdef1234567890")
        assert stamp.endswith("-testing")

    def test_development_suffix(self, monkeypatch):
        """development stamps end with -development."""
        monkeypatch.setattr("iconfucius.config.get_network", lambda: "development")
        stamp = _make_stamp("abcdef1234567890")
        assert stamp.endswith("-development")


# ---------------------------------------------------------------------------
# _find_resume_files
# ---------------------------------------------------------------------------

class TestFindResumeFiles:
    def test_prd_excludes_testing_and_development(self, tmp_path, monkeypatch):
        """prd filter excludes files tagged with testing or development."""
        monkeypatch.setattr("iconfucius.config.get_network", lambda: "prd")
        (tmp_path / "20260301-120000-web-aabb1122-ai-for-resume.jsonl").touch()
        (tmp_path / "20260301-130000-web-ccdd3344-testing-ai-for-resume.jsonl").touch()
        (tmp_path / "20260301-140000-web-eeff5566-development-ai-for-resume.jsonl").touch()
        result = _find_resume_files(tmp_path)
        assert len(result) == 1
        assert "aabb1122" in result[0].name

    def test_testing_only_finds_testing(self, tmp_path, monkeypatch):
        """testing filter returns only testing-tagged files."""
        monkeypatch.setattr("iconfucius.config.get_network", lambda: "testing")
        (tmp_path / "20260301-120000-web-aabb1122-ai-for-resume.jsonl").touch()
        (tmp_path / "20260301-130000-web-ccdd3344-testing-ai-for-resume.jsonl").touch()
        (tmp_path / "20260301-140000-web-eeff5566-development-ai-for-resume.jsonl").touch()
        result = _find_resume_files(tmp_path)
        assert len(result) == 1
        assert "-testing-" in result[0].name

    def test_development_only_finds_development(self, tmp_path, monkeypatch):
        """development filter returns only development-tagged files."""
        monkeypatch.setattr("iconfucius.config.get_network", lambda: "development")
        (tmp_path / "20260301-120000-web-aabb1122-ai-for-resume.jsonl").touch()
        (tmp_path / "20260301-130000-web-ccdd3344-testing-ai-for-resume.jsonl").touch()
        (tmp_path / "20260301-140000-web-eeff5566-development-ai-for-resume.jsonl").touch()
        result = _find_resume_files(tmp_path)
        assert len(result) == 1
        assert "-development-" in result[0].name

    def test_empty_directory(self, tmp_path, monkeypatch):
        """Empty directory returns empty list."""
        monkeypatch.setattr("iconfucius.config.get_network", lambda: "prd")
        result = _find_resume_files(tmp_path)
        assert result == []

    def test_no_matching_files(self, tmp_path, monkeypatch):
        """No matching files for the active network returns empty list."""
        monkeypatch.setattr("iconfucius.config.get_network", lambda: "testing")
        (tmp_path / "20260301-120000-web-aabb1122-ai-for-resume.jsonl").touch()
        result = _find_resume_files(tmp_path)
        assert result == []

    def test_files_sorted_chronologically(self, tmp_path, monkeypatch):
        """Returned files are sorted by name (timestamp-based order)."""
        monkeypatch.setattr("iconfucius.config.get_network", lambda: "prd")
        (tmp_path / "20260302-120000-web-22222222-ai-for-resume.jsonl").touch()
        (tmp_path / "20260301-120000-web-11111111-ai-for-resume.jsonl").touch()
        (tmp_path / "20260303-120000-web-33333333-ai-for-resume.jsonl").touch()
        result = _find_resume_files(tmp_path)
        assert len(result) == 3
        assert "11111111" in result[0].name
        assert "22222222" in result[1].name
        assert "33333333" in result[2].name


# ---------------------------------------------------------------------------
# _require_sdk
# ---------------------------------------------------------------------------

class TestRequireSdk:
    def test_returns_error_when_sdk_missing(self, monkeypatch):
        """Returns 503 error tuple when SDK is not available."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", False)
        result = _require_sdk()
        assert result is not None
        status, data = result
        assert status == 503
        assert "not installed" in data["error"]

    def test_returns_none_when_sdk_available(self, monkeypatch):
        """Returns None (no error) when SDK is available."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        result = _require_sdk()
        assert result is None


# ---------------------------------------------------------------------------
# _handle_setup_status
# ---------------------------------------------------------------------------

class TestHandleSetupStatus:
    def test_returns_503_without_sdk(self, monkeypatch):
        """Returns 503 when iconfucius SDK is not installed."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", False)
        status, data = _handle_setup_status()
        assert status == 503
        assert "not installed" in data["error"]

    def test_returns_status_with_sdk(self, monkeypatch):
        """Returns setup status from execute_tool when SDK is available."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        expected = {"config_exists": True, "wallet_exists": False, "ready": False, "bot_count": 0}
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: expected)
        status, data = _handle_setup_status()
        assert status == 200
        assert data == expected

    def test_returns_bot_count(self, monkeypatch):
        """Verify bot_count is included in the status response."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        expected = {"config_exists": True, "wallet_exists": True, "ready": True, "bot_count": 3}
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: expected)
        status, data = _handle_setup_status()
        assert status == 200
        assert data["bot_count"] == 3

    def test_setup_not_complete_without_bots(self, monkeypatch):
        """Setup is not complete when bot_count is 0, even if ready is True."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        expected = {"config_exists": True, "wallet_exists": True, "ready": True, "bot_count": 0}
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: expected)
        status, data = _handle_setup_status()
        assert status == 200
        assert data["ready"] is True
        assert data["bot_count"] == 0


# ---------------------------------------------------------------------------
# _handle_action_init
# ---------------------------------------------------------------------------

class TestHandleActionInit:
    def test_returns_503_without_sdk(self, monkeypatch):
        """Returns 503 when SDK is missing."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", False)
        status, data = _handle_action_init({})
        assert status == 503

    def test_init_success(self, monkeypatch, tmp_path):
        """Successful init returns 200 with result."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = {"status": "ok", "display": "Initialized with 3 bots."}
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: result)
        # Mock load_config since it's imported lazily inside the function
        monkeypatch.setattr("iconfucius.config.load_config", lambda reload=False: None)
        status, data = _handle_action_init({"num_bots": 3})
        assert status == 200
        assert data["status"] == "ok"

    def test_init_default_num_bots(self, monkeypatch, tmp_path):
        """Default num_bots is 3 when not specified."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        captured = {}
        def mock_execute(name, args):
            captured.update(args)
            return {"status": "ok"}
        monkeypatch.setattr("iconfucius.client.server.execute_tool", mock_execute)
        monkeypatch.setattr("iconfucius.config.load_config", lambda reload=False: None)
        _handle_action_init({})
        assert captured["num_bots"] == 3

    def test_init_error_but_config_exists(self, monkeypatch, tmp_path):
        """Returns 200 when init reports error but config already exists on disk."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: {"status": "error", "error": "already exists"})
        monkeypatch.setattr("iconfucius.config.find_config", lambda: str(tmp_path / "config.toml"))
        monkeypatch.setattr("iconfucius.config.load_config", lambda reload=False: None)
        status, data = _handle_action_init({})
        assert status == 200
        assert "already initialized" in data["display"].lower()


# ---------------------------------------------------------------------------
# _handle_action_wallet_create
# ---------------------------------------------------------------------------

class TestHandleActionWalletCreate:
    def test_returns_503_without_sdk(self, monkeypatch):
        """Returns 503 when SDK is missing."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", False)
        status, data = _handle_action_wallet_create({})
        assert status == 503

    def test_wallet_create_success(self, monkeypatch):
        """Successful wallet creation returns 200."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        result = {"status": "ok", "display": "Wallet created."}
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: result)
        status, data = _handle_action_wallet_create({})
        assert status == 200
        assert data["status"] == "ok"

    def test_wallet_create_error_but_exists(self, monkeypatch, tmp_path):
        """Returns 200 if wallet_create errors but PEM file exists on disk."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: {"status": "error", "error": "already exists"})
        pem_file = tmp_path / "identity-private.pem"
        pem_file.write_text("-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----")
        monkeypatch.setattr("iconfucius.config.get_pem_file", lambda: str(pem_file))
        status, data = _handle_action_wallet_create({})
        assert status == 200
        assert "already exists" in data["display"].lower()

    def test_wallet_create_real_error(self, monkeypatch):
        """Returns 400 on genuine error when PEM doesn't exist."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: {"status": "error", "error": "failed"})
        # get_pem_file raises or returns nonexistent path
        monkeypatch.setattr("iconfucius.config.get_pem_file", lambda: "/nonexistent/path.pem")
        status, data = _handle_action_wallet_create({})
        assert status == 400
        assert data["status"] == "error"


# ---------------------------------------------------------------------------
# _handle_action_set_bots
# ---------------------------------------------------------------------------

class TestHandleActionSetBots:
    def test_returns_503_without_sdk(self, monkeypatch):
        """Returns 503 when SDK is missing."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", False)
        status, data = _handle_action_set_bots({"num_bots": 3})
        assert status == 503

    def test_missing_num_bots(self, monkeypatch):
        """Returns 400 when num_bots is not provided."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        status, data = _handle_action_set_bots({})
        assert status == 400
        assert "num_bots" in data["error"]

    def test_set_bots_success(self, monkeypatch):
        """Successful set_bots returns 200."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        result = {"status": "ok", "display": "3 bots configured."}
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: result)
        status, data = _handle_action_set_bots({"num_bots": 3})
        assert status == 200
        assert data["status"] == "ok"

    def test_set_bots_passes_correct_args(self, monkeypatch):
        """Verify num_bots and force are forwarded to execute_tool."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        captured = {}
        def mock_execute(name, args):
            captured["name"] = name
            captured["args"] = args
            return {"status": "ok"}
        monkeypatch.setattr("iconfucius.client.server.execute_tool", mock_execute)
        _handle_action_set_bots({"num_bots": 5, "force": True})
        assert captured["name"] == "set_bot_count"
        assert captured["args"]["num_bots"] == 5
        assert captured["args"]["force"] is True

    def test_set_bots_error(self, monkeypatch):
        """Returns 400 on execute_tool error."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server.execute_tool",
                            lambda name, args: {"status": "error", "error": "insufficient funds"})
        status, data = _handle_action_set_bots({"num_bots": 3})
        assert status == 400
        assert data["status"] == "error"


# ---------------------------------------------------------------------------
# _handle_wallet_info
# ---------------------------------------------------------------------------

class TestHandleWalletInfo:
    def setup_method(self):
        _cache_clear()

    def test_returns_503_without_sdk(self, monkeypatch):
        """Returns 503 when SDK is missing."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", False)
        status, data = _handle_wallet_info()
        assert status == 503

    def test_returns_wallet_data(self, monkeypatch):
        """Returns wallet info (principal, address, balances) on success."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        mock_result = {
            "principal": "abc-principal",
            "btc_address": "bc1q-test",
            "balance_sats": 50000,
            "pending_sats": 1000,
            "btc_usd_rate": 100000.0,
        }
        monkeypatch.setattr("iconfucius.client.server.run_wallet_balance",
                            lambda ckbtc_minter=False: mock_result)
        status, data = _handle_wallet_info(bypass_cache=True)
        assert status == 200
        assert data["principal"] == "abc-principal"
        assert data["btc_address"] == "bc1q-test"
        assert data["balance_sats"] == 50000
        assert data["pending_sats"] == 1000
        assert data["btc_usd_rate"] == 100000.0
        # USD: 50000 sats / 1e8 * 100000 = $50
        assert data["balance_usd"] == pytest.approx(50.0, abs=0.01)

    def test_returns_404_when_wallet_missing(self, monkeypatch):
        """Returns 404 when run_wallet_balance returns None."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server.run_wallet_balance",
                            lambda ckbtc_minter=False: None)
        monkeypatch.setenv("ICONFUCIUS_ROOT", "/tmp/test-root")
        status, data = _handle_wallet_info(bypass_cache=True)
        assert status == 404
        assert "not found" in data["error"].lower()

    def test_usd_none_when_no_rate(self, monkeypatch):
        """USD values are None when btc_usd_rate is absent."""
        monkeypatch.setattr("iconfucius.client.server._HAS_ICONFUCIUS", True)
        monkeypatch.setattr("iconfucius.client.server._sync_project_root", lambda: None)
        monkeypatch.setattr("iconfucius.client.server._chdir_to_root", lambda: None)
        mock_result = {
            "principal": "abc",
            "btc_address": "bc1q",
            "balance_sats": 1000,
            "pending_sats": 0,
            "btc_usd_rate": None,
        }
        monkeypatch.setattr("iconfucius.client.server.run_wallet_balance",
                            lambda ckbtc_minter=False: mock_result)
        status, data = _handle_wallet_info(bypass_cache=True)
        assert status == 200
        assert data["balance_usd"] is None
        assert data["pending_usd"] is None
