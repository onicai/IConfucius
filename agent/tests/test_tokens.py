"""Tests for iconfucius.tokens — Token registry and lookup."""

import json
import time
from pathlib import Path
from unittest.mock import patch

from iconfucius.tokens import (
    _CACHE_TTL_SECONDS,
    _safety_note,
    format_known_tokens_for_prompt,
    load_known_tokens,
    lookup_known_token,
    lookup_token_with_fallback,
)


class TestLoadKnownTokens:
    def test_load_builtin_tokens(self):
        """Built-in tokens.toml should contain at least the well-known tokens."""
        tokens = load_known_tokens()
        assert len(tokens) > 0
        assert "29m8" in tokens  # IConfucius
        assert "28k1" in tokens  # Crypto Burger
        assert "2jjj" in tokens  # ODINDOG

    def test_tokens_have_name_and_ticker(self):
        tokens = load_known_tokens()
        for token_id, entry in tokens.items():
            assert "name" in entry, f"Token {token_id} missing 'name'"
            assert "ticker" in entry, f"Token {token_id} missing 'ticker'"


class TestLookupKnownToken:
    def test_lookup_by_id(self):
        result = lookup_known_token("29m8")
        assert result is not None
        assert result["id"] == "29m8"
        assert result["name"] == "IConfucius"

    def test_lookup_by_name_case_insensitive(self):
        result = lookup_known_token("iconfucius")
        assert result is not None
        assert result["id"] == "29m8"

    def test_lookup_by_name_exact(self):
        result = lookup_known_token("IConfucius")
        assert result is not None
        assert result["id"] == "29m8"

    def test_lookup_by_ticker(self):
        result = lookup_known_token("ICONFUCIUS")
        assert result is not None
        assert result["id"] == "29m8"

    def test_lookup_by_ticker_lowercase(self):
        result = lookup_known_token("cryptoburg")
        assert result is not None
        assert result["id"] == "28k1"

    def test_lookup_unknown_returns_none(self):
        result = lookup_known_token("nonexistent_token_xyz")
        assert result is None


class TestFormatKnownTokensForPrompt:
    def test_format_contains_header(self):
        text = format_known_tokens_for_prompt()
        assert "| ID" in text
        assert "| Name" in text
        assert "| Ticker" in text

    def test_format_contains_known_token(self):
        text = format_known_tokens_for_prompt()
        # The prompt shows top 50 sorted alphabetically by name;
        # just check that some tokens are present
        assert "| " in text
        assert len(text.split("\n")) > 10

    def test_format_has_total_count(self):
        text = format_known_tokens_for_prompt()
        assert "total known tokens" in text


class TestLocalOverride:
    def test_local_toml_adds_tokens(self, tmp_path, monkeypatch):
        """A project-local tokens.toml should add tokens to the registry."""
        # Create a local tokens.toml with a test token
        local_toml = tmp_path / "tokens.toml"
        local_toml.write_text(
            '[tokens.test1]\nname = "TestToken"\nticker = "TEST"\n'
        )

        # Point _project_root to tmp_path
        monkeypatch.setattr("iconfucius.tokens._project_root", lambda: str(tmp_path))

        tokens = load_known_tokens()
        assert "test1" in tokens
        assert tokens["test1"]["name"] == "TestToken"
        # Built-in tokens should still be present
        assert "29m8" in tokens


class TestLookupTokenWithFallback:
    def test_known_token_no_api_call(self):
        """Known tokens should be returned without an API call."""
        with patch("iconfucius.tokens._search_api") as mock_api:
            result = lookup_token_with_fallback("29m8")
            assert result is not None
            assert result["id"] == "29m8"
            mock_api.assert_not_called()

    def test_cached_token_no_api_call(self, tmp_path, monkeypatch):
        """Cached tokens should be returned without an API call."""
        cache_file = tmp_path / ".token-cache.json"
        cache_data = {
            "test2": {
                "name": "CachedToken",
                "ticker": "CACHED",
                "bonded": True,
                "cached_at": time.time(),
            }
        }
        cache_file.write_text(json.dumps(cache_data))

        monkeypatch.setattr("iconfucius.tokens._cache_path", lambda: cache_file)

        with patch("iconfucius.tokens._search_api") as mock_api:
            result = lookup_token_with_fallback("CachedToken")
            assert result is not None
            assert result["id"] == "test2"
            mock_api.assert_not_called()

    def test_expired_cache_triggers_api(self, tmp_path, monkeypatch):
        """Expired cache entries should trigger an API search."""
        cache_file = tmp_path / ".token-cache.json"
        cache_data = {
            "expired1": {
                "name": "ExpiredToken",
                "ticker": "EXPRD",
                "bonded": True,
                "cached_at": time.time() - _CACHE_TTL_SECONDS - 1,
            }
        }
        cache_file.write_text(json.dumps(cache_data))

        monkeypatch.setattr("iconfucius.tokens._cache_path", lambda: cache_file)

        with patch("iconfucius.tokens._search_api", return_value=[]) as mock_api:
            result = lookup_token_with_fallback("ExpiredToken")
            assert result is None
            mock_api.assert_called_once()

    def test_unknown_returns_none_on_api_miss(self):
        """Unknown token with empty API results returns None."""
        with patch("iconfucius.tokens._search_api", return_value=[]):
            result = lookup_token_with_fallback("nonexistent_xyz_123")
            assert result is None


class TestSafetyNote:
    def test_known_bonded(self):
        note = _safety_note({"bonded": True}, is_known=True)
        assert "VERIFIED" in note

    def test_bonded_not_known(self):
        note = _safety_note(
            {"bonded": True, "twitter_verified": True, "holder_count": 500},
            is_known=False,
        )
        assert "bonded" in note
        assert "not in known tokens" in note

    def test_not_bonded_warning(self):
        note = _safety_note(
            {"bonded": False, "twitter_verified": False, "holder_count": 3},
            is_known=False,
        )
        assert "WARNING" in note
        assert "NOT bonded" in note
        assert "only 3 holders" in note

    def test_high_holder_count_formatted(self):
        note = _safety_note(
            {"bonded": True, "twitter_verified": False, "holder_count": 1500},
            is_known=False,
        )
        assert "1,500 holders" in note
