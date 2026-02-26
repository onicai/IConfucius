"""Security-focused tests — wrong amounts, wrong accounts, edge cases.

These tests verify that financial operations handle edge cases safely
and never silently send wrong amounts or to wrong addresses.
"""

from unittest.mock import MagicMock, patch

import pytest

from iconfucius.skills.executor import (
    _usd_to_sats,
    _usd_to_tokens,
    execute_tool,
)

# Valid bech32 address for tests that go through is_bech32_btc_address()
_BTC_ADDR = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
_FAKE_PEM = "fake.pem"
from iconfucius.cli.chat import (
    _describe_tool_call,
    _run_tool_loop,
)


# ---------------------------------------------------------------------------
# Helper: build a tool block for the chat pre-conversion tests
# ---------------------------------------------------------------------------

def _make_tool_response(name, tool_input, *, tool_id="id_1"):
    """Build a mock LLM response with a single tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = tool_id
    tool_block.name = name
    tool_block.input = dict(tool_input)  # shallow copy

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Done."

    resp_tool = MagicMock()
    resp_tool.content = [tool_block]
    resp_text = MagicMock()
    resp_text.content = [text_block]
    return resp_tool, resp_text


# ===================================================================
# 1. USD-to-sats conversion edge cases
# ===================================================================

class TestUsdToSatsEdgeCases:
    """Verify _usd_to_sats handles dangerous inputs correctly."""

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    def test_negative_usd_returns_negative_sats(self, _mock):
        """Negative USD produces negative sats — callers must validate."""
        result = _usd_to_sats(-10.0)
        assert result == -10_000

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    def test_zero_usd_returns_zero(self, _mock):
        """Verify zero usd returns zero."""
        assert _usd_to_sats(0.0) == 0

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=0.0)
    def test_zero_rate_raises(self, _mock):
        """Division by zero rate must raise, not silently return infinity."""
        with pytest.raises(ZeroDivisionError):
            _usd_to_sats(10.0)

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=-100_000.0)
    def test_negative_rate_inverts_sign(self, _mock):
        """Negative rate flips the sign — callers must validate."""
        result = _usd_to_sats(10.0)
        assert result < 0

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    def test_very_small_usd_truncates_to_zero(self, _mock):
        """$0.000001 at $100k/BTC → 0 sats (int truncation)."""
        result = _usd_to_sats(0.000001)
        assert result == 0

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    def test_fractional_cent(self, _mock):
        """$0.01 at $100k/BTC → 10 sats."""
        result = _usd_to_sats(0.01)
        assert result == 10

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    def test_large_usd_no_overflow(self, _mock):
        """$1M at $100k/BTC → 10 BTC = 1,000,000,000 sats."""
        result = _usd_to_sats(1_000_000.0)
        assert result == 1_000_000_000  # 10 BTC
        assert result < 2**63  # fits in 64-bit signed int

    @patch("iconfucius.config.get_btc_to_usd_rate",
           side_effect=Exception("API offline"))
    def test_rate_api_offline_raises(self, _mock):
        """Verify rate api offline raises."""
        with pytest.raises(Exception, match="API offline"):
            _usd_to_sats(10.0)


# ===================================================================
# 2. USD-to-tokens conversion edge cases
# ===================================================================

class TestUsdToTokensEdgeCases:
    """Verify _usd_to_tokens handles dangerous inputs correctly."""

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 0, "divisibility": 8})
    def test_zero_token_price_raises(self, _mock_fetch, _mock_rate):
        """Zero price → ValueError (not silent zero or infinity)."""
        with pytest.raises(ValueError, match="Could not fetch price"):
            _usd_to_tokens(10.0, "fake-token")

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data", return_value=None)
    def test_missing_token_data_raises(self, _mock_fetch, _mock_rate):
        """Verify missing token data raises."""
        with pytest.raises(ValueError, match="Could not fetch price"):
            _usd_to_tokens(10.0, "nonexistent")

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "divisibility": 8})
    def test_negative_usd_produces_negative_tokens(self, _f, _r):
        """Negative USD → negative tokens — callers must validate."""
        result = _usd_to_tokens(-5.0, "29m8")
        assert result < 0

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "divisibility": 8})
    def test_large_usd_produces_positive_tokens(self, _f, _r):
        """$100k at realistic price → large but valid token count."""
        result = _usd_to_tokens(100_000.0, "29m8")
        assert result > 0
        assert result < 2**63

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1, "divisibility": 8})
    def test_bogus_price_raises_overflow_guard(self, _f, _r):
        """price=1 + div=8 + large USD → exceeds 2^63 → ValueError.

        Guards against stale/bogus price data that would produce absurd
        token amounts and potentially cause loss of funds.
        """
        with pytest.raises(ValueError, match="Token amount too large"):
            _usd_to_tokens(100_000.0, "29m8")

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500})
    def test_missing_divisibility_defaults_to_8(self, _f, _r):
        """Missing divisibility key defaults to 8."""
        result = _usd_to_tokens(5.0, "29m8")
        assert result > 0

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "divisibility": 0})
    def test_divisibility_zero(self, _f, _r):
        """divisibility=0 means tokens are indivisible (10^0 = 1)."""
        result = _usd_to_tokens(5.0, "29m8")
        # sats=5000, raw = 5000 * 1e6 * 1 / 1500 = 3333333
        assert result > 0


# ===================================================================
# 3. Handler-level amount/address validation
# ===================================================================

class TestFundHandlerValidation:
    """Test _handle_fund validates inputs before moving money."""

    def test_missing_amount_and_usd(self):
        """Both amount and amount_usd missing → error."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("fund", {"bot_name": "bot-1"})
        assert result["status"] == "error"
        assert "amount" in result["error"].lower()

    def test_missing_bot(self):
        """No bot specified → error."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("fund", {"amount": 5000})
        assert result["status"] == "error"

    @patch("iconfucius.config.get_btc_to_usd_rate",
           side_effect=Exception("rate offline"))
    def test_usd_conversion_failure_returns_error(self, _mock):
        """When rate API is down, fund returns error — doesn't proceed."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("fund", {
                "bot_name": "bot-1", "amount_usd": 10.0,
            })
        assert result["status"] == "error"
        assert "USD conversion failed" in result["error"]

    def test_no_wallet_returns_error(self):
        """Verify no wallet returns error."""
        with patch("iconfucius.config.require_wallet", return_value=False):
            result = execute_tool("fund", {
                "bot_name": "bot-1", "amount": 5000,
            })
        assert result["status"] == "error"
        assert "wallet" in result["error"].lower()

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    def test_amount_takes_priority_over_usd(self, _mock):
        """When both amount and amount_usd provided, amount wins."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            with patch("iconfucius.cli.fund.run_fund",
                       return_value={"status": "ok", "funded": ["bot-1"],
                                     "failed": [], "amount": 5000}):
                result = execute_tool("fund", {
                    "bot_name": "bot-1", "amount": 5000, "amount_usd": 99.0,
                })
        assert result["status"] == "ok"
        # Should have used 5000 sats, not converted from $99


class TestWithdrawHandlerValidation:
    """Test _handle_withdraw validates inputs before moving money."""

    def test_missing_amount_and_usd(self):
        """Verify missing amount and usd."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("withdraw", {"bot_name": "bot-1"})
        assert result["status"] == "error"
        assert "amount" in result["error"].lower()

    def test_missing_bot(self):
        """Verify missing bot."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("withdraw", {"amount": "5000"})
        assert result["status"] == "error"

    @patch("iconfucius.config.get_btc_to_usd_rate",
           side_effect=Exception("offline"))
    def test_usd_conversion_failure(self, _mock):
        """Verify usd conversion failure."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("withdraw", {
                "bot_name": "bot-1", "amount_usd": 10.0,
            })
        assert result["status"] == "error"
        assert "USD conversion failed" in result["error"]

    def test_no_wallet(self):
        """Verify no wallet."""
        with patch("iconfucius.config.require_wallet", return_value=False):
            result = execute_tool("withdraw", {
                "bot_name": "bot-1", "amount": "5000",
            })
        assert result["status"] == "error"


