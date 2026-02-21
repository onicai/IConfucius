"""Tests for ConversationLogger and LoggingBackend."""

import json
import os
import stat
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from iconfucius.ai import AIBackend, ClaudeBackend, LoggingBackend, cached_system
from iconfucius.conversation_log import ConversationLogger, _MAX_LOG_FILES
from iconfucius.logging_config import _reset_session_stamp


_FAKE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
    "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)


@pytest.fixture(autouse=True)
def _fresh_session_stamp():
    """Reset the shared session stamp before each test."""
    _reset_session_stamp()


class TestConversationLogger:

    def test_creates_dir_with_0700(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
        conv_dir = tmp_path / ".logs" / "conversations"
        mode = stat.S_IMODE(conv_dir.stat().st_mode)
        assert mode == 0o700
        logger.close()

    def test_creates_files_with_0600(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
        for p in (logger.path_full, logger.path_cached):
            mode = stat.S_IMODE(p.stat().st_mode)
            assert mode == 0o600
        logger.close()

    def test_writes_valid_jsonl(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
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

        for p in (logger.path_full, logger.path_cached):
            lines = p.read_text().strip().split("\n")
            assert len(lines) == 2
            for line in lines:
                data = json.loads(line)
                assert "timestamp" in data
                assert "sequence" in data
                assert "call_type" in data

    def test_jwt_scrubbed(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
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

        for p in (logger.path_full, logger.path_cached):
            content = p.read_text()
            assert "eyJ" not in content
            assert "[JWT-REDACTED]" in content

    def test_sequence_increments(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
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

        lines = logger.path_full.read_text().strip().split("\n")
        seqs = [json.loads(line)["sequence"] for line in lines]
        assert seqs == [1, 2, 3]

    def test_tools_omitted_for_chat(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
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

        data = json.loads(logger.path_full.read_text().strip())
        assert "tools" not in data

    def test_cleanup_keeps_max_files(self, tmp_path):
        conv_dir = tmp_path / ".logs" / "conversations"
        conv_dir.mkdir(parents=True)
        extra = 3
        for i in range(_MAX_LOG_FILES + extra):
            (conv_dir / f"20260101-{i:06d}-ai-full.jsonl").write_text("")
            (conv_dir / f"20260101-{i:06d}-ai-cached.jsonl").write_text("")

        assert len(list(conv_dir.glob("*-ai-full.jsonl"))) == _MAX_LOG_FILES + extra
        assert len(list(conv_dir.glob("*-ai-cached.jsonl"))) == _MAX_LOG_FILES + extra

        # Creating a new logger triggers cleanup
        logger = ConversationLogger(base_dir=tmp_path)
        logger.close()

        for suffix in ("ai-full", "ai-cached"):
            remaining = sorted(conv_dir.glob(f"*-{suffix}.jsonl"))
            assert len(remaining) == _MAX_LOG_FILES
            names = {f.name for f in remaining}
            for i in range(extra):
                assert f"20260101-{i:06d}-{suffix}.jsonl" not in names

    def test_cleanup_noop_under_limit(self, tmp_path):
        conv_dir = tmp_path / ".logs" / "conversations"
        conv_dir.mkdir(parents=True)
        for i in range(5):
            (conv_dir / f"20260101-{i:06d}-ai-full.jsonl").write_text("")
            (conv_dir / f"20260101-{i:06d}-ai-cached.jsonl").write_text("")

        logger = ConversationLogger(base_dir=tmp_path)
        logger.close()

        for suffix in ("ai-full", "ai-cached"):
            remaining = list(conv_dir.glob(f"*-{suffix}.jsonl"))
            assert len(remaining) == 6  # 5 pre-existing + 1 new

    def test_tools_included_for_chat_with_tools(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
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

        data = json.loads(logger.path_full.read_text().strip())
        assert data["tools"] == [{"name": "test_tool"}]


# --- Fake backend for LoggingBackend tests ---

class _FakeBackend(AIBackend):
    def __init__(self):
        self.model = "fake-model"

    def chat(self, messages, system):
        return "fake response"

    def chat_with_tools(self, messages, system, tools):
        resp = MagicMock()
        resp.model_dump.return_value = {"id": "msg_test", "content": []}
        return resp

    def list_models(self):
        return [("fake-model", "Fake Model")]


class TestLoggingBackend:

    def test_chat_delegates_and_logs(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        result = backend.chat(
            [{"role": "user", "content": "hi"}], system="sys"
        )
        assert result == "fake response"
        logger.close()

        data = json.loads(logger.path_full.read_text().strip())
        assert data["call_type"] == "chat"
        assert data["response"] == "fake response"
        assert data["error"] is None
        assert data["duration_ms"] >= 0

    def test_chat_with_tools_delegates_and_logs(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        result = backend.chat_with_tools(
            [{"role": "user", "content": "check"}],
            system="sys",
            tools=[{"name": "wallet_balance"}],
        )
        # Should return the mock response object (not the serialized dict)
        assert result.model_dump(mode="json") == {"id": "msg_test", "content": []}
        logger.close()

        data = json.loads(logger.path_full.read_text().strip())
        assert data["call_type"] == "chat_with_tools"
        assert data["response"] == {"id": "msg_test", "content": []}
        assert "tools" in data

    def test_logs_errors_and_reraises(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)

        class _FailBackend(AIBackend):
            model = "fail-model"
            def chat(self, messages, system):
                raise RuntimeError("API down")

        backend = LoggingBackend(_FailBackend(), logger)

        with pytest.raises(RuntimeError, match="API down"):
            backend.chat([], system="sys")
        logger.close()

        data = json.loads(logger.path_full.read_text().strip())
        assert data["error"] == "API down"
        assert data["response"] is None

    def test_proxies_model_property(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        assert backend.model == "fake-model"
        backend.model = "new-model"
        assert backend.model == "new-model"
        logger.close()

    def test_list_models_delegates(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        models = backend.list_models()
        assert models == [("fake-model", "Fake Model")]
        logger.close()


class TestPromptCaching:

    def test_cached_system_returns_content_block_with_cache_control(self):
        result = ClaudeBackend._cached_system("You are helpful.")
        assert isinstance(result, list)
        assert len(result) == 1
        block = result[0]
        assert block["type"] == "text"
        assert block["text"] == "You are helpful."
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_logging_backend_logs_system_as_api_format(self, tmp_path):
        """LoggingBackend logs system in API format (list[dict] with cache_control)."""
        logger = ConversationLogger(base_dir=tmp_path)
        backend = LoggingBackend(_FakeBackend(), logger)

        backend.chat_with_tools(
            [{"role": "user", "content": "hi"}],
            system="test system prompt",
            tools=[{"name": "tool_a"}, {"name": "tool_b"}],
        )
        logger.close()

        data = json.loads(logger.path_full.read_text().strip())
        # system should now be API-format: list of content blocks with cache_control
        assert isinstance(data["system"], list)
        assert data["system"] == cached_system("test system prompt")
        # tools should have cache_control on the last element
        assert data["tools"][-1].get("cache_control") == {"type": "ephemeral"}


class TestCachedLogFile:
    """Tests for the ai-cached file's cache-detection behaviour."""

    def test_first_call_writes_full_system_and_tools(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
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

        full_data = json.loads(logger.path_full.read_text().strip())
        cached_data = json.loads(logger.path_cached.read_text().strip())

        # Both files should contain the full system and tools on first call
        assert full_data["system"] == system
        assert cached_data["system"] == system
        assert full_data["tools"] == tools
        assert cached_data["tools"] == tools

    def test_second_identical_call_uses_cached_placeholder(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
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

        full_lines = logger.path_full.read_text().strip().split("\n")
        cached_lines = logger.path_cached.read_text().strip().split("\n")

        # Full file: both calls have real system+tools
        for line in full_lines:
            d = json.loads(line)
            assert d["system"] == system
            assert d["tools"] == tools

        # Cached file: first call full, second call "[cached]"
        first = json.loads(cached_lines[0])
        assert first["system"] == system
        assert first["tools"] == tools

        second = json.loads(cached_lines[1])
        assert second["system"] == "[cached]"
        assert second["tools"] == "[cached]"

    def test_changed_system_resets_cache(self, tmp_path):
        logger = ConversationLogger(base_dir=tmp_path)
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
        logger = ConversationLogger(base_dir=tmp_path)
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
