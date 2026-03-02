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
from iconfucius.config import fmt_sats, fmt_tokens


# ---------------------------------------------------------------------------
# fmt_sats
# ---------------------------------------------------------------------------

class TestSatsStr:
    def test_with_usd_rate(self):
        """Format sats with a USD conversion appended."""
        result = fmt_sats(100_000_000, 100_000.0)
        assert "100,000,000 sats" in result
        assert "$100000.000" in result

    def test_without_usd_rate(self):
        """Format sats without USD when rate is None."""
        result = fmt_sats(5000, None)
        assert result == "5,000 sats"

    def test_zero(self):
        """Format zero sats with USD showing $0."""
        result = fmt_sats(0, 100_000.0)
        assert "0 sats" in result
        assert "$0.000" in result


# ---------------------------------------------------------------------------
# fmt_tokens (config.py)
# ---------------------------------------------------------------------------

class TestFmtTokens:
    """Tests for config.fmt_tokens — milli-subunit balance with USD."""

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "divisibility": 8, "decimals": 3})
    def test_valid_msu_amount(self, _mock_fetch, _mock_rate):
        """10^11 milli-subunits (1 display token) at price 1500 msat."""
        result = fmt_tokens(100_000_000_000, "29m8")
        assert "1.000 tokens" in result
        assert "$" in result

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "divisibility": 8, "decimals": 3})
    def test_string_msu_amount(self, _mock_fetch, _mock_rate):
        """String milli-subunit value is parsed to int correctly."""
        result = fmt_tokens("100000000000", "29m8")
        assert "1.000 tokens" in result
        assert "$" in result

    def test_invalid_count_fallback(self):
        """Non-numeric count falls back to simple string."""
        result = fmt_tokens("abc", "29m8")
        assert result == "abc tokens"

    def test_none_count_fallback(self):
        """None count falls back to simple string."""
        result = fmt_tokens(None, "29m8")
        assert result == "None tokens"

    @patch("iconfucius.tokens.fetch_token_data", return_value=None)
    def test_no_token_data_fallback(self, _mock_fetch):
        """Fallback when token not found."""
        result = fmt_tokens(100_000_000_000, "unknown")
        assert "100000000000 tokens" in result

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 0, "divisibility": 8, "decimals": 3})
    def test_zero_price_shows_zero_usd(self, _mock_fetch, _mock_rate):
        """Zero price shows $0.000."""
        result = fmt_tokens(100_000_000_000, "29m8")
        assert "1.000 tokens" in result
        assert "$0.000" in result

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 180, "divisibility": 8, "decimals": 3})
    def test_realistic_balance(self, _mock_fetch, _mock_rate):
        """Realistic balance in milli-subunits at price 180."""
        # 27,714,118.937 display tokens * 10^11 = 2_771_411_893_700_000_000 msu
        msu = 2_771_411_893_700_000_000
        result = fmt_tokens(msu, "29m8")
        assert "27,714,118.937 tokens" in result
        assert "$" in result

    @patch("iconfucius.config.get_btc_to_usd_rate",
           side_effect=Exception("offline"))
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "divisibility": 8, "decimals": 3})
    def test_rate_failure_fallback(self, _mock_fetch, _mock_rate):
        """Falls back when btc_usd rate call fails."""
        result = fmt_tokens(100_000_000_000, "29m8")
        assert "tokens" in result


# ---------------------------------------------------------------------------
# _fmt_token_amount
# ---------------------------------------------------------------------------