class TestWalletSendHandlerValidation:
    """Test _handle_wallet_send validates inputs before moving money."""

    def test_missing_amount_and_address(self):
        """Verify missing amount and address."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("wallet_send", {})
        assert result["status"] == "error"

    def test_missing_address(self):
        """Verify missing address."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("wallet_send", {"amount": "5000"})
        assert result["status"] == "error"
        assert "address" in result["error"].lower()

    def test_missing_amount(self):
        """Verify missing amount."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("wallet_send", {"address": "bc1qtest"})
        assert result["status"] == "error"
        assert "amount" in result["error"].lower()

    def test_empty_address(self):
        """Verify empty address."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("wallet_send", {
                "amount": "5000", "address": "",
            })
        assert result["status"] == "error"

    @patch("iconfucius.config.get_btc_to_usd_rate",
           side_effect=Exception("offline"))
    def test_usd_conversion_failure(self, _mock):
        """Verify usd conversion failure."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("wallet_send", {
                "amount_usd": 10.0, "address": "bc1qtest",
            })
        assert result["status"] == "error"
        assert "USD conversion failed" in result["error"]

    def test_no_wallet(self):
        """Verify no wallet."""
        with patch("iconfucius.config.require_wallet", return_value=False):
            result = execute_tool("wallet_send", {
                "amount": "5000", "address": "bc1qtest",
            })
        assert result["status"] == "error"


class TestWalletSendBtcMinimum:
    """Test that wallet_send rejects BTC sends below 50,000 sats."""

    def test_below_minimum_returns_error(self):
        """14,437 sats is below 50,000 minimum for bc1 addresses."""
        with patch("iconfucius.config.require_wallet", return_value=_FAKE_PEM):
            result = execute_tool("wallet_send", {
                "amount": "14437", "address": _BTC_ADDR,
            })
        assert result["status"] == "error"
        assert result["minimum_sats"] == 50_000
        assert "14,437" in result["error"]

    def test_exact_minimum_passes_validation(self):
        """50,000 sats should pass the minimum check (may fail later at CLI)."""
        with patch("iconfucius.config.require_wallet", return_value=_FAKE_PEM):
            result = execute_tool("wallet_send", {
                "amount": "50000", "address": _BTC_ADDR,
            })
        # Should NOT be the minimum error
        assert "minimum_sats" not in result

    def test_ic_principal_no_minimum_check(self):
        """Sends to IC principals should not enforce the BTC minimum."""
        with patch("iconfucius.config.require_wallet", return_value=_FAKE_PEM):
            result = execute_tool("wallet_send", {
                "amount": "5000",
                "address": "rrkah-fqaaa-aaaaa-aaaaq-cai",
            })
        assert "minimum_sats" not in result

    def test_amount_all_bypasses_minimum(self):
        """'all' should bypass the minimum check (minter handles it)."""
        with patch("iconfucius.config.require_wallet", return_value=_FAKE_PEM):
            result = execute_tool("wallet_send", {
                "amount": "all", "address": _BTC_ADDR,
            })
        assert "minimum_sats" not in result

    def test_usd_amount_below_minimum_returns_error(self):
        """$10 at ~$69,200/BTC converts to ~14,450 sats — below 50,000 minimum."""
        with (
            patch("iconfucius.config.require_wallet", return_value=_FAKE_PEM),
            patch("iconfucius.config.get_btc_to_usd_rate", return_value=69_200.0),
        ):
            result = execute_tool("wallet_send", {
                "amount_usd": 10.0, "address": _BTC_ADDR,
            })
        assert result["status"] == "error"
        assert result["minimum_sats"] == 50_000


class TestTradeBuyHandlerValidation:
    """Test _handle_trade_buy validates all required params."""

    def test_missing_token_id(self):
        """Verify missing token id."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_buy", {
                "amount": 5000, "bot_name": "bot-1",
            })
        assert result["status"] == "error"
        assert "token_id" in result["error"]

    def test_missing_amount(self):
        """Verify missing amount."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_buy", {
                "token_id": "29m8", "bot_name": "bot-1",
            })
        assert result["status"] == "error"

    def test_missing_bot(self):
        """Verify missing bot."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_buy", {
                "token_id": "29m8", "amount": 5000,
            })
        assert result["status"] == "error"

    @patch("iconfucius.config.get_btc_to_usd_rate",
           side_effect=Exception("offline"))
    def test_usd_conversion_failure(self, _mock):
        """Verify usd conversion failure."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_buy", {
                "token_id": "29m8", "amount_usd": 10.0, "bot_name": "bot-1",
            })
        assert result["status"] == "error"
        assert "USD conversion failed" in result["error"]


class TestTradeSellHandlerValidation:
    """Test _handle_trade_sell validates all required params."""

    def test_missing_token_id(self):
        """Verify missing token id."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_sell", {
                "amount": 5000, "bot_name": "bot-1",
            })
        assert result["status"] == "error"

    def test_missing_amount(self):
        """Verify missing amount."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_sell", {
                "token_id": "29m8", "bot_name": "bot-1",
            })
        assert result["status"] == "error"

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           side_effect=Exception("API down"))
    def test_usd_conversion_with_token_api_failure(self, _f, _r):
        """Verify usd conversion with token api failure."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_sell", {
                "token_id": "29m8", "amount_usd": 10.0, "bot_name": "bot-1",
            })
        assert result["status"] == "error"
        assert "USD conversion failed" in result["error"]


