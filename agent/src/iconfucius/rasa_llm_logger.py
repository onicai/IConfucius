"""litellm CustomLogger callback that logs Rasa LLM calls to ConversationLogger.

Captures all LLM requests made by Rasa Pro internals (CompactLLMCommandGenerator,
ContextualResponseRephraser) via litellm and writes them to the same JSONL format
used by the non-Rasa chat backend.
"""

from datetime import datetime

from litellm.integrations.custom_logger import CustomLogger

from iconfucius.conversation_log import ConversationLogger


def _call_type(kwargs: dict) -> str:
    """Return a call_type label from the model_group_id that Rasa passes as ``model``."""
    model = kwargs.get("model", "")
    return f"rasa-{model}" if model else "rasa-unknown"


def _extract_messages(kwargs: dict) -> tuple[str | None, list[dict]]:
    """Split messages into system prompt and the rest."""
    messages = kwargs.get("messages", [])
    system = None
    rest = []
    for msg in messages:
        if isinstance(msg, dict):
            if msg.get("role") == "system" and system is None:
                system = msg.get("content", "")
            else:
                rest.append(msg)
    return system, rest


class RasaLLMLogger(CustomLogger):
    """Logs litellm calls made by Rasa to a ConversationLogger."""

    def __init__(self, conv_logger: ConversationLogger) -> None:
        super().__init__()
        self._conv_logger = conv_logger

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._log(kwargs, response_obj, start_time, end_time, error=None)

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self._log(kwargs, response_obj, start_time, end_time, error=str(response_obj))

    async def async_log_success_event(
        self, kwargs, response_obj, start_time, end_time
    ):
        await self._alog(kwargs, response_obj, start_time, end_time, error=None)

    async def async_log_failure_event(
        self, kwargs, response_obj, start_time, end_time
    ):
        await self._alog(
            kwargs, response_obj, start_time, end_time, error=str(response_obj)
        )

    def _build_log_kwargs(
        self,
        kwargs: dict,
        response_obj,
        start_time: datetime,
        end_time: datetime,
        *,
        error: str | None,
    ) -> dict:
        """Build the keyword arguments for log_interaction / alog_interaction."""
        call_type = _call_type(kwargs)
        model = kwargs.get("model", "unknown")
        system, messages = _extract_messages(kwargs)

        response_text = None
        if response_obj and hasattr(response_obj, "choices") and response_obj.choices:
            choice = response_obj.choices[0]
            if hasattr(choice, "message") and choice.message:
                response_text = choice.message.content

        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return dict(
            call_type=call_type,
            model=model,
            system=system,
            messages=messages,
            tools=None,
            response=response_text,
            duration_ms=duration_ms,
            error=error,
        )

    def _log(self, kwargs, response_obj, start_time, end_time, *, error):
        try:
            log_kwargs = self._build_log_kwargs(
                kwargs, response_obj, start_time, end_time, error=error
            )
            self._conv_logger.log_interaction(**log_kwargs)
        except Exception:
            pass  # Never break Rasa because of logging

    async def _alog(self, kwargs, response_obj, start_time, end_time, *, error):
        try:
            log_kwargs = self._build_log_kwargs(
                kwargs, response_obj, start_time, end_time, error=error
            )
            await self._conv_logger.alog_interaction(**log_kwargs)
        except Exception:
            pass  # Never break Rasa because of logging
