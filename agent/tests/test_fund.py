"""Tests for iconfucius.cli.fund — fund + deposit into Odin.Fun."""

from unittest.mock import MagicMock, patch, call

import pytest

M = "iconfucius.cli.fund"


def _make_mock_identity(principal_str="controller-principal"):
    identity = MagicMock()
    identity.sender.return_value = MagicMock(__str__=lambda s: principal_str)
    return identity


def _make_mock_auth(bot_principal="bot-principal-abc"):
    delegate = MagicMock()
    delegate.der_pubkey = b"\x30" * 44
    return {
        "delegate_identity": delegate,
        "bot_principal_text": bot_principal,
        "jwt_token": "jwt",
    }


class TestRunFundSuccess:
    @patch("iconfucius.cli.balance.run_all_balances")
    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.transfer", return_value={"Ok": 1})
    @patch(f"{M}.get_balance", return_value=100_000)
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Principal")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_single_bot(self, MockId, MockClient, MockAgent, MockPrincipal,
                         MockCanister, mock_load, mock_create_icrc1,
                         mock_get_bal, mock_transfer, mock_patch_del,
                         mock_unwrap, mock_rate, mock_run_all,
                         odin_project, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        # Mock approve canister
        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Ok": 1}
        # Mock deposit canister
        mock_deposit = MagicMock()
        mock_deposit.ckbtc_deposit.return_value = {"ok": 1}
        # Mock Odin trading canister (balance query)
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = 5_000_000  # 5000 sats in msat
        MockCanister.side_effect = [mock_ckbtc, mock_deposit, mock_odin]

        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=5000, verbose=False)

        assert result["status"] == "ok"
        assert result["funded"] == ["bot-1"]
        assert result["failed"] == []
        assert result["amount"] == 5000
        assert result["details"] == [{"bot": "bot-1", "odin_balance_sats": 5000}]
        assert len(result["notes"]) == 1
        assert "New Odin.Fun balance" in result["notes"][0]
        mock_transfer.assert_called_once()
        mock_ckbtc.icrc2_approve.assert_called_once()
        mock_deposit.ckbtc_deposit.assert_called_once()

    @patch("iconfucius.cli.balance.run_all_balances")
    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.transfer", return_value={"Ok": 1})
    @patch(f"{M}.get_balance", return_value=500_000)
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Principal")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_multiple_bots(self, MockId, MockClient, MockAgent, MockPrincipal,
                            MockCanister, mock_load, mock_create_icrc1,
                            mock_get_bal, mock_transfer, mock_patch_del,
                            mock_unwrap, mock_rate, mock_run_all,
                            odin_project, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        # Use a single mock with all methods — avoids thread-ordering issues
        # with side_effect lists in concurrent run_per_bot
        mock_canister = MagicMock()
        mock_canister.icrc2_approve.return_value = {"Ok": 1}
        mock_canister.ckbtc_deposit.return_value = {"ok": 1}
        mock_canister.getBalance.return_value = 5_000_000  # 5000 sats in msat
        MockCanister.return_value = mock_canister

        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1", "bot-2", "bot-3"], amount=5000, verbose=False)

        assert result["status"] == "ok"
        assert len(result["funded"]) == 3
        assert result["bot_count"] == 3
        assert len(result["details"]) == 3
        assert len(result["notes"]) == 3
        assert mock_transfer.call_count == 3

    @patch("iconfucius.cli.balance.run_all_balances")
    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.transfer", return_value={"Ok": 1})
    @patch(f"{M}.get_balance", return_value=100_000)
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Principal")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_balance_differs_from_deposit(self, MockId, MockClient, MockAgent,
                                           MockPrincipal, MockCanister,
                                           mock_load, mock_create_icrc1,
                                           mock_get_bal, mock_transfer,
                                           mock_patch_del, mock_unwrap,
                                           mock_rate, mock_run_all,
                                           odin_project, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Ok": 1}
        mock_deposit = MagicMock()
        mock_deposit.ckbtc_deposit.return_value = {"ok": 1}
        # Balance is less than deposited due to fees
        mock_odin = MagicMock()
        mock_odin.getBalance.return_value = 4_985_000  # 4985 sats in msat
        MockCanister.side_effect = [mock_ckbtc, mock_deposit, mock_odin]

        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=5000, verbose=False)

        assert result["status"] == "ok"
        assert result["details"] == [{"bot": "bot-1", "odin_balance_sats": 4985}]
        assert len(result["notes"]) == 1
        assert "New Odin.Fun balance" in result["notes"][0]


class TestRunFundErrors:
    def test_no_wallet(self, odin_project_no_wallet):
        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=5000)
        assert result["status"] == "error"
        assert "No wallet found" in result["error"]

    def test_zero_amount(self, odin_project):
        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=0)
        assert result["status"] == "error"
        assert "Amount must be positive" in result["error"]

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.get_balance", return_value=100)
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_insufficient_balance(self, MockId, MockClient, MockAgent,
                                   mock_create, mock_get_bal, mock_rate,
                                   odin_project):
        MockId.from_pem.return_value = _make_mock_identity()

        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=50000)

        assert result["status"] == "error"
        assert "Insufficient wallet balance" in result["error"]

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.transfer", return_value={"Err": {"InsufficientFunds": {"balance": 0}}})
    @patch(f"{M}.get_balance", return_value=100_000)
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_transfer_failure(self, MockId, MockClient, MockAgent,
                               mock_load, mock_create, mock_get_bal,
                               mock_transfer, mock_patch_del, mock_rate,
                               odin_project, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=5000)

        assert result["status"] == "partial"
        assert len(result["failed"]) == 1
        assert "transfer" in result["failed"][0]["error"]

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.transfer", return_value={"Ok": 1})
    @patch(f"{M}.get_balance", return_value=100_000)
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Principal")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_approve_failure(self, MockId, MockClient, MockAgent, MockPrincipal,
                              MockCanister, mock_load, mock_create,
                              mock_get_bal, mock_transfer, mock_patch_del,
                              mock_unwrap, mock_rate,
                              odin_project, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Err": {"GenericError": {}}}
        MockCanister.return_value = mock_ckbtc

        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=5000)

        assert result["status"] == "partial"
        assert len(result["failed"]) == 1
        assert "approve" in result["failed"][0]["error"]

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.transfer", return_value={"Ok": 1})
    @patch(f"{M}.get_balance", return_value=100_000)
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.load_session")
    @patch(f"{M}.Canister")
    @patch(f"{M}.Principal")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_deposit_failure(self, MockId, MockClient, MockAgent, MockPrincipal,
                              MockCanister, mock_load, mock_create,
                              mock_get_bal, mock_transfer, mock_patch_del,
                              mock_unwrap, mock_rate,
                              odin_project, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Ok": 1}
        mock_deposit = MagicMock()
        mock_deposit.ckbtc_deposit.return_value = {"err": "deposit error"}
        MockCanister.side_effect = [mock_ckbtc, mock_deposit]

        from iconfucius.cli.fund import run_fund
        result = run_fund(bot_names=["bot-1"], amount=5000)

        assert result["status"] == "partial"
        assert len(result["failed"]) == 1
        assert "deposit" in result["failed"][0]["error"]