# ===================================================================
# 4. Pre-conversion in chat tool loop — security edge cases
# ===================================================================

class TestPreConversionSecurity:
    """Verify the amount_usd pre-conversion in _run_tool_loop is safe."""

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_withdraw_usd_converted(self, mock_meta, mock_exec, mock_rate):
        """withdraw amount_usd is pre-converted to sats."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "withdraw", {"bot_name": "bot-1", "amount_usd": 10.0})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="y"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        call_args = mock_exec.call_args[0]
        assert call_args[0] == "withdraw"
        assert call_args[1]["amount"] == 10_000
        assert "amount_usd" not in call_args[1]

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_trade_buy_usd_converted(self, mock_meta, mock_exec, mock_rate):
        """trade_buy amount_usd is pre-converted to sats."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "trade_buy", {"token_id": "29m8", "amount_usd": 20.0,
                          "bot_name": "bot-1"})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="y"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        call_args = mock_exec.call_args[0]
        assert call_args[1]["amount"] == 20_000
        assert "amount_usd" not in call_args[1]

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_trade_sell_usd_preserved(self, mock_meta, mock_exec):
        """trade_sell amount_usd is NOT pre-converted (needs token conversion)."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "trade_sell", {"token_id": "29m8", "amount_usd": 10.0,
                           "bot_name": "bot-1"})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="y"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        call_args = mock_exec.call_args[0]
        assert call_args[1]["amount_usd"] == 10.0
        assert "amount" not in call_args[1] or call_args[1].get("amount") is None

    @patch("iconfucius.config.get_btc_to_usd_rate",
           side_effect=Exception("rate offline"))
    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_preconvert_rate_failure_passes_usd_through(self, mock_meta,
                                                          mock_exec, mock_rate):
        """When rate API is down, amount_usd passes through to handler."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "fund", {"bot_name": "bot-1", "amount_usd": 10.0})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="y"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        call_args = mock_exec.call_args[0]
        # Pre-conversion failed, so amount_usd still present
        assert call_args[1].get("amount_usd") == 10.0

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_amount_takes_priority_over_amount_usd(self, mock_meta, mock_exec,
                                                     mock_rate):
        """When AI provides both amount and amount_usd, amount wins."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "fund", {"bot_name": "bot-1", "amount": 3000, "amount_usd": 10.0})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="y"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        call_args = mock_exec.call_args[0]
        assert call_args[1]["amount"] == 3000  # not overwritten to 10,000


# ===================================================================
# 5. Bot resolution edge cases
# ===================================================================

class TestBotResolutionSecurity:
    """Verify bots are resolved correctly — no accidental all-bots."""

    def test_empty_args_no_bots(self):
        """Verify empty args no bots."""
        from iconfucius.skills.executor import _resolve_bot_names
        assert _resolve_bot_names({}) == []

    def test_bot_name_none_no_bots(self):
        """Verify bot name none no bots."""
        from iconfucius.skills.executor import _resolve_bot_names
        assert _resolve_bot_names({"bot_name": None}) == []

    def test_bot_names_empty_list_no_bots(self):
        """Verify bot names empty list no bots."""
        from iconfucius.skills.executor import _resolve_bot_names
        assert _resolve_bot_names({"bot_names": []}) == []

    def test_all_bots_false_ignored(self):
        """Verify all bots false ignored."""
        from iconfucius.skills.executor import _resolve_bot_names
        assert _resolve_bot_names({"all_bots": False}) == []

    def test_all_bots_true_resolves_all(self, odin_project):
        """Verify all bots true resolves all."""
        from iconfucius.skills.executor import _resolve_bot_names
        result = _resolve_bot_names({"all_bots": True})
        assert len(result) == 3
        assert "bot-1" in result

    def test_bot_names_preserved_in_order(self):
        """Verify bot names preserved in order."""
        from iconfucius.skills.executor import _resolve_bot_names
        result = _resolve_bot_names({"bot_names": ["bot-3", "bot-1", "bot-2"]})
        assert result == ["bot-3", "bot-1", "bot-2"]


# ===================================================================
# 6. Confirmation flow — user declined operations
# ===================================================================

class TestConfirmationSecurity:
    """Verify declined operations don't execute."""

    @patch("iconfucius.cli.chat.execute_tool")
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_declined_fund_not_executed(self, mock_meta, mock_exec):
        """User declining fund confirmation → tool not executed."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "fund", {"bot_name": "bot-1", "amount": 5000})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="n"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        mock_exec.assert_not_called()

    @patch("iconfucius.cli.chat.execute_tool")
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_declined_wallet_send_not_executed(self, mock_meta, mock_exec):
        """User declining wallet_send → tool not executed."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "wallet_send", {"amount": "5000", "address": "bc1qtest"})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="n"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        mock_exec.assert_not_called()

    @patch("iconfucius.cli.chat.execute_tool")
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_declined_trade_buy_not_executed(self, mock_meta, mock_exec):
        """User declining trade_buy → tool not executed."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "trade_buy", {"token_id": "29m8", "amount": 5000,
                          "bot_name": "bot-1"})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="n"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        mock_exec.assert_not_called()

    @patch("iconfucius.cli.chat.execute_tool")
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_declined_withdraw_not_executed(self, mock_meta, mock_exec):
        """User declining withdraw → tool not executed."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "withdraw", {"bot_name": "bot-1", "amount": "5000"})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="n"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        mock_exec.assert_not_called()

    @patch("iconfucius.cli.chat.execute_tool")
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_declined_trade_sell_not_executed(self, mock_meta, mock_exec):
        """User declining trade_sell → tool not executed."""
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "trade_sell", {"token_id": "29m8", "amount": "all",
                           "bot_name": "bot-1"})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="n"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        mock_exec.assert_not_called()


