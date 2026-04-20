"""Tests for iconfucius.health — Statuspage.io provider health checks."""

import json
from unittest.mock import MagicMock, patch

from iconfucius.health import fetch_provider_health


class TestFetchProviderHealth:
    def test_operational_returns_ok_true(self):
        """Operational component returns ok=True."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "components": [
                {"name": "Claude API (api.anthropic.com)", "status": "operational"},
                {"name": "Other", "status": "degraded_performance"},
            ]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("iconfucius.health.urlopen", return_value=mock_resp):
            result = fetch_provider_health("Anthropic", "https://status.claude.com/")

        assert result["ok"] is True
        assert result["status_detail"] == "operational"

    def test_degraded_returns_ok_false(self):
        """Non-operational component returns ok=False."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "components": [
                {"name": "Claude API (api.anthropic.com)", "status": "degraded_performance"},
            ]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("iconfucius.health.urlopen", return_value=mock_resp):
            result = fetch_provider_health("Anthropic", "https://status.claude.com/")

        assert result["ok"] is False
        assert result["status_detail"] == "degraded_performance"

    def test_unknown_provider_component_returns_none(self):
        """Unknown provider (no matching component) returns ok=None."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "components": [
                {"name": "Some Other API", "status": "operational"},
            ]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("iconfucius.health.urlopen", return_value=mock_resp):
            result = fetch_provider_health("UnknownProvider", "https://example.com/")

        assert result["ok"] is None
        assert result["status_detail"] == "unknown"

    def test_network_error_returns_none(self):
        """Network failure returns ok=None, status_detail=unknown."""
        from urllib.error import URLError

        with patch("iconfucius.health.urlopen", side_effect=URLError("timeout")):
            result = fetch_provider_health("Anthropic", "https://status.claude.com/")

        assert result["ok"] is None
        assert result["status_detail"] == "unknown"

    def test_invalid_json_returns_none(self):
        """Invalid JSON response returns ok=None."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("iconfucius.health.urlopen", return_value=mock_resp):
            result = fetch_provider_health("Anthropic", "https://status.claude.com/")

        assert result["ok"] is None
        assert result["status_detail"] == "unknown"
