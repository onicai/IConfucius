"""
iconfucius.cli.withdraw — Withdraw from Odin.Fun back to the iconfucius wallet

Withdraws BTC balance from Odin.Fun trading account and transfers it
back to the iconfucius wallet in one seamless operation.

Flow:
  1. token_withdraw (Odin.Fun -> bot ICRC-1)
  2. ICRC-1 transfer (bot -> iconfucius wallet)

Usage:
  iconfucius --bot bot-1 withdraw 1000
  iconfucius --bot bot-1 withdraw all
"""

import argparse
import time

from icp_agent import Agent, Client
from icp_canister import Canister
from icp_identity import Identity
from icp_principal import Principal

from iconfucius.config import fmt_sats, get_btc_to_usd_rate
from iconfucius.config import IC_HOST, ODIN_TRADING_CANISTER_ID, get_pem_file, get_verify_certificates, log, require_wallet, set_verbose
from iconfucius.siwb import siwb_login, load_session
from iconfucius.transfers import (
    CKBTC_FEE,
    create_icrc1_canister,
    get_balance,
    patch_delegate_sender,
    transfer,
    unwrap_canister_result,
)

# Odin uses millisatoshis (msat) for BTC amounts
# 1 sat = 1000 msat
MSAT_PER_SAT = 1000