# ===================================================================
# 7. Describe tool call — correct amounts shown before confirm
# ===================================================================

class TestDescribeToolCallAccuracy:
    """Verify the confirmation prompt shows correct amounts."""

    def test_fund_shows_sats(self):
        """Verify fund shows sats."""
        desc = _describe_tool_call("fund", {"amount": 5000, "bot_name": "bot-1"})
        assert "5,000" in desc
        assert "bot-1" in desc

    def test_fund_all_bots_shows_each(self):
        """Verify fund all bots shows each."""
        desc = _describe_tool_call("fund", {"amount": 5000, "all_bots": True})
        assert "all bots" in desc.lower()
        assert "each" in desc.lower()

    def test_trade_buy_shows_amount_and_token(self):
        """Verify trade buy shows amount and token."""
        desc = _describe_tool_call("trade_buy", {
            "amount": 5000, "token_id": "29m8", "bot_name": "bot-1"})
        assert "5,000" in desc
        assert "29m8" in desc

    def test_trade_sell_all_shows_all(self):
        """Verify trade sell all shows all."""
        desc = _describe_tool_call("trade_sell", {
            "amount": "all", "token_id": "29m8", "bot_name": "bot-1"})
        assert "all" in desc.lower()

    def test_trade_sell_usd_shows_dollar(self):
        """Verify trade sell usd shows dollar."""
        desc = _describe_tool_call("trade_sell", {
            "amount_usd": 10.0, "token_id": "29m8", "bot_name": "bot-1"})
        assert "$10.000" in desc

    def test_withdraw_shows_amount(self):
        """Verify withdraw shows amount."""
        desc = _describe_tool_call("withdraw", {
            "amount": "5000", "bot_name": "bot-1"})
        assert "5,000" in desc or "5000" in desc

    def test_wallet_send_shows_address(self):
        """Verify wallet send shows address."""
        desc = _describe_tool_call("wallet_send", {
            "amount": "5000", "address": "bc1qtestaddr123"})
        assert "bc1qtestaddr123" in desc

    def test_wallet_send_shows_principal(self):
        """Verify wallet send shows principal."""
        principal = "y7paa-3ewsi-2iqfz-xlcd7-jpcvq-ibor6-brggk-t7xyl-fv4hy-6ze7d-pqe"
        desc = _describe_tool_call("wallet_send", {
            "amount": "5000", "address": principal})
        assert principal in desc


