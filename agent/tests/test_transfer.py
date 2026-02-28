"""Tests for iconfucius.cli.transfer — transfer tokens between Odin.Fun accounts."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

M = "iconfucius.cli.transfer"
A = "iconfucius.accounts"
C = "iconfucius.config"
S = "iconfucius.siwb"


def _make_mock_auth(bot_principal="bot-principal-abc"):
    """Create a mock auth for testing."""
    delegate = MagicMock()
    delegate.der_pubkey = b"\x30" * 44
    return {
        "delegate_identity": delegate,
        "bot_principal_text": bot_principal,
        "jwt_token": "jwt",
    }


def _get_balance_side_effect(token_balance, btc_msat=200_000):
    """Return different values for BTC vs token getBalance calls.

    Default btc_msat=200_000 (200 sats) is enough for the 100 sats transfer fee.
    """
    def _impl(principal, asset, **kwargs):
        """Shared implementation for test cases."""
        if asset == "btc":
            return btc_msat
        return token_balance
    return _impl


# ---------------------------------------------------------------------------
# resolve_odin_account tests
# ---------------------------------------------------------------------------

class TestResolveOdinAccount:
    @patch(f"{A}.cffi_get_with_retry")
    def test_resolves_valid_principal(self, mock_get):
        """Verify resolves valid principal."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"principal": "abc-def"}]}
        mock_get.return_value = mock_resp

        from iconfucius.accounts import resolve_odin_account
        assert resolve_odin_account("abc-def") == "abc-def"

    @patch(f"{A}.cffi_get_with_retry")
    def test_resolves_btc_address_to_principal(self, mock_get):
        """Verify resolves btc address to principal."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"principal": "resolved-principal-xyz"}]}
        mock_get.return_value = mock_resp

        from iconfucius.accounts import resolve_odin_account
        assert resolve_odin_account("bc1qfakeaddress") == "resolved-principal-xyz"

    @patch(f"{A}.cffi_get_with_retry")
    def test_returns_none_for_unknown_address(self, mock_get):
        """Verify returns none for unknown address."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}
        mock_get.return_value = mock_resp

        from iconfucius.accounts import resolve_odin_account
        assert resolve_odin_account("zzzzz-zzzzz-zzzzz-zzzzz-zzz") is None

    @patch(f"{A}.cffi_get_with_retry")
    def test_returns_none_on_404(self, mock_get):
        """Verify returns none on 404."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        from iconfucius.accounts import resolve_odin_account
        assert resolve_odin_account("zzzzz-zzzzz-zzzzz-zzzzz-zzz") is None

    @patch(f"{A}.cffi_get_with_retry")
    def test_returns_none_on_api_error(self, mock_get):
        """Verify returns none on api error."""
        mock_get.side_effect = Exception("connection error")

        from iconfucius.accounts import resolve_odin_account
        assert resolve_odin_account("dxqin-ibe62-ihc5d-ql3na-dqe") is None

    @patch(f"{A}.cffi_get_with_retry")
    def test_returns_none_on_empty_json(self, mock_get):
        """Verify returns none on empty json."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_get.return_value = mock_resp

        from iconfucius.accounts import resolve_odin_account
        assert resolve_odin_account("dxqin-ibe62-ihc5d-ql3na-dqe") is None


# ---------------------------------------------------------------------------
# lookup_odin_account tests
# ---------------------------------------------------------------------------

class TestLookupOdinAccount:
    @patch(f"{A}.cffi_get_with_retry")
    def test_returns_account_details(self, mock_get):
        """Verify returns account details."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{
            "principal": "abc-def",
            "username": "trader42",
            "btc_wallet_address": "bc1qwallet",
            "btc_deposit_address": "bc1qdeposit",
            "bio": "Hello",
            "avatar": None,
            "admin": False,
            "verified": True,
            "follower_count": 10,
            "following_count": 5,
            "created_at": "2024-01-01",
        }]}
        mock_get.return_value = mock_resp

        from iconfucius.accounts import lookup_odin_account
        result = lookup_odin_account("abc-def")
        assert result is not None
        assert result["principal"] == "abc-def"
        assert result["username"] == "trader42"
        assert result["btc_wallet_address"] == "bc1qwallet"
        assert result["follower_count"] == 10

    @patch(f"{A}.cffi_get_with_retry")
    def test_returns_none_for_unknown(self, mock_get):
        """Verify returns none for unknown."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}
        mock_get.return_value = mock_resp

        from iconfucius.accounts import lookup_odin_account
        assert lookup_odin_account("zzzzz-zzzzz") is None

    @patch(f"{A}.cffi_get_with_retry")
    def test_returns_none_on_error(self, mock_get):
        """Verify returns none on error."""
        mock_get.side_effect = Exception("network error")

        from iconfucius.accounts import lookup_odin_account
        assert lookup_odin_account("abc-def") is None


