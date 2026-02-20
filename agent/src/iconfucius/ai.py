"""AI backend abstraction for persona chat."""

import os
from abc import ABC, abstractmethod

from iconfucius.persona import Persona


class APIKeyMissingError(Exception):
    """Raised when a required API key is not configured."""


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

    def __init__(self, model: str, api_key: str | None = None):
        import anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key or key == "your-api-key-here":
            raise APIKeyMissingError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Get your API key at: https://console.anthropic.com/settings/keys\n"
                "Then add it to .env:\n"
                "  ANTHROPIC_API_KEY=sk-ant-..."
            )
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model

    def chat(self, messages: list[dict], system: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    def chat_with_tools(self, messages: list[dict], system: str,
                        tools: list[dict]):
        return self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=tools,
        )

    def list_models(self) -> list[tuple[str, str]]:
        try:
            page = self.client.models.list(limit=100)
            result = []
            for m in page.data:
                result.append((m.id, getattr(m, "display_name", m.id)))
            return result
        except Exception:
            return []


def create_backend(persona: Persona) -> AIBackend:
    """Create an AI backend from persona config.

    Args:
        persona: Loaded persona with ai_backend and ai_model fields.

    Returns:
        Configured AIBackend instance.

    Raises:
        ValueError: If the AI backend is not supported.
    """
    if persona.ai_backend == "claude":
        return ClaudeBackend(model=persona.ai_model)
    raise ValueError(
        f"Unsupported AI backend: '{persona.ai_backend}'. "
        f"Currently supported: claude"
    )
