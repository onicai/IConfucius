"""Tests for iconfucius.cli.wallet — wallet identity and fund management."""

import os
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from iconfucius.cli import app

runner = CliRunner()

# Patch at source modules since wallet.py uses local imports
ID = "icp_identity.Identity"
AG = "icp_agent.Agent"
CL = "icp_agent.Client"
TR = "iconfucius.transfers"


# ---------------------------------------------------------------------------
# wallet create
# ---------------------------------------------------------------------------

class TestWalletCreate:
    @patch(ID)
    def test_creates_wallet(self, MockIdentity, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        mock_identity = MagicMock()
        mock_identity.to_pem.return_value = b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n"
        MockIdentity.return_value = mock_identity

        result = runner.invoke(app, ["wallet", "create"])
        assert result.exit_code == 0
        assert "Wallet created" in result.output
        pem_path = tmp_path / ".wallet" / "identity-private.pem"
        assert pem_path.exists()

    @patch(ID)
    def test_refuses_overwrite(self, MockIdentity, odin_project):
        result = runner.invoke(app, ["wallet", "create"])
        assert result.exit_code == 1
        assert "already exists" in result.output

    @patch(ID)
    def test_force_overwrites(self, MockIdentity, odin_project):
        mock_identity = MagicMock()
        mock_identity.to_pem.return_value = b"-----BEGIN PRIVATE KEY-----\nnew\n-----END PRIVATE KEY-----\n"
        MockIdentity.return_value = mock_identity

        result = runner.invoke(app, ["wallet", "create", "--force"])
        assert result.exit_code == 0
        assert "Wallet created" in result.output

    @patch(ID)
    def test_force_creates_backup(self, MockIdentity, odin_project):
        """--force should back up existing PEM before creating new one."""
        mock_identity = MagicMock()
        mock_identity.to_pem.return_value = b"new-pem-content"
        MockIdentity.return_value = mock_identity

        original_content = (odin_project / ".wallet" / "identity-private.pem").read_text()
        result = runner.invoke(app, ["wallet", "create", "--force"])
        assert result.exit_code == 0
        assert "Backed up" in result.output

        backup = odin_project / ".wallet" / "identity-private.pem-backup-01"
        assert backup.exists()
        assert backup.read_text() == original_content

    @patch(ID)
    def test_force_increments_backup_number(self, MockIdentity, odin_project):
        """Multiple --force calls should create -backup-01, -backup-02, etc."""
        mock_identity = MagicMock()
        mock_identity.to_pem.return_value = b"new-pem"
        MockIdentity.return_value = mock_identity

        # Create a pre-existing backup-01
        (odin_project / ".wallet" / "identity-private.pem-backup-01").write_text("old-backup")

        result = runner.invoke(app, ["wallet", "create", "--force"])
        assert result.exit_code == 0

        # backup-01 should be untouched, backup-02 should exist
        assert (odin_project / ".wallet" / "identity-private.pem-backup-01").read_text() == "old-backup"
        assert (odin_project / ".wallet" / "identity-private.pem-backup-02").exists()

    @patch(ID)
    def test_force_preserves_backup_content(self, MockIdentity, odin_project):
        """Backup should contain the old PEM, new file should have new content."""
        mock_identity = MagicMock()
        mock_identity.to_pem.return_value = b"brand-new-key"
        MockIdentity.return_value = mock_identity

        old_content = (odin_project / ".wallet" / "identity-private.pem").read_text()
        runner.invoke(app, ["wallet", "create", "--force"])

        backup = odin_project / ".wallet" / "identity-private.pem-backup-01"
        assert backup.read_text() == old_content
        new_content = (odin_project / ".wallet" / "identity-private.pem").read_bytes()
        assert new_content == b"brand-new-key"

    @pytest.mark.skipif(os.name == "nt", reason="Unix file permissions not supported on Windows")
    @patch(ID)
    def test_sets_pem_permissions(self, MockIdentity, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        mock_identity = MagicMock()
        mock_identity.to_pem.return_value = b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n"
        MockIdentity.return_value = mock_identity

        runner.invoke(app, ["wallet", "create"])
        pem_path = tmp_path / ".wallet" / "identity-private.pem"
        mode = oct(os.stat(pem_path).st_mode)[-3:]
        assert mode == "600"

    @patch(ID)
    def test_shows_diagram(self, MockIdentity, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        mock_identity = MagicMock()
        mock_identity.to_pem.return_value = b"fake-pem"
        MockIdentity.return_value = mock_identity

        result = runner.invoke(app, ["wallet", "create"])
        assert "iconfucius wallet" in result.output
        assert "bot-1" in result.output


# ---------------------------------------------------------------------------
# wallet info
# ---------------------------------------------------------------------------

class TestWalletInfo:
    @patch(f"{TR}.get_btc_address", return_value="bc1qtest123")
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(f"{TR}.get_balance", return_value=25000)
    @patch(f"{TR}.create_icrc1_canister")
    @patch("iconfucius.cli.balance.Agent")
    @patch("iconfucius.cli.balance.Client")
    @patch("iconfucius.cli.balance.Identity")
    def test_shows_info(self, MockIdentity, MockClient, MockAgent,
                         mock_create, mock_get_bal, mock_minter,
                         mock_btc_addr, odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "test-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        result = runner.invoke(app, ["wallet", "info"])
        assert result.exit_code == 0
        assert "25,000 sats" in result.output
        # Funding instructions moved to how_to_fund_wallet / wallet receive
        assert "To fund your wallet:" not in result.output
        assert "Wallet PEM file:" in result.output
        assert "Notes:" in result.output
        # No minter section by default
        assert "ckBTC minter:" not in result.output

    @patch(f"{TR}.unwrap_canister_result", return_value=0)
    @patch(f"{TR}.get_withdrawal_account",
           return_value={"owner": "minter", "subaccount": []})
    @patch(f"{TR}.get_btc_address", return_value="bc1qtest123")
    @patch(f"{TR}.check_btc_deposits",
           return_value={"Err": {"NoNewUtxos": {
               "required_confirmations": 4,
               "current_confirmations": [2],
               "pending_utxos": [[]],
               "suspended_utxos": [[]],
           }}})
    @patch(f"{TR}.get_pending_btc", return_value=5000)
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(f"{TR}.get_balance", return_value=25000)
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_info_shows_confirmations(self, MockIdentity, MockClient, MockAgent,
                                       mock_create, mock_get_bal, mock_minter,
                                       mock_pending, mock_check, mock_btc_addr,
                                       mock_withdrawal_acct, mock_unwrap,
                                       odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "test-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        result = runner.invoke(app, ["wallet", "info", "--ckbtc-minter"])
        assert result.exit_code == 0
        assert "ckBTC minter:" in result.output
        assert "5,000 sats" in result.output
        assert "2/4" in result.output

    @patch(f"{TR}.unwrap_canister_result", return_value=0)
    @patch(f"{TR}.get_withdrawal_account",
           return_value={"owner": "minter", "subaccount": []})
    @patch(f"{TR}.get_btc_address", return_value="bc1qtest123")
    @patch(f"{TR}.check_btc_deposits",
           return_value={"Ok": [{"amount": 5000}]})
    @patch(f"{TR}.get_pending_btc", return_value=5000)
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(f"{TR}.get_balance")
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_info_converts_pending_btc(self, MockIdentity, MockClient, MockAgent,
                                        mock_create, mock_get_bal, mock_minter,
                                        mock_pending, mock_check, mock_btc_addr,
                                        mock_withdrawal_acct, mock_unwrap,
                                        odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "test-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        mock_get_bal.side_effect = [25000, 30000]  # before, after conversion

        result = runner.invoke(app, ["wallet", "info", "--ckbtc-minter"])
        assert result.exit_code == 0
        assert "converted 5,000 sats" in result.output
        assert "Updated ckBTC balance" in result.output

    @patch(f"{TR}.unwrap_canister_result")
    @patch(f"{TR}.get_withdrawal_account",
           return_value={"owner": "minter", "subaccount": []})
    @patch(f"{TR}.get_btc_address", return_value="bc1qtest123")
    @patch(f"{TR}.get_pending_btc", return_value=0)
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(f"{TR}.get_balance", return_value=25000)
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_info_shows_withdrawal_status(self, MockIdentity, MockClient,
                                           MockAgent, mock_create, mock_get_bal,
                                           mock_minter, mock_pending,
                                           mock_btc_addr, mock_withdrawal_acct,
                                           mock_unwrap, odin_project, tmp_path,
                                           monkeypatch):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "test-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        # unwrap: first call for withdrawal account balance (0),
        # second call for retrieve_btc_status_v2
        mock_unwrap.side_effect = [
            0,
            {"Submitted": {"txid": b"\x08g8a\x0fe\xfdx/k\xf7jv\xa9\x89\x82H4U\x13\xc1\xadK!C\x8d\x8cj\xc4G\xef?"}},
        ]

        # Create withdrawals tracking file
        import json
        status_file = tmp_path / ".wallet" / "btc_withdrawals.json"
        status_file.parent.mkdir(exist_ok=True)
        status_file.write_text(json.dumps([{
            "block_index": 99,
            "btc_address": "bc1qtest456",
            "amount": 50000,
        }]))

        result = runner.invoke(app, ["wallet", "info", "--ckbtc-minter"])
        assert result.exit_code == 0
        assert "Sending BTC: Submitted" in result.output
        assert "50,000 sats" in result.output
        assert "mempool.space/tx/" in result.output


# ---------------------------------------------------------------------------
# wallet receive
# ---------------------------------------------------------------------------

class TestWalletReceive:
    @patch("iconfucius.cli.balance.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{TR}.get_balance", return_value=10000)
    @patch(f"{TR}.get_btc_address", return_value="bc1qtestaddr123")
    @patch(f"{TR}.create_icrc1_canister")
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_shows_addresses(self, MockIdentity, MockClient, MockAgent,
                              mock_minter, mock_ckbtc, mock_btc_addr,
                              mock_get_bal, mock_rate, odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "controller-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        result = runner.invoke(app, ["wallet", "receive"])
        assert result.exit_code == 0
        assert "Fund your iconfucius wallet" in result.output
        assert "bc1qtestaddr123" in result.output
        assert "controller-principal" in result.output
        assert "Option 1: Send BTC" in result.output
        assert "Option 2: Send ckBTC" in result.output
        assert "10,000 sats" in result.output


# ---------------------------------------------------------------------------
# wallet send (ckBTC)
# ---------------------------------------------------------------------------

class TestWalletSendCkbtc:
    @patch(f"{TR}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{TR}.transfer", return_value={"Ok": 42})
    @patch(f"{TR}.get_balance")
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_send_ckbtc_success(self, MockIdentity, MockClient, MockAgent,
                                 mock_create, mock_get_bal, mock_transfer,
                                 mock_unwrap, odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        mock_get_bal.side_effect = [5000, 3990]  # before, after

        result = runner.invoke(app, ["wallet", "send", "1000", "dest-principal"])
        assert result.exit_code == 0
        assert "Transfer succeeded" in result.output

    @patch(f"{TR}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{TR}.get_balance", return_value=5)
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_send_ckbtc_insufficient(self, MockIdentity, MockClient, MockAgent,
                                      mock_create, mock_get_bal, mock_unwrap,
                                      odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        result = runner.invoke(app, ["wallet", "send", "1000", "dest-principal"])
        assert result.exit_code == 1
        assert "Insufficient balance" in result.output

    @patch(f"{TR}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{TR}.transfer", return_value={"Ok": 1})
    @patch(f"{TR}.get_balance")
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_send_all_ckbtc(self, MockIdentity, MockClient, MockAgent,
                             mock_create, mock_get_bal, mock_transfer,
                             mock_unwrap, odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        mock_get_bal.side_effect = [5000, 0]

        result = runner.invoke(app, ["wallet", "send", "all", "dest-principal"])
        assert result.exit_code == 0
        assert "Sending all: 4,990 sats" in result.output


# ---------------------------------------------------------------------------
# wallet send (BTC)
# ---------------------------------------------------------------------------

class TestWalletSendBtc:
    @patch(f"{TR}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{TR}.retrieve_btc_withdrawal", return_value={"Ok": {"block_index": 99}})
    @patch(f"{TR}.estimate_withdrawal_fee",
           return_value={"minter_fee": 10, "bitcoin_fee": 2000})
    @patch(f"{TR}.get_withdrawal_account",
           return_value={"owner": "minter", "subaccount": []})
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(f"{TR}.get_balance")
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_send_btc_success(self, MockIdentity, MockClient, MockAgent,
                               mock_create_icrc1, mock_get_bal,
                               mock_create_minter, mock_withdrawal_acct,
                               mock_est_fee, mock_retrieve,
                               mock_unwrap, odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc1_transfer.return_value = [{"value": {"Ok": 1}}]
        mock_ckbtc.icrc1_balance_of.return_value = 0  # no existing withdrawal balance
        mock_create_icrc1.side_effect = [mock_ckbtc, mock_ckbtc]

        mock_get_bal.side_effect = [100_000, 40_000]

        result = runner.invoke(app, ["wallet", "send", "50000", "bc1qtest123"])
        assert result.exit_code == 0
        assert "BTC withdrawal initiated" in result.output

    @patch(f"{TR}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{TR}.estimate_withdrawal_fee",
           return_value={"minter_fee": 10, "bitcoin_fee": 2000})
    @patch(f"{TR}.get_withdrawal_account",
           return_value={"owner": "minter", "subaccount": []})
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(f"{TR}.get_balance", return_value=100_000)
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_send_btc_below_minimum(self, MockIdentity, MockClient, MockAgent,
                                      mock_create_icrc1, mock_get_bal,
                                      mock_create_minter, mock_withdrawal_acct,
                                      mock_est_fee,
                                      mock_unwrap, odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc1_balance_of.return_value = 0
        mock_create_icrc1.side_effect = [mock_ckbtc, mock_ckbtc]

        result = runner.invoke(app, ["wallet", "send", "5000", "bc1qtest123"])
        assert result.exit_code == 1
        assert "withdrawal amount too low" in result.output.lower()
        assert "50,000" in result.output


# ---------------------------------------------------------------------------
# wallet balances
# ---------------------------------------------------------------------------

class TestWalletBalance:
    @patch("iconfucius.cli.balance.run_all_balances")
    def test_wallet_balance_command(self, mock_run, odin_project):
        result = runner.invoke(app, ["wallet", "balance", "--all-bots"])
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# Backup warning
# ---------------------------------------------------------------------------

class TestBackupWarning:
    @patch(f"{TR}.get_btc_address", return_value="bc1qtest123")
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(f"{TR}.get_balance", return_value=25000)
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_backup_warning_shown(self, MockIdentity, MockClient, MockAgent,
                                   mock_create, mock_get_bal, mock_minter,
                                   mock_btc_addr,
                                   odin_project):
        """wallet info shows the backup warning when PEM exists."""
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "test-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        result = runner.invoke(app, ["wallet", "info"])
        assert "Back up .wallet/identity-private.pem" in result.output


# ---------------------------------------------------------------------------
# _backup_pem (unit tests)
# ---------------------------------------------------------------------------

class TestBackupPem:
    def test_creates_backup_01(self, tmp_path):
        from iconfucius.cli.wallet import _backup_pem

        pem = tmp_path / "identity-private.pem"
        pem.write_text("original-key")

        result = _backup_pem(pem)
        assert result == tmp_path / "identity-private.pem-backup-01"
        assert result.exists()
        assert result.read_text() == "original-key"
        assert not pem.exists()  # original was moved

    def test_increments_past_existing_backups(self, tmp_path):
        from iconfucius.cli.wallet import _backup_pem

        pem = tmp_path / "identity-private.pem"
        pem.write_text("current-key")
        # Pre-create backup-01 and backup-02
        (tmp_path / "identity-private.pem-backup-01").write_text("old-1")
        (tmp_path / "identity-private.pem-backup-02").write_text("old-2")

        result = _backup_pem(pem)
        assert result.name == "identity-private.pem-backup-03"
        assert result.read_text() == "current-key"
        # Existing backups untouched
        assert (tmp_path / "identity-private.pem-backup-01").read_text() == "old-1"
        assert (tmp_path / "identity-private.pem-backup-02").read_text() == "old-2"

    def test_returns_backup_path(self, tmp_path):
        from iconfucius.cli.wallet import _backup_pem

        pem = tmp_path / "identity-private.pem"
        pem.write_text("key")

        backup = _backup_pem(pem)
        assert backup.parent == tmp_path
        assert backup.name == "identity-private.pem-backup-01"

    def test_raises_after_99_backups(self, tmp_path):
        from iconfucius.cli.wallet import _backup_pem

        pem = tmp_path / "identity-private.pem"
        pem.write_text("key")
        # Create backups 01-99
        for i in range(1, 100):
            (tmp_path / f"identity-private.pem-backup-{i:02d}").write_text(f"backup-{i}")

        with pytest.raises(RuntimeError, match="Too many PEM backups"):
            _backup_pem(pem)
