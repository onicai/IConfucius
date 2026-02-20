"""
iconfucius.cli.fund — Fund bots and deposit into Odin.Fun trading accounts

Transfers ckBTC from the iconfucius wallet to each bot and deposits
into their Odin.Fun trading accounts in one seamless operation.

Flow per bot:
  1. ICRC-1 transfer from iconfucius wallet to bot
  2. ICRC-2 approve (bot allows deposit canister to spend)
  3. ckbtc_deposit (deposit canister pulls ckBTC into Odin.Fun)

Usage:
  iconfucius --bot bot-1 fund 5000     Fund bot-1
  iconfucius --all-bots fund 5000      Fund all bots with 5000 each
"""

from icp_agent import Agent, Client
from icp_canister import Canister
from icp_identity import Identity
from icp_principal import Principal

from iconfucius.config import fmt_sats, get_btc_to_usd_rate
from iconfucius.config import (
    CKBTC_LEDGER_CANISTER_ID,
    IC_HOST,
    MIN_DEPOSIT_SATS,
    ODIN_DEPOSIT_CANISTER_ID,
    ODIN_TRADING_CANISTER_ID,
    get_pem_file,
    get_verify_certificates,
    log,
    require_wallet,
    set_verbose,
)
from iconfucius.siwb import load_session, siwb_login
from iconfucius.transfers import (
    CKBTC_FEE,
    create_icrc1_canister,
    get_balance,
    patch_delegate_sender,
    transfer,
    unwrap_canister_result,
)

from iconfucius.candid import CKBTC_LEDGER_CANDID, ODIN_DEPOSIT_CANDID, ODIN_TRADING_CANDID


def _fund_one_bot(bot_name, amount, pem_content, verbose, btc_usd_rate):
    """Fund a single bot and deposit into Odin.Fun. Thread-safe.

    Creates its own IC agents so it can run in a thread pool without
    sharing mutable state with other threads.

    Returns:
        dict with "status" key: "ok" on success, "failed" on error.
    """
    set_verbose(verbose)

    # Create thread-local agents from the shared PEM content
    wallet_identity = Identity.from_pem(pem_content)
    client = Client(url=IC_HOST)
    wallet_agent = Agent(wallet_identity, client)
    icrc1_canister__wallet = create_icrc1_canister(wallet_agent)

    # 3a: SIWB login
    auth = load_session(bot_name=bot_name, verbose=verbose)
    if not auth:
        log("")
        log(f"  No cached session for {bot_name}, performing SIWB login...")
        auth = siwb_login(bot_name=bot_name, verbose=verbose)
        set_verbose(verbose)

    bot_principal = auth["bot_principal_text"]
    delegate_identity = auth["delegate_identity"]
    patch_delegate_sender(delegate_identity)
    log(f"  Bot principal: {bot_principal}")

    # 3b: Transfer from wallet to bot (amount + fee for approve step)
    transfer_amount = amount + CKBTC_FEE
    log(f"  Transferring {fmt_sats(transfer_amount, btc_usd_rate)} to bot...")
    result = transfer(icrc1_canister__wallet, bot_principal, transfer_amount)
    if isinstance(result, dict) and "Err" in result:
        return {"status": "failed", "step": "transfer", "error": str(result["Err"])}
    tx_index = result.get("Ok", result) if isinstance(result, dict) else result
    log(f"  Transfer done, block index: {tx_index}")

    # 3c: ICRC-2 Approve (bot allows deposit canister to spend)
    auth_agent = Agent(delegate_identity, client)
    icrc1_canister__bot = Canister(
        agent=auth_agent,
        canister_id=CKBTC_LEDGER_CANISTER_ID,
        candid_str=CKBTC_LEDGER_CANDID,
    )

    deposit_canister_principal = Principal.from_str(ODIN_DEPOSIT_CANISTER_ID)
    approve_amount = amount + CKBTC_FEE

    log(f"  Approving {fmt_sats(approve_amount, btc_usd_rate)} for deposit canister...")
    approve_result = unwrap_canister_result(icrc1_canister__bot.icrc2_approve({
        "spender": {"owner": deposit_canister_principal, "subaccount": []},
        "amount": approve_amount,
        "fee": [],
        "memo": [],
        "from_subaccount": [],
        "created_at_time": [],
        "expected_allowance": [],
        "expires_at": [],
    }, verify_certificate=get_verify_certificates()))

    log(f"  Approve result: {approve_result}")

    if isinstance(approve_result, dict) and "Err" in approve_result:
        return {"status": "failed", "step": "approve", "error": str(approve_result["Err"])}

    # 3d: ckbtc_deposit (deposit canister pulls ckBTC into Odin.Fun)
    odin_deposit = Canister(
        agent=auth_agent,
        canister_id=ODIN_DEPOSIT_CANISTER_ID,
        candid_str=ODIN_DEPOSIT_CANDID,
    )

    log(f"  Depositing {fmt_sats(amount, btc_usd_rate)} into Odin.Fun...")
    deposit_result = unwrap_canister_result(
        odin_deposit.ckbtc_deposit([], amount, verify_certificate=get_verify_certificates())
    )

    log(f"  Deposit result: {deposit_result}")

    if isinstance(deposit_result, dict) and "err" in deposit_result:
        return {"status": "failed", "step": "deposit", "error": str(deposit_result["err"])}

    # Best-effort: query post-deposit Odin.Fun balance
    MSAT_PER_SAT = 1000
    odin_balance_sats = None
    try:
        anon_agent = Agent(Identity(anonymous=True), client)
        odin_anon = Canister(
            agent=anon_agent,
            canister_id=ODIN_TRADING_CANISTER_ID,
            candid_str=ODIN_TRADING_CANDID,
        )
        odin_balance_msat = unwrap_canister_result(
            odin_anon.getBalance(bot_principal, "btc", "btc",
                                 verify_certificate=get_verify_certificates())
        )
        odin_balance_sats = odin_balance_msat // MSAT_PER_SAT
    except Exception:
        pass  # deposit succeeded; balance check is informational

    result = {"status": "ok", "odin_balance_sats": odin_balance_sats}
    if odin_balance_sats is not None:
        result["note"] = (
            f"Deposited {fmt_sats(amount, btc_usd_rate)} into {bot_name}. "
            f"New Odin.Fun balance is {fmt_sats(odin_balance_sats, btc_usd_rate)}."
        )
    return result