# ---------------------------------------------------------------------------
# run_transfer tests
# ---------------------------------------------------------------------------

class TestRunTransferErrors:
    def test_no_wallet(self, odin_project_no_wallet):
        """Verify no wallet."""
        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="1000",
            to_address="dxqin-ibe62-ihc5d-ql3na-dqe",
        )
        assert result["status"] == "error"
        assert "No wallet found" in result["error"]

    @patch(f"{M}.resolve_odin_account", return_value=None)
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    def test_rejects_unregistered_account(self, mock_token, mock_resolve, odin_project):
        """Verify rejects unregistered account."""
        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="1000",
            to_address="zzzzz-zzzzz-zzzzz-zzzzz-zzz",
        )
        assert result["status"] == "error"
        assert "not a registered Odin.fun account" in result["error"]

    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="same-principal-abc")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_rejects_self_transfer(self, MockClient, MockAgent, MockCanister,
                                    mock_token, mock_resolve, mock_load,
                                    mock_patch_del, mock_unwrap, odin_project):
        """Verify rejects self transfer."""
        mock_load.return_value = _make_mock_auth(bot_principal="same-principal-abc")

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="1000",
            to_address="same-principal-abc",
        )
        assert result["status"] == "error"
        assert "same account" in result["error"]

    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="same-principal-abc")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_rejects_self_transfer_via_btc_address(self, MockClient, MockAgent, MockCanister,
                                                     mock_token, mock_resolve, mock_load,
                                                     mock_patch_del, mock_unwrap, odin_project):
        """BTC address that resolves to the source bot's principal is rejected."""
        mock_load.return_value = _make_mock_auth(bot_principal="same-principal-abc")

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="1000",
            to_address="bc1qfakeaddress",  # resolves to same-principal-abc
        )
        assert result["status"] == "error"
        assert "same account" in result["error"]

    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="dest-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_rejects_zero_amount(self, MockClient, MockAgent, MockCanister,
                                  mock_token, mock_resolve, mock_load,
                                  mock_patch_del, mock_unwrap, odin_project):
        """Verify rejects zero amount."""
        mock_load.return_value = _make_mock_auth()
        mock_odin_canister = MagicMock()
        mock_odin_canister.getBalance.side_effect = _get_balance_side_effect(5000)
        MockCanister.return_value = mock_odin_canister

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="0",
            to_address="dest-principal-xyz",
        )
        assert result["status"] == "error"
        assert "greater than 0" in result["error"]

    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="dest-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_insufficient_balance(self, MockClient, MockAgent, MockCanister,
                                   mock_token, mock_resolve, mock_load,
                                   mock_patch_del, mock_unwrap, odin_project):
        """Verify insufficient balance."""
        mock_load.return_value = _make_mock_auth()
        mock_odin_canister = MagicMock()
        mock_odin_canister.getBalance.side_effect = _get_balance_side_effect(500)
        MockCanister.return_value = mock_odin_canister

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="10000",
            to_address="dest-principal-xyz",
        )
        assert result["status"] == "error"
        assert "Insufficient" in result["error"]


class TestRunTransferAllEmpty:
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="dest-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_transfer_all_zero_balance(self, MockClient, MockAgent, MockCanister,
                                        mock_token, mock_resolve, mock_load,
                                        mock_patch_del, mock_unwrap, odin_project):
        """Verify transfer all zero balance."""
        mock_load.return_value = _make_mock_auth()
        mock_odin_canister = MagicMock()
        mock_odin_canister.getBalance.side_effect = _get_balance_side_effect(0)
        MockCanister.return_value = mock_odin_canister

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="all",
            to_address="dest-principal-xyz",
        )
        assert result["status"] == "error"
        assert "balance is 0" in result["error"]


# ---------------------------------------------------------------------------
# Bot name resolution tests
# ---------------------------------------------------------------------------

