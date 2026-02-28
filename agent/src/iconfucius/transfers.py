"""
iconfucius.transfers — Shared ICRC-1 transfer utilities

This module provides common functionality for ICRC-1 token transfers.

Works with any ICRC-1 compatible token (ckBTC, ckETH, etc.).
"""

import hashlib
import types

from icp_agent import Agent, Client
from icp_canister import Canister
from icp_identity import Identity
from icp_principal import Principal

from iconfucius.candid import CKBTC_MINTER_CANDID, ICRC1_CANDID
from iconfucius.config import (
    CKBTC_LEDGER_CANISTER_ID,
    CKBTC_MINTER_CANISTER_ID,
    IC_HOST,
    get_verify_certificates,
)

# ckBTC transfer fee (satoshis)
CKBTC_FEE = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def unwrap_canister_result(raw):
    """Extract value from icp-py-core canister response."""
    if isinstance(raw, list) and len(raw) > 0:
        item = raw[0]
        return item["value"] if isinstance(item, dict) and "value" in item else item
    return raw


def patch_delegate_sender(delegate_identity):
    """Monkey-patch DelegateIdentity.sender() to work with SIWB keys.

    icp-py-core's Principal.self_authenticating() rejects the SIWB
    delegation key format. Compute the principal directly with
    sha224(pubkey) + 0x02.
    """
    _pk = delegate_identity.der_pubkey
    _principal_bytes = hashlib.sha224(_pk).digest() + b"\x02"
    _bot_principal = Principal(_principal_bytes)
    delegate_identity.sender = types.MethodType(lambda self: _bot_principal, delegate_identity)



def create_ckbtc_minter(agent) -> Canister:
    """Create a ckBTC minter canister instance."""
    return Canister(
        agent=agent,
        canister_id=CKBTC_MINTER_CANISTER_ID,
        candid_str=CKBTC_MINTER_CANDID,
    )


def get_btc_address(minter: Canister, owner_principal: str) -> str:
    """Get BTC deposit address for an IC principal via ckBTC minter."""
    principal_obj = Principal.from_str(owner_principal)
    result = unwrap_canister_result(minter.get_btc_address({
        "owner": [principal_obj],
        "subaccount": [],
    }, verify_certificate=get_verify_certificates()))
    return result


def get_pending_btc(minter: Canister, owner_principal: str) -> int:
    """Get total pending BTC (sats) awaiting conversion to ckBTC."""
    principal_obj = Principal.from_str(owner_principal)
    result = unwrap_canister_result(minter.get_known_utxos({
        "owner": [principal_obj],
        "subaccount": [],
    }, verify_certificate=get_verify_certificates()))
    if isinstance(result, list):
        return sum(utxo.get("value", 0) for utxo in result)
    return 0


def check_btc_deposits(minter: Canister, owner_principal: str):
    """Check for new BTC deposits and mint ckBTC."""
    principal_obj = Principal.from_str(owner_principal)
    result = unwrap_canister_result(minter.update_balance({
        "owner": [principal_obj],
        "subaccount": [],
    }, verify_certificate=get_verify_certificates()))
    return result


def get_withdrawal_account(minter: Canister):
    """Get the withdrawal account for BTC retrieval."""
    result = unwrap_canister_result(
        minter.get_withdrawal_account(verify_certificate=get_verify_certificates())
    )
    return result


def estimate_withdrawal_fee(minter: Canister, amount: int = None):
    """Estimate the fee for BTC withdrawal."""
    args = {"amount": [amount] if amount is not None else []}
    result = unwrap_canister_result(
        minter.estimate_withdrawal_fee(args, verify_certificate=get_verify_certificates())
    )
    return result


def retrieve_btc_withdrawal(minter: Canister, btc_address: str, amount: int):
    """Initiate BTC withdrawal to a Bitcoin address."""
    result = unwrap_canister_result(minter.retrieve_btc({
        "address": btc_address,
        "amount": amount,
    }, verify_certificate=get_verify_certificates()))
    return result


def create_icrc1_canister(agent, canister_id: str = CKBTC_LEDGER_CANISTER_ID) -> Canister:
    """Create an ICRC-1 canister instance."""
    return Canister(
        agent=agent,
        canister_id=canister_id,
        candid_str=ICRC1_CANDID,
    )


def get_balance(canister: Canister, owner_principal: str) -> int:
    """Get ICRC-1 token balance for an owner."""
    principal_obj = Principal.from_str(owner_principal)
    balance = unwrap_canister_result(canister.icrc1_balance_of({
        "owner": principal_obj,
        "subaccount": [],
    }, verify_certificate=get_verify_certificates()))
    return balance


def transfer(
    canister: Canister,
    to_principal: str,
    amount: int,
) -> dict:
    """Execute an ICRC-1 transfer.

    Args:
        canister: Authenticated ICRC-1 canister instance
        to_principal: Recipient principal ID
        amount: Amount to transfer (in smallest unit, e.g., satoshis for ckBTC)

    Returns:
        dict with either {"Ok": block_index} or {"Err": error_details}
    """
    to_principal_obj = Principal.from_str(to_principal)

    result_raw = canister.icrc1_transfer(
        {
            "to": {"owner": to_principal_obj, "subaccount": []},
            "amount": amount,
            "fee": [],  # Use ledger default
            "memo": [],
            "from_subaccount": [],
            "created_at_time": [],
        },
        verify_certificate=get_verify_certificates(),
    )
    result = unwrap_canister_result(result_raw)
    return result