def run_fund(bot_names: list, amount: int, verbose: bool = False) -> dict:
    """Fund bot(s) and deposit into Odin.Fun trading accounts.

    Returns a structured dict:
        {"status": "ok"/"error"/"partial", ...}

    Args:
        bot_names: List of bot names to fund.
        amount: Amount in sats to deposit into each bot's Odin.Fun account.
        verbose: If True, enable detailed logging.
    """
    from iconfucius.logging_config import get_logger
    logger = get_logger()

    set_verbose(verbose)
    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    if amount <= 0:
        return {"status": "error", "error": "Amount must be positive"}

    if amount < MIN_DEPOSIT_SATS:
        return {"status": "error",
                "error": f"Minimum deposit is {MIN_DEPOSIT_SATS:,} sats, got {amount:,}"}

    # Fetch BTC/USD rate
    try:
        btc_usd_rate = get_btc_to_usd_rate()
    except Exception:
        btc_usd_rate = None

    def _fmt(sats):
        return fmt_sats(sats, btc_usd_rate)

    # -----------------------------------------------------------------------
    # Step 1: Load iconfucius wallet
    # -----------------------------------------------------------------------
    from iconfucius.cli.concurrent import report_status
    report_status("loading wallet...")
    logger.info("Step 1: Load iconfucius wallet...")
    pem_path = get_pem_file()
    with open(pem_path, "r") as f:
        pem_content = f.read()
    wallet_identity = Identity.from_pem(pem_content)
    wallet_principal = str(wallet_identity.sender())
    logger.info("Step 1: Wallet loaded")
    log(f"  Wallet principal: {wallet_principal}")

    client = Client(url=IC_HOST)
    anon_agent = Agent(Identity(anonymous=True), client)
    icrc1_canister__anon = create_icrc1_canister(anon_agent)

    # -----------------------------------------------------------------------
    # Step 2: Check wallet balance
    # -----------------------------------------------------------------------
    wallet_balance = get_balance(icrc1_canister__anon, wallet_principal)

    # Per bot cost: amount (deposit) + CKBTC_FEE (approve allowance) + CKBTC_FEE (transfer fee)
    per_bot_cost = amount + 2 * CKBTC_FEE
    total_needed = per_bot_cost * len(bot_names)

    logger.info("Step 2: Wallet balance: %s", _fmt(wallet_balance))

    if wallet_balance < total_needed:
        return {
            "status": "error",
            "error": (f"Insufficient wallet balance. "
                      f"Need {_fmt(total_needed)} "
                      f"({len(bot_names)} bot(s) x {amount:,} + fees), "
                      f"have {_fmt(wallet_balance)}"),
        }

    # -----------------------------------------------------------------------
    # Step 3: Fund and deposit for each bot (concurrent)
    # -----------------------------------------------------------------------
    report_status(f"funding {len(bot_names)} bot(s)...")
    suffix = " each" if len(bot_names) > 1 else ""
    logger.info("Step 3: Funding %d bot(s) with %s%s...",
                len(bot_names), _fmt(amount), suffix)

    from iconfucius.cli.concurrent import run_per_bot

    results = run_per_bot(
        lambda name: _fund_one_bot(name, amount, pem_content, verbose, btc_usd_rate),
        bot_names,
    )

    funded, failed, details, notes = [], [], [], []
    for bot_name, result in results:
        if isinstance(result, Exception):
            failed.append({"bot": bot_name, "error": str(result)})
        elif result["status"] == "failed":
            failed.append({"bot": bot_name,
                           "error": f"{result['step']}: {result['error']}"})
        else:
            funded.append(bot_name)
            details.append({
                "bot": bot_name,
                "odin_balance_sats": result.get("odin_balance_sats"),
            })
            if result.get("note"):
                notes.append(result["note"])

    logger.info("Funded %d/%d bot(s)", len(funded), len(bot_names))

    all_ok = not failed
    return {
        "status": "ok" if all_ok else "partial",
        "funded": funded,
        "failed": failed,
        "amount": amount,
        "bot_count": len(bot_names),
        "details": details,
        "notes": notes,
    }