class TestBotNameResolution:
    """Tests for resolving bot names to principals via session cache."""

    @patch(f"{M}.resolve_odin_account", return_value="bot49-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{C}.get_bot_names", return_value=["bot-1", "bot-49"])
    def test_resolves_bot_name_from_session_cache(
        self, mock_names, mock_token, mock_resolve, odin_project, tmp_path
    ):
        """Bot name in to_address is resolved to principal from session cache."""
        session_file = tmp_path / "session_bot-49.json"
        session_file.write_text(json.dumps({"bot_principal_text": "bot49-principal-xyz"}))

        with patch(f"{S}._session_path", return_value=str(session_file)):
            # Will hit self-transfer check since we need SIWB login mocked too,
            # but we just need to verify the bot name was resolved before that.
            # Use a different bot as source.
            with patch(f"{M}.load_session") as mock_load, \
                 patch(f"{M}.patch_delegate_sender"), \
                 patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x), \
                 patch(f"{M}.Canister") as MockCanister, \
                 patch(f"{M}.Agent"), \
                 patch(f"{M}.Client"):
                mock_load.return_value = _make_mock_auth(bot_principal="source-bot-principal")
                mock_odin = MagicMock()
                mock_odin.getBalance.side_effect = _get_balance_side_effect(10000)
                mock_odin.token_transfer.return_value = {"ok": None}
                MockCanister.return_value = mock_odin

                from iconfucius.cli.transfer import run_transfer
                result = run_transfer(
                    bot_name="bot-1", token_id="29m8", amount="5000",
                    to_address="bot-49",
                )
                assert result["status"] == "ok"
                assert result["to_principal"] == "bot49-principal-xyz"

    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{C}.get_bot_names", return_value=["bot-1", "bot-49"])
    def test_error_no_session_cache(self, mock_names, mock_token, odin_project, tmp_path):
        """Bot name with no session cache returns error."""
        nonexistent = str(tmp_path / "no-such-file.json")

        with patch(f"{S}._session_path", return_value=nonexistent):
            from iconfucius.cli.transfer import run_transfer
            result = run_transfer(
                bot_name="bot-1", token_id="29m8", amount="1000",
                to_address="bot-49",
            )
            assert result["status"] == "error"
            assert "No session cache" in result["error"]

    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{C}.get_bot_names", return_value=["bot-1", "bot-49"])
    def test_error_session_cache_no_principal(self, mock_names, mock_token, odin_project, tmp_path):
        """Bot name with session cache but no principal returns error."""
        session_file = tmp_path / "session_bot-49.json"
        session_file.write_text(json.dumps({"jwt_token": "some-jwt"}))

        with patch(f"{S}._session_path", return_value=str(session_file)):
            from iconfucius.cli.transfer import run_transfer
            result = run_transfer(
                bot_name="bot-1", token_id="29m8", amount="1000",
                to_address="bot-49",
            )
            assert result["status"] == "error"
            assert "has no principal" in result["error"]

    @patch(f"{M}.resolve_odin_account", return_value="dest-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{C}.get_bot_names", return_value=["bot-1"])
    def test_non_bot_name_skips_resolution(
        self, mock_names, mock_token, mock_resolve, odin_project
    ):
        """Address that isn't a bot name goes directly to resolve_odin_account."""
        with patch(f"{M}.load_session") as mock_load, \
             patch(f"{M}.patch_delegate_sender"), \
             patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x), \
             patch(f"{M}.Canister") as MockCanister, \
             patch(f"{M}.Agent"), \
             patch(f"{M}.Client"):
            mock_load.return_value = _make_mock_auth()
            mock_odin = MagicMock()
            mock_odin.getBalance.side_effect = _get_balance_side_effect(10000)
            mock_odin.token_transfer.return_value = {"ok": None}
            MockCanister.return_value = mock_odin

            from iconfucius.cli.transfer import run_transfer
            result = run_transfer(
                bot_name="bot-1", token_id="29m8", amount="5000",
                to_address="dest-principal-xyz",
            )
            assert result["status"] == "ok"
            # resolve_odin_account was called with the raw address, not a bot name
            mock_resolve.assert_called_once_with("dest-principal-xyz")


