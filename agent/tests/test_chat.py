"""Tests for iconfucius.cli.chat — Chat command and persona integration."""

import json
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

import iconfucius.config as cfg
from iconfucius.cli import app
from iconfucius.cli.chat import (
    _block_to_dict,
    _bot_target,
    _check_pypi_version,
    _describe_tool_call,
    _fmt_sats,
    _generate_startup,
    _get_language_code,
    _format_api_error,
    _handle_ai_interactive,
    _handle_model_interactive,
    _handle_upgrade,
    _persist_ai_config,
    _persist_ai_model,
    _persist_ai_timeout,
    _prompt_increase_timeout,
    _reset_ai_config,
    _resolve_principal_to_bot_name,
    _run_tool_loop,
    _Spinner,
    _MAX_TOOL_ITERATIONS,
    QUOTE_TOPICS,
)
from iconfucius.persona import DEFAULT_MODEL, Persona

runner = CliRunner()


class TestChatCommand:
    @patch("iconfucius.cli.chat.run_chat")
    def test_explicit_chat_command(self, mock_run_chat):
        """Verify explicit chat command."""
        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0
        mock_run_chat.assert_called_once()
        args = mock_run_chat.call_args
        assert args.kwargs["persona_name"] == "iconfucius"

    @patch("iconfucius.cli.chat.run_chat")
    def test_chat_with_persona_flag(self, mock_run_chat):
        """Verify chat with persona flag."""
        result = runner.invoke(app, ["chat", "--persona", "iconfucius"])
        assert result.exit_code == 0
        args = mock_run_chat.call_args
        assert args.kwargs["persona_name"] == "iconfucius"

    @patch("iconfucius.cli.chat.run_chat")
    def test_chat_with_bot_flag(self, mock_run_chat):
        """Verify chat with bot flag."""
        result = runner.invoke(app, ["chat", "--bot", "bot-2"])
        assert result.exit_code == 0
        args = mock_run_chat.call_args
        assert args.kwargs["bot_name"] == "bot-2"

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool", return_value={
        "status": "ok", "config_exists": True, "wallet_exists": True,
        "env_exists": True, "has_api_key": True, "ready": True,
    })
    def test_bare_invocation_starts_chat(self, mock_exec, mock_run_chat):
        """Verify bare invocation starts chat."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        mock_run_chat.assert_called_once()

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool", return_value={
        "status": "ok", "config_exists": True, "wallet_exists": True,
        "env_exists": True, "has_api_key": True, "ready": True,
    })
    def test_bare_with_persona_option(self, mock_exec, mock_run_chat):
        """Verify bare with persona option."""
        result = runner.invoke(app, ["--persona", "iconfucius"])
        assert result.exit_code == 0
        args = mock_run_chat.call_args
        assert args.kwargs["persona_name"] == "iconfucius"


class TestPersonaCommands:
    def test_persona_list(self):
        """Verify persona list."""
        result = runner.invoke(app, ["persona", "list"])
        assert result.exit_code == 0
        assert "iconfucius" in result.output

    def test_persona_show(self):
        """Verify persona show."""
        result = runner.invoke(app, ["persona", "show", "iconfucius"])
        assert result.exit_code == 0
        assert "IConfucius" in result.output
        assert "claude" in result.output  # ai_api_type

    def test_persona_show_not_found(self):
        """Verify persona show not found."""
        result = runner.invoke(app, ["persona", "show", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# Startup generation
# ---------------------------------------------------------------------------

def _make_persona(**overrides) -> Persona:
    """Create a test Persona with sensible defaults."""
    defaults = dict(
        name="TestBot",
        ai_api_type="claude",
        ai_model=DEFAULT_MODEL,
        ai_base_url="",
        system_prompt="You are a test bot.",
        greeting_prompt=(
            "Reply with exactly three lines (separate each with a blank line):\n"
            "Line 1: A quote about {topic}. Start with \"{icon} \".\n"
            "Line 2: Welcome the user. One sentence.\n"
            "Line 3: Tell user to type 'exit' to leave. One sentence."
        ),
        goodbye_prompt="Say goodbye in one sentence.",
    )
    defaults.update(overrides)
    return Persona(**defaults)


class TestGenerateStartup:
    def test_returns_greeting_and_goodbye(self):
        """_generate_startup returns a (greeting, goodbye) tuple."""
        mock_backend = MagicMock()
        mock_backend.chat.return_value = (
            "☕️ A wise quote about coffee.\n\n"
            "Welcome to Odin.fun, friend.\n\n"
            "Type 'exit' when your journey is done.\n\n"
            "May your path be ever illuminated."
        )
        persona = _make_persona()
        greeting, goodbye = _generate_startup(mock_backend, persona, "en")
        assert len(greeting) > 0
        assert len(goodbye) > 0
        assert "illuminated" in goodbye

    def test_uses_persona_greeting_prompt_template(self):
        """The greeting prompt template gets {icon} and {topic} filled in."""
        mock_backend = MagicMock()
        mock_backend.chat.return_value = "Line1\n\nLine2\n\nLine3\n\nGoodbye"
        persona = _make_persona(
            greeting_prompt="Say hi about {topic} with {icon}."
        )
        _generate_startup(mock_backend, persona, "en")
        call_args = mock_backend.chat.call_args
        user_msg = call_args[0][0][0]["content"]
        # Placeholders should be replaced with actual values
        assert "{topic}" not in user_msg
        assert "{icon}" not in user_msg

    def test_uses_persona_system_prompt(self):
        """The system prompt passed to the backend is the persona's."""
        mock_backend = MagicMock()
        mock_backend.chat.return_value = "Quote\n\nWelcome\n\nExit\n\nBye"
        persona = _make_persona(system_prompt="Custom system prompt.")
        _generate_startup(mock_backend, persona, "en")
        call_args = mock_backend.chat.call_args
        assert call_args[1]["system"] == "Custom system prompt."

    def test_includes_goodbye_prompt_in_request(self):
        """The goodbye prompt from the persona is included in the API request."""
        mock_backend = MagicMock()
        mock_backend.chat.return_value = "Quote\n\nWelcome\n\nExit\n\nBye"
        persona = _make_persona(goodbye_prompt="Bid farewell warmly.")
        _generate_startup(mock_backend, persona, "en")
        call_args = mock_backend.chat.call_args
        user_msg = call_args[0][0][0]["content"]
        assert "Bid farewell warmly." in user_msg


class TestLanguageDetection:
    def test_english_default(self, monkeypatch):
        """Verify english default."""
        monkeypatch.setattr("locale.getlocale", lambda: ("en_US", "UTF-8"))
        assert _get_language_code() == "en"

    def test_chinese_detected(self, monkeypatch):
        """Verify chinese detected."""
        monkeypatch.setattr("locale.getlocale", lambda: ("zh_CN", "UTF-8"))
        assert _get_language_code() == "cn"

    def test_none_locale_defaults_to_english(self, monkeypatch):
        """Verify none locale defaults to english."""
        monkeypatch.setattr("locale.getlocale", lambda: (None, None))
        assert _get_language_code() == "en"


class TestFormatApiError:
    def test_credit_balance_error(self):
        """Verify credit balance error."""
        e = Exception("Your credit balance is too low")
        msg = _format_api_error(e)
        assert "credit" in msg.lower()
        assert "console.anthropic.com" in msg

    def test_auth_error(self):
        """Verify auth error."""
        e = Exception("Invalid api_key provided")
        msg = _format_api_error(e)
        assert "Authentication" in msg

    def test_rate_limit_error(self):
        """Verify rate limit error."""
        e = Exception("rate limit exceeded")
        msg = _format_api_error(e)
        assert "Rate limited" in msg

    def test_overloaded_error(self):
        """Verify overloaded error."""
        e = Exception("API is overloaded")
        msg = _format_api_error(e)
        assert "overloaded" in msg.lower()

    def test_generic_error_passthrough(self):
        """Verify generic error passthrough."""
        e = Exception("Something weird happened")
        msg = _format_api_error(e)
        assert "Something weird happened" in msg


class TestQuoteTopics:
    def test_topics_not_empty(self):
        """Verify topics not empty."""
        assert len(QUOTE_TOPICS) > 0

    def test_each_topic_has_required_keys(self):
        """Verify each topic has required keys."""
        for entry in QUOTE_TOPICS:
            assert "cn" in entry
            assert "en" in entry
            assert "icon" in entry


