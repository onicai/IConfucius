"""Tests for iconfucius.channels.sse — SSE channel for Rasa."""

import asyncio
import json

import pytest

from iconfucius.channels.sse import SSEInput, SSEOutputChannel


# ------------------------------------------------------------------
# SSEOutputChannel
# ------------------------------------------------------------------

class TestSSEOutputChannel:
    """Tests for the SSE output channel queue-based message routing."""

    def test_name(self):
        assert SSEOutputChannel.name() == "sse"

    @pytest.mark.asyncio
    async def test_send_text_message(self):
        queue = asyncio.Queue()
        ch = SSEOutputChannel(queue)
        await ch.send_text_message("user-1", "Hello world")

        item = queue.get_nowait()
        assert item == {"event": "bot_uttered", "data": {"text": "Hello world"}}

    @pytest.mark.asyncio
    async def test_send_text_with_buttons(self):
        queue = asyncio.Queue()
        ch = SSEOutputChannel(queue)
        buttons = [{"title": "Yes", "payload": "/yes"}]
        await ch.send_text_with_buttons("user-1", "Choose:", buttons)

        item = queue.get_nowait()
        assert item["event"] == "bot_uttered"
        assert item["data"]["text"] == "Choose:"
        assert item["data"]["buttons"] == buttons

    @pytest.mark.asyncio
    async def test_send_image_url(self):
        queue = asyncio.Queue()
        ch = SSEOutputChannel(queue)
        await ch.send_image_url("user-1", "https://example.com/img.png")

        item = queue.get_nowait()
        assert item == {
            "event": "bot_uttered",
            "data": {"image": "https://example.com/img.png"},
        }

    @pytest.mark.asyncio
    async def test_send_custom_json(self):
        queue = asyncio.Queue()
        ch = SSEOutputChannel(queue)
        payload = {"type": "tool_status", "tool": "wallet_balance", "text": "Checking..."}
        await ch.send_custom_json("user-1", payload)

        item = queue.get_nowait()
        assert item["event"] == "custom"
        assert item["data"] == payload

    @pytest.mark.asyncio
    async def test_multiple_messages_preserve_order(self):
        queue = asyncio.Queue()
        ch = SSEOutputChannel(queue)
        await ch.send_text_message("u", "first")
        await ch.send_custom_json("u", {"type": "status"})
        await ch.send_text_message("u", "second")

        items = [queue.get_nowait() for _ in range(3)]
        assert items[0]["data"]["text"] == "first"
        assert items[1]["event"] == "custom"
        assert items[2]["data"]["text"] == "second"

    @pytest.mark.asyncio
    async def test_extra_kwargs_ignored(self):
        """send_text_message accepts arbitrary kwargs without error."""
        queue = asyncio.Queue()
        ch = SSEOutputChannel(queue)
        await ch.send_text_message("u", "hi", extra_param="ignored")

        item = queue.get_nowait()
        assert item["data"]["text"] == "hi"


# ------------------------------------------------------------------
# SSEInput
# ------------------------------------------------------------------

class TestSSEInput:
    """Tests for the SSE input channel configuration and metadata."""

    def test_name(self):
        assert SSEInput.name() == "sse"

    def test_from_credentials_none(self):
        ch = SSEInput.from_credentials(None)
        assert isinstance(ch, SSEInput)

    def test_from_credentials_empty_dict(self):
        ch = SSEInput.from_credentials({})
        assert isinstance(ch, SSEInput)

    def test_blueprint_returns_blueprint(self):
        ch = SSEInput()

        async def noop(msg):
            pass

        bp = ch.blueprint(noop)
        assert bp.name == "sse_webhook"


# ------------------------------------------------------------------
# _stream_response
# ------------------------------------------------------------------

class TestStreamResponse:
    """Tests for the SSE stream response logic."""

    @pytest.mark.asyncio
    async def test_stream_response_writes_sse_events(self):
        """Verify _stream_response writes correctly formatted SSE lines."""
        ch = SSEInput()
        written = []

        class FakeResp:
            async def write(self, data):
                written.append(data)

        async def on_new_message(msg):
            await msg.output_channel.send_text_message(msg.sender_id, "Reply 1")
            await msg.output_channel.send_custom_json(
                msg.sender_id, {"type": "tool_status", "text": "Working..."},
            )
            await msg.output_channel.send_text_message(msg.sender_id, "Reply 2")

        await ch._stream_response(on_new_message, "hello", "sender-1", None, FakeResp())

        assert len(written) == 3
        # Verify SSE format
        assert written[0].startswith("event: bot_uttered\n")
        assert '"Reply 1"' in written[0]
        assert written[1].startswith("event: custom\n")
        assert '"tool_status"' in written[1]
        assert written[2].startswith("event: bot_uttered\n")
        assert '"Reply 2"' in written[2]

    @pytest.mark.asyncio
    async def test_stream_response_sse_format(self):
        """Each written chunk must be: event: <type>\\ndata: <json>\\n\\n"""
        ch = SSEInput()
        written = []

        class FakeResp:
            async def write(self, data):
                written.append(data)

        async def on_new_message(msg):
            await msg.output_channel.send_text_message(msg.sender_id, "test")

        await ch._stream_response(on_new_message, "hi", "s1", None, FakeResp())

        chunk = written[0]
        lines = chunk.split("\n")
        assert lines[0] == "event: bot_uttered"
        assert lines[1].startswith("data: ")
        parsed = json.loads(lines[1][6:])
        assert parsed == {"text": "test"}
        assert lines[2] == ""  # trailing blank line (SSE separator)

    @pytest.mark.asyncio
    async def test_stream_response_empty_message(self):
        """on_new_message that sends nothing still completes."""
        ch = SSEInput()
        written = []

        class FakeResp:
            async def write(self, data):
                written.append(data)

        async def on_new_message(msg):
            pass  # No responses

        await ch._stream_response(on_new_message, "", "s1", None, FakeResp())
        assert written == []

    @pytest.mark.asyncio
    async def test_stream_response_exception_propagates(self):
        """Exceptions in on_new_message propagate after stream closes."""
        ch = SSEInput()

        class FakeResp:
            async def write(self, data):
                pass

        async def on_new_message(msg):
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await ch._stream_response(on_new_message, "hi", "s1", None, FakeResp())

    @pytest.mark.asyncio
    async def test_stream_response_passes_metadata(self):
        """Metadata from the request is forwarded to UserMessage."""
        ch = SSEInput()
        captured = {}

        class FakeResp:
            async def write(self, data):
                pass

        async def on_new_message(msg):
            captured["metadata"] = msg.metadata
            captured["sender_id"] = msg.sender_id
            captured["text"] = msg.text
            captured["input_channel"] = msg.input_channel

        await ch._stream_response(
            on_new_message, "hello", "sender-42",
            {"lang": "en"}, FakeResp(),
        )

        assert captured["metadata"] == {"lang": "en"}
        assert captured["sender_id"] == "sender-42"
        assert captured["text"] == "hello"
        assert captured["input_channel"] == "sse"

    @pytest.mark.asyncio
    async def test_stream_response_unicode(self):
        """Non-ASCII text is preserved in SSE output."""
        ch = SSEInput()
        written = []

        class FakeResp:
            async def write(self, data):
                written.append(data)

        async def on_new_message(msg):
            await msg.output_channel.send_text_message(msg.sender_id, "子曰：学而时习之")

        await ch._stream_response(on_new_message, "hi", "s1", None, FakeResp())

        assert "子曰：学而时习之" in written[0]