# ===================================================================
# 8. Wallet balance handler — no sensitive data leaking to AI
# ===================================================================

class TestWalletBalanceDataLeakage:
    """Verify wallet_balance doesn't leak per-bot details to AI."""

    def test_returns_totals_and_safe_bot_fields(self):
        """AI receives totals + per-bot balances including principals."""
        fake_data = {
            "wallet_ckbtc_sats": 50_000,
            "bots": [
                {"name": "bot-1", "odin_sats": 10_000,
                 "principal": "bot-principal-1", "tokens": []},
                {"name": "bot-2", "odin_sats": 20_000,
                 "principal": "bot-principal-2", "tokens": []},
            ],
            "totals": {
                "odin_sats": 30_000,
                "token_value_sats": 5_000,
                "portfolio_sats": 85_000,
            },
            "_display": "table with all data",
        }
        with patch("iconfucius.cli.balance.run_all_balances",
                    return_value=fake_data):
            with patch("iconfucius.config.require_wallet", return_value=True):
                with patch("iconfucius.config.get_bot_names",
                            return_value=["bot-1", "bot-2"]):
                    result = execute_tool("wallet_balance", {})

        assert result["status"] == "ok"
        # Totals should be present
        assert result["wallet_ckbtc_sats"] == 50_000
        assert result["total_odin_sats"] == 30_000
        assert result["portfolio_sats"] == 85_000
        # Per-bot balances with principals exposed for AI to surface
        assert len(result["bots"]) == 2
        for bot in result["bots"]:
            assert set(bot.keys()) == {"name", "principal", "odin_sats", "tokens", "has_odin_account"}
        assert result["bots"][0]["principal"] == "bot-principal-1"
        assert result["bots"][1]["principal"] == "bot-principal-2"
        # No terminal output — AI summarizes from structured data
        assert "_terminal_output" not in result

    def test_bot_token_dicts_exclude_div(self):
        """AI must not see 'div' in per-bot token dicts — it's a backend concern."""
        fake_data = {
            "wallet_ckbtc_sats": 50_000,
            "bots": [
                {"name": "bot-1", "odin_sats": 10_000,
                 "principal": "bot-principal-1",
                 "tokens": [{"ticker": "TEST", "id": "t1",
                              "balance": 5.0, "value_sats": 1000}]},
            ],
            "totals": {
                "odin_sats": 10_000,
                "token_value_sats": 1_000,
                "portfolio_sats": 61_000,
            },
            "_display": "table",
        }
        with patch("iconfucius.cli.balance.run_all_balances",
                    return_value=fake_data):
            with patch("iconfucius.config.require_wallet", return_value=True):
                with patch("iconfucius.config.get_bot_names",
                            return_value=["bot-1"]):
                    result = execute_tool("wallet_balance", {})

        assert result["status"] == "ok"
        token = result["bots"][0]["tokens"][0]
        assert "div" not in token
        assert token["ticker"] == "TEST"
        assert token["balance"] == 5.0

    def test_none_data_returns_error(self):
        """Verify none data returns error."""
        with patch("iconfucius.cli.balance.run_all_balances",
                    return_value=None):
            with patch("iconfucius.config.require_wallet", return_value=True):
                with patch("iconfucius.config.get_bot_names",
                            return_value=["bot-1"]):
                    result = execute_tool("wallet_balance", {})
        assert result["status"] == "error"


