"""Tests for ConversationLogger and LoggingBackend."""

import json
import os
import stat
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from iconfucius.ai import AIBackend, ClaudeBackend, LoggingBackend, cached_system
from iconfucius.conversation_log import ConversationLogger, _MAX_LOG_FILES
_FAKE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
    "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)


class TestConversationLogger:

    def test_creates_dir_with_0700(self, tmp_path):
        """Verify creates dir with 0700."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        conv_dir = tmp_path / ".logs" / "conversations"
        mode = stat.S_IMODE(conv_dir.stat().st_mode)
        assert mode == 0o700
        logger.close()

    def test_creates_file_with_0600(self, tmp_path):
        """Verify creates file with 0600."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        mode = stat.S_IMODE(logger.path_cached.stat().st_mode)
        assert mode == 0o600
        logger.close()

    def test_writes_valid_jsonl(self, tmp_path):
        """Verify writes valid jsonl."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        logger.log_interaction(
            call_type="chat",
            model="test-model",
            system="You are a test.",
            messages=[{"role": "user", "content": "hello"}],
            response="Hi there!",
            duration_ms=100,
            error=None,
        )
        logger.log_interaction(
            call_type="chat",
            model="test-model",
            system="You are a test.",
            messages=[{"role": "user", "content": "bye"}],
            response="Goodbye!",
            duration_ms=50,
            error=None,
        )
        logger.close()

        lines = logger.path_cached.read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert "timestamp" in data
            assert "sequence" in data
            assert "call_type" in data

    def test_jwt_scrubbed(self, tmp_path):
        """Verify jwt scrubbed."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        logger.log_interaction(
            call_type="chat",
            model="test-model",
            system="You are a test.",
            messages=[{"role": "user", "content": f"token: {_FAKE_JWT}"}],
            response=f"Got token {_FAKE_JWT}",
            duration_ms=100,
            error=None,
        )
        logger.close()

        content = logger.path_cached.read_text()
        assert "eyJ" not in content
        assert "[JWT-REDACTED]" in content

    def test_sequence_increments(self, tmp_path):
        """Verify sequence increments."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        for _ in range(3):
            logger.log_interaction(
                call_type="chat",
                model="m",
                system="s",
                messages=[],
                response="r",
                duration_ms=0,
                error=None,
            )
        logger.close()

        lines = logger.path_cached.read_text().strip().split("\n")
        seqs = [json.loads(line)["sequence"] for line in lines]
        assert seqs == [1, 2, 3]

    def test_tools_omitted_for_chat(self, tmp_path):
        """Verify tools omitted for chat."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        logger.log_interaction(
            call_type="chat",
            model="m",
            system="s",
            messages=[],
            response="r",
            duration_ms=0,
            error=None,
        )
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        assert "tools" not in data

    def test_cleanup_keeps_max_files(self, tmp_path):
        """Verify cleanup keeps max files."""
        conv_dir = tmp_path / ".logs" / "conversations"
        conv_dir.mkdir(parents=True)
        extra = 3
        for i in range(_MAX_LOG_FILES + extra):
            (conv_dir / f"20260101-{i:06d}-ai-cached.jsonl").write_text("")

        assert len(list(conv_dir.glob("*-ai-cached.jsonl"))) == _MAX_LOG_FILES + extra

        # Creating a new logger triggers cleanup
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        logger.close()

        remaining = sorted(conv_dir.glob("*-ai-cached.jsonl"))
        assert len(remaining) == _MAX_LOG_FILES
        names = {f.name for f in remaining}
        for i in range(extra):
            assert f"20260101-{i:06d}-ai-cached.jsonl" not in names

    def test_cleanup_noop_under_limit(self, tmp_path):
        """Verify cleanup noop under limit."""
        conv_dir = tmp_path / ".logs" / "conversations"
        conv_dir.mkdir(parents=True)
        for i in range(5):
            (conv_dir / f"20260101-{i:06d}-ai-cached.jsonl").write_text("")

        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        logger.close()

        remaining = list(conv_dir.glob("*-ai-cached.jsonl"))
        assert len(remaining) == 6  # 5 pre-existing + 1 new

    def test_tools_included_for_chat_with_tools(self, tmp_path):
        """Verify tools included for chat with tools."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        logger.log_interaction(
            call_type="chat_with_tools",
            model="m",
            system="s",
            messages=[],
            tools=[{"name": "test_tool"}],
            response={"content": []},
            duration_ms=0,
            error=None,
        )
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        assert data["tools"] == [{"name": "test_tool"}]

    def test_raw_openai_response_logged(self, tmp_path):
        """raw_openai_response is included in log entry when provided."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        raw = {"choices": [{"message": {"content": "hi"}}]}
        logger.log_interaction(
            call_type="chat_with_tools",
            model="m",
            system="s",
            messages=[],
            tools=[{"name": "t"}],
            response={"content": []},
            duration_ms=0,
            error=None,
            raw_openai_response=raw,
        )
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        assert data["raw_openai_response"] == raw

    def test_raw_openai_response_omitted_when_none(self, tmp_path):
        """raw_openai_response is not in log entry when None."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        logger.log_interaction(
            call_type="chat",
            model="m",
            system="s",
            messages=[],
            response="r",
            duration_ms=0,
            error=None,
        )
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        assert "raw_openai_response" not in data

    def test_no_full_file_created(self, tmp_path):
        """Only the cached log file is created, no full file."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        logger.log_interaction(
            call_type="chat",
            model="m",
            system="s",
            messages=[],
            response="r",
            duration_ms=0,
            error=None,
        )
        logger.close()

        conv_dir = tmp_path / ".logs" / "conversations"
        assert list(conv_dir.glob("*-ai-full.jsonl")) == []
        assert len(list(conv_dir.glob("*-ai-cached.jsonl"))) == 1


