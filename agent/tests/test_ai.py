"""Tests for iconfucius.ai — OpenAICompatBackend and create_backend()."""

from unittest.mock import MagicMock, patch

import pytest

import iconfucius.config as cfg
from iconfucius.ai import (
    LlamaCppBackend, OpenAICompatBackend, cached_messages, create_backend,
)
from iconfucius.openai_compat import OpenAICompatResponse


# ---------------------------------------------------------------------------
# create_backend()
# ---------------------------------------------------------------------------

class TestCreateBackend:

    def test_create_backend_openai(self, tmp_path, monkeypatch):
        """create_backend returns OpenAICompatBackend for openai persona."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = MagicMock()
        persona.ai_api_type = "openai"
        persona.ai_model = "test-model"
        persona.ai_base_url = "http://localhost:9999"

        backend = create_backend(persona)
        assert isinstance(backend, OpenAICompatBackend)
        assert backend.model == "test-model"
        assert backend.base_url == "http://localhost:9999"

        cfg._cached_config = None
        cfg._cached_config_path = None

    def test_legacy_alias(self):
        """LlamaCppBackend is an alias for OpenAICompatBackend."""
        assert LlamaCppBackend is OpenAICompatBackend

    def test_create_backend_unsupported(self):
        """Raise ValueError for an unrecognized ai_api_type."""
        persona = MagicMock()
        persona.ai_api_type = "unknown"
        with pytest.raises(ValueError, match="Unsupported AI API type"):
            create_backend(persona)


# ---------------------------------------------------------------------------
# LlamaCppBackend
# ---------------------------------------------------------------------------

class TestOpenAICompatBackendChat:

    def test_chat_basic(self):
        """chat() sends correct payload and returns text."""
        backend = OpenAICompatBackend(model="test-model",
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
        backend = OpenAICompatBackend(model="test-model",
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
        backend = OpenAICompatBackend(model="x",
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

        backend = OpenAICompatBackend(model="x",
                                  base_url="http://localhost:1")

        with patch.object(
            backend._requests, "post",
            side_effect=requests.exceptions.ConnectionError("unreachable"),
        ):
            with pytest.raises(requests.exceptions.ConnectionError):
                backend.chat([{"role": "user", "content": "hi"}], "sys")

    def test_list_models_connection_error(self):
        """list_models returns [] on connection failure."""
        backend = OpenAICompatBackend(model="x",
                                  base_url="http://localhost:1")
        assert backend.list_models() == []

    def test_chat_with_tools_caches_messages(self):
        """Multi-turn messages are sent with cache markers stripped."""
        backend = OpenAICompatBackend(model="test-model",
                                  base_url="http://localhost:9999")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "Got it."}}
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        messages = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "second"},
        ]

        with patch.object(backend._requests, "post",
                          return_value=mock_resp) as mock_post:
            backend.chat_with_tools(messages, "sys", [])

        payload = mock_post.call_args[1]["json"]
        oai_msgs = payload["messages"]
        # system + 3 conversation messages
        assert len(oai_msgs) == 4
        # No cache_control keys should appear in OpenAI format
        for m in oai_msgs:
            assert "cache_control" not in m
            if isinstance(m.get("content"), list):
                for block in m["content"]:
                    assert "cache_control" not in block

    def test_base_url_trailing_slash_stripped(self):
        """Trailing slash is removed from the base URL."""
        backend = OpenAICompatBackend(model="x",
                                  base_url="http://localhost:9999/")
        assert backend.base_url == "http://localhost:9999"

    def test_model_dump_compatibility(self):
        """Verify response works with LoggingBackend's model_dump call."""
        backend = OpenAICompatBackend(model="test-model",
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
# OpenAICompatBackend api_key support
# ---------------------------------------------------------------------------

class TestOpenAICompatBackendApiKey:

    def test_api_key_passed_to_headers(self):
        """API key is included in request headers when provided."""
        backend = OpenAICompatBackend(model="x",
                                      base_url="http://localhost:9999",
                                      api_key="sk-test-123")
        headers = backend._headers()
        assert headers == {"Authorization": "Bearer sk-test-123"}

    def test_no_api_key_empty_headers(self, monkeypatch):
        """No API key results in empty headers."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        backend = OpenAICompatBackend(model="x",
                                      base_url="http://localhost:9999")
        headers = backend._headers()
        assert headers == {}

    def test_api_key_from_env(self, monkeypatch):
        """API key falls back to OPENAI_API_KEY env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        backend = OpenAICompatBackend(model="x",
                                      base_url="http://localhost:9999")
        headers = backend._headers()
        assert headers == {"Authorization": "Bearer sk-env-key"}


# ---------------------------------------------------------------------------
# cached_messages()
# ---------------------------------------------------------------------------

class TestCachedMessages:

    def test_empty_returns_empty(self):
        """Return an empty list when given no messages."""
        assert cached_messages([]) == []

    def test_single_message_unchanged(self):
        """One message — nothing to cache (no prior history)."""
        msgs = [{"role": "user", "content": "hello"}]
        result = cached_messages(msgs)
        assert result == msgs

    def test_string_content_wrapped(self):
        """String content on penultimate message is wrapped in a block."""
        msgs = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
            {"role": "user", "content": "second question"},
        ]
        result = cached_messages(msgs)

        # Penultimate (assistant) should now have a list content block
        penultimate = result[1]
        assert isinstance(penultimate["content"], list)
        assert len(penultimate["content"]) == 1
        block = penultimate["content"][0]
        assert block["type"] == "text"
        assert block["text"] == "first answer"
        assert block["cache_control"] == {"type": "ephemeral"}

        # Other messages unchanged
        assert result[0] == msgs[0]
        assert result[2] == msgs[2]

    def test_list_content_cache_on_last_block(self):
        """List content gets cache_control on its last block."""
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "r1"},
                {"type": "tool_result", "tool_use_id": "t2", "content": "r2"},
            ]},
            {"role": "assistant", "content": "done"},
        ]
        result = cached_messages(msgs)

        penultimate = result[1]
        assert isinstance(penultimate["content"], list)
        # First block untouched
        assert "cache_control" not in penultimate["content"][0]
        # Last block has cache_control
        assert penultimate["content"][1]["cache_control"] == {"type": "ephemeral"}

    def test_assistant_tool_use_blocks(self):
        """Assistant message with tool_use blocks gets cache_control on last."""
        msgs = [
            {"role": "user", "content": "check balance"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Let me check..."},
                {"type": "tool_use", "id": "t1", "name": "wallet_balance",
                 "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1",
                 "content": '{"status":"ok"}'},
            ]},
        ]
        result = cached_messages(msgs)

        # Penultimate is the assistant message
        penultimate = result[1]
        blocks = penultimate["content"]
        assert "cache_control" not in blocks[0]
        assert blocks[1]["cache_control"] == {"type": "ephemeral"}

    def test_original_messages_not_mutated(self):
        """cached_messages must not mutate the original list or dicts."""
        inner = {"type": "tool_result", "tool_use_id": "t1", "content": "r"}
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "user", "content": [inner]},
            {"role": "assistant", "content": "ok"},
        ]
        _ = cached_messages(msgs)  # return value not needed; testing mutation only

        # Original inner dict should not have cache_control
        assert "cache_control" not in inner
        # Original messages list should be unchanged
        assert msgs[1]["content"][0] is inner

    def test_two_messages(self):
        """With exactly two messages, first gets cache breakpoint."""
        msgs = [
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"},
        ]
        result = cached_messages(msgs)

        first = result[0]
        assert isinstance(first["content"], list)
        assert first["content"][0]["cache_control"] == {"type": "ephemeral"}
        # Second unchanged
        assert result[1] == msgs[1]