class TestFmtTokenAmount:
    def test_divisibility_8_large_balance(self):
        """Regression: raw balance 2_771_411_893_677_396 with div=8 should
        display as ~27,714,118.937 — NOT as 2,771,411,893,677,396."""
        result = _fmt_token_amount(2_771_411_893_677_396, 8)
        assert result == "27,714,118.937"
        # Must NOT contain the raw 15+ digit number
        assert "2,771,411,893,677,396" not in result

    def test_divisibility_8_small_balance(self):
        """Small raw balance with divisibility 8 shows sub-unit decimals."""
        result = _fmt_token_amount(100, 8)
        # 100 / 10^8 = 0.000001
        assert "0.000001" in result

    def test_divisibility_0(self):
        """Divisibility 0 returns the raw integer with commas."""
        result = _fmt_token_amount(1_234_567, 0)
        assert result == "1,234,567"

    def test_zero_balance(self):
        """Zero balance returns the string '0' regardless of divisibility."""
        assert _fmt_token_amount(0, 8) == "0"

    def test_divisibility_2(self):
        """Divisibility 2 divides by 100 and shows three decimal places."""
        result = _fmt_token_amount(12345, 2)
        assert result == "123.450"

    def test_tiny_amount_shows_more_decimals(self):
        """Amounts below 0.01 display full precision instead of truncating."""
        # 1 / 10^8 = 0.00000001 — less than 0.01, so full precision
        result = _fmt_token_amount(1, 8)
        assert "0.00000001" in result


# ---------------------------------------------------------------------------
# _format_padded_table
# ---------------------------------------------------------------------------

class TestFormatPaddedTable:
    def test_basic_table(self):
        """Render a two-column table with headers, separator, and data rows."""
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
        """Column widths expand to fit the longest cell content."""
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
        """BotBalances defaults to None for all balance fields (unchecked)."""
        data = BotBalances(bot_name="bot-1", bot_principal="abc")
        assert data.odin_sats is None
        assert data.token_holdings is None
        assert data.has_odin_account is None

    def test_with_holdings(self):
        """BotBalances stores provided odin_sats, holdings, and account flag."""
        holdings = [{"ticker": "ICONFUCIUS", "token_id": "29m8",
                     "balance": 1000, "divisibility": 8, "value_sats": 50}]
        data = BotBalances(bot_name="bot-1", bot_principal="abc",
                           odin_sats=5000.0, token_holdings=holdings,
                           has_odin_account=True)
        assert data.odin_sats == 5000.0
        assert len(data.token_holdings) == 1
        assert data.has_odin_account is True


# ---------------------------------------------------------------------------
# _format_holdings_table
# ---------------------------------------------------------------------------