class TestSpinner:
    def test_spinner_context_manager(self):
        """Spinner starts and stops without errors."""
        import time
        with _Spinner("testing..."):
            time.sleep(0.1)
        # If we get here, the spinner cleaned up properly


# ---------------------------------------------------------------------------
# Tool use helpers
# ---------------------------------------------------------------------------

class TestFmtSats:
    def test_normal_int(self):
        """Verify normal int."""
        result = _fmt_sats(5000)
        assert "5,000" in result
        assert "sats" in result

    def test_none_returns_question_mark(self):
        """Verify none returns question mark."""
        assert _fmt_sats(None) == "?"

    def test_string_passthrough(self):
        """Verify string passthrough."""
        assert _fmt_sats("all") == "all"


class TestBotTarget:
    def test_all_bots(self):
        """Verify all bots."""
        assert _bot_target({"all_bots": True}) == "all bots"

    def test_bot_names_list(self):
        """Verify bot names list."""
        result = _bot_target({"bot_names": ["bot-12", "bot-14"]})
        assert "bot-12" in result
        assert "bot-14" in result

    def test_single_bot_name(self):
        """Verify single bot name."""
        assert _bot_target({"bot_name": "bot-1"}) == "bot-1"

    def test_none_returns_question_mark(self):
        """Verify none returns question mark."""
        assert _bot_target({}) == "?"

    def test_all_bots_takes_priority(self):
        """Verify all bots takes priority."""
        result = _bot_target({"all_bots": True, "bot_name": "bot-1"})
        assert result == "all bots"

    def test_bot_names_takes_priority_over_bot_name(self):
        """Verify bot names takes priority over bot name."""
        result = _bot_target({"bot_names": ["bot-2"], "bot_name": "bot-1"})
        assert result == "bot-2"


class TestDescribeToolCall:
    def test_fund(self):
        """Verify fund."""
        desc = _describe_tool_call("fund", {"bot_name": "bot-1", "amount": 5000})
        assert "bot-1" in desc
        assert "5,000" in desc

    def test_fund_none_amount(self):
        """Verify fund none amount."""
        desc = _describe_tool_call("fund", {"bot_name": "bot-1", "amount": None})
        assert "bot-1" in desc
        assert "?" in desc

    def test_trade_buy_none_amount(self):
        """Verify trade buy none amount."""
        desc = _describe_tool_call(
            "trade_buy",
            {"token_id": "29m8", "amount": None, "bot_name": "bot-1"},
        )
        assert "?" in desc
        assert "bot-1" in desc

    def test_trade_buy(self):
        """Verify trade buy."""
        desc = _describe_tool_call(
            "trade_buy",
            {"token_id": "29m8", "amount": 1000, "bot_name": "bot-1"},
        )
        assert "29m8" in desc
        assert "1,000" in desc
        assert "bot-1" in desc

    def test_trade_sell(self):
        """Verify trade sell."""
        desc = _describe_tool_call(
            "trade_sell",
            {"token_id": "29m8", "amount": "all", "bot_name": "bot-1"},
        )
        assert "29m8" in desc
        assert "all" in desc

    def test_trade_buy_after_usd_preconvert(self):
        """After pre-conversion, trade_buy sees sats (not amount_usd)."""
        desc = _describe_tool_call(
            "trade_buy",
            {"token_id": "29m8", "amount": 14832, "bot_name": "bot-1"},
        )
        assert "14,832" in desc
        assert "29m8" in desc

    def test_trade_sell_usd(self):
        """trade_sell is excluded from pre-conversion, sees amount_usd."""
        desc = _describe_tool_call(
            "trade_sell",
            {"token_id": "29m8", "amount_usd": 5.0, "bot_name": "bot-1"},
        )
        assert "$5.000" in desc
        assert "29m8" in desc

    def test_trade_sell_tokens(self):
        """Verify trade sell tokens."""
        desc = _describe_tool_call(
            "trade_sell",
            {"token_id": "29m8", "amount": "5000000", "bot_name": "bot-1"},
        )
        # 5,000,000 raw sub-units / 10^8 divisibility = 0.050 tokens
        assert "0.050 tokens" in desc

    def test_withdraw(self):
        """Verify withdraw."""
        desc = _describe_tool_call(
            "withdraw", {"amount": "5000", "bot_name": "bot-1"}
        )
        assert "bot-1" in desc

    def test_wallet_send(self):
        """Verify wallet send."""
        desc = _describe_tool_call(
            "wallet_send", {"amount": "1000", "address": "bc1qtest"}
        )
        assert "bc1qtest" in desc

    def test_fund_all_bots(self):
        """Verify fund all bots."""
        desc = _describe_tool_call("fund", {"all_bots": True, "amount": 5000})
        assert "all bots" in desc
        assert "5,000" in desc

    def test_fund_bot_names_list(self):
        """Verify fund bot names list."""
        desc = _describe_tool_call(
            "fund",
            {"bot_names": ["bot-12", "bot-14"], "amount": 20000},
        )
        assert "bot-12" in desc
        assert "bot-14" in desc
        assert "20,000" in desc

    def test_trade_buy_all_bots(self):
        """Verify trade buy all bots."""
        desc = _describe_tool_call(
            "trade_buy",
            {"all_bots": True, "token_id": "29m8", "amount": 1000},
        )
        assert "all bots" in desc
        assert "29m8" in desc

    def test_withdraw_bot_names_list(self):
        """Verify withdraw bot names list."""
        desc = _describe_tool_call(
            "withdraw",
            {"bot_names": ["bot-3", "bot-7"], "amount": "all"},
        )
        assert "bot-3" in desc
        assert "bot-7" in desc

    def test_unknown_tool_fallback(self):
        """Verify unknown tool fallback."""
        desc = _describe_tool_call("something", {"a": 1})
        assert "something" in desc

    def test_fund_usd_after_preconvert(self):
        """After pre-conversion, fund sees sats (not amount_usd)."""
        desc = _describe_tool_call(
            "fund",
            {"bot_name": "bot-1", "amount": 14832},
        )
        assert "14,832" in desc
        assert "bot-1" in desc

    def test_withdraw_usd_after_preconvert(self):
        """After pre-conversion, withdraw sees sats (not amount_usd)."""
        desc = _describe_tool_call(
            "withdraw",
            {"bot_name": "bot-1", "amount": "14832"},
        )
        assert "14,832" in desc

    def test_wallet_send_usd_after_preconvert(self):
        """After pre-conversion, wallet_send sees sats (not amount_usd)."""
        desc = _describe_tool_call(
            "wallet_send",
            {"amount": "14832", "address": "bc1qtest"},
        )
        assert "14,832" in desc
        assert "bc1qtest" in desc

    def test_token_transfer(self):
        """Verify token transfer."""
        desc = _describe_tool_call(
            "token_transfer",
            {"token_id": "29m8", "amount": "5000000000", "bot_name": "bot-1",
             "to_address": "dest-principal-xyz"},
        )
        assert "29m8" in desc
        assert "bot-1" in desc
        assert "dest-principal-xyz" in desc

    def test_token_transfer_all(self):
        """Verify token transfer all."""
        desc = _describe_tool_call(
            "token_transfer",
            {"token_id": "29m8", "amount": "all", "bot_name": "bot-1",
             "to_address": "bot-2"},
        )
        assert "all" in desc
        assert "29m8" in desc
        assert "bot-2" in desc

    def test_token_transfer_all_bots(self):
        """Verify token transfer all bots."""
        desc = _describe_tool_call(
            "token_transfer",
            {"token_id": "29m8", "amount": "1000", "all_bots": True,
             "to_address": "dest-principal-xyz"},
        )
        assert "all bots" in desc
        assert "dest-principal-xyz" in desc

    def test_token_transfer_shows_bot_name(self):
        """When to_address is a principal matching a bot, show bot name."""
        with patch("iconfucius.cli.chat._resolve_principal_to_bot_name",
                   return_value="bot-3 (kfjfo-xyz)"):
            desc = _describe_tool_call(
                "token_transfer",
                {"token_id": "29m8", "amount": "all", "bot_name": "bot-1",
                 "to_address": "kfjfo-xyz"},
            )
        assert "bot-3 (kfjfo-xyz)" in desc
        assert "bot-1" in desc


