"""Tests for getPublicKeyQuery / getPublicKey flow in siwb.py"""

import pytest
from unittest.mock import MagicMock, patch

M = "iconfucius.siwb"

FAKE_PUBKEY_HEX = "ab" * 32  # 32 bytes x-only pubkey
FAKE_ADDRESS = "bc1p" + "a" * 58  # fake P2TR address
FAKE_LEDGER_PRINCIPAL = "mxzaz-hqaaa-aaaar-qaada-cai"


def _make_pubkey_ok(bot_name="bot-1"):
    """Build a getPublicKey/getPublicKeyQuery Ok response."""
    return {"Ok": {
        "botName": bot_name,
        "publicKeyHex": FAKE_PUBKEY_HEX,
        "address": FAKE_ADDRESS,
    }}


def _make_pubkey_err_cache_miss():
    """Build a getPublicKeyQuery Err response for cache miss."""
    return {"Err": {"Other": "Not Found - call getPublicKey to populate cache."}}


def _make_pubkey_err(error):
    """Build a getPublicKey/getPublicKeyQuery Err response."""
    return {"Err": error}


def _make_fee_tokens_response(fee_tokens):
    """Build a getFeeTokens Ok response."""
    return {"Ok": {
        "canisterId": "g7qkb-iiaaa-aaaar-qb3za-cai",
        "treasury": {
            "treasuryName": "funnAI Treasury Canister",
            "treasuryPrincipal": "qbhxa-ziaaa-aaaaa-qbqza-cai",
        },
        "feeTokens": fee_tokens,
        "usage": "test",
    }}


def _make_ckbtc_fee_token(fee=100):
    """Build a ckBTC fee token entry."""
    return {"tokenName": "ckBTC", "tokenLedger": FAKE_LEDGER_PRINCIPAL, "fee": fee}


