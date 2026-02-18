"""Tests for sign_with_fee() — ICRC-2 fee payment flow in siwb.py"""

import pytest
from unittest.mock import MagicMock, patch

M = "iconfucius.siwb"

FAKE_SIGNATURE_HEX = "a" * 128  # 64 bytes
FAKE_LEDGER_PRINCIPAL = "mxzaz-hqaaa-aaaar-qaada-cai"


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


def _make_sign_ok():
    """Build a sign Ok response."""
    return {"Ok": {"botName": "bot-1", "signatureHex": FAKE_SIGNATURE_HEX}}


def _make_ckbtc_fee_token(fee=100):
    """Build a ckBTC fee token entry."""
    return {"tokenName": "ckBTC", "tokenLedger": FAKE_LEDGER_PRINCIPAL, "fee": fee}


class TestSignWithFeeNoFees:
    """When no fee tokens are configured, sign without payment."""

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_sign_called_without_payment(self, mock_unwrap, mock_log):
        mock_cksigner = MagicMock()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response([])
        mock_cksigner.sign.return_value = _make_sign_ok()
        mock_agent = MagicMock()

        from iconfucius.siwb import sign_with_fee
        result = sign_with_fee(mock_cksigner, mock_agent, "bot-1", b"\x00" * 32)

        assert "Ok" in result
        assert result["Ok"]["signatureHex"] == FAKE_SIGNATURE_HEX

        # Verify sign called with empty payment (opt None)
        mock_cksigner.sign.assert_called_once()
        call_args = mock_cksigner.sign.call_args[0][0]
        assert call_args["botName"] == "bot-1"
        assert call_args["message"] == b"\x00" * 32
        assert call_args["payment"] == []  # opt None

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_no_icrc2_approve_called(self, mock_unwrap, mock_log):
        mock_cksigner = MagicMock()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response([])
        mock_cksigner.sign.return_value = _make_sign_ok()

        from iconfucius.siwb import sign_with_fee
        with patch(f"{M}.Canister") as MockCanister:
            sign_with_fee(mock_cksigner, MagicMock(), "bot-1", b"\x00" * 32)
            MockCanister.assert_not_called()  # No ckBTC canister created


class TestSignWithFeeCkbtcFee:
    """When ckBTC fee is configured, approve then sign with payment."""

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    @patch(f"{M}.Principal")
    @patch(f"{M}.Canister")
    def test_approve_and_sign_with_payment(
        self, MockCanister, MockPrincipal, mock_unwrap, mock_unwrap_cr, mock_log
    ):
        mock_cksigner = MagicMock()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response(
            [_make_ckbtc_fee_token(100)]
        )
        mock_cksigner.sign.return_value = _make_sign_ok()

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Ok": 42}
        MockCanister.return_value = mock_ckbtc

        from iconfucius.siwb import sign_with_fee
        result = sign_with_fee(mock_cksigner, MagicMock(), "bot-1", b"\x00" * 32)

        assert "Ok" in result
        mock_ckbtc.icrc2_approve.assert_called_once()

        # Verify approve amount = fee + CKBTC_FEE (100 + 10)
        approve_args = mock_ckbtc.icrc2_approve.call_args[0][0]
        assert approve_args["amount"] == 110

        # Verify sign called with payment
        sign_args = mock_cksigner.sign.call_args[0][0]
        assert len(sign_args["payment"]) == 1
        assert sign_args["payment"][0]["tokenName"] == "ckBTC"
        assert sign_args["payment"][0]["amount"] == 100

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    @patch(f"{M}.Principal")
    @patch(f"{M}.Canister")
    def test_token_ledger_passed_through(
        self, MockCanister, MockPrincipal, mock_unwrap, mock_unwrap_cr, mock_log
    ):
        mock_cksigner = MagicMock()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response(
            [_make_ckbtc_fee_token(100)]
        )
        mock_cksigner.sign.return_value = _make_sign_ok()

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {"Ok": 1}
        MockCanister.return_value = mock_ckbtc

        from iconfucius.siwb import sign_with_fee
        sign_with_fee(mock_cksigner, MagicMock(), "bot-1", b"\x00" * 32)

        # tokenLedger from getFeeTokens should be passed through to sign payment
        sign_args = mock_cksigner.sign.call_args[0][0]
        assert sign_args["payment"][0]["tokenLedger"] == FAKE_LEDGER_PRINCIPAL


class TestSignWithFeeErrors:
    """Error handling in sign_with_fee()."""

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_get_fee_tokens_error(self, mock_unwrap, mock_log):
        mock_cksigner = MagicMock()
        mock_cksigner.getFeeTokens.return_value = {"Err": {"Other": "canister error"}}

        from iconfucius.siwb import sign_with_fee
        with pytest.raises(RuntimeError, match="getFeeTokens failed"):
            sign_with_fee(mock_cksigner, MagicMock(), "bot-1", b"\x00" * 32)

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_no_ckbtc_fee_token(self, mock_unwrap, mock_log):
        mock_cksigner = MagicMock()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response(
            [{"tokenName": "ICP", "tokenLedger": "ryjl3-tyaaa-aaaaa-aaaba-cai", "fee": 50}]
        )

        from iconfucius.siwb import sign_with_fee
        with pytest.raises(RuntimeError, match="no ckBTC fee token configured"):
            sign_with_fee(mock_cksigner, MagicMock(), "bot-1", b"\x00" * 32)

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    @patch(f"{M}.Principal")
    @patch(f"{M}.Canister")
    def test_approve_failure(
        self, MockCanister, MockPrincipal, mock_unwrap, mock_unwrap_cr, mock_log
    ):
        mock_cksigner = MagicMock()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response(
            [_make_ckbtc_fee_token(100)]
        )

        mock_ckbtc = MagicMock()
        mock_ckbtc.icrc2_approve.return_value = {
            "Err": {"InsufficientFunds": {"balance": 50}}
        }
        MockCanister.return_value = mock_ckbtc

        from iconfucius.siwb import sign_with_fee
        with pytest.raises(RuntimeError, match="icrc2_approve for fee payment failed"):
            sign_with_fee(mock_cksigner, MagicMock(), "bot-1", b"\x00" * 32)

        # sign should NOT have been called
        mock_cksigner.sign.assert_not_called()

    @patch(f"{M}.log")
    @patch(f"{M}.unwrap", side_effect=lambda x: x)
    def test_sign_error_returned(self, mock_unwrap, mock_log):
        """sign_with_fee returns Err dict without raising — caller decides."""
        mock_cksigner = MagicMock()
        mock_cksigner.getFeeTokens.return_value = _make_fee_tokens_response([])
        mock_cksigner.sign.return_value = {"Err": {"Other": "bad message size"}}

        from iconfucius.siwb import sign_with_fee
        result = sign_with_fee(mock_cksigner, MagicMock(), "bot-1", b"\x00" * 32)

        assert "Err" in result
        assert result["Err"]["Other"] == "bad message size"