# ===================================================================
# 9. Token tools include total_supply for AI context
# ===================================================================

class TestTokenToolsTotalSupply:
    """Verify token tools include total_supply so AI knows supply is 21M."""

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "price_1h": 1400,
                         "price_6h": 1300, "price_1d": 1200,
                         "marketcap": 31_500_000_000, "volume_24": 5_000_000,
                         "holder_count": 42, "btc_liquidity": 1_000_000})
    @patch("iconfucius.tokens.lookup_token_with_fallback",
           return_value={"id": "29m8", "name": "IConfucius", "ticker": "ICONFUCIUS"})
    def test_token_price_includes_total_supply(self, _lookup, _fetch, _rate):
        """Verify token price includes total supply."""
        result = execute_tool("token_price", {"query": "ICONFUCIUS"})
        assert result["status"] == "ok"
        assert result["total_supply"] == 21_000_000
        assert "21,000,000" in result["display"]

    @patch("iconfucius.tokens.discover_tokens")
    def test_token_discover_includes_total_supply(self, mock_discover):
        """Verify token discover includes total supply."""
        mock_discover.return_value = [
            {"id": "t1", "name": "Token1", "ticker": "TK1",
             "price_sats": 1.5, "marketcap_sats": 31_500_000,
             "volume_24h_sats": 5_000, "holder_count": 10,
             "bonded": True, "twitter_verified": False,
             "safety": "Known token", "total_supply": 21_000_000},
        ]
        result = execute_tool("token_discover", {})
        assert result["status"] == "ok"
        assert result["tokens"][0]["total_supply"] == 21_000_000


