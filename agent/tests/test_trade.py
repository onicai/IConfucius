"""Tests for iconfucius.cli.trade — buy/sell tokens on Odin.Fun."""

from unittest.mock import MagicMock, patch

import pytest

M = "iconfucius.cli.trade"


def _make_mock_auth(bot_principal="bot-principal-abc"):
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
    @patch(f"{M}._fetch_token_info", return_value={"ticker": "TEST", "price": 1000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_buy(self, MockClient, MockAgent, MockCanister, mock_token_info,
                  mock_load, mock_patch_del, mock_unwrap, mock_rate,
                  odin_project, capsys):
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 100]  # BTC msat, token
        mock_odin.token_trade.return_value = {"ok": None}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        run_trade(bot_name="bot-1", action="buy", token_id="29m8",
                  amount="1000", verbose=False)

        output = capsys.readouterr().out
        assert "Trade: BUY" in output
        assert "Trade executed successfully" in output
        mock_odin.token_trade.assert_called_once()

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}._fetch_token_info", return_value={"ticker": "TEST", "price": 500_000_000_000_000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_sell(self, MockClient, MockAgent, MockCanister, mock_token_info,
                   mock_load, mock_patch_del, mock_unwrap, mock_rate,
                   odin_project, capsys):
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 500]
        mock_odin.token_trade.return_value = {"ok": None}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        run_trade(bot_name="bot-1", action="sell", token_id="29m8",
                  amount="100", verbose=False)

        output = capsys.readouterr().out
        assert "Trade: SELL" in output
        assert "Trade executed successfully" in output


class TestRunTradeSellAll:
    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}._fetch_token_info", return_value={"ticker": "TEST", "price": 500_000_000_000_000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_sell_all(self, MockClient, MockAgent, MockCanister, mock_token_info,
                      mock_load, mock_patch_del, mock_unwrap, mock_rate,
                      odin_project, capsys):
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 99_999]
        mock_odin.token_trade.return_value = {"ok": None}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        run_trade(bot_name="bot-1", action="sell", token_id="29m8",
                  amount="all", verbose=False)

        output = capsys.readouterr().out
        assert "SELL ALL" in output
        assert "Trade executed successfully" in output
        # Verify trade used the full token balance
        call_args = mock_odin.token_trade.call_args[0][0]
        assert call_args["amount"] == {"token": 99_999}

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}._fetch_token_info", return_value={"ticker": "TEST", "price": 1000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_sell_all_zero_balance(self, MockClient, MockAgent, MockCanister,
                                    mock_token_info, mock_load, mock_patch_del,
                                    mock_unwrap, mock_rate,
                                    odin_project, capsys):
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 0]
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        run_trade(bot_name="bot-1", action="sell", token_id="29m8",
                  amount="all", verbose=False)

        output = capsys.readouterr().out
        assert "No" in output and "to sell" in output
        mock_odin.token_trade.assert_not_called()


class TestRunTradeErrors:
    def test_no_wallet(self, odin_project_no_wallet, capsys):
        from iconfucius.cli.trade import run_trade
        run_trade(bot_name="bot-1", action="buy", token_id="29m8", amount="1000")
        output = capsys.readouterr().out
        assert "No iconfucius wallet found" in output

    def test_invalid_action(self, odin_project, capsys):
        from iconfucius.cli.trade import run_trade
        run_trade(bot_name="bot-1", action="hold", token_id="29m8", amount="1000")
        output = capsys.readouterr().out
        assert "must be 'buy' or 'sell'" in output

    def test_buy_all_rejected(self, odin_project, capsys):
        from iconfucius.cli.trade import run_trade
        run_trade(bot_name="bot-1", action="buy", token_id="29m8", amount="all")
        output = capsys.readouterr().out
        assert "only supported for sell" in output

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}._fetch_token_info", return_value={"ticker": "TEST", "price": 1000})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_trade_failure(self, MockClient, MockAgent, MockCanister,
                            mock_token_info, mock_load, mock_patch_del,
                            mock_unwrap, mock_rate,
                            odin_project, capsys):
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 100]
        mock_odin.token_trade.return_value = {"err": "insufficient BTC"}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade
        run_trade(bot_name="bot-1", action="buy", token_id="29m8",
                  amount="1000", verbose=False)

        output = capsys.readouterr().out
        assert "FAILED" in output

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}._fetch_token_info", return_value=None)
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_token_info_unavailable(self, MockClient, MockAgent, MockCanister,
                                     mock_token_info, mock_load, mock_patch_del,
                                     mock_unwrap, mock_rate,
                                     odin_project, capsys):
        """Trade should work even if token info API is unavailable."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.side_effect = [5_000_000, 100]
        mock_odin.token_trade.return_value = {"ok": None}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.trade import run_trade

        # Should not raise
        run_trade(bot_name="bot-1", action="buy", token_id="29m8",
                  amount="1000", verbose=False)

        output = capsys.readouterr().out
        assert "Trade executed successfully" in output