class TestResolvePrincipalToBotName:
    """Test principal-to-bot-name resolution for transfer confirmation."""

    def test_resolves_known_principal(self, tmp_path):
        """Principal matching a bot's session cache returns 'bot-N (principal)'."""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        (cache_dir / "session_bot-3.json").write_text(
            json.dumps({"bot_principal_text": "kfjfo-3squy-bcwy5-xyz"})
        )

        with patch("iconfucius.config.get_bot_names",
                   return_value=["bot-1", "bot-3"]), \
             patch("iconfucius.siwb._session_path",
                   side_effect=lambda name: str(cache_dir / f"session_{name}.json")):
            result = _resolve_principal_to_bot_name("kfjfo-3squy-bcwy5-xyz")
        assert result == "bot-3 (kfjfo-3squy-bcwy5-xyz)"

    def test_unknown_principal_returns_as_is(self, tmp_path):
        """Principal not matching any bot returns unchanged."""
        with patch("iconfucius.config.get_bot_names",
                   return_value=["bot-1"]), \
             patch("iconfucius.siwb._session_path",
                   return_value=str(tmp_path / "nonexistent.json")):
            result = _resolve_principal_to_bot_name("unknown-principal-xyz")
        assert result == "unknown-principal-xyz"

    def test_no_config_returns_as_is(self):
        """When config is missing, returns principal unchanged."""
        with patch("iconfucius.config.get_bot_names",
                   side_effect=Exception("no config")):
            result = _resolve_principal_to_bot_name("some-principal")
        assert result == "some-principal"


