"""AI backend abstraction for persona chat."""

import os
import time
from abc import ABC, abstractmethod

from iconfucius.persona import Persona


class APIKeyMissingError(Exception):
    """Raised when a required API key is not configured."""


def cached_system(system: str) -> list[dict]:
    """Wrap system text in a content block with Anthropic cache_control."""
    return [{"type": "text", "text": system,
             "cache_control": {"type": "ephemeral"}}]


def cached_tools(tools: list[dict]) -> list[dict]:
    """Shallow-copy tools and add cache_control to the last definition."""
    if not tools:
        return tools
    result = [*tools]
    result[-1] = {**result[-1], "cache_control": {"type": "ephemeral"}}
    return result


def cached_messages(messages: list[dict]) -> list[dict]:
    """Add cache_control breakpoint to messages for prompt caching.

    Places a cache breakpoint on the second-to-last message so all prior
    conversation history is cached on subsequent API requests.  Only the
    newest message (the last one) is "fresh" input.

    Works with all content types:
    - String content: wrapped in a content block with cache_control
    - List content (tool_use, tool_result blocks): cache_control added to
      the last block in the list
    """
    if len(messages) < 2:
        return messages

    result = list(messages)          # shallow copy
    idx = len(result) - 2            # second-to-last message

    msg = result[idx]
    content = msg.get("content")

    if isinstance(content, str):
        result[idx] = {
            **msg,
            "content": [{
                "type": "text",
                "text": content,
                "cache_control": {"type": "ephemeral"},
            }],
        }
    elif isinstance(content, list) and content:
        new_content = list(content)
        last = new_content[-1]
        if isinstance(last, dict):
            new_content[-1] = {**last, "cache_control": {"type": "ephemeral"}}
        result[idx] = {**msg, "content": new_content}

    return result


class AIBackend(ABC):
    """Abstract base class for AI chat backends."""

    @abstractmethod
    def chat(self, messages: list[dict], system: str) -> str:
        """Send messages to AI and return response text.

        Args:
            messages: Conversation history as list of {"role": ..., "content": ...}.
            system: System prompt text.

        Returns:
            Assistant response text.
        """

    def chat_with_tools(self, messages: list[dict], system: str,
                        tools: list[dict]):
        """Send messages with tool definitions and return the full response.

        Args:
            messages: Conversation history.
            system: System prompt text.
            tools: Tool definitions in Anthropic API format.

        Returns:
            Full API response object (with content blocks that may include
            text and tool_use).

        Raises:
            NotImplementedError: If the backend does not support tool use.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support tool use."
        )

    def list_models(self) -> list[tuple[str, str]]:
        """Return available models as (model_id, display_name) pairs.

        Returns:
            List of (model_id, display_name) tuples, or [] on failure.
        """
        return []


class ClaudeBackend(AIBackend):
    """Claude API backend via anthropic SDK."""

    def __init__(self, model: str, api_key: str | None = None,
                 timeout: int = 600):
        """Initialize the Claude backend with model name, API key, and timeout."""
        import anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key or key == "your-api-key-here":
            raise APIKeyMissingError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Get your API key at: https://console.anthropic.com/settings/keys\n"
                "Then add it to .env:\n"
                "  ANTHROPIC_API_KEY=sk-ant-..."
            )
        self.client = anthropic.Anthropic(api_key=key, timeout=timeout)
        self.model = model

    @staticmethod
    def _cached_system(system: str) -> list[dict]:
        """Wrap system text in a content block with cache_control."""
        return cached_system(system)

    def chat(self, messages: list[dict], system: str) -> str:
        """Send a chat message to Claude and return the text response."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=cached_system(system),
            messages=cached_messages(messages),
        )
        return response.content[0].text

    def chat_with_tools(self, messages: list[dict], system: str,
                        tools: list[dict]):
        """Send a chat message to Claude with tool definitions and return the full response."""
        return self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=cached_system(system),
            messages=cached_messages(messages),
            tools=cached_tools(tools),
        )

    def list_models(self) -> list[tuple[str, str]]:
        """Fetch available models from the Claude API."""
        try:
            page = self.client.models.list(limit=100)
            result = []
            for m in page.data:
                result.append((m.id, getattr(m, "display_name", m.id)))
            return result
        except Exception:
            return []


