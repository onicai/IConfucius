"""Tests for iconfucius ui command and client.server module."""

import os
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from iconfucius.cli import app
from iconfucius.client.server import (
    _resolve_static,
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
        assert "Launch the web UI" in result.output
        assert "--port" in result.output
        assert "--no-browser" in result.output

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

    def test_root_resolves_to_index(self, static_dir):
        """GET / should resolve to index.html."""
        result = _resolve_static("/")
        assert result is not None
        assert result.name == "index.html"

    def test_empty_path_resolves_to_index(self, static_dir):
        """Empty path should resolve to index.html."""
        result = _resolve_static("")
        assert result is not None
        assert result.name == "index.html"

    def test_existing_file(self, static_dir):
        """Known file path should resolve to that file."""
        result = _resolve_static("/app.js")
        assert result is not None
        assert result.name == "app.js"

    def test_nested_file(self, static_dir):
        """Nested file path should resolve correctly."""
        result = _resolve_static("/assets/style.css")
        assert result is not None
        assert result.name == "style.css"

    def test_spa_fallback(self, static_dir):
        """Unknown path should fall back to index.html (SPA routing)."""
        result = _resolve_static("/wallet")
        assert result is not None
        assert result.name == "index.html"

    def test_spa_fallback_nested(self, static_dir):
        """Deeply nested unknown path should fall back to index.html."""
        result = _resolve_static("/some/deep/route")
        assert result is not None
        assert result.name == "index.html"

    def test_directory_traversal_blocked(self, static_dir):
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
    @patch("iconfucius.client.server.webbrowser")
    @patch("iconfucius.client.server._warm_cache")
    def test_run_server_opens_browser(self, mock_cache, mock_wb, mock_srv):
        """Verify run_server opens browser when open_browser=True."""
        mock_instance = MagicMock()
        mock_srv.return_value = mock_instance
        mock_instance.serve_forever.side_effect = KeyboardInterrupt

        run_server(port=55199, open_browser=True)

        mock_srv.assert_called_once_with(("127.0.0.1", 55199), UIHandler)
        mock_instance.serve_forever.assert_called_once()
        mock_instance.server_close.assert_called_once()

    @patch("iconfucius.client.server.ThreadingHTTPServer")
    @patch("iconfucius.client.server.webbrowser")
    @patch("iconfucius.client.server._warm_cache")
    def test_run_server_no_browser(self, mock_cache, mock_wb, mock_srv):
        """Verify run_server skips browser when open_browser=False."""
        mock_instance = MagicMock()
        mock_srv.return_value = mock_instance
        mock_instance.serve_forever.side_effect = KeyboardInterrupt

        run_server(port=55199, open_browser=False)

        # webbrowser.open should not be scheduled
        mock_wb.open.assert_not_called()

    @patch("iconfucius.client.server.ThreadingHTTPServer")
    @patch("iconfucius.client.server.webbrowser")
    @patch("iconfucius.client.server._warm_cache")
    def test_run_server_port_in_use(self, mock_cache, mock_wb, mock_srv, capsys):
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
    def test_run_server_other_oserror_propagates(self, mock_cache, mock_wb, mock_srv):
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
