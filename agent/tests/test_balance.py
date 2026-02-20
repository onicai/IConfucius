"""Tests for iconfucius.cli.balance — balance collection and display."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch, call

import pytest

from iconfucius.cli.balance import (
    BotBalances,
    _fmt_token_amount,
    _format_padded_table,
    _format_holdings_table,
    _collect_wallet_info,
    collect_balances,
    run_all_balances,
)
from iconfucius.config import fmt_sats


# ---------------------------------------------------------------------------
# fmt_sats
# ---------------------------------------------------------------------------

class TestSatsStr:
    def test_with_usd_rate(self):
        result = fmt_sats(100_000_000, 100_000.0)
        assert "100,000,000 sats" in result
        assert "$100000.00" in result

    def test_without_usd_rate(self):
        result = fmt_sats(5000, None)
        assert result == "5,000 sats"

    def test_zero(self):
        result = fmt_sats(0, 100_000.0)
        assert "0 sats" in result
        assert "$0.00" in result


# ---------------------------------------------------------------------------
# _fmt_token_amount
# ---------------------------------------------------------------------------

class TestFmtTokenAmount:
    def test_divisibility_8_large_balance(self):
        """Regression: raw balance 2_771_411_893_677_396 with div=8 should
        display as ~27,714,118.94 — NOT as 2,771,411,893,677,396."""
        result = _fmt_token_amount(2_771_411_893_677_396, 8)
        assert result == "27,714,118.94"
        # Must NOT contain the raw 15+ digit number
        assert "2,771,411,893,677,396" not in result

    def test_divisibility_8_small_balance(self):
        result = _fmt_token_amount(100, 8)
        # 100 / 10^8 = 0.000001
        assert "0.000001" in result

    def test_divisibility_0(self):
        result = _fmt_token_amount(1_234_567, 0)
        assert result == "1,234,567"

    def test_zero_balance(self):
        assert _fmt_token_amount(0, 8) == "0"

    def test_divisibility_2(self):
        result = _fmt_token_amount(12345, 2)
        assert result == "123.45"

    def test_tiny_amount_shows_more_decimals(self):
        # 1 / 10^8 = 0.00000001 — less than 0.01, so full precision
        result = _fmt_token_amount(1, 8)
        assert "0.00000001" in result


# ---------------------------------------------------------------------------
# _format_padded_table
# ---------------------------------------------------------------------------

class TestFormatPaddedTable:
    def test_basic_table(self):
        headers = ["Name", "Value"]
        rows = [("Alice", "100"), ("Bob", "2000")]
        lines = _format_padded_table(headers, rows)
        output = "\n".join(lines)
        assert "Name" in output
        assert "Value" in output
        assert "Alice" in output
        assert "Bob" in output
        assert "---" in output

    def test_auto_sizes_columns(self):
        headers = ["A", "B"]
        rows = [("very long cell", "x")]
        lines = _format_padded_table(headers, rows)
        output = "\n".join(lines)
        assert "very long cell" in output


# ---------------------------------------------------------------------------
# BotBalances dataclass
# ---------------------------------------------------------------------------

class TestBotBalances:
    def test_defaults(self):
        data = BotBalances(bot_name="bot-1", bot_principal="abc")
        assert data.odin_sats == 0.0
        assert data.token_holdings == []

    def test_with_holdings(self):
        holdings = [{"ticker": "ICONFUCIUS", "token_id": "29m8",
                     "balance": 1000, "divisibility": 8, "value_sats": 50}]
        data = BotBalances(bot_name="bot-1", bot_principal="abc",
                           odin_sats=5000.0, token_holdings=holdings)
        assert data.odin_sats == 5000.0
        assert len(data.token_holdings) == 1


# ---------------------------------------------------------------------------
# _format_holdings_table
# ---------------------------------------------------------------------------

class TestFormatHoldingsTable:
    def test_single_bot_no_tokens(self):
        data = [BotBalances("bot-1", "abc", odin_sats=1000.0)]
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        assert "bot-1" in output
        assert "1,000 sats" in output

    def test_single_bot_with_tokens(self):
        data = [BotBalances("bot-1", "abc", odin_sats=5000.0,
                            token_holdings=[
                                {"ticker": "TEST", "token_id": "t1",
                                 "balance": 50_000_000_000, "divisibility": 8,
                                 "value_sats": 100}
                            ])]
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        assert "TEST (t1)" in output
        assert "500.00" in output

    def test_multi_bot_shows_totals(self):
        data = [
            BotBalances("bot-1", "abc", odin_sats=3000.0,
                        token_holdings=[
                            {"ticker": "X", "token_id": "x1",
                             "balance": 10_000_000_000, "divisibility": 8,
                             "value_sats": 10}
                        ]),
            BotBalances("bot-2", "def", odin_sats=2000.0,
                        token_holdings=[
                            {"ticker": "X", "token_id": "x1",
                             "balance": 20_000_000_000, "divisibility": 8,
                             "value_sats": 20}
                        ]),
        ]
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        assert "TOTAL" in output
        assert "5,000 sats" in output
        assert "300.00" in output
        assert "Total portfolio value:" in output

    def test_no_totals_for_single_bot(self):
        data = [BotBalances("bot-1", "abc", odin_sats=1000.0)]
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        assert "TOTAL" not in output

    def test_no_usd_rate(self):
        data = [BotBalances("bot-1", "abc", odin_sats=1000.0)]
        output = _format_holdings_table(data, btc_usd_rate=None)
        assert "1,000 sats" in output
        assert "$" not in output

    def test_token_balance_adjusted_for_divisibility(self):
        """Regression: raw balance must be divided by 10^divisibility.

        Without the fix, 2_771_411_893_677_396 would display as
        '2,771,411,893,677,396' instead of '27,714,118.94'.
        """
        data = [BotBalances("bot-1", "abc", odin_sats=1000.0,
                            token_holdings=[
                                {"ticker": "ICONFUCIUS", "token_id": "29m8",
                                 "balance": 2_771_411_893_677_396,
                                 "divisibility": 8,
                                 "value_sats": 2200}
                            ])]
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        # Should show the adjusted amount, not the raw integer
        assert "27,714,118.94" in output
        # Must NOT contain the raw 16-digit number
        assert "2,771,411,893,677,396" not in output


# ---------------------------------------------------------------------------
# _collect_wallet_info
# ---------------------------------------------------------------------------

class TestCollectWalletInfo:
    @patch("iconfucius.transfers.get_btc_address", return_value="bc1qtest456")
    @patch("iconfucius.transfers.create_ckbtc_minter")
    @patch("iconfucius.transfers.get_balance", return_value=50000)
    @patch("iconfucius.transfers.create_icrc1_canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    def test_returns_data_and_display(self, MockId, MockClient, MockAgent,
                               mock_create, mock_get_bal, mock_minter,
                               mock_btc_addr,
                               odin_project):
        mock_identity = MagicMock()
        mock_identity.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockId.from_pem.return_value = mock_identity

        data, lines = _collect_wallet_info(100_000.0)
        output = "\n".join(lines)
        assert "ICRC-1 ckBTC:" in output
        assert "50,000 sats" in output
        assert "To fund your wallet:" in output
        assert "ctrl-principal" in output
        assert "bc1qtest456" in output
        # No minter section by default
        assert "ckBTC minter:" not in output
        # Data dict
        assert data["balance_sats"] == 50000
        assert data["principal"] == "ctrl-principal"
        assert data["btc_address"] == "bc1qtest456"

    @patch("iconfucius.transfers.unwrap_canister_result", return_value=0)
    @patch("iconfucius.transfers.get_withdrawal_account",
           return_value={"owner": "minter", "subaccount": []})
    @patch("iconfucius.transfers.get_btc_address", return_value="bc1qtest456")
    @patch("iconfucius.transfers.get_pending_btc", return_value=0)
    @patch("iconfucius.transfers.create_ckbtc_minter")
    @patch("iconfucius.transfers.get_balance", return_value=50000)
    @patch("iconfucius.transfers.create_icrc1_canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    def test_ckbtc_minter_shows_minter_section(self, MockId, MockClient, MockAgent,
                               mock_create, mock_get_bal, mock_minter,
                               mock_pending, mock_btc_addr,
                               mock_withdrawal_acct, mock_unwrap,
                               odin_project):
        mock_identity = MagicMock()
        mock_identity.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockId.from_pem.return_value = mock_identity

        data, lines = _collect_wallet_info(100_000.0, ckbtc_minter=True)
        output = "\n".join(lines)
        assert "ICRC-1 ckBTC:" in output
        assert "ckBTC minter:" in output
        assert "Incoming BTC:" in output
        assert "Outgoing BTC:" in output
        assert "fee dust" not in output

    @patch("iconfucius.transfers.unwrap_canister_result", return_value=640)
    @patch("iconfucius.transfers.get_withdrawal_account",
           return_value={"owner": "minter", "subaccount": []})
    @patch("iconfucius.transfers.get_btc_address", return_value="bc1qtest456")
    @patch("iconfucius.transfers.get_pending_btc", return_value=0)
    @patch("iconfucius.transfers.create_ckbtc_minter")
    @patch("iconfucius.transfers.get_balance", return_value=50000)
    @patch("iconfucius.transfers.create_icrc1_canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    def test_shows_dust_note(self, MockId, MockClient, MockAgent,
                              mock_create, mock_get_bal, mock_minter,
                              mock_pending, mock_btc_addr,
                              mock_withdrawal_acct, mock_unwrap,
                              odin_project):
        mock_identity = MagicMock()
        mock_identity.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockId.from_pem.return_value = mock_identity

        data, lines = _collect_wallet_info(100_000.0, ckbtc_minter=True)
        output = "\n".join(lines)
        assert "640 sats" in output
        assert "fee dust" in output


# ---------------------------------------------------------------------------
# collect_balances
# ---------------------------------------------------------------------------

class TestCollectBalances:
    @patch("iconfucius.cli.balance.cffi_requests")
    @patch("iconfucius.cli.balance.Canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    @patch("iconfucius.cli.balance.load_session")
    def test_collects_all_data(self, mock_load, MockId, MockClient,
                               MockAgent, MockCanister, mock_cffi,
                               mock_siwb_auth):
        mock_load.return_value = mock_siwb_auth

        # Mock Odin canister getBalance
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = [{"value": 5000000}]  # 5000 sats in msat
        MockCanister.return_value = mock_odin

        # Mock REST API
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"type": "token", "ticker": "TEST", "id": "t1",
                 "balance": 100, "divisibility": 8, "price": 1000000}
            ]
        }
        mock_resp.text = '{"data": []}'
        mock_cffi.get.return_value = mock_resp

        result = collect_balances("bot-1", verbose=False)
        assert isinstance(result, BotBalances)
        assert result.bot_name == "bot-1"
        assert result.odin_sats == 5000.0
        assert len(result.token_holdings) == 1
        assert result.token_holdings[0]["ticker"] == "TEST"

    @patch("iconfucius.cli.balance.cffi_requests")
    @patch("iconfucius.cli.balance.Canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    @patch("iconfucius.cli.balance.siwb_login")
    @patch("iconfucius.cli.balance.load_session", return_value=None)
    def test_falls_back_to_siwb_login(self, mock_load,
                                       mock_login,
                                       MockId, MockClient, MockAgent,
                                       MockCanister, mock_cffi,
                                       mock_siwb_auth):
        mock_login.return_value = mock_siwb_auth
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = [{"value": 0}]
        MockCanister.return_value = mock_odin
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}
        mock_resp.text = '{"data": []}'
        mock_cffi.get.return_value = mock_resp

        result = collect_balances("bot-1", verbose=False)
        mock_login.assert_called_once()


# ---------------------------------------------------------------------------
# run_all_balances
# ---------------------------------------------------------------------------

class TestRunAllBalances:
    def test_no_wallet(self, odin_project_no_wallet):
        result = run_all_balances(bot_names=["bot-1"])
        assert result is None

    @patch("iconfucius.cli.balance._format_holdings_table", return_value="table")
    @patch("iconfucius.cli.balance._collect_wallet_info")
    @patch("iconfucius.cli.balance.collect_balances")
    @patch("iconfucius.cli.balance._fetch_btc_usd_rate", return_value=100_000.0)
    def test_success(self, mock_rate, mock_collect, mock_wallet,
                     mock_holdings, odin_project):
        mock_wallet.return_value = (
            {"principal": "p", "btc_address": "bc1", "balance_sats": 50000,
             "pending_sats": 0, "withdrawal_balance_sats": 0,
             "active_withdrawal_count": 0, "address_btc_sats": 0},
            ["wallet line"],
        )
        mock_collect.return_value = BotBalances("bot-1", "abc", odin_sats=1000.0)

        result = run_all_balances(bot_names=["bot-1"])
        assert result is not None
        assert result["wallet_ckbtc_sats"] == 50000
        assert "_display" in result
        mock_wallet.assert_called_once()
        mock_holdings.assert_called_once()

    @patch("iconfucius.cli.balance._collect_wallet_info")
    @patch("iconfucius.cli.balance.collect_balances", side_effect=Exception("fail"))
    @patch("iconfucius.cli.balance._fetch_btc_usd_rate", return_value=100_000.0)
    def test_handles_collection_error(self, mock_rate, mock_collect,
                                       mock_wallet, odin_project):
        mock_wallet.return_value = (
            {"principal": "p", "btc_address": "bc1", "balance_sats": 50000,
             "pending_sats": 0, "withdrawal_balance_sats": 0,
             "active_withdrawal_count": 0, "address_btc_sats": 0},
            ["wallet line"],
        )

        result = run_all_balances(bot_names=["bot-1"])
        assert result is None
