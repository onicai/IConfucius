"""Shared OpenAI-compatible format translator.

Converts between Anthropic message/tool format and the OpenAI
chat-completions format used by llama.cpp, Ollama, vLLM, etc.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field


# ---------------------------------------------------------------------------
# Response wrapper dataclasses
# ---------------------------------------------------------------------------
# These support attribute access (block.type, block.text, etc.) as required
# by the tool loop in chat.py, AND model_dump(mode="json") as required by
# LoggingBackend.

@dataclass
class TextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class ToolUseBlock:
    type: str = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class OpenAICompatResponse:
    """Wraps an OpenAI-format response so it looks like an Anthropic response."""

    content: list  # list of TextBlock | ToolUseBlock

    def model_dump(self, mode=None) -> dict:
        return {"content": [asdict(b) for b in self.content]}


# ---------------------------------------------------------------------------
# Anthropic -> OpenAI conversion
# ---------------------------------------------------------------------------

def anthropic_messages_to_openai(messages: list[dict],
                                 system: str) -> list[dict]:
    """Convert Anthropic-format messages to OpenAI chat-completions format.

    - System prompt becomes a ``{"role": "system"}`` first message.
    - ``tool_use`` content blocks become ``tool_calls`` on assistant messages.
    - ``tool_result`` blocks (bundled in a single user message by Anthropic)
      become separate ``{"role": "tool"}`` messages (one per result).
    - ``cache_control`` keys are stripped.
    """
    result: list[dict] = []

    # System prompt
    if system:
        result.append({"role": "system", "content": system})

    for msg in messages:
        role = msg["role"]
        content = msg.get("content")

        # Simple text message (string content)
        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue

        # Content is a list of blocks
        if not isinstance(content, list):
            result.append({"role": role, "content": content})
            continue

        # Check what block types are present
        has_tool_use = any(
            isinstance(b, dict) and b.get("type") == "tool_use"
            for b in content
        )
        has_tool_result = any(
            isinstance(b, dict) and b.get("type") == "tool_result"
            for b in content
        )

        if role == "assistant" and has_tool_use:
            # Assistant message with tool_use blocks -> tool_calls
            text_parts = []
            tool_calls = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(
                                block.get("input", {}),
                            ),
                        },
                    })
            oai_msg: dict = {"role": "assistant"}
            oai_msg["content"] = "\n".join(text_parts) if text_parts else None
            if tool_calls:
                oai_msg["tool_calls"] = tool_calls
            result.append(oai_msg)

        elif has_tool_result:
            # User message with tool_result blocks -> separate tool messages
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    result.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": block.get("content", ""),
                    })

        else:
            # Regular content blocks -> concatenate text
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            result.append({
                "role": role,
                "content": "\n".join(text_parts) if text_parts else "",
            })

    return result


def anthropic_tools_to_openai(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool definitions to OpenAI function-calling format.

    ``{name, description, input_schema}`` ->
    ``{type: "function", function: {name, description, parameters}}``
    """
    result = []
    for tool in tools:
        # Strip cache_control if present
        schema = dict(tool.get("input_schema", {}))
        schema.pop("cache_control", None)

        oai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": schema,
            },
        }
        result.append(oai_tool)
    return result


# ---------------------------------------------------------------------------
# OpenAI -> Anthropic conversion
# ---------------------------------------------------------------------------

def openai_response_to_anthropic(data: dict) -> OpenAICompatResponse:
    """Convert an OpenAI chat-completions JSON response to our wrapper.

    Handles ``choices[0].message.content`` (text) and
    ``choices[0].message.tool_calls`` (function calls).
    """
    blocks: list = []

    choices = data.get("choices", [])
    if not choices:
        return OpenAICompatResponse(content=[TextBlock(text="")])

    message = choices[0].get("message", {})

    # Text content
    text = message.get("content")
    if text:
        blocks.append(TextBlock(text=text))

    # Tool calls
    for tc in message.get("tool_calls", []):
        func = tc.get("function", {})
        raw_args = func.get("arguments", "{}")
        try:
            parsed_args = json.loads(raw_args)
        except (json.JSONDecodeError, TypeError):
            parsed_args = {"_raw": raw_args}

        blocks.append(ToolUseBlock(
            id=tc.get("id", f"call_{uuid.uuid4().hex[:24]}"),
            name=func.get("name", ""),
            input=parsed_args,
        ))

    # Ensure at least one block
    if not blocks:
        blocks.append(TextBlock(text=""))

    return OpenAICompatResponse(content=blocks)