# ===================================================================
# 10. Terminal output handling — print to user, don't send to AI
# ===================================================================

class TestTerminalOutputSecurity:
    """Verify _terminal_output is printed and stripped from AI context."""

    @patch("iconfucius.cli.chat.execute_tool")
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": False})
    def test_terminal_output_stripped_from_messages(self, mock_meta,
                                                     mock_exec, capsys):
        """_terminal_output is printed but not included in message history."""
        mock_exec.return_value = {
            "status": "ok",
            "_terminal_output": "SENSITIVE TABLE DATA",
        }
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "wallet_balance", {"all_bots": True})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        messages = []
        _run_tool_loop(backend, messages, "system", [], "TestBot")

        # Terminal output was printed
        captured = capsys.readouterr()
        assert "SENSITIVE TABLE DATA" in captured.out

        # Check what was sent back to the AI
        # The second chat_with_tools call should have tool_result
        second_call = backend.chat_with_tools.call_args_list[1]
        sent_messages = second_call[0][0]  # first positional arg
        # Find the tool_result message
        tool_results = [m for m in sent_messages
                        if m.get("role") == "user"
                        and any(c.get("type") == "tool_result"
                                for c in m.get("content", []))]
        if tool_results:
            content_str = str(tool_results[-1])
            assert "SENSITIVE TABLE DATA" not in content_str