# --- Fake backend for LoggingBackend tests ---

class _FakeBackend(AIBackend):
    def __init__(self):
        """Initialize the instance."""
        self.model = "fake-model"

    def chat(self, messages, system):
        """Send a chat message and return the response."""
        return "fake response"

    def chat_with_tools(self, messages, system, tools):
        """Send a chat message with tool definitions and return the response."""
        resp = MagicMock()
        resp.model_dump.return_value = {"id": "msg_test", "content": []}
        return resp

    def list_models(self):
        """List available models from the backend."""
        return [("fake-model", "Fake Model")]


class TestLoggingBackend:

    def test_chat_delegates_and_logs(self, tmp_path):
        """Verify chat delegates and logs."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        result = backend.chat(
            [{"role": "user", "content": "hi"}], system="sys"
        )
        assert result == "fake response"
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        assert data["call_type"] == "chat"
        assert data["response"] == "fake response"
        assert data["error"] is None
        assert data["duration_ms"] >= 0

    def test_chat_with_tools_delegates_and_logs(self, tmp_path):
        """Verify chat with tools delegates and logs."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        result = backend.chat_with_tools(
            [{"role": "user", "content": "check"}],
            system="sys",
            tools=[{"name": "wallet_balance"}],
        )
        # Should return the mock response object (not the serialized dict)
        assert result.model_dump(mode="json") == {"id": "msg_test", "content": []}
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        assert data["call_type"] == "chat_with_tools"
        assert data["response"] == {"id": "msg_test", "content": []}
        assert "tools" in data

    def test_logs_errors_and_reraises(self, tmp_path):
        """Verify logs errors and reraises."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)

        class _FailBackend(AIBackend):
            model = "fail-model"
            def chat(self, messages, system):
                """Send a chat message and return the response."""
                raise RuntimeError("API down")

        backend = LoggingBackend(_FailBackend(), logger)

        with pytest.raises(RuntimeError, match="API down"):
            backend.chat([], system="sys")
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        assert data["error"] == "API down"
        assert data["response"] is None

    def test_proxies_model_property(self, tmp_path):
        """Verify proxies model property."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        assert backend.model == "fake-model"
        backend.model = "new-model"
        assert backend.model == "new-model"
        logger.close()

    def test_list_models_delegates(self, tmp_path):
        """Verify list models delegates."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        models = backend.list_models()
        assert models == [("fake-model", "Fake Model")]
        logger.close()


class TestPromptCaching:

    def test_cached_system_returns_content_block_with_cache_control(self):
        """Verify cached system returns content block with cache control."""
        result = ClaudeBackend._cached_system("You are helpful.")
        assert isinstance(result, list)
        assert len(result) == 1
        block = result[0]
        assert block["type"] == "text"
        assert block["text"] == "You are helpful."
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_logging_backend_logs_system_as_api_format(self, tmp_path):
        """LoggingBackend logs system in API format (list[dict] with cache_control)."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        backend.chat_with_tools(
            [{"role": "user", "content": "hi"}],
            system="test system prompt",
            tools=[{"name": "tool_a"}, {"name": "tool_b"}],
        )
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        # system should now be API-format: list of content blocks with cache_control
        assert isinstance(data["system"], list)
        assert data["system"] == cached_system("test system prompt")
        # tools should have cache_control on the last element
        assert data["tools"][-1].get("cache_control") == {"type": "ephemeral"}


