"""Reusable SSE (Server-Sent Events) channel for Rasa.

Provides a streaming alternative to Rasa's built-in REST channel.
The client POSTs a message and receives an SSE stream of bot responses.
Turn completion is signalled by the stream closing -- no polling or
heartbeat needed.

Usage in credentials.yml:
    iconfucius.channels.sse.SSEInput: {}

Or if published as a separate package in futre:
    <package_name>.SSEInput: {}
"""
from __future__ import annotations

import asyncio
import json
from functools import partial
from typing import Any, Awaitable, Callable, Dict, List, Optional, Text

from rasa.core.channels.channel import (
    InputChannel,
    OutputChannel,
    UserMessage,
)
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import BaseHTTPResponse, ResponseStream


class SSEOutputChannel(OutputChannel):
    """Output channel that enqueues messages as SSE events."""

    @classmethod
    def name(cls) -> Text:
        return "sse"

    def __init__(self, queue: asyncio.Queue) -> None:
        super().__init__()
        self._queue = queue

    async def _enqueue(self, event: str, data: Dict[str, Any]) -> None:
        await self._queue.put({"event": event, "data": data})

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        await self._enqueue("bot_uttered", {"text": text})

    async def send_text_with_buttons(
        self, recipient_id: Text, text: Text,
        buttons: List[Dict[Text, Any]], **kwargs: Any,
    ) -> None:
        await self._enqueue(
            "bot_uttered", {"text": text, "buttons": buttons},
        )

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any,
    ) -> None:
        await self._enqueue("bot_uttered", {"image": image})

    async def send_custom_json(
        self, recipient_id: Text, json_message: Dict[Text, Any],
        **kwargs: Any,
    ) -> None:
        await self._enqueue("custom", json_message)


class SSEInput(InputChannel):
    """SSE input channel for Rasa.

    Exposes two endpoints under /webhooks/sse/:
      GET  /             -- health check
      POST /webhook      -- send message, receive SSE stream

    The SSE stream emits events as the agent processes the message:
      event: bot_uttered  -- text/button responses
      event: custom       -- custom JSON (e.g. tool_status updates)

    The stream closes when the agent finishes processing, providing
    a natural turn-completion signal without polling.
    """

    @classmethod
    def name(cls) -> Text:
        return "sse"

    @classmethod
    def from_credentials(
        cls, credentials: Optional[Dict[Text, Any]],
    ) -> SSEInput:
        return cls()

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]],
    ) -> Blueprint:
        sse_webhook = Blueprint("sse_webhook", __name__)

        @sse_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> BaseHTTPResponse:
            return response.json({"status": "ok"})

        @sse_webhook.route("/webhook", methods=["POST"])
        async def receive(
            request: Request,
        ) -> BaseHTTPResponse:
            payload = request.json or {}
            if not isinstance(payload, dict):
                return response.json(
                    {"error": "JSON object body required"},
                    status=400,
                )

            sender_id = payload.get("sender_id", "default")
            text = payload.get("message", "")
            metadata = payload.get("metadata")

            return ResponseStream(
                partial(
                    self._stream_response,
                    on_new_message,
                    text,
                    sender_id,
                    metadata,
                ),
                content_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

        return sse_webhook

    async def _stream_response(
        self,
        on_new_message: Callable[[UserMessage], Awaitable[Any]],
        text: str,
        sender_id: str,
        metadata: Optional[Dict[str, Any]],
        resp: ResponseStream,
    ) -> None:
        queue: asyncio.Queue = asyncio.Queue()
        output = SSEOutputChannel(queue)
        message = UserMessage(
            text, output, sender_id,
            input_channel=self.name(), metadata=metadata,
        )

        async def _process() -> None:
            try:
                await on_new_message(message)
            finally:
                await queue.put(None)  # Sentinel: processing done

        task = asyncio.ensure_future(_process())

        while True:
            item = await queue.get()
            if item is None:
                break
            event = item["event"]
            data = json.dumps(item["data"], ensure_ascii=False)
            await resp.write(f"event: {event}\ndata: {data}\n\n")

        await task  # Propagate any exceptions