from iconfucius.candid import ODIN_TRADING_CANDID


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_withdraw(bot_name: str, amount: str, verbose: bool = False) -> dict:
    """Withdraw from Odin.Fun and transfer back to iconfucius wallet.

    Returns a structured dict:
        {"status": "ok"/"error"/"partial", ...}

    Args:
        bot_name: Name of the bot to withdraw from.
        amount: Amount in sats, or 'all' for entire balance.
        verbose: If True, enable detailed logging.
    """
    from iconfucius.logging_config import get_logger
    logger = get_logger()

    set_verbose(verbose)
    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    # Fetch BTC/USD rate for display
    try:
        btc_usd_rate = get_btc_to_usd_rate()
    except Exception:
        btc_usd_rate = None

    def _fmt(sats):
        return fmt_sats(sats, btc_usd_rate)

    # -----------------------------------------------------------------------
    # Step 1: SIWB login
    # -----------------------------------------------------------------------
    logger.info("Step 1: SIWB Login (bot=%s)...", bot_name)
    auth = load_session(bot_name=bot_name, verbose=verbose)
    if not auth:
        log("")
        log("No valid cached session, performing full SIWB login...")
        auth = siwb_login(bot_name=bot_name, verbose=verbose)
        set_verbose(verbose)

    delegate_identity = auth["delegate_identity"]
    bot_principal_text = auth["bot_principal_text"]
    patch_delegate_sender(delegate_identity)
    logger.info("Step 1: SIWB Login done")
    log(f"  Bot principal: {bot_principal_text}")

    client = Client(url=IC_HOST)
    auth_agent = Agent(delegate_identity, client)

    odin = Canister(
        agent=auth_agent,
        canister_id=ODIN_TRADING_CANISTER_ID,
        candid_str=ODIN_TRADING_CANDID,
    )

    # -----------------------------------------------------------------------
    # Step 2: Check Odin.Fun balance
    # -----------------------------------------------------------------------
    logger.info("Step 2: Odin.Fun balance (bot=%s)...", bot_name)

    odin_btc_msat = unwrap_canister_result(
        odin.getBalance(bot_principal_text, "btc",
                             verify_certificate=get_verify_certificates())
    )
    odin_btc_sats = odin_btc_msat // MSAT_PER_SAT

    logger.info("Step 2: Odin.Fun balance: %s", _fmt(odin_btc_sats))

    # -----------------------------------------------------------------------
    # Step 3: Determine withdrawal amount
    # -----------------------------------------------------------------------
    if amount.lower() == "all":
        withdraw_sats = odin_btc_sats
        logger.info("Step 3: Withdrawing ALL: %s", _fmt(withdraw_sats))
    else:
        withdraw_sats = int(amount)
        logger.info("Step 3: Withdrawing: %s", _fmt(withdraw_sats))

    if withdraw_sats <= 0:
        return {"status": "error", "error": "No funds to withdraw"}

    if withdraw_sats > odin_btc_sats:
        return {
            "status": "error",
            "error": f"Insufficient balance. Available: {_fmt(odin_btc_sats)}",
        }

    # Convert to millisatoshis for Odin
    withdraw_msat = withdraw_sats * MSAT_PER_SAT

    # -----------------------------------------------------------------------
    # Step 4: Execute Odin.Fun withdrawal
    # -----------------------------------------------------------------------
    logger.info("Step 4: token_withdraw (%s)...", _fmt(withdraw_sats))

    withdraw_request = {
        "protocol": {"ckbtc": None},
        "tokenid": "btc",
        "address": bot_principal_text,
        "amount": withdraw_msat,
    }
    log("")
    log(f"  Request: {withdraw_request}")

    try:
        result = unwrap_canister_result(
            odin.token_withdraw(withdraw_request, verify_certificate=get_verify_certificates())
        )
        log(f"  Result: {result}")

        if isinstance(result, dict) and "err" in result:
            return {"status": "error", "step": "token_withdraw",
                    "error": str(result["err"])}

        logger.info("Step 4: token_withdraw done")
    except RuntimeError as e:
        # The Odin canister sometimes returns malformed responses even on success
        logger.info("Step 4: token_withdraw done (with warning)")
        log(f"  Warning: Response parsing error: {e}")
        log("  Checking if withdrawal completed anyway...")

    # -----------------------------------------------------------------------
    # Step 5: Wait and verify ckBTC arrived on bot
    # -----------------------------------------------------------------------
    logger.info("Step 5: Verify withdrawal (waiting 5s)...")
    time.sleep(5)

    icrc1_canister = create_icrc1_canister(auth_agent)
    bot_ckbtc = get_balance(icrc1_canister, bot_principal_text)
    logger.info("Step 5: bot received %s", _fmt(bot_ckbtc))

    if bot_ckbtc <= CKBTC_FEE:
        return {
            "status": "partial",
            "error": "ckBTC balance too low to transfer to wallet. Withdrawal may be pending.",
            "bot_name": bot_name,
            "withdrawn_sats": withdraw_sats,
        }

    # -----------------------------------------------------------------------
    # Step 6: Transfer ckBTC from bot to iconfucius wallet
    # -----------------------------------------------------------------------
    logger.info("Step 6: Transfer to iconfucius wallet...")

    # Load wallet identity for the destination
    pem_path = get_pem_file()
    with open(pem_path, "r") as f:
        pem_content = f.read()
    wallet_identity = Identity.from_pem(pem_content)
    wallet_principal = str(wallet_identity.sender())

    # Transfer bot's ckBTC to wallet (minus fee)
    sweep_amount = bot_ckbtc - CKBTC_FEE

    log(f"  Transferring {_fmt(sweep_amount)} to wallet...")
    result = transfer(icrc1_canister, wallet_principal, sweep_amount)

    if isinstance(result, dict) and "Err" in result:
        return {"status": "error", "step": "transfer",
                "error": str(result["Err"])}

    tx_index = result.get("Ok", result) if isinstance(result, dict) else result
    logger.info("Step 6: Transfer done (%s), block index: %s",
                _fmt(sweep_amount), tx_index)

    # Verify wallet balance
    wallet_balance = get_balance(icrc1_canister, wallet_principal)
    logger.info("Withdrawal complete. Wallet balance: %s", _fmt(wallet_balance))

    return {
        "status": "ok",
        "bot_name": bot_name,
        "withdrawn_sats": withdraw_sats,
        "transferred_sats": sweep_amount,
        "wallet_balance_sats": wallet_balance,
    }


def main():
    """CLI entry point for standalone usage."""
    parser = argparse.ArgumentParser(description="Withdraw from Odin.Fun to iconfucius wallet")
    parser.add_argument("amount", help="Amount in sats, or 'all' to withdraw entire balance")
    args = parser.parse_args()
    run_withdraw("bot-1", args.amount)


if __name__ == "__main__":
    main()
