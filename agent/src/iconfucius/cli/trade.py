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
from icp_principal import Principal

from iconfucius.config import fmt_sats, fmt_tokens, get_btc_to_usd_rate
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
              verbose: bool = False) -> dict:
    """Run the trade with specified action, token, and amount.

    Returns a structured dict:
        {"status": "ok", "action": ..., "bot_name": ..., ...}
        {"status": "error", "error": "..."}
        {"status": "skipped", "reason": "..."}

    Args:
        bot_name: Name of the bot to trade with.
        action: Trade action ('buy' or 'sell').
        token_id: Token ID to trade.
        amount: Amount in sats (buy), tokens (sell), or 'all' (sell entire balance).
        verbose: If True, enable detailed logging.
    """
    from iconfucius.logging_config import get_logger
    logger = get_logger()

    set_verbose(verbose)
    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    if action not in ("buy", "sell"):
        return {"status": "error", "error": f"action must be 'buy' or 'sell', got '{action}'"}

    sell_all = amount.lower() == "all"
    if sell_all and action != "sell":
        return {"status": "error", "error": "'all' amount is only supported for sell, not buy"}
    if not sell_all:
        amount_int = int(amount)
        if action == "buy" and amount_int < MIN_TRADE_SATS:
            return {"status": "error",
                    "error": f"Minimum buy amount is {MIN_TRADE_SATS:,} sats, got {amount_int:,}"}

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

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    if action == "buy":
        logger.info("Trade: BUY %s of %s (bot=%s)", _fmt(amount_int), token_label, bot_name)
    elif sell_all:
        logger.info("Trade: SELL ALL %s (bot=%s)", token_label, bot_name)
    else:
        logger.info("Trade: SELL %s %s (bot=%s)", fmt_tokens(amount_int, token_id), token_label, bot_name)

    # -----------------------------------------------------------------------
    # Step 1: SIWB login
    # -----------------------------------------------------------------------
    logger.info("Step 1: SIWB Login (bot=%s)...", bot_name)
    auth = load_session(bot_name=bot_name, verbose=verbose)
    if not auth:
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
    # Step 2: Check Odin.Fun holdings before
    # -----------------------------------------------------------------------
    logger.info("Step 2: Odin.Fun holdings (bot=%s)...", bot_name)

    btc_before_msat = unwrap_canister_result(
        odin.getBalance(bot_principal_text, "btc",
                             verify_certificate=get_verify_certificates())
    )
    btc_before_sats = btc_before_msat // MSAT_PER_SAT
    token_before = unwrap_canister_result(
        odin.getBalance(bot_principal_text, token_id,
                             verify_certificate=get_verify_certificates())
    )

    logger.info("Step 2: BTC=%s, %s=%s (bot=%s)",
                _fmt(btc_before_sats), token_label, fmt_tokens(token_before, token_id), bot_name)

    # Cap buy amount to actual Odin.Fun balance
    capped_from = None
    if action == "buy" and amount_int > btc_before_sats:
        if btc_before_sats < MIN_TRADE_SATS:
            return {"status": "error", "bot_name": bot_name,
                    "error": f"Odin.Fun balance too low: {_fmt(btc_before_sats)} "
                             f"(minimum {MIN_TRADE_SATS:,} sats)"}
        logger.info("Capping buy from %s to %s (actual balance) (bot=%s)",
                    _fmt(amount_int), _fmt(btc_before_sats), bot_name)
        capped_from = amount_int
        amount_int = btc_before_sats

    # Resolve 'all' to actual token balance
    if sell_all:
        if token_before <= 0:
            return {"status": "skipped", "bot_name": bot_name,
                    "reason": f"No {token_label} to sell"}
        amount_int = token_before

    # Check minimum trade value for sell
    if action == "sell" and token_price:
        sell_value_microsats = (amount_int * token_price) / (10 ** token_divisibility)
        sell_value_sats = int(sell_value_microsats / 1_000_000)
        if sell_value_sats < MIN_TRADE_SATS:
            return {"status": "skipped", "bot_name": bot_name,
                    "reason": f"Sell value too low: {_fmt(sell_value_sats)} "
                              f"(minimum {MIN_TRADE_SATS:,} sats)"}

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
        logger.info("Step 3: Buy %s with %s (bot=%s)...", token_label, _fmt(amount_int), bot_name)
    else:
        trade_request = {
            "tokenid": token_id,
            "typeof": {"sell": None},
            "amount": {"token": amount_int},
            "settings": [],
        }
        logger.info("Step 3: Sell %s %s (bot=%s)...", fmt_tokens(amount_int, token_id), token_label, bot_name)

    log(f"  Trade request: {trade_request}")

    result = unwrap_canister_result(
        odin.token_trade(trade_request, verify_certificate=get_verify_certificates())
    )
    log(f"  Result: {result}")

    if isinstance(result, dict) and "err" in result:
        return {"status": "error", "bot_name": bot_name,
                "error": str(result["err"])}

    logger.info("Trade executed successfully (bot=%s)", bot_name)
    result = {
        "status": "ok",
        "action": action,
        "bot_name": bot_name,
        "token_id": token_id,
        "token_label": token_label,
        "amount": amount_int,
        "btc_before_sats": btc_before_sats,
        "token_before": token_before,
    }
    if capped_from is not None:
        result["note"] = (
            f"Requested {_fmt(capped_from)} but {bot_name} only had "
            f"{_fmt(amount_int)} on Odin.Fun. Buy amount was auto-capped."
        )
    return result


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
