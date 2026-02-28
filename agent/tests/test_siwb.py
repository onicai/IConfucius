"""Tests for iconfucius.siwb — session caching helpers."""

import json
import os

from iconfucius.siwb import read_cached_principal


class TestReadCachedPrincipal:
    def test_returns_principal_from_valid_cache(self, tmp_path, monkeypatch):
        """Returns bot_principal_text from a valid cache file."""
        monkeypatch.setattr("iconfucius.siwb._session_path",
                            lambda bot_name: str(tmp_path / "session.json"))
        cache_data = {"bot_principal_text": "abc-principal", "jwt_token": "old"}
        (tmp_path / "session.json").write_text(json.dumps(cache_data))

        assert read_cached_principal("bot-1") == "abc-principal"

    def test_returns_none_when_no_cache_file(self, tmp_path, monkeypatch):
        """Returns None when the cache file does not exist."""
        monkeypatch.setattr("iconfucius.siwb._session_path",
                            lambda bot_name: str(tmp_path / "missing.json"))

        assert read_cached_principal("bot-1") is None

    def test_returns_none_on_malformed_json(self, tmp_path, monkeypatch):
        """Returns None when the cache file contains invalid JSON."""
        monkeypatch.setattr("iconfucius.siwb._session_path",
                            lambda bot_name: str(tmp_path / "bad.json"))
        (tmp_path / "bad.json").write_text("{not valid json")

        assert read_cached_principal("bot-1") is None

    def test_returns_none_when_principal_is_empty(self, tmp_path, monkeypatch):
        """Returns None when bot_principal_text is empty string."""
        monkeypatch.setattr("iconfucius.siwb._session_path",
                            lambda bot_name: str(tmp_path / "session.json"))
        cache_data = {"bot_principal_text": "", "jwt_token": "old"}
        (tmp_path / "session.json").write_text(json.dumps(cache_data))

        assert read_cached_principal("bot-1") is None
