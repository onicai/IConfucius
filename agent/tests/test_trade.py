"""Tests for iconfucius.cli.trade — buy/sell tokens on Odin.Fun."""

from unittest.mock import MagicMock, patch

import pytest

M = "iconfucius.cli.trade"


def _make_mock_auth(bot_principal="bot-principal-abc"):
    """Create a mock auth for testing."""
    delegate = MagicMock()
    delegate.der_pubkey = b"\x30" * 44
    return {
        "delegate_identity": delegate,
        "bot_principal_text": bot_principal,
        "jwt_token": "jwt",
    }


class TestRunTradeSuccess:
    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST", "price": 1000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_buy(self, MockClient, MockAgent, MockCanister, mock_token_info,
                  mock_load, mock_patch_del, mock_unwrap, mock_rate,
                  odin_project):
        """Verify buy."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 100]  # BTC msat, token
        mock_odin.token_trade.return_value = {"ok": None}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        result = run_trade(bot_name="bot-1", action="buy", token_id="29m8",
                           amount="1000", verbose=False)

        assert result["status"] == "ok"
        assert result["action"] == "buy"
        assert result["bot_name"] == "bot-1"
        assert result["token_id"] == "29m8"
        assert result["amount"] == 1000
        assert "note" not in result
        mock_odin.token_trade.assert_called_once()

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST", "price": 1000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_buy_capped_to_balance(self, MockClient, MockAgent, MockCanister,
                                    mock_token_info, mock_load, mock_patch_del,
                                    mock_unwrap, mock_rate,
                                    odin_project):
        """Buy amount exceeding Odin.Fun balance is auto-capped."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [3_000_000, 0]  # 3000 sats on Odin
        mock_odin.token_trade.return_value = {"ok": None}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        # Request 5000 sats -> should be capped to 3000
        result = run_trade(bot_name="bot-1", action="buy", token_id="29m8",
                           amount="5000", verbose=False)

        assert result["status"] == "ok"
        assert result["amount"] == 3000  # capped to balance
        assert "auto-capped" in result["note"]
        call_args = mock_odin.token_trade.call_args[0][0]
        assert call_args["amount"] == {"btc": 3_000_000}  # 3000 sats in msat

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST", "price": 1000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_buy_balance_below_minimum(self, MockClient, MockAgent, MockCanister,
                                        mock_token_info, mock_load, mock_patch_del,
                                        mock_unwrap, mock_rate,
                                        odin_project):
        """Buy fails when Odin.Fun balance is below MIN_TRADE_SATS."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [100_000, 0]  # 100 sats < 500 min
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        result = run_trade(bot_name="bot-1", action="buy", token_id="29m8",
                           amount="5000", verbose=False)

        assert result["status"] == "error"
        assert "too low" in result["error"]
        mock_odin.token_trade.assert_not_called()

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST", "price": 500_000_000_000_000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_sell(self, MockClient, MockAgent, MockCanister, mock_token_info,
                   mock_load, mock_patch_del, mock_unwrap, mock_rate,
                   odin_project):
        """Verify sell."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 500]
        mock_odin.token_trade.return_value = {"ok": None}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        result = run_trade(bot_name="bot-1", action="sell", token_id="29m8",
                           amount="100", verbose=False)

        assert result["status"] == "ok"
        assert result["action"] == "sell"
        assert result["amount"] == 100


class TestRunTradeSellAll:
    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST", "price": 500_000_000_000_000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_sell_all(self, MockClient, MockAgent, MockCanister, mock_token_info,
                      mock_load, mock_patch_del, mock_unwrap, mock_rate,
                      odin_project):
        """Verify sell all."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 99_999]
        mock_odin.token_trade.return_value = {"ok": None}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        result = run_trade(bot_name="bot-1", action="sell", token_id="29m8",
                           amount="all", verbose=False)

        assert result["status"] == "ok"
        assert result["amount"] == 99_999
        # Verify trade used the full token balance
        call_args = mock_odin.token_trade.call_args[0][0]
        assert call_args["amount"] == {"token": 99_999}

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST", "price": 1000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_sell_all_zero_balance(self, MockClient, MockAgent, MockCanister,
                                    mock_token_info, mock_load, mock_patch_del,
                                    mock_unwrap, mock_rate,
                                    odin_project):
        """Verify sell all zero balance."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 0]
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        result = run_trade(bot_name="bot-1", action="sell", token_id="29m8",
                           amount="all", verbose=False)

        assert result["status"] == "skipped"
        assert "to sell" in result["reason"]
        mock_odin.token_trade.assert_not_called()


class TestRunTradeErrors:
    def test_no_wallet(self, odin_project_no_wallet):
        """Verify no wallet."""
        from iconfucius.cli.trade import run_trade
        result = run_trade(bot_name="bot-1", action="buy", token_id="29m8", amount="1000")
        assert result["status"] == "error"
        assert "wallet" in result["error"].lower()

    def test_invalid_action(self, odin_project):  # noqa: ARG002
        """Verify invalid action."""
        from iconfucius.cli.trade import run_trade
        result = run_trade(bot_name="bot-1", action="hold", token_id="29m8", amount="1000")
        assert result["status"] == "error"
        assert "must be 'buy' or 'sell'" in result["error"]

    def test_buy_all_rejected(self, odin_project):  # noqa: ARG002
        """Verify buy all rejected."""
        from iconfucius.cli.trade import run_trade
        result = run_trade(bot_name="bot-1", action="buy", token_id="29m8", amount="all")
        assert result["status"] == "error"
        assert "only supported for sell" in result["error"]

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST", "price": 1000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_trade_failure(self, MockClient, MockAgent, MockCanister,
                            mock_token_info, mock_load, mock_patch_del,
                            mock_unwrap, mock_rate,
                            odin_project):
        """Verify trade failure."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 100]
        mock_odin.token_trade.return_value = {"err": "insufficient BTC"}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        result = run_trade(bot_name="bot-1", action="buy", token_id="29m8",
                           amount="1000", verbose=False)

        assert result["status"] == "error"
        assert "insufficient BTC" in result["error"]

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.fetch_token_data", return_value=None)
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_token_info_unavailable(self, MockClient, MockAgent, MockCanister,
                                     mock_token_info, mock_load, mock_patch_del,
                                     mock_unwrap, mock_rate,
                                     odin_project):
        """Trade should work even if token info API is unavailable."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 100]
        mock_odin.token_trade.return_value = {"ok": None}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade

        # Should not raise
        result = run_trade(bot_name="bot-1", action="buy", token_id="29m8",
                           amount="1000", verbose=False)

        assert result["status"] == "ok"