# ===================================================================
# 11. Fund low-level — zero & negative amounts
# ===================================================================

class TestFundLowLevelAmounts:
    """Test run_fund with edge-case amounts."""

    def test_zero_amount(self, odin_project):
        """Verify zero amount."""
        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=0)
        assert result["status"] == "error"
        assert "positive" in result["error"].lower()

    def test_negative_amount(self, odin_project):
        """Verify negative amount."""
        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=-5000)
        assert result["status"] == "error"
        assert "positive" in result["error"].lower()


# ===================================================================
# 12. Max iterations guard — prevent infinite tool loops
# ===================================================================

class TestMaxIterationsGuard:
    """Verify the tool loop doesn't run forever."""

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": False})
    def test_stops_after_max_iterations(self, mock_meta, mock_exec, capsys):
        """Tool loop stops after _MAX_TOOL_ITERATIONS even if AI keeps calling tools."""
        from iconfucius.cli.chat import _MAX_TOOL_ITERATIONS

        backend = MagicMock()
        # Always return tool_use blocks
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "id_1"
        tool_block.name = "wallet_balance"
        tool_block.input = {}
        resp = MagicMock()
        resp.content = [tool_block]
        backend.chat_with_tools.return_value = resp

        messages = []
        _run_tool_loop(backend, messages, "system", [], "TestBot")

        # Should have stopped at the max
        assert mock_exec.call_count <= _MAX_TOOL_ITERATIONS

        # Warning message printed when limit is hit
        captured = capsys.readouterr().out
        assert "Tool loop limit reached" in captured
        assert "continue" in captured


# ===================================================================
# 13. Multi-tool batch — all-or-nothing confirmation
# ===================================================================

class TestBatchConfirmationSecurity:
    """Verify batch confirmation is all-or-nothing for state-changing ops."""

    @patch("iconfucius.cli.chat.execute_tool")
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_batch_decline_skips_all_tools(self, mock_meta, mock_exec):
        """Declining batch confirmation skips ALL tools in the batch."""
        backend = MagicMock()

        # Two confirmable tools in one response
        block1 = MagicMock(type="tool_use", id="id_1", name="fund",
                           input={"bot_name": "bot-1", "amount": 5000})
        block2 = MagicMock(type="tool_use", id="id_2", name="fund",
                           input={"bot_name": "bot-2", "amount": 5000})
        resp1 = MagicMock()
        resp1.content = [block1, block2]

        text_block = MagicMock(type="text", text="Done.")
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        with patch("builtins.input", return_value="n"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        mock_exec.assert_not_called()

    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_batch_confirm_executes_all_tools(self, mock_meta, mock_exec):
        """Confirming batch executes ALL tools in the batch."""
        backend = MagicMock()

        block1 = MagicMock(type="tool_use", id="id_1", name="fund",
                           input={"bot_name": "bot-1", "amount": 5000})
        block2 = MagicMock(type="tool_use", id="id_2", name="fund",
                           input={"bot_name": "bot-2", "amount": 5000})
        resp1 = MagicMock()
        resp1.content = [block1, block2]

        text_block = MagicMock(type="text", text="Done.")
        resp2 = MagicMock()
        resp2.content = [text_block]
        backend.chat_with_tools.side_effect = [resp1, resp2]

        with patch("builtins.input", return_value="y"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        assert mock_exec.call_count == 2
