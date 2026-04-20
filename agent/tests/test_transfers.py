"""Tests for iconfucius.transfers — shared ICRC-1 transfer utilities."""

from unittest.mock import MagicMock, patch

import pytest

from iconfucius.transfers import (
    CKBTC_FEE,
    CKBTC_LEDGER_CANISTER_ID,
    IC_HOST,
    _icrc1_checksum,
    parse_icrc1_account,
    unwrap_canister_result,
    patch_delegate_sender,
    create_icrc1_canister,
    create_ckbtc_minter,
    get_balance,
    transfer,
    get_btc_address,
    check_btc_deposits,
    get_withdrawal_account,
    estimate_withdrawal_fee,
    retrieve_btc_withdrawal,
)


# ---------------------------------------------------------------------------
# _icrc1_checksum
# ---------------------------------------------------------------------------

class TestIcrc1Checksum:
    def test_known_checksum(self):
        """Verify checksum for known principal + subaccount."""
        from icp_principal import Principal
        p = Principal.from_str("k3pwi-qyaaa-aaaab-acbrq-cai")
        sub_hex = "ed7b8190c5714532b566097699c97158" + "0" * 32
        result = _icrc1_checksum(p.bytes, bytes.fromhex(sub_hex))
        assert result == "uco74ta"

    def test_checksum_is_7_chars(self):
        """Verify checksum is always 7 base32 chars."""
        result = _icrc1_checksum(b"\x00" * 10, b"\x00" * 32)
        assert len(result) == 7


# ---------------------------------------------------------------------------
# parse_icrc1_account
# ---------------------------------------------------------------------------

class TestParseIcrc1Account:
    def test_plain_principal(self):
        """Verify plain principal returns empty subaccount."""
        principal_obj, subaccount = parse_icrc1_account("aaaaa-aa")
        assert subaccount == []

    def test_valid_icrc1_account(self):
        """Verify valid ICRC-1 principal-checksum.subaccount parses correctly."""
        sub_hex = "ed7b8190c5714532b566097699c97158" + "0" * 32
        addr = f"k3pwi-qyaaa-aaaab-acbrq-cai-uco74ta.{sub_hex}"
        principal_obj, subaccount = parse_icrc1_account(addr)
        assert str(principal_obj) == "k3pwi-qyaaa-aaaab-acbrq-cai"
        assert subaccount == [bytes.fromhex(sub_hex)]

    def test_invalid_checksum(self):
        """Verify invalid checksum raises ValueError."""
        sub_hex = "ed7b8190c5714532b566097699c97158" + "0" * 32
        addr = f"k3pwi-qyaaa-aaaab-acbrq-cai-aaaaaaa.{sub_hex}"
        with pytest.raises(ValueError, match="checksum mismatch"):
            parse_icrc1_account(addr)

    def test_invalid_hex(self):
        """Verify invalid hex in subaccount raises ValueError."""
        addr = "k3pwi-qyaaa-aaaab-acbrq-cai-aaaaaaa.ZZZZ_not_hex"
        with pytest.raises(ValueError, match="not valid hex"):
            parse_icrc1_account(addr)

    def test_wrong_subaccount_length(self):
        """Verify wrong subaccount length raises ValueError."""
        addr = "k3pwi-qyaaa-aaaab-acbrq-cai-aaaaaaa.aabbccdd"
        with pytest.raises(ValueError, match="must be 32 bytes"):
            parse_icrc1_account(addr)

    def test_invalid_principal(self):
        """Verify invalid principal raises ValueError."""
        with pytest.raises(ValueError, match="Invalid IC principal"):
            parse_icrc1_account("not-a-valid-principal")


# ---------------------------------------------------------------------------
# unwrap_canister_result
# ---------------------------------------------------------------------------

class TestUnwrapCanisterResult:
    def test_list_with_value_dict(self):
        """Verify list with value dict."""
        assert unwrap_canister_result([{"value": 42}]) == 42

    def test_list_with_plain_item(self):
        """Verify list with plain item."""
        assert unwrap_canister_result([123]) == 123

    def test_empty_list(self):
        """Verify empty list."""
        assert unwrap_canister_result([]) == []

    def test_non_list_passthrough(self):
        """Verify non list passthrough."""
        assert unwrap_canister_result("hello") == "hello"

    def test_dict_passthrough(self):
        """Verify dict passthrough."""
        result = {"Ok": 5}
        assert unwrap_canister_result(result) == {"Ok": 5}

    def test_none_passthrough(self):
        """Verify none passthrough."""
        assert unwrap_canister_result(None) is None

    def test_nested_value(self):
        """Verify nested value."""
        assert unwrap_canister_result([{"value": {"Ok": 99}}]) == {"Ok": 99}