class TestFormatHoldingsTable:
    def test_single_bot_no_tokens(self):
        """Single bot with no token holdings shows only ODIN sats."""
        data = [BotBalances("bot-1", "abc", odin_sats=1000.0, token_holdings=[])]
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        assert "bot-1" in output
        assert "1,000 sats" in output

    def test_single_bot_with_tokens(self):
        """Single bot with token holdings includes adjusted token amounts."""
        data = [BotBalances("bot-1", "abc", odin_sats=5000.0,
                            token_holdings=[
                                {"ticker": "TEST", "token_id": "t1",
                                 "balance": 50_000_000_000, "divisibility": 8,
                                 "value_sats": 100}
                            ])]
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        assert "TEST (t1)" in output
        assert "500.000" in output

    def test_multi_bot_shows_totals(self):
        """Multiple bots produce a TOTAL row and portfolio value summary."""
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
        assert "300.000" in output
        assert "Total portfolio value:" in output

    def test_no_totals_for_single_bot(self):
        """Single-bot output omits the TOTAL row."""
        data = [BotBalances("bot-1", "abc", odin_sats=1000.0, token_holdings=[])]
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        assert "TOTAL" not in output

    def test_no_usd_rate(self):
        """Verify no usd rate."""
        data = [BotBalances("bot-1", "abc", odin_sats=1000.0, token_holdings=[])]
        output = _format_holdings_table(data, btc_usd_rate=None)
        assert "1,000 sats" in output
        assert "$" not in output

    def test_token_balance_adjusted_for_divisibility(self):
        """Regression: raw balance must be divided by 10^divisibility.

        Without the fix, 2_771_411_893_677_396 would display as
        '2,771,411,893,677,396' instead of '27,714,118.937'.
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
        assert "27,714,118.937" in output
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
        """Verify returns data and display."""
        mock_identity = MagicMock()
        mock_identity.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockId.from_pem.return_value = mock_identity

        data, lines = _collect_wallet_info(100_000.0)
        output = "\n".join(lines)
        assert "ICRC-1 ckBTC:" in output
        assert "50,000 sats" in output
        # Funding instructions are in how_to_fund_wallet, not here
        assert "To fund your wallet:" not in output
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
        """Verify ckbtc minter shows minter section."""
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
        """Verify shows dust note."""
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
    @patch("iconfucius.http_utils.cffi_get_with_retry")
    @patch("iconfucius.cli.balance.Canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    @patch("iconfucius.cli.balance.read_cached_principal", return_value="principal-abc")
    def test_collects_all_data(self, _mock_read_principal, _MockId, _MockClient,
                               _MockAgent, MockCanister, mock_cffi):
        """Verify collects all data."""
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
                 "balance": 100_000, "divisibility": 8, "decimals": 3,
                 "price": 1000000}
            ]
        }
        mock_resp.text = '{"data": []}'
        mock_cffi.return_value = mock_resp

        with patch("iconfucius.accounts.resolve_odin_account", return_value="principal-abc"):
            result = collect_balances("bot-1", verbose=False)
        assert isinstance(result, BotBalances)
        assert result.bot_name == "bot-1"
        assert result.odin_sats == 5000.0
        assert len(result.token_holdings) == 1
        assert result.token_holdings[0]["ticker"] == "TEST"
        # balance should be corrected: 100_000 / 10^3 = 100
        assert result.token_holdings[0]["balance"] == 100
        assert result.has_odin_account is True

    @patch("iconfucius.http_utils.cffi_get_with_retry")
    @patch("iconfucius.cli.balance.Canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    @patch("iconfucius.cli.balance.siwb_login")
    @patch("iconfucius.cli.balance.read_cached_principal", return_value=None)
    def test_falls_back_to_siwb_login(self, _mock_read_principal,
                                       mock_login,
                                       _MockId, _MockClient, _MockAgent,
                                       MockCanister, mock_cffi):
        """When no cached principal, falls back to SIWB login."""
        mock_login.return_value = {
            "bot_principal_text": "principal-abc",
        }
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = [{"value": 0}]
        MockCanister.return_value = mock_odin
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}
        mock_resp.text = '{"data": []}'
        mock_cffi.return_value = mock_resp

        with patch("iconfucius.accounts.resolve_odin_account", return_value="principal-abc"):
            collect_balances("bot-1", verbose=False)
        mock_login.assert_called_once()

    @patch("iconfucius.http_utils.cffi_get_with_retry")
    @patch("iconfucius.cli.balance.Canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    @patch("iconfucius.cli.balance.read_cached_principal", return_value="principal-abc")
    def test_decimals_correction(self, _mock_read_principal, _MockId, _MockClient,
                                  _MockAgent, MockCanister, mock_cffi):
        """API balance with decimals=3 should be divided by 1000."""
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = [{"value": 0}]
        MockCanister.return_value = mock_odin

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"type": "token", "ticker": "ICONFUCIUS", "id": "29m8",
                 "balance": 132482122800932, "divisibility": 8,
                 "decimals": 3, "price": 5709}
            ]
        }
        mock_resp.text = '{"data": []}'
        mock_cffi.return_value = mock_resp

        with patch("iconfucius.accounts.resolve_odin_account", return_value="principal-abc"):
            result = collect_balances("bot-1", verbose=False)
        t = result.token_holdings[0]
        # 132482122800932 / 10^3 = 132482122800.932
        assert t["balance"] == pytest.approx(132482122800.932)
        # Human-readable: 132482122800.932 / 10^8 ≈ 1324.82
        human = t["balance"] / (10 ** t["divisibility"])
        assert human == pytest.approx(1324.82, rel=0.01)
        # value_sats uses raw_balance (not decimals-corrected balance)
        # 132482122800932 * 5709 / 10^8 / 1e6 = 7563.74
        assert t["value_sats"] == pytest.approx(7563.74, rel=0.01)

    @patch("iconfucius.http_utils.cffi_get_with_retry")
    @patch("iconfucius.cli.balance.Canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    @patch("iconfucius.cli.balance.read_cached_principal", return_value="principal-abc")
    def test_decimals_zero_no_correction(self, _mock_read_principal, _MockId, _MockClient,
                                          _MockAgent, MockCanister, mock_cffi):
        """When decimals=0, balance is stored unchanged."""
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = [{"value": 0}]
        MockCanister.return_value = mock_odin

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"type": "token", "ticker": "TEST", "id": "t1",
                 "balance": 50_000_000_000, "divisibility": 8,
                 "decimals": 0, "price": 1000}
            ]
        }
        mock_resp.text = '{"data": []}'
        mock_cffi.return_value = mock_resp

        with patch("iconfucius.accounts.resolve_odin_account", return_value="principal-abc"):
            result = collect_balances("bot-1", verbose=False)
        # decimals=0 → no correction
        assert result.token_holdings[0]["balance"] == 50_000_000_000

    @patch("iconfucius.cli.balance.read_cached_principal", return_value="principal-abc")
    def test_no_odin_account_returns_early(self, _mock_read_principal):
        """Bot without Odin.fun account returns immediately with has_odin_account=False."""
        with patch("iconfucius.accounts.resolve_odin_account", return_value=None):
            result = collect_balances("bot-1", verbose=False)
        assert isinstance(result, BotBalances)
        assert result.bot_name == "bot-1"
        assert result.has_odin_account is False
        assert result.odin_sats is None
        assert result.token_holdings is None

    @patch("iconfucius.cli.balance.siwb_login")
    @patch("iconfucius.cli.balance.read_cached_principal", return_value=None)
    def test_insufficient_funds_returns_note(self, _mock_read_principal,
                                              mock_login):
        """InsufficientFunds during siwb_login for uncached bot returns graceful note."""
        mock_login.side_effect = RuntimeError(
            "icrc2_approve for fee payment failed: {'InsufficientFunds': {'balance': 7}}"
        )
        result = collect_balances("bot-1", verbose=False)
        assert isinstance(result, BotBalances)
        assert result.bot_name == "bot-1"
        assert result.bot_principal == ""
        assert result.odin_sats is None
        assert "not yet initialized" in result.note

    @patch("iconfucius.cli.balance.siwb_login")
    @patch("iconfucius.cli.balance.read_cached_principal", return_value=None)
    def test_other_runtime_errors_propagate(self, _mock_read_principal,
                                             mock_login):
        """RuntimeErrors from siwb_login propagate."""
        mock_login.side_effect = RuntimeError("signBip322 failed: timeout")
        with pytest.raises(RuntimeError, match="signBip322 failed"):
            collect_balances("bot-1", verbose=False)

    @patch("iconfucius.http_utils.cffi_get_with_retry")
    @patch("iconfucius.cli.balance.Canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    @patch("iconfucius.cli.balance.read_cached_principal", return_value="principal-abc")
    def test_public_api_no_jwt(self, _mock_read_principal, _MockId, _MockClient,
                                _MockAgent, MockCanister, mock_cffi):
        """REST API call must NOT include an Authorization header."""
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = [{"value": 0}]
        MockCanister.return_value = mock_odin

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}
        mock_resp.text = '{"data": []}'
        mock_cffi.return_value = mock_resp

        with patch("iconfucius.accounts.resolve_odin_account", return_value="principal-abc"):
            collect_balances("bot-1", verbose=False)

        # Verify the REST API call was made and no Authorization header sent
        mock_cffi.assert_called_once()
        _args, kwargs = mock_cffi.call_args
        headers = kwargs.get("headers", {}) or {}
        assert "Authorization" not in headers


# ---------------------------------------------------------------------------
# run_all_balances
# ---------------------------------------------------------------------------

class TestRunAllBalances:
    def test_no_wallet(self, odin_project_no_wallet):  # noqa: ARG002
        """Verify no wallet."""
        result = run_all_balances(bot_names=["bot-1"])
        assert result is None

    @patch("iconfucius.cli.balance._format_holdings_table", return_value="table")
    @patch("iconfucius.cli.balance._collect_wallet_info")
    @patch("iconfucius.cli.balance.collect_balances")
    @patch("iconfucius.cli.balance._fetch_btc_usd_rate", return_value=100_000.0)
    def test_success(self, mock_rate, mock_collect, mock_wallet,
                     mock_holdings, odin_project):
        """Verify success."""
        mock_wallet.return_value = (
            {"principal": "p", "btc_address": "bc1", "balance_sats": 50000,
             "pending_sats": 0, "withdrawal_balance_sats": 0,
             "active_withdrawal_count": 0, "address_btc_sats": 0},
            ["wallet line"],
        )
        mock_collect.return_value = BotBalances("bot-1", "abc", odin_sats=1000.0,
                                                token_holdings=[],
                                                has_odin_account=True)

        result = run_all_balances(bot_names=["bot-1"])
        assert result is not None
        assert result["wallet_ckbtc_sats"] == 50000
        assert "_display" in result
        assert result["bots"][0]["has_odin_account"] is True
        mock_wallet.assert_called_once()
        mock_holdings.assert_called_once()

    @patch("iconfucius.cli.balance._format_holdings_table", return_value="table")
    @patch("iconfucius.cli.balance._collect_wallet_info")
    @patch("iconfucius.cli.balance.collect_balances")
    @patch("iconfucius.cli.balance._fetch_btc_usd_rate", return_value=100_000.0)
    def test_failed_bot_has_unknown_odin_account(self, mock_rate, mock_collect,
                                                  mock_wallet, mock_holdings,
                                                  odin_project):
        """A bot that fails balance collection appears with has_odin_account=None."""
        mock_wallet.return_value = (
            {"principal": "p", "btc_address": "bc1", "balance_sats": 50000,
             "pending_sats": 0, "withdrawal_balance_sats": 0,
             "active_withdrawal_count": 0, "address_btc_sats": 0},
            ["wallet line"],
        )
        # bot-1 succeeds, bot-2 fails
        mock_collect.side_effect = [
            BotBalances("bot-1", "abc", odin_sats=1000.0, token_holdings=[],
                        has_odin_account=True),
            Exception("SIWB login failed"),
        ]

        result = run_all_balances(bot_names=["bot-1", "bot-2"])
        assert result is not None
        bots = result["bots"]
        assert len(bots) == 2
        assert bots[0]["name"] == "bot-1"
        assert bots[0]["has_odin_account"] is True
        assert bots[0]["tokens"] == []
        assert bots[1]["name"] == "bot-2"
        assert bots[1]["has_odin_account"] is None
        assert bots[1]["odin_sats"] is None
        assert bots[1]["tokens"] is None

    @patch("iconfucius.cli.balance._format_holdings_table", return_value="table")
    @patch("iconfucius.cli.balance._collect_wallet_info")
    @patch("iconfucius.cli.balance.collect_balances")
    @patch("iconfucius.cli.balance._fetch_btc_usd_rate", return_value=100_000.0)
    def test_token_dicts_exclude_div(self, mock_rate, mock_collect,
                                      mock_wallet, mock_holdings,
                                      odin_project):
        """Token dicts in bots and totals must not contain 'div' (backend concern)."""
        mock_wallet.return_value = (
            {"principal": "p", "btc_address": "bc1", "balance_sats": 50000,
             "pending_sats": 0, "withdrawal_balance_sats": 0,
             "active_withdrawal_count": 0, "address_btc_sats": 0},
            ["wallet line"],
        )
        mock_collect.return_value = BotBalances(
            "bot-1", "abc", odin_sats=1000.0, has_odin_account=True,
            token_holdings=[{
                "ticker": "TEST", "token_id": "t1",
                "balance": 500_000_000, "divisibility": 8,
                "value_sats": 1000,
            }],
        )

        result = run_all_balances(bot_names=["bot-1"])
        assert result is not None
        # Per-bot token dicts must not expose div
        bot_token = result["bots"][0]["tokens"][0]
        assert "div" not in bot_token
        assert bot_token["ticker"] == "TEST"
        assert bot_token["balance"] == 5.0  # 500_000_000 / 10^8
        # Totals token dicts must not expose div
        totals_token = result["totals"]["tokens"]["TEST"]
        assert "div" not in totals_token

    @patch("iconfucius.cli.balance._collect_wallet_info")
    @patch("iconfucius.cli.balance.collect_balances", side_effect=Exception("fail"))
    @patch("iconfucius.cli.balance._fetch_btc_usd_rate", return_value=100_000.0)
    def test_handles_collection_error(self, mock_rate, mock_collect,
                                       mock_wallet, odin_project):
        """Verify handles collection error."""
        mock_wallet.return_value = (
            {"principal": "p", "btc_address": "bc1", "balance_sats": 50000,
             "pending_sats": 0, "withdrawal_balance_sats": 0,
             "active_withdrawal_count": 0, "address_btc_sats": 0},
            ["wallet line"],
        )

        result = run_all_balances(bot_names=["bot-1"])
        assert result is None

    @patch("iconfucius.cli.balance._format_holdings_table", return_value="table")
    @patch("iconfucius.cli.balance._collect_wallet_info")
    @patch("iconfucius.cli.balance.collect_balances")
    @patch("iconfucius.cli.balance._fetch_btc_usd_rate", return_value=100_000.0)
    def test_failed_bot_includes_error_message(self, _mock_rate, mock_collect,
                                                mock_wallet, _mock_holdings,
                                                odin_project):
        """Failed bots include the actual error message in their note."""
        mock_wallet.return_value = (
            {"principal": "p", "btc_address": "bc1", "balance_sats": 50000,
             "pending_sats": 0, "withdrawal_balance_sats": 0,
             "active_withdrawal_count": 0, "address_btc_sats": 0},
            ["wallet line"],
        )
        # bot-1 succeeds, bot-2 raises a connection error
        def side_effect(name, *a, **kw):
            if name == "bot-1":
                return BotBalances("bot-1", "abc", odin_sats=1000.0,
                                   has_odin_account=True, token_holdings=[])
            raise ConnectionError("Could not connect to server")
        mock_collect.side_effect = side_effect

        result = run_all_balances(bot_names=["bot-1", "bot-2"])
        assert result is not None
        bots = result["bots"]
        failed = [b for b in bots if b["name"] == "bot-2"]
        assert len(failed) == 1
        assert "Could not connect to server" in failed[0]["note"]


class TestFormatHoldingsTableUnknown:
    """Tests for ? display when odin_sats is None (API failure)."""

    def test_unknown_bot_shows_question_marks_for_tokens(self):
        """When odin_sats is None, token columns should show ? not 0."""
        data = [
            BotBalances("bot-1", "abc", odin_sats=1000.0,
                        token_holdings=[
                            {"ticker": "TEST", "token_id": "t1",
                             "balance": 10_000_000_000, "divisibility": 8,
                             "value_sats": 50}
                        ]),
            BotBalances("bot-2", "def", odin_sats=None,
                        token_holdings=None),
        ]
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        lines = output.strip().split("\n")
        # Find the bot-2 row
        bot2_line = [line for line in lines if "bot-2" in line]
        assert len(bot2_line) == 1
        # bot-2 row should have ? for ckBTC and ? for TEST column
        assert bot2_line[0].count("?") == 2

    def test_all_unknown_totals_show_question_marks(self):
        """When all bots have odin_sats=None, TOTAL row shows ? for all columns."""
        data = [
            BotBalances("bot-1", "abc", odin_sats=None, token_holdings=None),
            BotBalances("bot-2", "def", odin_sats=None, token_holdings=None),
        ]
        # Need at least one ticker column to test — but with all None,
        # all_tickers will be empty since token_holdings is None for both.
        # So test with no token columns: just ckBTC should show ?
        output = _format_holdings_table(data, btc_usd_rate=100_000.0)
        lines = output.strip().split("\n")
        total_line = [line for line in lines if "TOTAL" in line]
        assert len(total_line) == 1
        assert "?" in total_line[0]
        assert "Total portfolio value: ?" in output