class TestCachedLogFile:
    """Tests for the ai-cached file's cache-detection behaviour."""

    def test_first_call_writes_full_system_and_tools(self, tmp_path):
        """Verify first call writes full system and tools."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        system = cached_system("You are wise.")
        tools = [{"name": "t1"}, {"name": "t2"}]

        logger.log_interaction(
            call_type="chat_with_tools",
            model="m",
            system=system,
            messages=[],
            tools=tools,
            response="ok",
            duration_ms=0,
            error=None,
        )
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        assert data["system"] == system
        assert data["tools"] == tools

    def test_second_identical_call_uses_cached_placeholder(self, tmp_path):
        """Verify second identical call uses cached placeholder."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        system = cached_system("You are wise.")
        tools = [{"name": "t1"}]

        for _ in range(2):
            logger.log_interaction(
                call_type="chat_with_tools",
                model="m",
                system=system,
                messages=[],
                tools=tools,
                response="ok",
                duration_ms=0,
                error=None,
            )
        logger.close()

        cached_lines = logger.path_cached.read_text().strip().split("\n")

        # First call: full system+tools
        first = json.loads(cached_lines[0])
        assert first["system"] == system
        assert first["tools"] == tools

        # Second call: "[cached]"
        second = json.loads(cached_lines[1])
        assert second["system"] == "[cached]"
        assert second["tools"] == "[cached]"

    def test_changed_system_resets_cache(self, tmp_path):
        """Verify changed system resets cache."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        tools = [{"name": "t1"}]

        logger.log_interaction(
            call_type="chat_with_tools",
            model="m",
            system=cached_system("prompt A"),
            messages=[],
            tools=tools,
            response="ok",
            duration_ms=0,
            error=None,
        )
        logger.log_interaction(
            call_type="chat_with_tools",
            model="m",
            system=cached_system("prompt B"),
            messages=[],
            tools=tools,
            response="ok",
            duration_ms=0,
            error=None,
        )
        logger.close()

        cached_lines = logger.path_cached.read_text().strip().split("\n")
        first = json.loads(cached_lines[0])
        second = json.loads(cached_lines[1])

        # Both should have full system since the system changed
        assert first["system"] == cached_system("prompt A")
        assert second["system"] == cached_system("prompt B")

    def test_chat_only_caches_system(self, tmp_path):
        """chat() calls (no tools) should still cache system when unchanged."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        system = cached_system("sys")

        for _ in range(2):
            logger.log_interaction(
                call_type="chat",
                model="m",
                system=system,
                messages=[],
                response="r",
                duration_ms=0,
                error=None,
            )
        logger.close()

        cached_lines = logger.path_cached.read_text().strip().split("\n")
        first = json.loads(cached_lines[0])
        second = json.loads(cached_lines[1])

        assert first["system"] == system
        assert "tools" not in first

        assert second["system"] == "[cached]"
        assert "tools" not in second


