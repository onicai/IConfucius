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
                         odin_project, capsys, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        # Mock approve canister
        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Ok": 1}
        # Mock deposit canister
        mock_deposit = MagicMock()
        mock_deposit.ckbtc_deposit.return_value = {"ok": 1}
        MockCanister.side_effect = [mock_ckbtc, mock_deposit]

        from iconfucius.cli.fund import run_fund
        run_fund(bot_names=["bot-1"], amount=5000, verbose=False)

        output = capsys.readouterr().out
        assert "bot-1: done" in output
        assert "Funded 1 bot(s) successfully" in output
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
                            odin_project, capsys, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Ok": 1}
        mock_deposit = MagicMock()
        mock_deposit.ckbtc_deposit.return_value = {"ok": 1}
        MockCanister.side_effect = [mock_ckbtc, mock_deposit] * 3

        from iconfucius.cli.fund import run_fund
        run_fund(bot_names=["bot-1", "bot-2", "bot-3"], amount=5000, verbose=False)

        output = capsys.readouterr().out
        assert "Funded 3 bot(s) successfully" in output
        assert mock_transfer.call_count == 3


class TestRunFundErrors:
    def test_no_wallet(self, odin_project_no_wallet, capsys):
        from iconfucius.cli.fund import run_fund
        run_fund(bot_names=["bot-1"], amount=5000)
        output = capsys.readouterr().out
        assert "No iconfucius wallet found" in output

    def test_zero_amount(self, odin_project, capsys):
        from iconfucius.cli.fund import run_fund
        run_fund(bot_names=["bot-1"], amount=0)
        output = capsys.readouterr().out
        assert "Amount must be positive" in output

    @patch(f"{M}.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{M}.get_balance", return_value=100)
    @patch(f"{M}.create_icrc1_canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    @patch(f"{M}.Identity")
    def test_insufficient_balance(self, MockId, MockClient, MockAgent,
                                   mock_create, mock_get_bal, mock_rate,
                                   odin_project, capsys):
        MockId.from_pem.return_value = _make_mock_identity()

        from iconfucius.cli.fund import run_fund
        run_fund(bot_names=["bot-1"], amount=50000)

        output = capsys.readouterr().out
        assert "Insufficient wallet balance" in output

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
                               odin_project, capsys, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        from iconfucius.cli.fund import run_fund
        run_fund(bot_names=["bot-1"], amount=5000)

        output = capsys.readouterr().out
        assert "FAILED (transfer)" in output

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
                              odin_project, capsys, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Err": {"GenericError": {}}}
        MockCanister.return_value = mock_ckbtc

        from iconfucius.cli.fund import run_fund
        run_fund(bot_names=["bot-1"], amount=5000)

        output = capsys.readouterr().out
        assert "FAILED (approve)" in output

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
                              odin_project, capsys, mock_siwb_auth):
        MockId.from_pem.return_value = _make_mock_identity()
        mock_load.return_value = mock_siwb_auth

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Ok": 1}
        mock_deposit = MagicMock()
        mock_deposit.ckbtc_deposit.return_value = {"err": "deposit error"}
        MockCanister.side_effect = [mock_ckbtc, mock_deposit]

        from iconfucius.cli.fund import run_fund
        run_fund(bot_names=["bot-1"], amount=5000)

        output = capsys.readouterr().out
        assert "FAILED (deposit)" in output