class TestGetPublicKeyQueryCacheHit:
    """When getPublicKeyQuery returns Ok (cache hit), getPublicKey is not called."""

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_uses_query_result(self, mock_unwrap, mock_log):
        """Test that a cache hit returns the query result without calling getPublicKey."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_ok()

        from iconfucius.siwb import _get_public_key
        pubkey_hex, address = _get_public_key(mock_cksigner, "bot-1")

        assert pubkey_hex == FAKE_PUBKEY_HEX
        assert address == FAKE_ADDRESS
        mock_cksigner.getPublicKeyQuery.assert_called_once()
        mock_cksigner.getPublicKey.assert_not_called()

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_passes_bot_name(self, mock_unwrap, mock_log):
        """Test that the bot name is forwarded to getPublicKeyQuery."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_ok("my-bot")

        from iconfucius.siwb import _get_public_key
        _get_public_key(mock_cksigner, "my-bot")

        args = mock_cksigner.getPublicKeyQuery.call_args[0][0]
        assert args["botName"] == "my-bot"

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_no_fee_check_on_cache_hit(self, mock_unwrap, mock_log):
        """Cache hit skips fee approval entirely."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_ok()

        from iconfucius.siwb import _get_public_key
        _get_public_key(mock_cksigner, "bot-1")

        mock_cksigner.getFeeTokens.assert_not_called()


class TestGetPublicKeyQueryCacheMissNoFees:
    """Cache miss with no fees configured — free fallback to getPublicKey."""

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_falls_back_to_update(self, mock_unwrap, mock_log):
        """Test that a cache miss triggers a fallback to getPublicKey update call."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_err_cache_miss()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response([])
        mock_cksigner.getPublicKey.return_value = _make_pubkey_ok()

        from iconfucius.siwb import _get_public_key
        pubkey_hex, address = _get_public_key(mock_cksigner, "bot-1")

        assert pubkey_hex == FAKE_PUBKEY_HEX
        assert address == FAKE_ADDRESS
        mock_cksigner.getPublicKeyQuery.assert_called_once()
        mock_cksigner.getPublicKey.assert_called_once()

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_fallback_passes_bot_name_and_empty_payment(self, mock_unwrap, mock_log):
        """Test that fallback passes the bot name and an empty payment list when no fees."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_err_cache_miss()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response([])
        mock_cksigner.getPublicKey.return_value = _make_pubkey_ok("my-bot")

        from iconfucius.siwb import _get_public_key
        _get_public_key(mock_cksigner, "my-bot")

        args = mock_cksigner.getPublicKey.call_args[0][0]
        assert args["botName"] == "my-bot"
        assert args["payment"] == []  # opt None


class TestGetPublicKeyQueryCacheMissWithFees:
    """Cache miss with fees configured — approve + pay on fallback."""

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    @patch(f"{M}.Principal")
    @patch(f"{M}.Canister")
    def test_approves_and_passes_payment(
        self, MockCanister, MockPrincipal, mock_unwrap, mock_unwrap_cr, mock_log
    ):
        """Test that fees trigger icrc2_approve and payment is included in getPublicKey."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_err_cache_miss()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response(
            [_make_ckbtc_fee_token(100)]
        )
        mock_cksigner.getPublicKey.return_value = _make_pubkey_ok()

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Ok": 42}
        MockCanister.return_value = mock_ckbtc

        from iconfucius.siwb import _get_public_key
        pubkey_hex, address = _get_public_key(
            mock_cksigner, "bot-1", wallet_agent=MagicMock(),
        )

        assert pubkey_hex == FAKE_PUBKEY_HEX
        mock_ckbtc.icrc2_approve.assert_called_once()

        # getPublicKey called with payment record
        args = mock_cksigner.getPublicKey.call_args[0][0]
        assert len(args["payment"]) == 1
        assert args["payment"][0]["tokenName"] == "ckBTC"
        assert args["payment"][0]["amount"] == 100

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    @patch(f"{M}.Principal")
    @patch(f"{M}.Canister")
    def test_approve_failure_raises(
        self, MockCanister, MockPrincipal, mock_unwrap, mock_unwrap_cr, mock_log
    ):
        """Test that a failed icrc2_approve raises RuntimeError and skips getPublicKey."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_err_cache_miss()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response(
            [_make_ckbtc_fee_token(100)]
        )

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {
            "Err": {"InsufficientFunds": {"balance": 50}}
        }
        MockCanister.return_value = mock_ckbtc

        from iconfucius.siwb import _get_public_key
        with pytest.raises(RuntimeError, match="icrc2_approve for fee payment failed"):
            _get_public_key(mock_cksigner, "bot-1", wallet_agent=MagicMock())

        mock_cksigner.getPublicKey.assert_not_called()

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_fees_required_no_wallet_agent_raises(self, mock_unwrap, mock_log):
        """Test that fees without a wallet_agent raises RuntimeError."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_err_cache_miss()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response(
            [_make_ckbtc_fee_token(100)]
        )

        from iconfucius.siwb import _get_public_key
        with pytest.raises(RuntimeError, match="no wallet_agent provided"):
            _get_public_key(mock_cksigner, "bot-1")  # no wallet_agent


class TestGetPublicKeyErrors:
    """Error handling in the getPublicKey query+fallback flow."""

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_update_error_raises(self, mock_unwrap, mock_log):
        """When both query and update fail, raises RuntimeError."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_err_cache_miss()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response([])
        mock_cksigner.getPublicKey.return_value = _make_pubkey_err({"Unauthorized": None})

        from iconfucius.siwb import _get_public_key
        with pytest.raises(RuntimeError, match="getPublicKey failed"):
            _get_public_key(mock_cksigner, "bot-1")

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_query_unauthorized_still_falls_back(self, mock_unwrap, mock_log):
        """Any query Err triggers fallback, not just cache miss."""
        mock_cksigner = MagicMock()
        mock_cksigner.getPublicKeyQuery.return_value = _make_pubkey_err(
            {"Unauthorized": None}
        )
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response([])
        mock_cksigner.getPublicKey.return_value = _make_pubkey_ok()

        from iconfucius.siwb import _get_public_key
        pubkey_hex, address = _get_public_key(mock_cksigner, "bot-1")

        assert pubkey_hex == FAKE_PUBKEY_HEX
        mock_cksigner.getPublicKey.assert_called_once()
