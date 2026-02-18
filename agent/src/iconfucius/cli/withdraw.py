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

def run_withdraw(bot_name: str, amount: str, verbose: bool = False):
    """Withdraw from Odin.Fun and transfer back to iconfucius wallet.

    Args:
        bot_name: Name of the bot to withdraw from.
        amount: Amount in sats, or 'all' for entire balance.
        verbose: If True, print detailed step output.
    """
    set_verbose(verbose)
    if not require_wallet():
        return

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
    print(f"Step 1: SIWB Login (bot={bot_name})...", end=" ", flush=True)
    auth = load_session(bot_name=bot_name, verbose=verbose)
    if not auth:
        log("")
        log("No valid cached session, performing full SIWB login...")
        auth = siwb_login(bot_name=bot_name, verbose=verbose)
        set_verbose(verbose)

    delegate_identity = auth["delegate_identity"]
    bot_principal_text = auth["bot_principal_text"]
    patch_delegate_sender(delegate_identity)
    print("done")
    log(f"  Bot principal: {bot_principal_text}")

    client = Client(url=IC_HOST)
    anon_agent = Agent(Identity(anonymous=True), client)
    auth_agent = Agent(delegate_identity, client)

    odin_anon = Canister(
        agent=anon_agent,
        canister_id=ODIN_TRADING_CANISTER_ID,
        candid_str=ODIN_TRADING_CANDID,
    )
    odin_auth = Canister(
        agent=auth_agent,
        canister_id=ODIN_TRADING_CANISTER_ID,
        candid_str=ODIN_TRADING_CANDID,
    )

    # -----------------------------------------------------------------------
    # Step 2: Check Odin.Fun balance
    # -----------------------------------------------------------------------
    print(f"Step 2: Odin.Fun balance (bot={bot_name})...", end=" ", flush=True)

    odin_btc_msat = unwrap_canister_result(
        odin_anon.getBalance(bot_principal_text, "btc", "btc",
                             verify_certificate=get_verify_certificates())
    )
    odin_btc_sats = odin_btc_msat // MSAT_PER_SAT

    print(_fmt(odin_btc_sats))

    # -----------------------------------------------------------------------
    # Step 3: Determine withdrawal amount
    # -----------------------------------------------------------------------
    if amount.lower() == "all":
        withdraw_sats = odin_btc_sats
        print(f"Step 3: Withdrawing ALL: {_fmt(withdraw_sats)}")
    else:
        withdraw_sats = int(amount)
        print(f"Step 3: Withdrawing: {_fmt(withdraw_sats)}")

    if withdraw_sats <= 0:
        print("No funds to withdraw.")
        return

    if withdraw_sats > odin_btc_sats:
        print(f"Insufficient balance. Available: {_fmt(odin_btc_sats)}")
        return

    # Convert to millisatoshis for Odin
    withdraw_msat = withdraw_sats * MSAT_PER_SAT

    # -----------------------------------------------------------------------
    # Step 4: Execute Odin.Fun withdrawal
    # -----------------------------------------------------------------------
    print(f"Step 4: token_withdraw ({_fmt(withdraw_sats)})...", end=" ", flush=True)

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
            odin_auth.token_withdraw(withdraw_request, verify_certificate=get_verify_certificates())
        )
        log(f"  Result: {result}")

        if isinstance(result, dict) and "err" in result:
            print(f"FAILED: {result['err']}")
            return

        print("done")
    except RuntimeError as e:
        # The Odin canister sometimes returns malformed responses even on success
        print("done (with warning)")
        log(f"  Warning: Response parsing error: {e}")
        log("  Checking if withdrawal completed anyway...")

    # -----------------------------------------------------------------------
    # Step 5: Wait and verify ckBTC arrived on bot
    # -----------------------------------------------------------------------
    print(f"Step 5: Verify withdrawal (waiting 5s)...", end=" ", flush=True)
    time.sleep(5)

    icrc1_canister__anon = create_icrc1_canister(anon_agent)
    bot_ckbtc = get_balance(icrc1_canister__anon, bot_principal_text)
    print(f"done (bot received {_fmt(bot_ckbtc)})")

    if bot_ckbtc <= CKBTC_FEE:
        print(f"\n  Note: ckBTC balance too low to transfer to wallet. "
              f"Withdrawal may be pending.")
        return

    # -----------------------------------------------------------------------
    # Step 6: Transfer ckBTC from bot to iconfucius wallet
    # -----------------------------------------------------------------------
    print(f"Step 6: Transfer to iconfucius wallet...", end=" ", flush=True)

    # Load wallet identity for the destination
    pem_path = get_pem_file()
    with open(pem_path, "r") as f:
        pem_content = f.read()
    wallet_identity = Identity.from_pem(pem_content)
    wallet_principal = str(wallet_identity.sender())

    # Transfer bot's ckBTC to wallet (minus fee)
    icrc1_canister__bot = create_icrc1_canister(auth_agent)
    sweep_amount = bot_ckbtc - CKBTC_FEE

    log(f"  Transferring {_fmt(sweep_amount)} to wallet...")
    result = transfer(icrc1_canister__bot, wallet_principal, sweep_amount)

    if isinstance(result, dict) and "Err" in result:
        print(f"FAILED: {result['Err']}")
    else:
        tx_index = result.get("Ok", result) if isinstance(result, dict) else result
        print(f"done ({_fmt(sweep_amount)})")
        log(f"  Transfer block index: {tx_index}")

    # Verify wallet balance
    wallet_balance = get_balance(icrc1_canister__anon, wallet_principal)
    print(f"\n✅ Withdrawal complete!")
    print(f"Wallet balance: {_fmt(wallet_balance)}")


def main():
    """CLI entry point for standalone usage."""
    parser = argparse.ArgumentParser(description="Withdraw from Odin.Fun to iconfucius wallet")
    parser.add_argument("amount", help="Amount in sats, or 'all' to withdraw entire balance")
    args = parser.parse_args()
    run_withdraw("bot-1", args.amount)


if __name__ == "__main__":
    main()