# ---------------------------------------------------------------------------
# patch_delegate_sender
# ---------------------------------------------------------------------------

class TestPatchDelegateSender:
    def test_patches_sender_method(self):
        """Verify patches sender method."""
        mock_identity = MagicMock()
        mock_identity.der_pubkey = b"\x00" * 44

        patch_delegate_sender(mock_identity)

        principal = mock_identity.sender()
        assert principal is not None
        assert str(principal) != ""

    def test_sender_returns_consistent_principal(self):
        """Verify sender returns consistent principal."""
        mock_identity = MagicMock()
        mock_identity.der_pubkey = b"\xab" * 44

        patch_delegate_sender(mock_identity)

        p1 = mock_identity.sender()
        p2 = mock_identity.sender()
        assert p1 == p2


# ---------------------------------------------------------------------------
# create_icrc1_canister
# ---------------------------------------------------------------------------

class TestCreateIcrc1Canister:
    @patch("iconfucius.transfers.Canister")
    def test_default_canister_id(self, MockCanister):
        """Verify default canister id."""
        agent = MagicMock()
        create_icrc1_canister(agent)
        MockCanister.assert_called_once()
        assert MockCanister.call_args.kwargs["canister_id"] == CKBTC_LEDGER_CANISTER_ID

    @patch("iconfucius.transfers.Canister")
    def test_custom_canister_id(self, MockCanister):
        """Verify custom canister id."""
        agent = MagicMock()
        create_icrc1_canister(agent, "custom-id")
        assert MockCanister.call_args.kwargs["canister_id"] == "custom-id"


# ---------------------------------------------------------------------------
# create_ckbtc_minter
# ---------------------------------------------------------------------------

class TestCreateCkbtcMinter:
    @patch("iconfucius.transfers.Canister")
    def test_creates_minter(self, MockCanister):
        """Verify creates minter with embedded candid (no auto-fetch)."""
        agent = MagicMock()
        create_ckbtc_minter(agent)
        MockCanister.assert_called_once()
        assert "candid_str" in MockCanister.call_args.kwargs
        assert MockCanister.call_args.kwargs["candid_str"] is not None
        assert "auto_fetch_candid" not in MockCanister.call_args.kwargs


# ---------------------------------------------------------------------------
# get_balance
# ---------------------------------------------------------------------------

class TestGetBalance:
    @patch("iconfucius.transfers.Principal")
    def test_returns_balance(self, MockPrincipal):
        """Verify returns balance."""
        canister = MagicMock()
        canister.icrc1_balance_of.return_value = [{"value": 5000}]
        assert get_balance(canister, "some-principal") == 5000

    @patch("iconfucius.transfers.Principal")
    def test_returns_zero_balance(self, MockPrincipal):
        """Verify returns zero balance."""
        canister = MagicMock()
        canister.icrc1_balance_of.return_value = [{"value": 0}]
        assert get_balance(canister, "some-principal") == 0


# ---------------------------------------------------------------------------
# transfer
# ---------------------------------------------------------------------------

