"""Tests for iconfucius.cli.withdraw — withdraw from Odin.Fun back to wallet."""

from unittest.mock import MagicMock, patch

import pytest

M = "iconfucius.cli.withdraw"


def _make_mock_identity(principal_str="controller-principal"):
    """Create a mock identity for testing."""
    identity = MagicMock()
    identity.sender.return_value = MagicMock(__str__=lambda _: principal_str)
    return identity


def _make_mock_auth(bot_principal="bot-principal-abc"):
    """Create a mock auth for testing."""
    delegate = MagicMock()
    delegate.der_pubkey = b"\x30" * 44
    return {
        "delegate_identity": delegate,
        "bot_principal_text": bot_principal,
        "jwt_token": "jwt",
    }


class TestRunWithdrawSuccess:
    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.transfer", return_value={"Ok": 1})
    @patch(f"{M}.get_balance")
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_withdraw_specific_amount(self, MockId, MockClient, MockAgent,
                                       MockCanister, mock_load,
                                       mock_patch_del, mock_unwrap,
                                       mock_create_icrc1, mock_get_bal,
                                       mock_transfer, mock_rate,
                                       odin_project):
        """Verify withdraw specific amount."""
        mock_load.return_value = _make_mock_auth()
        MockId.from_pem.return_value = _make_mock_identity()

        # Odin canister: getBalance returns 5000 sats in msat
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = 5_000_000  # 5000 sats in msat
        mock_odin.token_withdraw.return_value = {"ok": True}
        MockCanister.side_effect = [mock_odin, mock_odin]

        # After withdrawal, bot has 4990 sats ckBTC (minus fee)
        mock_get_bal.side_effect = [4990, 0, 50000]  # bot ckbtc, bot after sweep, controller
        mock_transfer.return_value = {"Ok": 1}

        from iconfucius.cli.withdraw import run_withdraw
        result = run_withdraw(bot_name="bot-1", amount="3000")

        assert result["status"] == "ok"
        assert result["withdrawn_sats"] == 3000
        assert result["transferred_sats"] == 4990 - 10  # bot_ckbtc - CKBTC_FEE

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.transfer", return_value={"Ok": 1})
    @patch(f"{M}.get_balance")
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_withdraw_all(self, MockId, MockClient, MockAgent,
                           MockCanister, mock_load, mock_patch_del,
                           mock_unwrap, mock_create_icrc1, mock_get_bal,
                           mock_transfer, mock_rate,
                           odin_project):
        """Verify withdraw all."""
        mock_load.return_value = _make_mock_auth()
        MockId.from_pem.return_value = _make_mock_identity()

        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = 10_000_000  # 10000 sats
        mock_odin.token_withdraw.return_value = {"ok": True}
        MockCanister.side_effect = [mock_odin, mock_odin]

        mock_get_bal.side_effect = [9990, 0, 60000]
        mock_transfer.return_value = {"Ok": 1}

        from iconfucius.cli.withdraw import run_withdraw
        result = run_withdraw(bot_name="bot-1", amount="all")

        assert result["status"] == "ok"
        assert result["withdrawn_sats"] == 10000
        assert "wallet_balance_sats" in result


class TestRunWithdrawErrors:
    def test_no_wallet(self, odin_project_no_wallet):
        """Verify no wallet."""
        from iconfucius.cli.withdraw import run_withdraw
        result = run_withdraw(bot_name="bot-1", amount="1000")
        assert result["status"] == "error"
        assert "No wallet found" in result["error"]

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_insufficient_balance(self, MockClient, MockAgent, MockCanister,
                                   mock_load, mock_patch_del, mock_unwrap,
                                   mock_rate, odin_project):
        """Verify insufficient balance."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = 500_000  # 500 sats
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.withdraw import run_withdraw
        result = run_withdraw(bot_name="bot-1", amount="10000")

        assert result["status"] == "error"
        assert "Insufficient balance" in result["error"]

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_zero_balance(self, MockClient, MockAgent, MockCanister,
                           mock_load, mock_patch_del, mock_unwrap,
                           mock_rate, odin_project):
        """Verify zero balance."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = 0
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.withdraw import run_withdraw
        result = run_withdraw(bot_name="bot-1", amount="all")

        assert result["status"] == "error"
        assert "No funds to withdraw" in result["error"]

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_withdraw_canister_error(self, MockClient, MockAgent, MockCanister,
                                      mock_load, mock_patch_del, mock_unwrap,
                                      mock_rate, odin_project):
        """Verify withdraw canister error."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = 5_000_000
        mock_odin.token_withdraw.return_value = {"err": "withdrawal error"}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.withdraw import run_withdraw
        result = run_withdraw(bot_name="bot-1", amount="1000")

        assert result["status"] == "error"
        assert result["step"] == "token_withdraw"

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.get_balance", return_value=5)  # Below fee
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_sweep_skipped_when_balance_too_low(self, MockClient, MockAgent,
                                                  MockCanister, mock_load,
                                                  mock_patch_del, mock_unwrap,
                                                  mock_create_icrc1,
                                                  mock_get_bal, mock_rate,
                                                  odin_project):
        """Verify sweep skipped when balance too low."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = 5_000_000
        mock_odin.token_withdraw.return_value = {"ok": True}
        MockCanister.side_effect = [mock_odin, mock_odin]

        from iconfucius.cli.withdraw import run_withdraw
        result = run_withdraw(bot_name="bot-1", amount="1000")

        assert result["status"] == "partial"
        assert "too low to transfer" in result["error"]