class OpenAICompatBackend(AIBackend):
    """Backend for any OpenAI-compatible API (llama.cpp, Ollama, vLLM, etc.)."""

    def __init__(self, model: str = "default", base_url: str = "http://localhost:55128",
                 timeout: int = 600, api_key: str | None = None):
        """Initialize the OpenAI-compatible backend with model, base URL, and credentials."""
        import requests as _requests
        self._requests = _requests
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def _headers(self) -> dict:
        """Build request headers, including Authorization if an API key is set."""
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    def _post(self, payload: dict) -> dict:
        """POST to /v1/chat/completions and return parsed JSON."""
        url = f"{self.base_url}/v1/chat/completions"
        resp = self._requests.post(url, json=payload, headers=self._headers(),
                                   timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def chat(self, messages: list[dict], system: str) -> str:
        """Send a chat message via the OpenAI-compatible API and return the text response."""
        from iconfucius.openai_compat import (
            anthropic_messages_to_openai,
            openai_response_to_anthropic,
        )
        oai_messages = anthropic_messages_to_openai(
            cached_messages(messages), system,
        )
        data = self._post({
            "model": self.model,
            "messages": oai_messages,
            "max_tokens": 4096,
        })
        response = openai_response_to_anthropic(data)
        return "".join(
            b.text for b in response.content if b.type == "text"
        )

    def chat_with_tools(self, messages: list[dict], system: str,
                        tools: list[dict]):
        """Send a chat message with tools via the OpenAI-compatible API and return the response."""
        from iconfucius.openai_compat import (
            anthropic_messages_to_openai,
            anthropic_tools_to_openai,
            openai_response_to_anthropic,
        )
        oai_messages = anthropic_messages_to_openai(
            cached_messages(messages), system,
        )
        oai_tools = anthropic_tools_to_openai(tools)
        data = self._post({
            "model": self.model,
            "messages": oai_messages,
            "tools": oai_tools,
            "max_tokens": 4096,
        })
        response = openai_response_to_anthropic(data)
        response._raw_openai = data  # attached for LoggingBackend
        return response

    def list_models(self) -> list[tuple[str, str]]:
        """Fetch available models from the OpenAI-compatible API endpoint."""
        try:
            url = f"{self.base_url}/v1/models"
            resp = self._requests.get(url, headers=self._headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return [(m["id"], m["id"]) for m in data.get("data", [])]
        except Exception:
            return []


# Legacy alias for backward compatibility
LlamaCppBackend = OpenAICompatBackend


class LoggingBackend(AIBackend):
    """Transparent wrapper that logs every AI call to a ConversationLogger."""

    def __init__(self, backend: AIBackend, conv_logger):
        """Initialize the logging wrapper with an AI backend and conversation logger."""
        self._backend = backend
        self._logger = conv_logger

    @property
    def model(self):
        """Return the model name from the wrapped backend."""
        return self._backend.model

    @model.setter
    def model(self, value):
        """Set the model name on the wrapped backend."""
        self._backend.model = value

    def chat(self, messages: list[dict], system: str) -> str:
        """Send a chat message through the wrapped backend and log the interaction."""
        t0 = time.monotonic()
        error = None
        response = None
        try:
            response = self._backend.chat(messages, system)
            return response
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._logger.log_interaction(
                call_type="chat",
                model=self.model,
                system=cached_system(system),
                messages=cached_messages(messages),
                response=response,
                duration_ms=duration_ms,
                error=error,
            )

    def chat_with_tools(self, messages: list[dict], system: str,
                        tools: list[dict]):
        """Send a chat message with tools through the wrapped backend and log the interaction."""
        t0 = time.monotonic()
        error = None
        response = None
        serialized = None
        raw_response = None
        try:
            response = self._backend.chat_with_tools(messages, system, tools)
            serialized = response.model_dump(mode="json")
            raw_response = getattr(response, "_raw_openai", None)
            return response
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            duration_ms = int((time.monotonic() - t0) * 1000)
            log_kwargs = dict(
                call_type="chat_with_tools",
                model=self.model,
                system=cached_system(system),
                messages=cached_messages(messages),
                tools=cached_tools(tools),
                response=serialized,
                duration_ms=duration_ms,
                error=error,
            )
            if raw_response is not None:
                log_kwargs["raw_openai_response"] = raw_response
            self._logger.log_interaction(**log_kwargs)

    def list_models(self) -> list[tuple[str, str]]:
        """Delegate model listing to the wrapped backend."""
        return self._backend.list_models()


def create_backend(persona: Persona) -> AIBackend:
    """Create an AI backend from persona config.

    Args:
        persona: Loaded persona with ai_api_type, ai_model, ai_base_url fields.

    Returns:
        Configured AIBackend instance.

    Raises:
        ValueError: If the AI API type is not supported.
    """
    from iconfucius.config import get_ai_timeout
    timeout = get_ai_timeout()
    if persona.ai_api_type == "claude":
        return ClaudeBackend(model=persona.ai_model, timeout=timeout)
    if persona.ai_api_type == "openai":
        return OpenAICompatBackend(
            model=persona.ai_model,
            base_url=persona.ai_base_url or "http://localhost:55128",
            timeout=timeout,
        )
    raise ValueError(
        f"Unsupported AI API type: '{persona.ai_api_type}'. "
        f"Currently supported: claude, openai"
    )
