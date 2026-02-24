"""Tests for iconfucius.openai_compat — OpenAI format translator."""

import json

import pytest

from iconfucius.openai_compat import (
    OpenAICompatResponse,
    TextBlock,
    ToolUseBlock,
    anthropic_messages_to_openai,
    anthropic_tools_to_openai,
    openai_response_to_anthropic,
)


class TestAnthropicMessagesToOpenAI:
    """Test anthropic_messages_to_openai()."""

    def test_system_prompt_to_openai(self):
        result = anthropic_messages_to_openai([], "You are helpful.")
        assert result == [{"role": "system", "content": "You are helpful."}]

    def test_empty_system_prompt(self):
        result = anthropic_messages_to_openai(
            [{"role": "user", "content": "hi"}], ""
        )
        assert result[0]["role"] == "user"

    def test_text_messages_passthrough(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = anthropic_messages_to_openai(messages, "sys")
        assert result[0] == {"role": "system", "content": "sys"}
        assert result[1] == {"role": "user", "content": "Hello"}
        assert result[2] == {"role": "assistant", "content": "Hi there"}

    def test_tool_use_to_openai(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check."},
                    {
                        "type": "tool_use",
                        "id": "call_123",
                        "name": "get_price",
                        "input": {"token": "BTC"},
                    },
                ],
            },
        ]
        result = anthropic_messages_to_openai(messages, "")
        msg = result[0]
        assert msg["role"] == "assistant"
        assert msg["content"] == "Let me check."
        assert len(msg["tool_calls"]) == 1
        tc = msg["tool_calls"][0]
        assert tc["id"] == "call_123"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "get_price"
        assert json.loads(tc["function"]["arguments"]) == {"token": "BTC"}

    def test_tool_results_to_openai(self):
        """Bundled Anthropic tool results become separate OpenAI tool messages."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_1",
                        "content": '{"price": 100}',
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_2",
                        "content": '{"price": 200}',
                    },
                ],
            },
        ]
        result = anthropic_messages_to_openai(messages, "")
        assert len(result) == 2
        assert result[0] == {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": '{"price": 100}',
        }
        assert result[1] == {
            "role": "tool",
            "tool_call_id": "call_2",
            "content": '{"price": 200}',
        }

    def test_cache_control_stripped(self):
        """cache_control blocks in content are stripped (not passed through)."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello",
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
            },
        ]
        result = anthropic_messages_to_openai(messages, "")
        # Should produce a clean user message with text only
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_multiple_tool_use_blocks(self):
        """Multiple tool_use blocks in one assistant message."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "c1",
                        "name": "tool_a",
                        "input": {"x": 1},
                    },
                    {
                        "type": "tool_use",
                        "id": "c2",
                        "name": "tool_b",
                        "input": {"y": 2},
                    },
                ],
            },
        ]
        result = anthropic_messages_to_openai(messages, "")
        assert len(result[0]["tool_calls"]) == 2


class TestAnthropicToolsToOpenAI:
    """Test anthropic_tools_to_openai()."""

    def test_tool_definitions_conversion(self):
        tools = [
            {
                "name": "get_price",
                "description": "Get token price",
                "input_schema": {
                    "type": "object",
                    "properties": {"token": {"type": "string"}},
                    "required": ["token"],
                },
            },
        ]
        result = anthropic_tools_to_openai(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        func = result[0]["function"]
        assert func["name"] == "get_price"
        assert func["description"] == "Get token price"
        assert func["parameters"]["type"] == "object"
        assert "token" in func["parameters"]["properties"]

    def test_cache_control_in_schema_stripped(self):
        tools = [
            {
                "name": "t",
                "description": "d",
                "input_schema": {
                    "type": "object",
                    "cache_control": {"type": "ephemeral"},
                },
            },
        ]
        result = anthropic_tools_to_openai(tools)
        assert "cache_control" not in result[0]["function"]["parameters"]

    def test_empty_tools(self):
        assert anthropic_tools_to_openai([]) == []


class TestOpenAIResponseToAnthropic:
    """Test openai_response_to_anthropic()."""

    def test_response_text_only(self):
        data = {
            "choices": [
                {"message": {"content": "Hello world", "role": "assistant"}}
            ]
        }
        resp = openai_response_to_anthropic(data)
        assert len(resp.content) == 1
        assert resp.content[0].type == "text"
        assert resp.content[0].text == "Hello world"

    def test_response_with_tool_calls(self):
        data = {
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
        resp = openai_response_to_anthropic(data)
        assert len(resp.content) == 1
        block = resp.content[0]
        assert block.type == "tool_use"
        assert block.id == "call_abc"
        assert block.name == "get_price"
        assert block.input == {"token": "BTC"}

    def test_response_text_plus_tool_calls(self):
        data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Let me check.",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "lookup",
                                    "arguments": "{}",
                                },
                            },
                        ],
                    }
                }
            ]
        }
        resp = openai_response_to_anthropic(data)
        assert len(resp.content) == 2
        assert resp.content[0].type == "text"
        assert resp.content[1].type == "tool_use"

    def test_response_empty_choices(self):
        resp = openai_response_to_anthropic({"choices": []})
        assert len(resp.content) == 1
        assert resp.content[0].type == "text"
        assert resp.content[0].text == ""

    def test_malformed_tool_args(self):
        """Non-JSON arguments string is wrapped in _raw key."""
        data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_x",
                                "type": "function",
                                "function": {
                                    "name": "bad",
                                    "arguments": "not json{{{",
                                },
                            },
                        ],
                    }
                }
            ]
        }
        resp = openai_response_to_anthropic(data)
        block = resp.content[0]
        assert block.type == "tool_use"
        assert block.input == {"_raw": "not json{{{"}


class TestOpenAICompatResponse:
    """Test the response wrapper dataclass."""

    def test_model_dump(self):
        resp = OpenAICompatResponse(content=[
            TextBlock(text="hello"),
            ToolUseBlock(id="c1", name="fn", input={"a": 1}),
        ])
        dumped = resp.model_dump(mode="json")
        assert dumped == {
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "tool_use", "id": "c1", "name": "fn",
                 "input": {"a": 1}},
            ]
        }

    def test_model_dump_no_mode(self):
        resp = OpenAICompatResponse(content=[TextBlock(text="x")])
        dumped = resp.model_dump()
        assert "content" in dumped

    def test_attribute_access(self):
        """Verify TextBlock and ToolUseBlock support attribute access."""
        tb = TextBlock(text="hi")
        assert tb.type == "text"
        assert tb.text == "hi"

        tub = ToolUseBlock(id="c1", name="fn", input={"k": "v"})
        assert tub.type == "tool_use"
        assert tub.id == "c1"
        assert tub.name == "fn"
        assert tub.input == {"k": "v"}