class TestRunTransferSuccess:
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="dest-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "ICONFUCIUS"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_transfer_specific_amount(self, MockClient, MockAgent, MockCanister,
                                       mock_token, mock_resolve, mock_load,
                                       mock_patch_del, mock_unwrap, odin_project):
        """Verify transfer specific amount."""
        mock_load.return_value = _make_mock_auth()
        mock_odin_canister = MagicMock()
        mock_odin_canister.getBalance.return_value = 10_000_000_000_000
        mock_odin_canister.token_transfer.return_value = {"ok": None}
        MockCanister.return_value = mock_odin_canister

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="5000000000000",
            to_address="dest-principal-xyz",
        )

        assert result["status"] == "ok"
        assert result["bot_name"] == "bot-1"
        assert result["token_id"] == "29m8"
        assert result["amount"] == 5_000_000_000_000
        assert result["to_address"] == "dest-principal-xyz"
        assert result["to_principal"] == "dest-principal-xyz"
        assert result["token_before"] == 10_000_000_000_000
        mock_odin_canister.token_transfer.assert_called_once()
        call_args = mock_odin_canister.token_transfer.call_args[0][0]
        assert call_args["to"] == "dest-principal-xyz"
        assert call_args["tokenid"] == "29m8"
        assert call_args["amount"] == 5_000_000_000_000

    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="resolved-dest-principal")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "ICONFUCIUS"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_transfer_via_btc_address(self, MockClient, MockAgent, MockCanister,
                                       mock_token, mock_resolve, mock_load,
                                       mock_patch_del, mock_unwrap, odin_project):
        """BTC address resolves to principal; canister call uses the resolved principal."""
        mock_load.return_value = _make_mock_auth()
        mock_odin_canister = MagicMock()
        mock_odin_canister.getBalance.return_value = 10_000_000_000_000
        mock_odin_canister.token_transfer.return_value = {"ok": None}
        MockCanister.return_value = mock_odin_canister

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="5000000000000",
            to_address="bc1qfakebtcaddress",
        )

        assert result["status"] == "ok"
        assert result["to_address"] == "bc1qfakebtcaddress"
        assert result["to_principal"] == "resolved-dest-principal"
        # Canister call must use the resolved principal, not the BTC address
        call_args = mock_odin_canister.token_transfer.call_args[0][0]
        assert call_args["to"] == "resolved-dest-principal"

    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="dest-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "ICONFUCIUS"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_transfer_all(self, MockClient, MockAgent, MockCanister,
                           mock_token, mock_resolve, mock_load,
                           mock_patch_del, mock_unwrap, odin_project):
        """Verify transfer all."""
        mock_load.return_value = _make_mock_auth()
        mock_odin_canister = MagicMock()
        mock_odin_canister.getBalance.return_value = 7_777_000_000_000
        mock_odin_canister.token_transfer.return_value = {"ok": None}
        MockCanister.return_value = mock_odin_canister

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="all",
            to_address="dest-principal-xyz",
        )

        assert result["status"] == "ok"
        assert result["amount"] == 7_777_000_000_000
        call_args = mock_odin_canister.token_transfer.call_args[0][0]
        assert call_args["amount"] == 7_777_000_000_000

    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="dest-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_transfer_canister_error(self, MockClient, MockAgent, MockCanister,
                                      mock_token, mock_resolve, mock_load,
                                      mock_patch_del, mock_unwrap, odin_project):
        """Verify transfer canister error."""
        mock_load.return_value = _make_mock_auth()
        mock_odin_canister = MagicMock()
        mock_odin_canister.getBalance.side_effect = _get_balance_side_effect(10_000)
        mock_odin_canister.token_transfer.return_value = {"err": "insufficient BTC for fee"}
        MockCanister.return_value = mock_odin_canister

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="5000",
            to_address="dest-principal-xyz",
        )

        assert result["status"] == "error"
        assert "insufficient BTC for fee" in result["error"]


# ---------------------------------------------------------------------------
# BTC balance fee check tests
# ---------------------------------------------------------------------------

class TestTransferInsufficientBtcForFee:
    """Transfer should return structured error with options when BTC < 100 sats."""

    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="dest-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_returns_options_when_btc_insufficient(
        self, MockClient, MockAgent, MockCanister,
        mock_token, mock_resolve, mock_load,
        mock_patch_del, mock_unwrap, odin_project,
    ):
        """Verify returns options when btc insufficient."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        # 0 BTC → insufficient for 100 sats fee
        mock_odin.getBalance.side_effect = _get_balance_side_effect(
            token_balance=10_000, btc_msat=0,
        )
        MockCanister.return_value = mock_odin

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="5000",
            to_address="dest-principal-xyz",
        )

        assert result["status"] == "error"
        assert result["error_type"] == "insufficient_btc_for_fee"
        assert result["fee_sats"] == 100
        assert result["btc_balance_sats"] == 0
        assert result["bot_name"] == "bot-1"
        assert len(result["options"]) == 2
        # Token transfer should NOT have been called
        mock_odin.token_transfer.assert_not_called()

    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.patch_delegate_sender")
    @patch(f"{M}.load_session")
    @patch(f"{M}.resolve_odin_account", return_value="dest-principal-xyz")
    @patch(f"{M}.fetch_token_data", return_value={"ticker": "TEST"})
    @patch(f"{M}.Canister")
    @patch(f"{M}.Agent")
    @patch(f"{M}.Client")
    def test_passes_when_btc_sufficient(
        self, MockClient, MockAgent, MockCanister,
        mock_token, mock_resolve, mock_load,
        mock_patch_del, mock_unwrap, odin_project,
    ):
        """Verify passes when btc sufficient."""
        mock_load.return_value = _make_mock_auth()
        mock_odin = MagicMock()
        # 200 sats BTC → enough for 100 sats fee
        mock_odin.getBalance.side_effect = _get_balance_side_effect(
            token_balance=10_000, btc_msat=200_000,
        )
        mock_odin.token_transfer.return_value = {"ok": None}
        MockCanister.return_value = mock_odin

        from iconfucius.cli.transfer import run_transfer
        result = run_transfer(
            bot_name="bot-1", token_id="29m8", amount="5000",
            to_address="dest-principal-xyz",
        )

        assert result["status"] == "ok"
        mock_odin.token_transfer.assert_called_once()
