"""Tests for iconfucius.ai — LlamaCppBackend and create_backend()."""

import json
from unittest.mock import MagicMock, patch

import pytest

import iconfucius.config as cfg
from iconfucius.ai import LlamaCppBackend, create_backend
from iconfucius.openai_compat import OpenAICompatResponse, TextBlock, ToolUseBlock


# ---------------------------------------------------------------------------
# create_backend()
# ---------------------------------------------------------------------------

class TestCreateBackend:

    def test_create_backend_llamacpp(self, tmp_path, monkeypatch):
        """create_backend returns LlamaCppBackend for llamacpp persona."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = MagicMock()
        persona.ai_backend = "llamacpp"
        persona.ai_model = "test-model"

        backend = create_backend(persona)
        assert isinstance(backend, LlamaCppBackend)
        assert backend.model == "test-model"

        cfg._cached_config = None
        cfg._cached_config_path = None

    def test_create_backend_unsupported(self):
        persona = MagicMock()
        persona.ai_backend = "unknown"
        with pytest.raises(ValueError, match="Unsupported AI backend"):
            create_backend(persona)


# ---------------------------------------------------------------------------
# LlamaCppBackend
# ---------------------------------------------------------------------------

class TestLlamaCppBackendChat:

    def test_chat_basic(self):
        """chat() sends correct payload and returns text."""
        backend = LlamaCppBackend(model="test-model",
                                  base_url="http://localhost:9999")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hello!"}}
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._requests, "post",
                          return_value=mock_resp) as mock_post:
            result = backend.chat(
                [{"role": "user", "content": "Hi"}],
                "You are helpful.",
            )

        assert result == "Hello!"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:9999/v1/chat/completions"
        payload = call_args[1]["json"]
        assert payload["model"] == "test-model"
        # System prompt should be first message
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"

    def test_chat_with_tools(self):
        """chat_with_tools() sends tools and returns OpenAICompatResponse."""
        backend = LlamaCppBackend(model="test-model",
                                  base_url="http://localhost:9999")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "get_price",
                                    "arguments": '{"token": "BTC"}',
                                },
                            },
                        ],
                    }
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        tools = [
            {
                "name": "get_price",
                "description": "Get price",
                "input_schema": {
                    "type": "object",
                    "properties": {"token": {"type": "string"}},
                },
            },
        ]

        with patch.object(backend._requests, "post",
                          return_value=mock_resp) as mock_post:
            result = backend.chat_with_tools(
                [{"role": "user", "content": "price?"}],
                "sys",
                tools,
            )

        assert isinstance(result, OpenAICompatResponse)
        assert len(result.content) == 1
        block = result.content[0]
        assert block.type == "tool_use"
        assert block.name == "get_price"
        assert block.input == {"token": "BTC"}

        # Verify tools were sent in payload
        payload = mock_post.call_args[1]["json"]
        assert "tools" in payload
        assert payload["tools"][0]["type"] == "function"

    def test_list_models(self):
        """list_models() parses /v1/models response."""
        backend = LlamaCppBackend(model="x",
                                  base_url="http://localhost:9999")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"id": "model-a"},
                {"id": "model-b"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._requests, "get",
                          return_value=mock_resp):
            result = backend.list_models()

        assert result == [("model-a", "model-a"), ("model-b", "model-b")]

    def test_connection_error(self):
        """Meaningful error when server is unreachable."""
        import requests

        backend = LlamaCppBackend(model="x",
                                  base_url="http://localhost:1")

        with pytest.raises(requests.exceptions.ConnectionError):
            backend.chat([{"role": "user", "content": "hi"}], "sys")

    def test_list_models_connection_error(self):
        """list_models returns [] on connection failure."""
        backend = LlamaCppBackend(model="x",
                                  base_url="http://localhost:1")
        assert backend.list_models() == []

    def test_base_url_trailing_slash_stripped(self):
        backend = LlamaCppBackend(model="x",
                                  base_url="http://localhost:9999/")
        assert backend.base_url == "http://localhost:9999"

    def test_model_dump_compatibility(self):
        """Verify response works with LoggingBackend's model_dump call."""
        backend = LlamaCppBackend(model="test-model",
                                  base_url="http://localhost:9999")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hi"}}
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch.object(backend._requests, "post",
                          return_value=mock_resp):
            result = backend.chat_with_tools(
                [{"role": "user", "content": "x"}], "sys", [],
            )

        dumped = result.model_dump(mode="json")
        assert isinstance(dumped, dict)
        assert "content" in dumped


# ---------------------------------------------------------------------------
# get_llamacpp_url()
# ---------------------------------------------------------------------------

class TestGetLlamacppUrl:

    def test_default_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        monkeypatch.delenv("LLAMACPP_URL", raising=False)
        cfg._cached_config = None
        cfg._cached_config_path = None

        from iconfucius.config import LLAMACPP_URL_DEFAULT, get_llamacpp_url
        assert get_llamacpp_url() == LLAMACPP_URL_DEFAULT

        cfg._cached_config = None
        cfg._cached_config_path = None

    def test_env_var_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        monkeypatch.setenv("LLAMACPP_URL", "http://myhost:8080")
        cfg._cached_config = None
        cfg._cached_config_path = None

        from iconfucius.config import get_llamacpp_url
        assert get_llamacpp_url() == "http://myhost:8080"

        cfg._cached_config = None
        cfg._cached_config_path = None

    def test_config_file_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        monkeypatch.delenv("LLAMACPP_URL", raising=False)
        cfg._cached_config = None
        cfg._cached_config_path = None

        config = '[ai]\nllamacpp_url = "http://configured:1234"\n'
        (tmp_path / "iconfucius.toml").write_text(config)

        from iconfucius.config import get_llamacpp_url
        assert get_llamacpp_url() == "http://configured:1234"

        cfg._cached_config = None
        cfg._cached_config_path = None

    def test_env_takes_precedence_over_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        monkeypatch.setenv("LLAMACPP_URL", "http://env:5555")
        cfg._cached_config = None
        cfg._cached_config_path = None

        config = '[ai]\nllamacpp_url = "http://config:1234"\n'
        (tmp_path / "iconfucius.toml").write_text(config)

        from iconfucius.config import get_llamacpp_url
        assert get_llamacpp_url() == "http://env:5555"

        cfg._cached_config = None
        cfg._cached_config_path = None