class TestTransfer:
    @patch("iconfucius.transfers.Principal")
    def test_successful_transfer(self, MockPrincipal):
        """Verify successful transfer."""
        canister = MagicMock()
        canister.icrc1_transfer.return_value = [{"value": {"Ok": 123}}]
        result = transfer(canister, "to-principal", 1000)
        assert result == {"Ok": 123}

    @patch("iconfucius.transfers.Principal")
    def test_transfer_error(self, MockPrincipal):
        """Verify transfer error."""
        canister = MagicMock()
        err = {"Err": {"InsufficientFunds": {"balance": 0}}}
        canister.icrc1_transfer.return_value = [{"value": err}]
        result = transfer(canister, "to-principal", 1000)
        assert "Err" in result

    @patch("iconfucius.transfers.Principal")
    def test_transfer_calls_with_correct_amount(self, MockPrincipal):
        """Verify transfer calls with correct amount."""
        canister = MagicMock()
        canister.icrc1_transfer.return_value = [{"value": {"Ok": 1}}]
        transfer(canister, "to-principal", 5000)
        call_args = canister.icrc1_transfer.call_args[0][0]
        assert call_args["amount"] == 5000

    @patch("iconfucius.transfers.Principal")
    def test_transfer_without_subaccount(self, MockPrincipal):
        """Verify plain principal uses empty subaccount."""
        canister = MagicMock()
        canister.icrc1_transfer.return_value = [{"value": {"Ok": 1}}]
        transfer(canister, "some-principal", 1000)
        call_args = canister.icrc1_transfer.call_args[0][0]
        assert call_args["to"]["subaccount"] == []

    def test_transfer_with_subaccount(self):
        """Verify ICRC-1 principal-checksum.subaccount parses correctly."""
        canister = MagicMock()
        canister.icrc1_transfer.return_value = [{"value": {"Ok": 1}}]
        sub_hex = "ed7b8190c5714532b566097699c97158" + "0" * 32
        addr = f"k3pwi-qyaaa-aaaab-acbrq-cai-uco74ta.{sub_hex}"
        transfer(canister, addr, 1000)
        call_args = canister.icrc1_transfer.call_args[0][0]
        assert call_args["to"]["subaccount"] == [bytes.fromhex(sub_hex)]


# ---------------------------------------------------------------------------
# get_btc_address
# ---------------------------------------------------------------------------

class TestGetBtcAddress:
    @patch("iconfucius.transfers.Principal")
    def test_returns_address(self, MockPrincipal):
        """Verify returns address."""
        minter = MagicMock()
        minter.get_btc_address.return_value = [{"value": "bc1qtest"}]
        result = get_btc_address(minter, "owner-principal")
        assert result == "bc1qtest"


# ---------------------------------------------------------------------------
# check_btc_deposits
# ---------------------------------------------------------------------------

class TestCheckBtcDeposits:
    @patch("iconfucius.transfers.Principal")
    def test_returns_result(self, MockPrincipal):
        """Verify returns result."""
        minter = MagicMock()
        minter.update_balance.return_value = [{"value": {"Ok": [{"block_index": 1}]}}]
        result = check_btc_deposits(minter, "owner-principal")
        assert "Ok" in result


# ---------------------------------------------------------------------------
# get_withdrawal_account
# ---------------------------------------------------------------------------

class TestGetWithdrawalAccount:
    def test_returns_account(self):
        """Verify returns account."""
        minter = MagicMock()
        minter.get_withdrawal_account.return_value = [
            {"value": {"owner": "minter-principal", "subaccount": []}}
        ]
        result = get_withdrawal_account(minter)
        assert result["owner"] == "minter-principal"


# ---------------------------------------------------------------------------
# estimate_withdrawal_fee
# ---------------------------------------------------------------------------

class TestEstimateWithdrawalFee:
    def test_returns_fee(self):
        """Verify returns fee."""
        minter = MagicMock()
        minter.estimate_withdrawal_fee.return_value = [
            {"value": {"minter_fee": 10, "bitcoin_fee": 2000}}
        ]
        result = estimate_withdrawal_fee(minter)
        assert result["minter_fee"] == 10
        assert result["bitcoin_fee"] == 2000


# ---------------------------------------------------------------------------
# retrieve_btc_withdrawal
# ---------------------------------------------------------------------------

class TestRetrieveBtcWithdrawal:
    def test_returns_result(self):
        """Verify returns result."""
        minter = MagicMock()
        minter.retrieve_btc.return_value = [
            {"value": {"Ok": {"block_index": 42}}}
        ]
        result = retrieve_btc_withdrawal(minter, "bc1qtest", 5000)
        assert result == {"Ok": {"block_index": 42}}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_ckbtc_fee(self):
        """Verify ckbtc fee."""
        assert CKBTC_FEE == 10

    def test_ic_host(self):
        """Verify ic host."""
        assert IC_HOST == "https://ic0.app"

    def test_ckbtc_canister_id(self):
        """Verify ckbtc canister id."""
        assert CKBTC_LEDGER_CANISTER_ID == "mxzaz-hqaaa-aaaar-qaada-cai"