class TestAmountUsdPreConversion:
    """Test that amount_usd is pre-converted to sats in the tool loop."""

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_fund_usd_converted_to_sats(self, mock_meta, mock_exec,
                                         mock_rate):
        """fund with amount_usd is converted to sats before execution."""
        backend = MagicMock()

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_fund"
        tool_block.name = "fund"
        tool_block.input = {"bot_name": "bot-1", "amount_usd": 10.0}
        resp1 = MagicMock()
        resp1.content = [tool_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        with patch("builtins.input", return_value="y"):
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        # amount should have been converted: $10 at $100k/BTC = 10,000 sats
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "fund"
        assert call_args[1]["amount"] == 10_000
        assert "amount_usd" not in call_args[1]

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_wallet_send_usd_converted(self, mock_meta, mock_exec, mock_rate):
        """wallet_send with amount_usd is converted to sats."""
        backend = MagicMock()

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_send"
        tool_block.name = "wallet_send"
        tool_block.input = {"amount_usd": 5.0, "address": "bc1qtest"}
        resp1 = MagicMock()
        resp1.content = [tool_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        with patch("builtins.input", return_value="y"):
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        call_args = mock_exec.call_args[0]
        assert call_args[1]["amount"] == 5_000  # $5 at $100k = 5,000 sats
        assert "amount_usd" not in call_args[1]

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_trade_sell_usd_not_preconverted(self, mock_meta, mock_exec):
        """trade_sell with amount_usd is NOT pre-converted (handler does it)."""
        backend = MagicMock()

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_sell"
        tool_block.name = "trade_sell"
        tool_block.input = {"token_id": "29m8", "amount_usd": 10.0,
                            "bot_name": "bot-1"}
        resp1 = MagicMock()
        resp1.content = [tool_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        with patch("builtins.input", return_value="y"):
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        # amount_usd should still be present — handler converts to tokens
        call_args = mock_exec.call_args[0]
        assert call_args[1]["amount_usd"] == 10.0

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_preconvert_skipped_when_amount_already_set(self, mock_meta,
                                                         mock_exec, mock_rate):
        """Pre-conversion skipped when both amount and amount_usd are set."""
        backend = MagicMock()

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_fund"
        tool_block.name = "fund"
        # AI provides both — amount takes priority
        tool_block.input = {"bot_name": "bot-1", "amount": 5000,
                            "amount_usd": 10.0}
        resp1 = MagicMock()
        resp1.content = [tool_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        with patch("builtins.input", return_value="y"):
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        # Original amount preserved (pre-conversion skipped)
        call_args = mock_exec.call_args[0]
        assert call_args[1]["amount"] == 5000


class TestBlockToDict:
    def test_text_block(self):
        """Verify text block."""
        block = MagicMock()
        block.type = "text"
        block.text = "Hello"
        result = _block_to_dict(block)
        assert result == {"type": "text", "text": "Hello"}

    def test_tool_use_block(self):
        """Verify tool use block."""
        block = MagicMock()
        block.type = "tool_use"
        block.id = "id_123"
        block.name = "wallet_balance"
        block.input = {"all_bots": True}
        result = _block_to_dict(block)
        assert result["type"] == "tool_use"
        assert result["id"] == "id_123"
        assert result["name"] == "wallet_balance"
        assert result["input"] == {"all_bots": True}


class TestRunToolLoop:
    def test_text_only_response(self):
        """Text-only response prints and returns."""
        backend = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Here is your answer."
        response = MagicMock()
        response.content = [text_block]
        backend.chat_with_tools.return_value = response

        messages = []
        _run_tool_loop(backend, messages, "system", [], "TestBot")

        # Should have added assistant message
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "Here is your answer."

    def test_tool_call_then_text(self):
        """Tool call followed by text response."""
        backend = MagicMock()

        # First response: tool call
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_1"
        tool_block.name = "setup_status"
        tool_block.input = {}
        resp1 = MagicMock()
        resp1.content = [tool_block]

        # Second response: text only
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Available personas: iconfucius"
        resp2 = MagicMock()
        resp2.content = [text_block]

        backend.chat_with_tools.side_effect = [resp1, resp2]

        messages = []
        _run_tool_loop(backend, messages, "system", [], "TestBot")

        # Should have: assistant (tool_use), user (tool_result), assistant (text)
        assert len(messages) == 3
        assert messages[0]["role"] == "assistant"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_single_confirm_prompt(self, mock_meta, mock_exec):
        """Single confirmable tool shows one [Y/n] prompt."""
        backend = MagicMock()

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_fund1"
        tool_block.name = "fund"
        tool_block.input = {"bot_name": "bot-1", "amount": 5000}
        resp1 = MagicMock()
        resp1.content = [tool_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        with patch("builtins.input", return_value="y"):
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        mock_exec.assert_called_once()

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_batch_confirm_asks_once(self, mock_meta, mock_exec):
        """Multiple confirmable tools in one response ask once."""
        backend = MagicMock()

        blocks = []
        for i in range(3):
            b = MagicMock()
            b.type = "tool_use"
            b.id = f"id_fund{i}"
            b.name = "fund"
            b.input = {"bot_name": f"bot-{i+1}", "amount": 5000}
            blocks.append(b)
        resp1 = MagicMock()
        resp1.content = blocks

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        with patch("builtins.input", return_value="y") as mock_input:
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        # Only one input() call for the batch
        mock_input.assert_called_once()
        # All three tools executed
        assert mock_exec.call_count == 3

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_batch_decline_skips_all(self, mock_meta, mock_exec):
        """Declining batch confirmation skips all confirmable tools."""
        backend = MagicMock()

        blocks = []
        for i in range(3):
            b = MagicMock()
            b.type = "tool_use"
            b.id = f"id_fund{i}"
            b.name = "fund"
            b.input = {"bot_name": f"bot-{i+1}", "amount": 5000}
            blocks.append(b)
        resp1 = MagicMock()
        resp1.content = blocks

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Cancelled."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        with patch("builtins.input", return_value="n"):
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        # No tools executed
        mock_exec.assert_not_called()
        # Tool results should all be declined
        tool_result_msg = messages[1]  # user message with tool_results
        import json
        for item in tool_result_msg["content"]:
            data = json.loads(item["content"])
            assert data["status"] == "declined"

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    def test_batch_mixed_confirm_and_no_confirm(self, mock_exec):
        """Non-confirmable tools run even when confirmable ones are declined."""
        backend = MagicMock()

        # One confirmable + one non-confirmable
        fund_block = MagicMock()
        fund_block.type = "tool_use"
        fund_block.id = "id_fund"
        fund_block.name = "fund"
        fund_block.input = {"bot_name": "bot-1", "amount": 5000}

        balance_block = MagicMock()
        balance_block.type = "tool_use"
        balance_block.id = "id_balance"
        balance_block.name = "wallet_balance"
        balance_block.input = {}

        resp1 = MagicMock()
        resp1.content = [fund_block, balance_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        def fake_meta(name):
            """Return fake metadata for testing."""
            if name == "fund":
                return {"requires_confirmation": True}
            return {"requires_confirmation": False}

        with patch("iconfucius.cli.chat.get_tool_metadata", side_effect=fake_meta), \
             patch("builtins.input", return_value="n"):
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        # Only the non-confirmable tool ran
        mock_exec.assert_called_once_with("wallet_balance", {},
                                          persona_name="")

    def test_max_iterations_guard(self, capsys):
        """Loop stops after MAX_TOOL_ITERATIONS and prints warning."""
        backend = MagicMock()

        # Always return a tool call
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_loop"
        tool_block.name = "setup_status"
        tool_block.input = {}
        response = MagicMock()
        response.content = [tool_block]
        backend.chat_with_tools.return_value = response

        messages = []
        _run_tool_loop(backend, messages, "system", [], "TestBot")

        # Should have called chat_with_tools exactly MAX_TOOL_ITERATIONS times
        assert backend.chat_with_tools.call_count == _MAX_TOOL_ITERATIONS

        # Warning message printed when limit is hit
        captured = capsys.readouterr().out
        assert "Tool loop limit reached" in captured
        assert "continue" in captured

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_confirmed_iterations_reset_counter(self, mock_meta, mock_exec):
        """User-confirmed iterations reset the counter, allowing > MAX loops."""
        backend = MagicMock()

        # Build more iterations than _MAX_TOOL_ITERATIONS, each with a
        # confirmable tool call.  After 15 confirmed iterations the AI
        # returns a text-only response to end the loop.
        total_iterations = _MAX_TOOL_ITERATIONS + 5

        responses = []
        for i in range(total_iterations):
            tool_block = MagicMock()
            tool_block.type = "tool_use"
            tool_block.id = f"id_confirm_{i}"
            tool_block.name = "fund"
            tool_block.input = {"bot_name": f"bot-{i}", "amount": 1000}
            resp = MagicMock()
            resp.content = [tool_block]
            responses.append(resp)

        # Final text-only response
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "All transfers complete."
        final_resp = MagicMock()
        final_resp.content = [text_block]
        responses.append(final_resp)

        backend.chat_with_tools.side_effect = responses

        # User confirms every operation (default Y)
        with patch("builtins.input", return_value=""):
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        # All confirmed iterations ran + final text response
        assert backend.chat_with_tools.call_count == total_iterations + 1
        assert mock_exec.call_count == total_iterations

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    def test_tool_call_passes_persona_key(self, mock_exec):
        """Tool calls receive persona_key for memory operations."""
        backend = MagicMock()

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_1"
        tool_block.name = "setup_status"
        tool_block.input = {}
        resp1 = MagicMock()
        resp1.content = [tool_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done"
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        messages = []
        _run_tool_loop(backend, messages, "system", [], "TestBot",
                       persona_key="iconfucius")

        mock_exec.assert_called_once_with("setup_status", {},
                                          persona_name="iconfucius")

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    def test_different_write_tools_deferred(self, mock_exec):
        """Different write tools in one response: only the first executes."""
        backend = MagicMock()

        fund_block = MagicMock()
        fund_block.type = "tool_use"
        fund_block.id = "id_fund"
        fund_block.name = "fund"
        fund_block.input = {"bot_name": "bot-1", "amount": 5000}

        buy_block = MagicMock()
        buy_block.type = "tool_use"
        buy_block.id = "id_buy"
        buy_block.name = "trade_buy"
        buy_block.input = {"token_id": "29m8", "amount": 5000,
                           "bot_name": "bot-1"}

        resp1 = MagicMock()
        resp1.content = [fund_block, buy_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        def fake_meta(name):
            """Return fake metadata for testing."""
            if name == "fund":
                return {"requires_confirmation": True, "category": "write"}
            if name == "trade_buy":
                return {"requires_confirmation": True, "category": "write"}
            return {"requires_confirmation": False, "category": "read"}

        with patch("iconfucius.cli.chat.get_tool_metadata",
                   side_effect=fake_meta), \
             patch("builtins.input", return_value="y"):
            messages = []
            _run_tool_loop(backend, messages, "system", [], "TestBot")

        # Only fund should have been executed
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "fund"

        # trade_buy should get a deferred result
        tool_result_msg = messages[1]  # user message with tool_results
        results_by_id = {
            r["tool_use_id"]: json.loads(r["content"])
            for r in tool_result_msg["content"]
        }
        assert results_by_id["id_fund"]["status"] == "ok"
        assert results_by_id["id_buy"]["status"] == "deferred"
        assert "one state-changing" in results_by_id["id_buy"]["error"].lower()


class TestToolResultPassthrough:
    """Tool results are sent as JSON to the AI for summarization."""

    @patch("iconfucius.cli.chat.execute_tool",
           return_value={"status": "ok", "wallet_ckbtc_sats": 50000,
                         "bots": [], "totals": {"portfolio_sats": 50000}})
    def test_full_result_sent_to_ai(self, mock_exec):
        """Tool result JSON is passed to the AI as-is."""
        backend = MagicMock()

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_1"
        tool_block.name = "wallet_balance"
        tool_block.input = {}
        resp1 = MagicMock()
        resp1.content = [tool_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Your wallet has 50,000 sats."
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        messages = []
        _run_tool_loop(backend, messages, "system", [], "TestBot")

        tool_result_msg = messages[1]  # user message with tool_results
        content = json.loads(tool_result_msg["content"][0]["content"])
        assert content["status"] == "ok"
        assert content["wallet_ckbtc_sats"] == 50000
        assert content["totals"]["portfolio_sats"] == 50000


# ---------------------------------------------------------------------------
# Chat hints placement
# ---------------------------------------------------------------------------


class TestChatHintsPlacement:
    """Hints (exit/model) appear right after the greeting, before wallet."""

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Wise greeting quote", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_hints_appear_after_greeting(self, mock_load, mock_backend_factory,
                                          _mock_startup,
                                          tmp_path, monkeypatch, capsys):
        """exit/model hints are printed immediately after the greeting."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        mock_backend_factory.return_value = backend

        with patch("builtins.input", side_effect=EOFError):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1")

        captured = capsys.readouterr().out
        assert "exit to quit" in captured
        assert "AI: claude" in captured
        assert "claude-sonnet-4-6" in captured

        # Hints must come after the greeting
        greeting_pos = captured.index("Wise greeting quote")
        exit_pos = captured.index("exit to quit")
        ai_pos = captured.index("AI:")
        assert exit_pos > greeting_pos
        assert ai_pos > exit_pos

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Wise greeting quote", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    @patch("iconfucius.cli.chat.execute_tool", return_value={
        "status": "ok", "config_exists": True, "wallet_exists": True,
        "env_exists": True, "has_api_key": True, "ready": True,
    })
    def test_hints_appear_before_wallet(self, _mock_exec, mock_load,
                                         mock_backend_factory,
                                         _mock_startup,
                                         tmp_path, monkeypatch, capsys):
        """Hints appear before wallet balance output."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        mock_backend_factory.return_value = backend

        wallet_data = {"_display": "Wallet: 50,000 sats", "balance_sats": 50000}
        with patch("builtins.input", side_effect=EOFError), \
             patch("iconfucius.cli.balance.run_wallet_balance",
                   return_value=wallet_data):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1")

        captured = capsys.readouterr().out
        ai_pos = captured.index("AI:")
        wallet_pos = captured.index("Wallet: 50,000 sats")
        assert ai_pos < wallet_pos


# ---------------------------------------------------------------------------
# Experimental warning at startup
# ---------------------------------------------------------------------------


class TestExperimentalWarning:
    """--experimental flag prints warning underneath the AI config line."""

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_experimental_flag_shows_warning(self, mock_load,
                                              mock_backend_factory,
                                              _mock_startup,
                                              tmp_path, monkeypatch, capsys):
        """--experimental prints the experimental warning after AI config."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-opus-4-6"
        mock_backend_factory.return_value = backend

        with patch("builtins.input", side_effect=EOFError):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1", experimental=True)

        captured = capsys.readouterr().out
        assert "/ai to change" in captured
        assert "Experimental features have been enabled" in captured
        assert "Use at your own risk" in captured
        # Enabled message after AI line, risk warning after enabled message
        ai_pos = captured.index("AI:")
        enabled_pos = captured.index("Experimental features have been enabled")
        risk_pos = captured.index("Use at your own risk")
        assert enabled_pos > ai_pos
        assert risk_pos > enabled_pos

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_no_experimental_flag_no_warning(self, mock_load,
                                              mock_backend_factory,
                                              mock_startup,
                                              tmp_path, monkeypatch, capsys):
        """Without --experimental, no experimental warning is shown."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-opus-4-6"
        mock_backend_factory.return_value = backend

        with patch("builtins.input", side_effect=EOFError):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1")

        captured = capsys.readouterr().out
        assert "Experimental features" not in captured
        assert "Use at your own risk" not in captured
        assert "/ai to change" not in captured

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_experimental_shows_ai_config_with_base_url(self, mock_load,
                                                         mock_backend_factory,
                                                         mock_startup,
                                                         tmp_path, monkeypatch,
                                                         capsys):
        """AI config line includes base_url when set."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(
            name="IConfucius",
            ai_api_type="openai",
            ai_model="llama-3",
            ai_base_url="http://localhost:55128",
        )
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "llama-3"
        mock_backend_factory.return_value = backend

        with patch("builtins.input", side_effect=["Y", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1", experimental=True)

        captured = capsys.readouterr().out
        assert "openai" in captured
        assert "llama-3" in captured
        assert "http://localhost:55128" in captured


# ---------------------------------------------------------------------------
# /ai hot-swap backend
# ---------------------------------------------------------------------------


class TestAiHotSwap:
    """Verify /ai commands hot-swap the backend without requiring restart."""

    @patch("iconfucius.cli.chat._persist_ai_config")
    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_ai_endpoint_hotswap(self, mock_load, mock_backend_factory,
                                  _mock_startup, _mock_persist,
                                  tmp_path, monkeypatch, capsys):
        """/ai interactive endpoint change creates a new backend."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        original_backend = MagicMock()
        original_backend.model = DEFAULT_MODEL
        new_backend = MagicMock()
        new_backend.model = "default"
        # First call returns original, second (after hot-swap) returns new
        mock_backend_factory.side_effect = [original_backend, new_backend]

        # /ai → 1 (endpoint) → Enter (default URL) → Enter (default model) → exit
        with patch("builtins.input",
                   side_effect=["/ai", "1", "", "", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1", experimental=True)

        # create_backend called twice: startup + hot-swap
        assert mock_backend_factory.call_count == 2
        # Persona was updated for the hot-swap call
        swap_call_persona = mock_backend_factory.call_args_list[1][0][0]
        assert swap_call_persona.ai_api_type == "openai"
        assert swap_call_persona.ai_base_url == "http://localhost:55128"

    @patch("iconfucius.cli.chat._persist_ai_config")
    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_ai_reset_hotswap(self, mock_load, mock_backend_factory,
                               mock_startup, mock_persist,
                               tmp_path, monkeypatch, capsys):
        """/ai reset hot-swaps back to default claude backend."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(
            name="IConfucius",
            ai_api_type="openai",
            ai_model="llama-3",
            ai_base_url="http://localhost:55128",
        )
        mock_load.return_value = persona
        original_backend = MagicMock()
        original_backend.model = "llama-3"
        reset_backend = MagicMock()
        reset_backend.model = DEFAULT_MODEL
        mock_backend_factory.side_effect = [original_backend, reset_backend]

        # Accept non-default warning → /ai reset → exit
        with patch("builtins.input",
                   side_effect=["Y", "/ai reset", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1", experimental=True)

        assert mock_backend_factory.call_count == 2
        swap_call_persona = mock_backend_factory.call_args_list[1][0][0]
        assert swap_call_persona.ai_api_type == "claude"
        assert swap_call_persona.ai_model == DEFAULT_MODEL
        assert swap_call_persona.ai_base_url == ""

    @patch("iconfucius.cli.chat._persist_ai_config")
    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_ai_interactive_reset_hotswap(self, mock_load, mock_backend_factory,
                                           mock_startup, mock_persist,
                                           tmp_path, monkeypatch, capsys):
        """/ai interactive reset (menu option 3) hot-swaps to default."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(
            name="IConfucius",
            ai_api_type="openai",
            ai_model="llama-3",
            ai_base_url="http://localhost:55128",
        )
        mock_load.return_value = persona
        original_backend = MagicMock()
        original_backend.model = "llama-3"
        original_backend.list_models.return_value = []
        reset_backend = MagicMock()
        reset_backend.model = DEFAULT_MODEL
        mock_backend_factory.side_effect = [original_backend, reset_backend]

        # Accept non-default warning → /ai → 3 (reset) → exit
        with patch("builtins.input",
                   side_effect=["Y", "/ai", "3", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1", experimental=True)

        assert mock_backend_factory.call_count == 2
        swap_call_persona = mock_backend_factory.call_args_list[1][0][0]
        assert swap_call_persona.ai_api_type == "claude"
        assert swap_call_persona.ai_base_url == ""

    @patch("iconfucius.cli.chat._persist_ai_config")
    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_ai_endpoint_no_restart_message(self, mock_load,
                                             mock_backend_factory,
                                             mock_startup, mock_persist,
                                             tmp_path, monkeypatch, capsys):
        """Endpoint change does not print 'Restart' message."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = DEFAULT_MODEL
        mock_backend_factory.return_value = backend

        with patch("builtins.input",
                   side_effect=["/ai", "1", "http://my-server:8080", "mymodel", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1", experimental=True)

        captured = capsys.readouterr().out
        assert "Restart" not in captured
        assert "http://my-server:8080" in captured


# ---------------------------------------------------------------------------
# Readline input history
# ---------------------------------------------------------------------------


class TestReadlineEnabled:
    """Verify readline is imported for input history and line editing."""

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_readline_imported_during_chat(self, mock_load,
                                            mock_backend_factory,
                                            mock_startup,
                                            tmp_path, monkeypatch):
        """readline is imported so input() supports arrow keys."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-opus-4-6"
        mock_backend_factory.return_value = backend

        import sys
        # Remove readline from loaded modules to verify it gets imported
        saved = sys.modules.pop("readline", None)
        try:
            with patch("builtins.input", side_effect=EOFError):
                from iconfucius.cli.chat import run_chat
                run_chat("iconfucius", "bot-1")

            assert "readline" in sys.modules
        finally:
            if saved is not None:
                sys.modules["readline"] = saved

    def test_readline_import_failure_is_silent(self):
        """If readline is unavailable, reloading the chat module doesn't raise."""
        import sys
        import importlib
        import iconfucius.cli.chat as chat_module

        saved = sys.modules.get("readline")
        # Make import readline raise ImportError
        sys.modules["readline"] = None
        try:
            # Reload triggers the try/except import readline block —
            # should complete without raising.
            importlib.reload(chat_module)
        finally:
            if saved is not None:
                sys.modules["readline"] = saved
            elif "readline" in sys.modules:
                del sys.modules["readline"]
            # Restore module to clean state
            importlib.reload(chat_module)


# ---------------------------------------------------------------------------
# Verbose flag propagation
# ---------------------------------------------------------------------------


class TestVerboseFlag:
    """Ensure --verbose is wired through run_chat."""

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Greeting", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    @patch("iconfucius.config.set_verbose")
    def test_set_verbose_called(self, mock_set_verbose, mock_load,
                                mock_backend_factory, mock_startup,
                                tmp_path, monkeypatch):
        """run_chat(verbose=True) calls set_verbose(True)."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        mock_backend_factory.return_value = MagicMock()

        from iconfucius.cli.chat import run_chat
        with patch("builtins.input", side_effect=EOFError):
            run_chat("iconfucius", "bot-1", verbose=True)

        mock_set_verbose.assert_called_once_with(True)

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Greeting", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    @patch("iconfucius.config.set_verbose")
    def test_set_verbose_false_by_default(self, mock_set_verbose, mock_load,
                                          mock_backend_factory, mock_startup,
                                          tmp_path, monkeypatch):
        """run_chat() without verbose calls set_verbose(False)."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        mock_backend_factory.return_value = MagicMock()

        from iconfucius.cli.chat import run_chat
        with patch("builtins.input", side_effect=EOFError):
            run_chat("iconfucius", "bot-1")

        mock_set_verbose.assert_called_once_with(False)

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Greeting", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    @patch("iconfucius.cli.chat.execute_tool", return_value={
        "status": "ok", "config_exists": True, "wallet_exists": True,
        "env_exists": True, "has_api_key": True, "ready": True,
    })
    def test_verbose_passed_to_run_all_balances(self, mock_exec, mock_load,
                                                 mock_backend_factory,
                                                 mock_startup,
                                                 tmp_path, monkeypatch,
                                                 capsys):
        """run_chat(verbose=True) passes verbose=True to run_all_balances."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n'
            '[bots.bot-1]\ndescription = "Bot 1"\n'
            '[bots.bot-2]\ndescription = "Bot 2"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        mock_backend_factory.return_value = backend

        wallet_data = {"_display": "Wallet: 50,000 sats", "balance_sats": 50000}

        with patch("builtins.input", side_effect=["", "hello", EOFError]), \
             patch("iconfucius.cli.balance.run_wallet_balance",
                   return_value=wallet_data), \
             patch("iconfucius.cli.balance.run_all_balances",
                   return_value={"_display": "Holdings", "bots": []}) \
                as mock_all_bal, \
             patch("iconfucius.cli.concurrent.set_progress_callback"), \
             patch("iconfucius.cli.concurrent.set_status_callback"), \
             patch("iconfucius.cli.chat._run_tool_loop",
                   side_effect=EOFError):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1", verbose=True)

        mock_all_bal.assert_called_once()
        _, kwargs = mock_all_bal.call_args
        assert kwargs.get("verbose") is True


# ---------------------------------------------------------------------------
# Bot holdings injection
# ---------------------------------------------------------------------------


class TestBotHoldingsDisplay:
    """Bot holdings are displayed at startup but NOT injected into system prompt."""

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Wise greeting quote", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    @patch("iconfucius.cli.chat.execute_tool", return_value={
        "status": "ok", "config_exists": True, "wallet_exists": True,
        "env_exists": True, "has_api_key": True, "ready": True,
    })
    def test_holdings_displayed_not_injected(self, mock_exec, mock_load,
                                              mock_backend_factory,
                                              mock_startup,
                                              tmp_path, monkeypatch, capsys):
        """Bot holdings are printed to terminal but not in system prompt."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n'
            '[bots.bot-1]\ndescription = "Bot 1"\n'
            '[bots.bot-2]\ndescription = "Bot 2"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        mock_backend_factory.return_value = backend

        wallet_data = {"_display": "Wallet: 50,000 sats", "balance_sats": 50000}
        bot_data = {
            "bots": [
                {
                    "name": "bot-1", "odin_sats": 10000,
                    "tokens": [
                        {"ticker": "RUNE", "id": "29m8", "balance": 5.0,
                         "div": 8, "value_sats": 3000},
                    ],
                },
                {"name": "bot-2", "odin_sats": 20000, "tokens": []},
            ],
            "totals": {"portfolio_sats": 83000},
            "_display": "Bot holdings table here",
        }

        captured_system = {}

        def spy_run_tool_loop(backend, messages, system, tools, persona_name,
                              **kwargs):
            """Spy wrapper around the tool loop for testing."""
            captured_system["value"] = system
            raise EOFError  # exit immediately

        with patch("builtins.input", side_effect=["", "hello", EOFError]), \
             patch("iconfucius.cli.balance.run_wallet_balance",
                   return_value=wallet_data), \
             patch("iconfucius.cli.balance.run_all_balances",
                   return_value=bot_data), \
             patch("iconfucius.cli.concurrent.set_progress_callback"), \
             patch("iconfucius.cli.concurrent.set_status_callback"), \
             patch("iconfucius.cli.chat._run_tool_loop",
                   side_effect=spy_run_tool_loop):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1")

        # Holdings displayed to terminal
        captured = capsys.readouterr().out
        assert "Bot holdings table here" in captured

        # But NOT injected into system prompt
        system = captured_system.get("value", "")
        assert "Bot Holdings" not in system
        assert "Wallet Balance" not in system


# ---------------------------------------------------------------------------
# /model slash command
# ---------------------------------------------------------------------------


class TestModelSlashCommand:
    """Tests for /model show and /model <name> hot-swap in the chat loop."""

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_model_show(self, mock_load, mock_backend_factory,
                        mock_startup, tmp_path, monkeypatch, capsys):
        """/model (no args) prints the current model name."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = []
        mock_backend_factory.return_value = backend

        # /model then exit
        with patch("builtins.input", side_effect=["/model", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1")

        captured = capsys.readouterr().out
        assert "Current model: claude-sonnet-4-6" in captured

    @patch("iconfucius.cli.chat._persist_ai_model")
    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_model_switch(self, mock_load, mock_backend_factory,
                          mock_startup, mock_persist,
                          tmp_path, monkeypatch, capsys):
        """/model <name> hot-swaps the backend model and persists."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        mock_backend_factory.return_value = backend

        with patch("builtins.input",
                   side_effect=["/model claude-haiku-4-5-20251001", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1")

        assert backend.model == "claude-haiku-4-5-20251001"
        mock_persist.assert_called_once_with("claude-haiku-4-5-20251001")
        captured = capsys.readouterr().out
        assert "Model changed to: claude-haiku-4-5-20251001" in captured

    @patch("iconfucius.cli.chat._persist_ai_model")
    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_model_interactive_decline(self, mock_load, mock_backend_factory,
                                        mock_startup,
                                        mock_persist,
                                        tmp_path, monkeypatch, capsys):
        """/model lists models; user says N; no change."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = [
            ("claude-opus-4-6", "Claude Opus 4.6"),
            ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ]
        mock_backend_factory.return_value = backend

        # /model → decline → exit
        with patch("builtins.input", side_effect=["/model", "n", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1")

        captured = capsys.readouterr().out
        assert "Available models:" in captured
        assert "Claude Opus 4.6" in captured
        mock_persist.assert_not_called()
        assert backend.model == "claude-sonnet-4-6"

    @patch("iconfucius.cli.chat._persist_ai_model")
    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_model_interactive_select(self, mock_load, mock_backend_factory,
                                       mock_startup,
                                       mock_persist,
                                       tmp_path, monkeypatch, capsys):
        """/model interactive: user picks a model, backend updated."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = [
            ("claude-opus-4-6", "Claude Opus 4.6"),
            ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ]
        mock_backend_factory.return_value = backend

        # /model → y → 1 → exit
        with patch("builtins.input",
                   side_effect=["/model", "y", "1", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1")

        assert backend.model == "claude-opus-4-6"
        mock_persist.assert_called_once_with("claude-opus-4-6")
        captured = capsys.readouterr().out
        assert "Model changed to: claude-opus-4-6" in captured

    @patch("iconfucius.cli.chat._generate_startup",
           return_value=("Hello!", "Goodbye!"))
    @patch("iconfucius.cli.chat.create_backend")
    @patch("iconfucius.cli.chat.load_persona")
    def test_model_api_failure_fallback(self, mock_load, mock_backend_factory,
                                         mock_startup,
                                         tmp_path, monkeypatch, capsys):
        """/model with empty list_models shows current only, no prompt."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        persona = _make_persona(name="IConfucius")
        mock_load.return_value = persona
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = []
        mock_backend_factory.return_value = backend

        # /model → exit (no prompt expected since list is empty)
        with patch("builtins.input", side_effect=["/model", EOFError]):
            from iconfucius.cli.chat import run_chat
            run_chat("iconfucius", "bot-1")

        captured = capsys.readouterr().out
        assert "Current model: claude-sonnet-4-6" in captured
        assert "Available models:" not in captured


# ---------------------------------------------------------------------------
# _handle_model_interactive (unit tests)
# ---------------------------------------------------------------------------


class TestHandleModelInteractive:
    """Unit tests for _handle_model_interactive."""

    @patch("iconfucius.cli.chat._persist_ai_model")
    def test_selection_applies_and_persists(self, mock_persist, capsys):
        """Selecting a model updates backend.model and calls _persist_ai_model."""
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = [
            ("claude-opus-4-6", "Claude Opus 4.6"),
            ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ]

        with patch("builtins.input", side_effect=["y", "1"]):
            _handle_model_interactive(backend)

        assert backend.model == "claude-opus-4-6"
        mock_persist.assert_called_once_with("claude-opus-4-6")
        captured = capsys.readouterr().out
        assert "Model changed to: claude-opus-4-6" in captured

    def test_empty_model_list_shows_current_only(self, capsys):
        """Empty list_models shows current model, no selection prompt."""
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = []

        _handle_model_interactive(backend)

        captured = capsys.readouterr().out
        assert "Current model: claude-sonnet-4-6" in captured
        assert "Available models:" not in captured

    def test_invalid_number_does_not_change(self, capsys):
        """Non-numeric or out-of-range input does not change the model."""
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = [
            ("claude-opus-4-6", "Claude Opus 4.6"),
        ]

        with patch("builtins.input", side_effect=["y", "99"]):
            _handle_model_interactive(backend)

        assert backend.model == "claude-sonnet-4-6"
        captured = capsys.readouterr().out
        assert "Invalid selection" in captured

    def test_non_numeric_input_does_not_change(self, capsys):
        """Non-numeric input does not change the model."""
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = [
            ("claude-opus-4-6", "Claude Opus 4.6"),
        ]

        with patch("builtins.input", side_effect=["y", "abc"]):
            _handle_model_interactive(backend)

        assert backend.model == "claude-sonnet-4-6"
        captured = capsys.readouterr().out
        assert "Invalid selection" in captured

    def test_keyboard_interrupt_on_confirm(self, capsys):
        """KeyboardInterrupt on confirm prompt returns gracefully."""
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = [
            ("claude-opus-4-6", "Claude Opus 4.6"),
        ]

        with patch("builtins.input", side_effect=KeyboardInterrupt):
            _handle_model_interactive(backend)

        assert backend.model == "claude-sonnet-4-6"

    def test_keyboard_interrupt_on_number(self, capsys):
        """KeyboardInterrupt on number prompt returns gracefully."""
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = [
            ("claude-opus-4-6", "Claude Opus 4.6"),
        ]

        with patch("builtins.input", side_effect=["y", KeyboardInterrupt]):
            _handle_model_interactive(backend)

        assert backend.model == "claude-sonnet-4-6"

    def test_current_model_marked_with_star(self, capsys):
        """Current model is marked with * in the list."""
        backend = MagicMock()
        backend.model = "claude-sonnet-4-6"
        backend.list_models.return_value = [
            ("claude-opus-4-6", "Claude Opus 4.6"),
            ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ]

        with patch("builtins.input", side_effect=["n"]):
            _handle_model_interactive(backend)

        captured = capsys.readouterr().out
        # The sonnet line should have a *, opus should not
        for line in captured.splitlines():
            if "claude-sonnet-4-6" in line and "Current model" not in line:
                assert "*" in line
            if "claude-opus-4-6" in line:
                assert "*" not in line


# ---------------------------------------------------------------------------
# _persist_ai_model
# ---------------------------------------------------------------------------


class TestPersistAiConfig:
    """Tests for _persist_ai_config writing to iconfucius.toml."""

    def test_commented_ai_block(self, tmp_path, monkeypatch):
        """Replaces a commented # [ai] block with an active section."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\ndefault_persona = "iconfucius"\n\n'
            '# [ai]\n'
            '# backend = "claude"\n'
            '# model = "claude-sonnet-4-6"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_config(model="claude-haiku-4-5-20251001")

        content = config.read_text()
        assert 'model = "claude-haiku-4-5-20251001"' in content
        assert "# [ai]" not in content

    def test_existing_ai_section_replaced(self, tmp_path, monkeypatch):
        """Replaces entire [ai] section content."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\nmodel = "claude-sonnet-4-6"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_config(api_type="openai", model="llama-3",
                           base_url="http://localhost:8080")

        content = config.read_text()
        assert 'api_type = "openai"' in content
        assert 'model = "llama-3"' in content
        assert 'base_url = "http://localhost:8080"' in content
        assert "claude-sonnet-4-6" not in content

    def test_no_ai_section(self, tmp_path, monkeypatch):
        """Appends a new [ai] section when none exists."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text('[settings]\ndefault_persona = "iconfucius"\n')
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_config(model="claude-haiku-4-5-20251001")

        content = config.read_text()
        assert 'model = "claude-haiku-4-5-20251001"' in content

    def test_invalidates_config_cache(self, tmp_path, monkeypatch):
        """After persisting, the config cache is cleared."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text('[settings]\n\n[ai]\nmodel = "old"\n')
        cfg._cached_config = {"stale": True}
        cfg._cached_config_path = config

        _persist_ai_config(model="new-model")

        assert cfg._cached_config is None

    def test_reset_removes_section(self, tmp_path, monkeypatch):
        """Empty persist_ai_config removes [ai] section."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\nmodel = "old"\n\n[bots.bot-1]\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_config()  # empty = remove overrides

        content = config.read_text()
        assert "[ai]" not in content
        assert "[bots.bot-1]" in content

    def test_legacy_persist_ai_model(self, tmp_path, monkeypatch):
        """_persist_ai_model still works as a wrapper."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text('[settings]\n')
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_model("claude-haiku-4-5-20251001")

        content = config.read_text()
        assert 'model = "claude-haiku-4-5-20251001"' in content


class TestResetAiConfig:
    """Tests for _reset_ai_config commenting out the [ai] section."""

    def test_comments_out_ai_section(self, tmp_path, monkeypatch):
        """Verify comments out ai section."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\napi_type = "openai"\nbase_url = "http://localhost:8080"\n\n[bots.bot-1]\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _reset_ai_config()

        content = config.read_text()
        assert "# [ai]" in content
        assert '# api_type = "openai"' in content
        assert "[bots.bot-1]" in content


class TestPersistAiTimeout:
    """Tests for _persist_ai_timeout writing timeout to [ai] section."""

    def test_adds_timeout_to_existing_ai(self, tmp_path, monkeypatch):
        """Timeout is added to an existing [ai] section."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\n'
            'api_type = "openai"\n'
            'base_url = "http://localhost:55128"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_timeout(1200)

        content = config.read_text()
        assert "timeout = 1200" in content
        assert 'api_type = "openai"' in content
        assert 'base_url = "http://localhost:55128"' in content

    def test_replaces_existing_timeout(self, tmp_path, monkeypatch):
        """Existing timeout value is replaced."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\n'
            'api_type = "openai"\n'
            'base_url = "http://localhost:55128"\n'
            'timeout = 600\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_timeout(1200)

        content = config.read_text()
        assert "timeout = 1200" in content
        assert "timeout = 600" not in content

    def test_creates_ai_section_if_missing(self, tmp_path, monkeypatch):
        """Creates [ai] section with timeout when none exists."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text('[settings]\n')
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_timeout(1200)

        content = config.read_text()
        assert "timeout = 1200" in content

    def test_default_timeout_removes_key(self, tmp_path, monkeypatch):
        """Setting timeout to default (600) omits the key."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\n'
            'api_type = "openai"\n'
            'base_url = "http://localhost:55128"\n'
            'timeout = 1200\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_timeout(600)  # AI_TIMEOUT_DEFAULT

        content = config.read_text()
        assert "timeout" not in content
        assert 'api_type = "openai"' in content


class TestPersistAiConfigTimeout:
    """Tests for timeout handling across AI config changes."""

    def test_ai_change_drops_timeout(self, tmp_path, monkeypatch):
        """Switching AI endpoint drops existing timeout."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\n'
            'api_type = "openai"\n'
            'base_url = "http://localhost:55128"\n'
            'timeout = 1200\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_config(api_type="openai",
                           base_url="http://other-server:8080")

        content = config.read_text()
        assert "timeout" not in content
        assert "http://other-server:8080" in content

    def test_reset_drops_timeout(self, tmp_path, monkeypatch):
        """Reset to default drops timeout."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\n'
            'api_type = "openai"\n'
            'timeout = 1200\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_config()  # reset to default

        content = config.read_text()
        assert "timeout" not in content
        assert "[ai]" not in content

    def test_model_change_preserves_timeout(self, tmp_path, monkeypatch):
        """Model change via _persist_ai_model preserves existing timeout."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\n'
            'model = "old-model"\n'
            'timeout = 1200\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_model("new-model")

        content = config.read_text()
        assert 'model = "new-model"' in content
        assert "timeout = 1200" in content

    def test_malformed_timeout_dropped(self, tmp_path, monkeypatch):
        """Non-numeric timeout is dropped when preserving config."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\n'
            'api_type = "openai"\n'
            'base_url = "http://localhost:55128"\n'
            'timeout = "not-a-number"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_config(api_type="openai",
                           base_url="http://localhost:55128",
                           keep_timeout=True)

        content = config.read_text()
        assert "timeout" not in content
        assert "http://localhost:55128" in content

    def test_negative_timeout_dropped(self, tmp_path, monkeypatch):
        """Negative timeout is dropped when preserving config."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\n'
            'api_type = "openai"\n'
            'base_url = "http://localhost:55128"\n'
            'timeout = -5\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        _persist_ai_config(api_type="openai",
                           base_url="http://localhost:55128",
                           keep_timeout=True)

        content = config.read_text()
        assert "timeout" not in content

    def test_config_can_be_reverted_after_failed_hotswap(self, tmp_path, monkeypatch):
        """_persist_ai_config can restore previous config after a failed hot-swap."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text(
            '[settings]\n\n[ai]\n'
            'api_type = "openai"\n'
            'base_url = "http://old-server:8080"\n'
        )
        cfg._cached_config = None
        cfg._cached_config_path = None

        # Simulate /ai switching to a new endpoint that persists first
        _persist_ai_config(api_type="openai",
                           base_url="http://broken-server:9999")

        content = config.read_text()
        assert "http://broken-server:9999" in content

        # Simulate the revert that happens when create_backend fails
        _persist_ai_config(api_type="openai",
                           base_url="http://old-server:8080",
                           keep_timeout=True)

        content = config.read_text()
        assert "http://old-server:8080" in content
        assert "broken-server" not in content


class TestPromptIncreaseTimeout:
    """Tests for the timeout increase wizard."""

    def test_user_accepts(self, tmp_path, monkeypatch):
        """User accepts timeout increase."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text('[settings]\n\n[ai]\napi_type = "openai"\n')
        cfg._cached_config = None
        cfg._cached_config_path = None

        with patch("builtins.input", return_value="y"):
            result = _prompt_increase_timeout()

        assert "1200" in result
        content = config.read_text()
        assert "timeout = 1200" in content

    def test_user_declines(self, tmp_path, monkeypatch):
        """User declines timeout increase."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text('[settings]\n\n[ai]\napi_type = "openai"\n')
        cfg._cached_config = None
        cfg._cached_config_path = None

        with patch("builtins.input", return_value="n"):
            result = _prompt_increase_timeout()

        assert result == ""
        content = config.read_text()
        assert "timeout" not in content

    def test_user_hits_enter_accepts(self, tmp_path, monkeypatch):
        """Pressing Enter (empty) accepts by default."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        config = tmp_path / "iconfucius.toml"
        config.write_text('[settings]\n\n[ai]\napi_type = "openai"\n')
        cfg._cached_config = None
        cfg._cached_config_path = None

        with patch("builtins.input", return_value=""):
            result = _prompt_increase_timeout()

        assert "1200" in result
        content = config.read_text()
        assert "timeout = 1200" in content

    def test_format_api_error_timeout(self):
        """Timeout errors trigger the wizard prompt."""
        e = ConnectionError(
            "HTTPConnectionPool(host='localhost', port=55128): "
            "Read timed out. (read timeout=600)"
        )
        with patch("iconfucius.cli.chat._prompt_increase_timeout",
                   return_value="Timeout updated to 1200s.") as mock:
            result = _format_api_error(e)
        mock.assert_called_once()
        assert "timed out" in result.lower()
        assert "1200" in result


class TestCheckPypiVersion:
    """Tests for _check_pypi_version — PyPI + GitHub release notes fetching."""

    def test_returns_none_when_up_to_date(self):
        """No update when PyPI version matches installed."""
        import iconfucius
        pypi_json = json.dumps({"info": {"version": iconfucius.__version__}}).encode()
        fake_resp = MagicMock()
        fake_resp.read.return_value = pypi_json
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)

        with patch("iconfucius.cli.chat.urlopen", return_value=fake_resp):
            version, notes = _check_pypi_version()
        assert version is None
        assert notes == ""

    def test_returns_latest_version_when_newer(self):
        """Returns latest version and empty notes when GitHub release missing."""
        pypi_json = json.dumps({"info": {"version": "99.0.0"}}).encode()
        fake_pypi = MagicMock()
        fake_pypi.read.return_value = pypi_json
        fake_pypi.__enter__ = lambda s: s
        fake_pypi.__exit__ = MagicMock(return_value=False)

        from urllib.error import URLError
        def mock_urlopen(url, **kwargs):
            """Mock urllib.request.urlopen for testing."""
            if "pypi.org" in url:
                return fake_pypi
            # GitHub release not found
            raise URLError("Not Found")

        with patch("iconfucius.cli.chat.urlopen", side_effect=mock_urlopen):
            version, notes = _check_pypi_version()
        assert version == "99.0.0"
        assert notes == ""

    def test_returns_release_notes_from_github(self):
        """Fetches release notes from GitHub releases API."""
        pypi_json = json.dumps({"info": {"version": "99.0.0"}}).encode()
        gh_json = json.dumps({"body": "- Feature A\n- Bug fix B"}).encode()

        def mock_urlopen(url, **kwargs):
            """Mock urllib.request.urlopen for testing."""
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            if "pypi.org" in url:
                resp.read.return_value = pypi_json
            else:
                resp.read.return_value = gh_json
            return resp

        with patch("iconfucius.cli.chat.urlopen", side_effect=mock_urlopen):
            version, notes = _check_pypi_version()
        assert version == "99.0.0"
        assert "Feature A" in notes
        assert "Bug fix B" in notes

    def test_returns_none_on_network_error(self):
        """Gracefully returns None on network failure."""
        from urllib.error import URLError
        with patch("iconfucius.cli.chat.urlopen", side_effect=URLError("offline")):
            version, notes = _check_pypi_version()
        assert version is None
        assert notes == ""


class TestHandleUpgrade:
    """Tests for _handle_upgrade — pip upgrade + re-exec flow."""

    def test_prints_error_on_pip_failure(self, capsys):
        """If pip fails, prints error and returns (no re-exec)."""
        failed = MagicMock(returncode=1, stderr="Permission denied")
        with patch("subprocess.run", return_value=failed) as mock_run:
            with patch("os.execvp") as mock_exec:
                _handle_upgrade()

        mock_run.assert_called_once()
        mock_exec.assert_not_called()
        output = capsys.readouterr().out
        assert "Upgrade failed" in output
        assert "Permission denied" in output

    def test_calls_pip_install_upgrade(self):
        """Calls pip install --upgrade iconfucius."""
        import sys
        success = MagicMock(returncode=0)

        pypi_json = json.dumps({"info": {"version": "99.0.0"}}).encode()
        fake_resp = MagicMock()
        fake_resp.read.return_value = pypi_json
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)

        with patch("subprocess.run", return_value=success) as mock_run:
            with patch("os.execvp") as mock_exec:
                with patch("iconfucius.cli.chat.urlopen", return_value=fake_resp):
                    _handle_upgrade()

        args = mock_run.call_args[0][0]
        assert args == [sys.executable, "-m", "pip", "install", "--upgrade", "iconfucius"]
        mock_exec.assert_called_once()

    def test_reexecs_process_on_success(self):
        """On successful pip upgrade, re-execs the process via os.execvp."""
        import sys
        success = MagicMock(returncode=0)

        from urllib.error import URLError
        with patch("subprocess.run", return_value=success):
            with patch("os.execvp") as mock_exec:
                with patch("iconfucius.cli.chat.urlopen", side_effect=URLError("x")):
                    _handle_upgrade()

        mock_exec.assert_called_once_with(sys.argv[0], sys.argv)
