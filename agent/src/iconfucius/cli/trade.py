"""
iconfucius.cli.trade — Buy or sell tokens on Odin.Fun

Usage:
  python -m iconfucius.cli.trade buy <token_id> <amount_sats>
  python -m iconfucius.cli.trade sell <token_id> <amount_tokens>

Examples:
  python -m iconfucius.cli.trade buy 29m8 500    # Buy 500 sats worth of ICONFUCIUS
  python -m iconfucius.cli.trade sell 29m8 1000   # Sell 1000 tokens
"""

import argparse
import sys

from curl_cffi import requests as cffi_requests
from icp_agent import Agent, Client
from icp_canister import Canister
from icp_identity import Identity
from icp_principal import Principal

from iconfucius.config import fmt_sats, get_btc_to_usd_rate
from iconfucius.config import IC_HOST, MIN_TRADE_SATS, ODIN_API_URL, ODIN_TRADING_CANISTER_ID, get_verify_certificates, log, require_wallet, set_verbose
from iconfucius.siwb import siwb_login, load_session

# Odin uses millisatoshis (msat) for BTC amounts
# 1 sat = 1000 msat
MSAT_PER_SAT = 1000

from iconfucius.candid import ODIN_TRADING_CANDID
from iconfucius.transfers import patch_delegate_sender, unwrap_canister_result


def _fetch_token_info(token_id: str) -> dict | None:
    """Fetch token info (ticker, price, divisibility) from Odin API."""
    try:
        resp = cffi_requests.get(
            f"{ODIN_API_URL}/token/{token_id}",
            impersonate="chrome",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_trade(bot_name: str, action: str, token_id: str, amount: str,
              verbose: bool = False):
    """Run the trade with specified action, token, and amount.

    Args:
        bot_name: Name of the bot to trade with.
        action: Trade action ('buy' or 'sell').
        token_id: Token ID to trade.
        amount: Amount in sats (buy), tokens (sell), or 'all' (sell entire balance).
        verbose: If True, print detailed step output.
    """
    set_verbose(verbose)
    if not require_wallet():
        return

    if action not in ("buy", "sell"):
        print(f"Error: action must be 'buy' or 'sell', got '{action}'")
        return

    sell_all = amount.lower() == "all"
    if sell_all and action != "sell":
        print("Error: 'all' amount is only supported for sell, not buy")
        return
    if not sell_all:
        amount_int = int(amount)
        if action == "buy" and amount_int < MIN_TRADE_SATS:
            print(f"Error: Minimum buy amount is {MIN_TRADE_SATS:,} sats, got {amount_int:,}")
            return

    # Fetch BTC/USD rate for display
    try:
        btc_usd_rate = get_btc_to_usd_rate()
    except Exception:
        btc_usd_rate = None

    def _fmt(sats):
        return fmt_sats(sats, btc_usd_rate)

    # Fetch token info (ticker name, price)
    token_info = _fetch_token_info(token_id)
    ticker = token_info.get("ticker", token_id) if token_info else token_id
    token_price = token_info.get("price", 0) if token_info else 0
    token_divisibility = 8  # Odin default
    token_label = f"{token_id} ({ticker})" if ticker != token_id else token_id

    def fmt_tokens(token_balance):
        """Format token balance with USD value."""
        if token_price and btc_usd_rate:
            value_microsats = (token_balance * token_price) / (10 ** token_divisibility)
            value_sats = value_microsats / 1_000_000
            usd = (value_sats / 100_000_000) * btc_usd_rate
            return f"{token_balance:,} (${usd:.2f})"
        return f"{token_balance:,}"

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    if action == "buy":
        print(f"Trade: BUY {_fmt(amount_int)} of {token_label}")
    elif sell_all:
        print(f"Trade: SELL ALL {token_label}")
    else:
        print(f"Trade: SELL {amount_int:,} {token_label}")

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
    # Step 2: Check Odin.Fun holdings before
    # -----------------------------------------------------------------------
    print(f"Step 2: Odin.Fun holdings (before)...", end=" ", flush=True)

    btc_before_msat = unwrap_canister_result(
        odin_anon.getBalance(bot_principal_text, "btc", "btc",
                             verify_certificate=get_verify_certificates())
    )
    btc_before_sats = btc_before_msat // MSAT_PER_SAT
    token_before = unwrap_canister_result(
        odin_anon.getBalance(bot_principal_text, token_id, "btc",
                             verify_certificate=get_verify_certificates())
    )

    print(f"BTC: {_fmt(btc_before_sats)}, {token_label}: {fmt_tokens(token_before)}")

    # Resolve 'all' to actual token balance
    if sell_all:
        if token_before <= 0:
            print(f"\nNo {token_label} to sell. Skipping.")
            return
        amount_int = token_before

    # Check minimum trade value for sell
    if action == "sell" and token_price:
        sell_value_microsats = (amount_int * token_price) / (10 ** token_divisibility)
        sell_value_sats = int(sell_value_microsats / 1_000_000)
        if sell_value_sats < MIN_TRADE_SATS:
            print(f"\nSell value too low: {_fmt(sell_value_sats)} "
                  f"(minimum {MIN_TRADE_SATS:,} sats). Skipping.")
            return

    # -----------------------------------------------------------------------
    # Step 3: Execute trade
    # -----------------------------------------------------------------------
    if action == "buy":
        amount_msat = amount_int * MSAT_PER_SAT
        trade_request = {
            "tokenid": token_id,
            "typeof": {"buy": None},
            "amount": {"btc": amount_msat},
            "settings": [],
        }
        print(f"Step 3: Buy {token_label} with {_fmt(amount_int)}...", end=" ", flush=True)
    else:
        trade_request = {
            "tokenid": token_id,
            "typeof": {"sell": None},
            "amount": {"token": amount_int},
            "settings": [],
        }
        print(f"Step 3: Sell {amount_int:,} {token_label}...", end=" ", flush=True)

    log("")
    log(f"  Trade request: {trade_request}")

    result = unwrap_canister_result(
        odin_auth.token_trade(trade_request, verify_certificate=get_verify_certificates())
    )
    log(f"  Result: {result}")

    if isinstance(result, dict) and "err" in result:
        print(f"FAILED: {result['err']}")
        return

    print("done")
    print(f"\n✅ Trade executed successfully!")


def main():
    """CLI entry point for standalone usage."""
    parser = argparse.ArgumentParser(description="Trade tokens on Odin.Fun")
    parser.add_argument("action", choices=["buy", "sell"], help="Trade action")
    parser.add_argument("token_id", help="Token ID (e.g., 29m8)")
    parser.add_argument("amount", type=int, help="Amount in sats (buy) or tokens (sell)")
    args = parser.parse_args()
    run_trade(args.action, args.token_id, args.amount)


if __name__ == "__main__":
    main()
