"""Tests for LLM hallucination scenarios.

Simulates cases where the AI generates tool calls with wrong, dangerous,
or nonsensical parameters. Each scenario is defined in a list so real
hallucinations from production conversations can be easily added.

The tests verify that:
1. The confirmation prompt shows accurate info (so the user can catch it)
2. Handlers reject clearly invalid inputs
3. Pre-conversion doesn't silently corrupt amounts
"""

from unittest.mock import MagicMock, patch

import pytest

from iconfucius.cli.chat import _describe_tool_call, _run_tool_loop
from iconfucius.skills.executor import execute_tool


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_tool_response(name, tool_input, *, tool_id="id_1"):
    """Build a mock LLM response containing one tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = tool_id
    tool_block.name = name
    tool_block.input = dict(tool_input)

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Done."

    resp_tool = MagicMock()
    resp_tool.content = [tool_block]
    resp_text = MagicMock()
    resp_text.content = [text_block]
    return resp_tool, resp_text


# ===================================================================
# Hallucination scenarios — extend this list with real examples!
# ===================================================================

# Each entry:
#   id           - short unique id for pytest parametrize
#   description  - what the hallucination is
#   tool_name    - tool the AI called
#   tool_input   - hallucinated parameters
#   user_said    - what the user actually asked (for documentation)
#   expect_error - if True, handler must return status=error
#   expect_in_confirm - substring that MUST appear in confirmation prompt
#                       (so user can catch the mistake)
#   expect_not_in_confirm - substring that must NOT appear (optional)

HALLUCINATIONS = [
    # ---- Amount confusion ----
    {
        "id": "fund_10_sats_instead_of_10_usd",
        "description": "User says '$10', AI sends amount=10 (sats, not dollars)",
        "tool_name": "fund",
        "tool_input": {"bot_name": "bot-1", "amount": 10},
        "user_said": "fund bot-1 with $10",
        "expect_error": False,
        "expect_in_confirm": "10 sats",
    },
    {
        "id": "send_btc_not_sats",
        "description": "AI sends 0.001 (BTC) instead of 100,000 sats",
        "tool_name": "wallet_send",
        "tool_input": {"amount": "0.001", "address": "bc1qtest"},
        "user_said": "send 0.001 BTC to bc1qtest",
        "expect_error": False,
        "expect_in_confirm": "0.001",
    },
    {
        "id": "fund_negative_amount",
        "description": "AI hallucinates a negative amount",
        "tool_name": "fund",
        "tool_input": {"bot_name": "bot-1", "amount": -5000},
        "user_said": "fund bot-1 with 5000 sats",
        "expect_error": False,
        "expect_in_confirm": "-5,000",
    },
    {
        "id": "trade_buy_zero_sats",
        "description": "AI sends zero-amount buy order",
        "tool_name": "trade_buy",
        "tool_input": {"token_id": "29m8", "amount": 0, "bot_name": "bot-1"},
        "user_said": "buy $5 of IConfucius",
        "expect_error": True,
    },
    {
        "id": "withdraw_absurdly_large",
        "description": "AI hallucinates 1 BTC withdraw (100M sats)",
        "tool_name": "withdraw",
        "tool_input": {"bot_name": "bot-1", "amount": "100000000"},
        "user_said": "withdraw 1000 sats from bot-1",
        "expect_error": False,
        "expect_in_confirm": "100,000,000",
    },

    # ---- Wrong target ----
    {
        "id": "send_to_own_address",
        "description": "AI sends funds to the user's own wallet principal",
        "tool_name": "wallet_send",
        "tool_input": {"amount": "5000",
                       "address": "y7paa-3ewsi-2iqfz-xlcd7-jpcvq-ibor6"},
        "user_said": "send 5000 sats to someone else",
        "expect_error": False,
        "expect_in_confirm": "y7paa",
    },
    {
        "id": "fund_wrong_bot",
        "description": "AI picks bot-2 when user said bot-1",
        "tool_name": "fund",
        "tool_input": {"bot_name": "bot-2", "amount": 5000},
        "user_said": "fund bot-1 with 5000 sats",
        "expect_error": False,
        "expect_in_confirm": "bot-2",
    },
    {
        "id": "trade_nonexistent_bot",
        "description": "AI invents a bot name that doesn't exist",
        "tool_name": "trade_buy",
        "tool_input": {"token_id": "29m8", "amount": 5000,
                       "bot_name": "bot-99"},
        "user_said": "buy 5000 sats of IConfucius",
        "expect_error": False,
        "expect_in_confirm": "bot-99",
    },

    # ---- Wrong token ----
    {
        "id": "buy_wrong_token_id",
        "description": "AI uses wrong token ID",
        "tool_name": "trade_buy",
        "tool_input": {"token_id": "xxxx", "amount": 5000,
                       "bot_name": "bot-1"},
        "user_said": "buy 5000 sats of IConfucius (29m8)",
        "expect_error": False,
        "expect_in_confirm": "xxxx",
    },
    {
        "id": "sell_wrong_token_id",
        "description": "AI sells wrong token",
        "tool_name": "trade_sell",
        "tool_input": {"token_id": "wrong", "amount": "all",
                       "bot_name": "bot-1"},
        "user_said": "sell all my IConfucius tokens",
        "expect_error": False,
        "expect_in_confirm": "wrong",
    },

    # ---- Missing required fields ----
    {
        "id": "fund_no_bot",
        "description": "AI forgets to specify which bot to fund",
        "tool_name": "fund",
        "tool_input": {"amount": 5000},
        "user_said": "fund bot-1 with 5000 sats",
        "expect_error": True,
    },
    {
        "id": "send_no_address",
        "description": "AI forgets the destination address",
        "tool_name": "wallet_send",
        "tool_input": {"amount": "5000"},
        "user_said": "send 5000 sats to bc1qtest",
        "expect_error": True,
    },
    {
        "id": "trade_buy_no_token",
        "description": "AI forgets token_id for buy",
        "tool_name": "trade_buy",
        "tool_input": {"amount": 5000, "bot_name": "bot-1"},
        "user_said": "buy 5000 sats of IConfucius",
        "expect_error": True,
    },
    {
        "id": "trade_sell_no_token",
        "description": "AI forgets token_id for sell",
        "tool_name": "trade_sell",
        "tool_input": {"amount": "all", "bot_name": "bot-1"},
        "user_said": "sell all IConfucius",
        "expect_error": True,
    },

    # ---- Confused operations ----
    {
        "id": "withdraw_sends_all_bots",
        "description": "User wants to withdraw from bot-1, AI sends all_bots",
        "tool_name": "withdraw",
        "tool_input": {"all_bots": True, "amount": "all"},
        "user_said": "withdraw all from bot-1",
        "expect_error": False,
        "expect_in_confirm": "all bots",
    },
    {
        "id": "fund_all_when_user_said_one",
        "description": "User funds one bot, AI funds all",
        "tool_name": "fund",
        "tool_input": {"all_bots": True, "amount": 5000},
        "user_said": "fund bot-1 with 5000 sats",
        "expect_error": False,
        "expect_in_confirm": "all bots",
        "expect_not_in_confirm": None,
    },

    # ---- USD/sats confusion ----
    {
        "id": "amount_usd_when_user_said_sats",
        "description": "User says 5000 sats, AI uses amount_usd=5000",
        "tool_name": "fund",
        "tool_input": {"bot_name": "bot-1", "amount_usd": 5000.0},
        "user_said": "fund bot-1 with 5000 sats",
        "expect_error": False,
        # After pre-conversion: $5000 at any rate → huge sats number
        # The confirm prompt must show this so user catches it
    },

    # ---- Sell all when user said sell some ----
    {
        "id": "sell_all_when_partial",
        "description": "User says 'sell 100 tokens', AI sends amount='all'",
        "tool_name": "trade_sell",
        "tool_input": {"token_id": "29m8", "amount": "all",
                       "bot_name": "bot-1"},
        "user_said": "sell 100 IConfucius tokens",
        "expect_error": False,
        "expect_in_confirm": "all",
    },

    # ---- Empty / whitespace address ----
    {
        "id": "send_whitespace_address",
        "description": "AI sends to whitespace-only address",
        "tool_name": "wallet_send",
        "tool_input": {"amount": "5000", "address": "   "},
        "user_said": "send 5000 sats to bc1qtest",
        "expect_error": True,
    },

    # --- Add real hallucinations from production below this line ---
    # {
    #     "id": "real_hallucination_001",
    #     "description": "Describe what happened",
    #     "tool_name": "...",
    #     "tool_input": {...},
    #     "user_said": "what the user actually typed",
    #     "expect_error": True/False,
    #     "expect_in_confirm": "...",
    # },
]


# ===================================================================
# Test: confirmation prompt shows accurate info for each hallucination
# ===================================================================

_CONFIRM_CASES = [h for h in HALLUCINATIONS if not h.get("expect_error")]


@pytest.mark.parametrize(
    "scenario",
    _CONFIRM_CASES,
    ids=[h["id"] for h in _CONFIRM_CASES],
)
def test_confirm_prompt_shows_hallucinated_values(scenario):
    """The confirm prompt must show the ACTUAL values the AI sent.

    This is the user's last line of defense — if the AI hallucinates
    a wrong amount/target/token, the confirmation prompt must make it
    visible so the user can decline.
    """
    desc = _describe_tool_call(scenario["tool_name"], scenario["tool_input"])
    expected = scenario.get("expect_in_confirm")
    if expected:
        assert expected in desc, (
            f"Confirmation prompt for '{scenario['id']}' should contain "
            f"'{expected}' but got: {desc}"
        )
    not_expected = scenario.get("expect_not_in_confirm")
    if not_expected:
        assert not_expected not in desc, (
            f"Confirmation prompt for '{scenario['id']}' should NOT contain "
            f"'{not_expected}' but got: {desc}"
        )


# ===================================================================
# Test: handlers reject clearly invalid hallucinated inputs
# ===================================================================

_ERROR_CASES = [h for h in HALLUCINATIONS if h.get("expect_error")]


@pytest.mark.parametrize(
    "scenario",
    _ERROR_CASES,
    ids=[h["id"] for h in _ERROR_CASES],
)
def test_handler_rejects_invalid_hallucination(scenario):
    """Handlers must return error for hallucinated invalid inputs."""
    with patch("iconfucius.config.require_wallet", return_value=True):
        result = execute_tool(scenario["tool_name"], scenario["tool_input"])
    assert result["status"] == "error", (
        f"Handler for '{scenario['id']}' should return error but got: {result}"
    )


# ===================================================================
# Test: pre-conversion makes hallucinated USD amounts visible
# ===================================================================

class TestPreConversionExposesHallucinations:
    """When AI hallucinates amount_usd, pre-conversion converts it to sats.

    This makes the hallucination visible in the confirmation prompt
    because fmt_sats shows "X sats ($Y.YY)" — the user sees the
    actual dollar amount and can catch mistakes.
    """

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_usd_5000_converted_to_huge_sats(self, mock_meta, mock_exec,
                                               mock_rate):
        """AI sends amount_usd=5000 (user said 5000 sats).

        Pre-conversion: $5000 / $100k * 1e8 = 5,000,000 sats.
        The confirm prompt shows "5,000,000 sats ($5,000.00)" — a
        clearly wrong amount that the user can decline.
        """
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "fund", {"bot_name": "bot-1", "amount_usd": 5000.0})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="y"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        call_args = mock_exec.call_args[0]
        # $5000 at $100k/BTC = 5,000,000 sats — clearly wrong
        assert call_args[1]["amount"] == 5_000_000
        assert "amount_usd" not in call_args[1]

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.cli.chat.execute_tool", return_value={"status": "ok"})
    @patch("iconfucius.cli.chat.get_tool_metadata",
           return_value={"requires_confirmation": True})
    def test_usd_0_01_converted_shows_tiny_amount(self, mock_meta, mock_exec,
                                                    mock_rate):
        """AI sends amount_usd=0.01 when user said $10.

        Pre-conversion: $0.01 / $100k * 1e8 = 10 sats.
        Confirm shows "10 sats ($0.01)" — user sees wrong dollar amount.
        """
        backend = MagicMock()
        resp_tool, resp_text = _make_tool_response(
            "fund", {"bot_name": "bot-1", "amount_usd": 0.01})
        backend.chat_with_tools.side_effect = [resp_tool, resp_text]

        with patch("builtins.input", return_value="y"):
            _run_tool_loop(backend, [], "system", [], "TestBot")

        call_args = mock_exec.call_args[0]
        assert call_args[1]["amount"] == 10  # $0.01 = 10 sats

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    def test_confirm_shows_converted_amount(self, mock_rate):
        """After pre-conversion, the confirm prompt shows sats (not USD)."""
        # Simulate post-pre-conversion state: amount_usd=5000 became amount=5_000_000
        desc = _describe_tool_call("fund", {
            "bot_name": "bot-1", "amount": 5_000_000,
        })
        # User sees "5,000,000 sats" — clearly wrong for "fund bot-1 with 5000 sats"
        assert "5,000,000" in desc


# ===================================================================
# Test: hallucinated tool calls that bypass confirmation
# ===================================================================

class TestHallucinatedReadOnlyTools:
    """AI might hallucinate parameters for read-only tools too.

    These don't require confirmation, so they auto-execute.
    Verify they don't cause harmful side effects.
    """

    def test_balance_check_wrong_bot_still_safe(self):
        """AI checks balance for wrong bot — harmless read-only operation."""
        # wallet_balance with a specific bot_name still only reads data
        with patch("iconfucius.cli.balance.run_all_balances",
                    return_value=None):
            with patch("iconfucius.config.require_wallet", return_value=True):
                with patch("iconfucius.config.get_bot_names",
                            return_value=["bot-1"]):
                    result = execute_tool("wallet_balance",
                                          {"bot_name": "bot-99"})
        # Returns error but no funds moved
        assert result["status"] == "error"

    def test_token_lookup_with_hallucinated_query(self):
        """AI sends random token query — harmless, just returns no results."""
        with patch("iconfucius.tokens._search_api", return_value=[]):
            result = execute_tool("token_lookup",
                                  {"query": "HALLUCINATED_TOKEN_XYZ_999"})
        assert result["status"] == "ok"
        assert result.get("api_results", []) == []