class TestCachedMessages:
    """Tests for message deduplication in the cached log file."""

    def test_first_call_logs_all_messages(self, tmp_path):
        """Verify first call logs all messages."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        msgs = [{"role": "user", "content": "hello"}]
        logger.log_interaction(
            call_type="chat", model="m", system="s",
            messages=msgs, response="r", duration_ms=0, error=None,
        )
        logger.close()

        data = json.loads(logger.path_cached.read_text().strip())
        assert data["messages"] == msgs

    def test_second_call_caches_prior_messages(self, tmp_path):
        """Verify second call caches prior messages."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)

        msgs1 = [{"role": "user", "content": "hello"}]
        logger.log_interaction(
            call_type="chat", model="m", system="s",
            messages=msgs1, response="r", duration_ms=0, error=None,
        )

        msgs2 = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "bye"},
        ]
        logger.log_interaction(
            call_type="chat", model="m", system="s",
            messages=msgs2, response="r", duration_ms=0, error=None,
        )
        logger.close()

        lines = logger.path_cached.read_text().strip().split("\n")
        first = json.loads(lines[0])
        second = json.loads(lines[1])

        # First call: full messages
        assert first["messages"] == msgs1

        # Second call: cached placeholder + only new messages
        assert second["messages"][0] == "[cached 1 messages]"
        assert second["messages"][1:] == msgs2[1:]

    def test_growing_conversation(self, tmp_path):
        """Simulate 3 turns of a growing conversation."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)

        turn1 = [{"role": "user", "content": "a"}]
        turn2 = turn1 + [{"role": "assistant", "content": "b"},
                         {"role": "user", "content": "c"}]
        turn3 = turn2 + [{"role": "assistant", "content": "d"},
                         {"role": "user", "content": "e"}]

        for msgs in [turn1, turn2, turn3]:
            logger.log_interaction(
                call_type="chat", model="m", system="s",
                messages=msgs, response="r", duration_ms=0, error=None,
            )
        logger.close()

        lines = logger.path_cached.read_text().strip().split("\n")
        d1 = json.loads(lines[0])
        d2 = json.loads(lines[1])
        d3 = json.loads(lines[2])

        assert d1["messages"] == turn1                         # 1 msg, all new
        assert d2["messages"][0] == "[cached 1 messages]"      # prior 1 cached
        assert len(d2["messages"]) == 3                        # placeholder + 2 new
        assert d3["messages"][0] == "[cached 3 messages]"      # prior 3 cached
        assert len(d3["messages"]) == 3                        # placeholder + 2 new


class TestLoggingBackendMessageCaching:
    """End-to-end: LoggingBackend passes cached_messages() to ConversationLogger.

    Simulates the real flow: LoggingBackend.chat() wraps messages with
    cached_messages() before logging. The logger should still deduplicate
    the growing message array even though cached_messages() transforms
    string content into list content blocks with cache_control markers.
    """

    def test_chat_caches_messages_across_turns(self, tmp_path):
        """Simulate 3 chat turns — logger should only log new messages."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        # Turn 1: user sends first message
        turn1 = [{"role": "user", "content": "hello"}]
        backend.chat(turn1, system="sys")

        # Turn 2: conversation grows (user + assistant + user)
        turn2 = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "how are you?"},
        ]
        backend.chat(turn2, system="sys")

        # Turn 3: conversation grows more
        turn3 = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "how are you?"},
            {"role": "assistant", "content": "I am well"},
            {"role": "user", "content": "goodbye"},
        ]
        backend.chat(turn3, system="sys")
        logger.close()

        lines = logger.path_cached.read_text().strip().split("\n")
        assert len(lines) == 3

        d1 = json.loads(lines[0])
        d2 = json.loads(lines[1])
        d3 = json.loads(lines[2])

        # Turn 1: 1 message, all new (no caching possible)
        assert len(d1["messages"]) == 1
        assert isinstance(d1["messages"][0], dict)

        # Turn 2: 3 messages total, but first 1 is cached
        assert d2["messages"][0] == "[cached 1 messages]"
        assert len(d2["messages"]) == 3   # placeholder + 2 new
        # The new messages should have cache_control on the second-to-last
        # (from cached_messages()), but that's fine — they're still logged

        # Turn 3: 5 messages total, but first 3 are cached
        assert d3["messages"][0] == "[cached 3 messages]"
        assert len(d3["messages"]) == 3   # placeholder + 2 new

    def test_chat_with_tools_caches_messages(self, tmp_path):
        """Same test but with chat_with_tools, which includes tool_use blocks."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        # Turn 1
        turn1 = [{"role": "user", "content": "check balance"}]
        backend.chat_with_tools(turn1, system="sys",
                                tools=[{"name": "balance"}])

        # Turn 2: includes tool_result blocks (list content)
        turn2 = [
            {"role": "user", "content": "check balance"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "balance", "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1",
                 "content": '{"sats": 50000}'},
            ]},
        ]
        backend.chat_with_tools(turn2, system="sys",
                                tools=[{"name": "balance"}])
        logger.close()

        lines = logger.path_cached.read_text().strip().split("\n")
        d1 = json.loads(lines[0])
        d2 = json.loads(lines[1])

        # Turn 1: full messages
        assert len(d1["messages"]) == 1
        assert isinstance(d1["messages"][0], dict)

        # Turn 2: first message cached
        assert d2["messages"][0] == "[cached 1 messages]"
        assert len(d2["messages"]) == 3  # placeholder + 2 new

    def test_single_message_turn_not_cached(self, tmp_path):
        """First call and calls with same message count should not cache."""
        logger = ConversationLogger(stamp="test", base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        # Two separate single-message turns (e.g. greeting + first user msg)
        backend.chat([{"role": "user", "content": "greeting"}], system="sys")
        backend.chat([{"role": "user", "content": "hello"}], system="sys")
        logger.close()

        lines = logger.path_cached.read_text().strip().split("\n")
        d1 = json.loads(lines[0])
        d2 = json.loads(lines[1])

        # Both should log full messages (1 msg each, no growth)
        assert isinstance(d1["messages"][0], dict)
        assert isinstance(d2["messages"][0], dict)
        # Second turn has same count (1), so no caching applies
        assert len(d2["messages"]) == 1
