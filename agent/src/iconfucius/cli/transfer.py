"""
iconfucius.cli.transfer — Transfer tokens between Odin.Fun accounts

Transfers tokens from a bot's Odin.Fun account to another Odin.Fun account.
This is an internal platform transfer — no selling/buying involved.

WARNING: Transfers are irreversible. Sending to a wrong address means
permanent loss of tokens.

Fee: 100 sats BTC (deducted from sender's Odin.Fun BTC balance).

Usage:
  iconfucius --bot bot-1 transfer 29m8 all dxqin-ibe62-...
  iconfucius --all-bots transfer 29m8 1000000000 dxqin-ibe62-...
"""

import json
import os

from icp_agent import Agent, Client
from icp_canister import Canister

from iconfucius.accounts import resolve_odin_account
from iconfucius.candid import ODIN_TRADING_CANDID
from iconfucius.config import (
    IC_HOST,
    ODIN_TRADING_CANISTER_ID,
    fmt_tokens,
    get_verify_certificates,
    log,
    require_wallet,
    set_verbose,
)
from iconfucius.siwb import load_session, siwb_login
from iconfucius.tokens import fetch_token_data
from iconfucius.transfers import patch_delegate_sender, unwrap_canister_result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_transfer(bot_name: str, token_id: str, amount: str,
                 to_address: str, verbose: bool = False) -> dict:
    """Transfer tokens from a bot's Odin.Fun account to another account.

    Returns a structured dict:
        {"status": "ok"/"error", ...}

    Args:
        bot_name: Name of the source bot.
        token_id: Token ID to transfer (e.g. '29m8').
        amount: Raw token sub-units, or 'all' for entire balance.
        to_address: Destination address — IC principal, BTC deposit address
            (btc_deposit_address), or BTC wallet address (btc_wallet_address)
            of a bot's Odin.fun account. All three are resolved to the
            account's IC principal via the Odin.fun /v1/users search API.
        verbose: If True, enable detailed logging.
    """
    from iconfucius.logging_config import get_logger
    logger = get_logger()

    set_verbose(verbose)
    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    # Fetch token info for display
    token_info = fetch_token_data(token_id)
    ticker = token_info.get("ticker", token_id) if token_info else token_id
    token_label = f"{token_id} ({ticker})" if ticker != token_id else token_id

    # -----------------------------------------------------------------------
    # Step 1: Resolve and validate destination address
    # -----------------------------------------------------------------------
    logger.info("Step 1: Resolve destination address...")

    # If to_address is a configured bot name, look up its principal from
    # the session cache so the AI can pass bot names directly.
    from iconfucius.config import get_bot_names
    if to_address in get_bot_names():
        from iconfucius.siwb import _session_path
        session_file = _session_path(to_address)
        if os.path.exists(session_file):
            with open(session_file) as _f:
                _session = json.load(_f)
            principal = _session.get("bot_principal_text")
            if principal:
                log(f"  Resolved bot name {to_address} -> {principal}")
                to_address = principal
            else:
                return {
                    "status": "error",
                    "error": (
                        f"Session cache for {to_address} has no principal. "
                        f"Run a balance check on {to_address} first."
                    ),
                }
        else:
            return {
                "status": "error",
                "error": (
                    f"No session cache for {to_address}. "
                    f"Run a balance check on {to_address} first to create one."
                ),
            }

    resolved_principal = resolve_odin_account(to_address)
    if not resolved_principal:
        return {
            "status": "error",
            "error": (
                f"'{to_address}' is not a registered Odin.fun account. "
                "Sending to an unknown address would result in permanent loss."
            ),
        }
    if resolved_principal != to_address:
        log(f"  Resolved {to_address} -> {resolved_principal}")
    logger.info("Step 1: Destination validated as Odin.fun account (%s)", resolved_principal)

    # -----------------------------------------------------------------------
    # Step 2: SIWB login (source bot)
    # -----------------------------------------------------------------------
    logger.info("Step 2: SIWB Login (bot=%s)...", bot_name)
    auth = load_session(bot_name=bot_name, verbose=verbose)
    if not auth:
        log("")
        log("No valid cached session, performing full SIWB login...")
        auth = siwb_login(bot_name=bot_name, verbose=verbose)
        set_verbose(verbose)

    delegate_identity = auth["delegate_identity"]
    bot_principal_text = auth["bot_principal_text"]
    patch_delegate_sender(delegate_identity)
    logger.info("Step 2: SIWB Login done")
    log(f"  Bot principal: {bot_principal_text}")

    # Reject self-transfer
    if bot_principal_text == resolved_principal:
        return {
            "status": "error",
            "error": "Cannot transfer to the same account (source = destination).",
        }

    client = Client(url=IC_HOST)
    auth_agent = Agent(delegate_identity, client)

    odin = Canister(
        agent=auth_agent,
        canister_id=ODIN_TRADING_CANISTER_ID,
        candid_str=ODIN_TRADING_CANDID,
    )

    # -----------------------------------------------------------------------
    # Step 3: Check BTC balance for transfer fee
    # -----------------------------------------------------------------------
    TRANSFER_FEE_SATS = 100
    MSAT_PER_SAT = 1000
    logger.info("Step 3: Check BTC balance for transfer fee (bot=%s)...", bot_name)

    btc_balance_msat = unwrap_canister_result(
        odin.getBalance(bot_principal_text, "btc",
                        verify_certificate=get_verify_certificates())
    )
    btc_balance_sats = btc_balance_msat // MSAT_PER_SAT
    logger.info("Step 3: BTC balance: %d sats", btc_balance_sats)

    if btc_balance_sats < TRANSFER_FEE_SATS:
        return {
            "status": "error",
            "error_type": "insufficient_btc_for_fee",
            "error": (
                f"{bot_name} has {btc_balance_sats} sats BTC but transfer "
                f"requires {TRANSFER_FEE_SATS} sats fee."
            ),
            "bot_name": bot_name,
            "btc_balance_sats": btc_balance_sats,
            "fee_sats": TRANSFER_FEE_SATS,
            "token_id": token_id,
            "token_label": token_label,
            "options": [
                "Fund bot from wallet (minimum 5,000 sats deposit) using the fund tool",
                "Sell some tokens first to free up BTC for the fee",
            ],
        }

    # -----------------------------------------------------------------------
    # Step 4: Check token balance
    # -----------------------------------------------------------------------
    logger.info("Step 4: Check token balance (bot=%s)...", bot_name)

    token_before = unwrap_canister_result(
        odin.getBalance(bot_principal_text, token_id,
                             verify_certificate=get_verify_certificates())
    )
    logger.info("Step 4: %s balance: %s", token_label, fmt_tokens(token_before, token_id))

    # -----------------------------------------------------------------------
    # Step 5: Resolve amount
    # -----------------------------------------------------------------------
    transfer_all = amount.lower() == "all"
    if transfer_all:
        amount_int = token_before
        if amount_int <= 0:
            return {
                "status": "error",
                "error": f"No {token_label} to transfer (balance is 0).",
            }
    else:
        amount_int = int(amount)

    if amount_int <= 0:
        return {"status": "error", "error": "Transfer amount must be greater than 0."}

    if amount_int > token_before:
        return {
            "status": "error",
            "error": (
                f"Insufficient {token_label} balance. "
                f"Have: {fmt_tokens(token_before, token_id)}, "
                f"requested: {fmt_tokens(amount_int, token_id)}"
            ),
        }

    # -----------------------------------------------------------------------
    # Step 6: Execute transfer
    # -----------------------------------------------------------------------
    logger.info("Step 6: token_transfer %s %s -> %s...",
                fmt_tokens(amount_int, token_id), token_label, resolved_principal)

    transfer_request = {
        "amount": amount_int,
        "to": resolved_principal,
        "tokenid": token_id,
    }
    log(f"  Transfer request: {transfer_request}")

    result = unwrap_canister_result(
        odin.token_transfer(transfer_request,
                                 verify_certificate=get_verify_certificates())
    )
    log(f"  Result: {result}")

    if isinstance(result, dict) and "err" in result:
        return {"status": "error", "error": str(result["err"])}

    logger.info("Transfer executed successfully (bot=%s)", bot_name)
    return {
        "status": "ok",
        "bot_name": bot_name,
        "token_id": token_id,
        "token_label": token_label,
        "amount": amount_int,
        "to_address": to_address,
        "to_principal": resolved_principal,
        "token_before": token_before,
    }
