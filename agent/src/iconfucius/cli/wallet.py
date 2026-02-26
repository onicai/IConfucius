"""
iconfucius.cli.wallet — Wallet identity and fund management

Commands:
    wallet create              Generate Ed25519 identity
    wallet info                Show wallet address and balance
    wallet receive             Show how to fund the wallet (ckBTC or BTC)
    wallet send <amt> <addr>   Send ckBTC to a principal or BTC to a Bitcoin address
"""

import os
import stat
import sys
from pathlib import Path
from typing import Optional

import typer

from iconfucius.config import PEM_FILE, _project_root, get_verify_certificates

wallet_app = typer.Typer(no_args_is_help=True)

_show_backup_warning = False

WALLET_DIR = ".wallet"

CERT_VERIFY_WARNING = """
WARNING: IC certificate verification is disabled. See README-security.md for details."""


def _wallet_dir() -> Path:
    """Return the .wallet/ directory path."""
    return Path(_project_root()) / WALLET_DIR


def _pem_path() -> Path:
    """Return the full path to identity-private.pem."""
    return Path(_project_root()) / PEM_FILE


def _backup_pem(pem: Path) -> Path:
    """Move an existing PEM file to a numbered backup.

    Picks the next available suffix: -backup-01, -backup-02, etc.
    Returns the backup path.
    """
    for i in range(1, 100):
        backup = pem.with_name(f"{pem.name}-backup-{i:02d}")
        if not backup.exists():
            pem.rename(backup)
            print(f"Backed up existing wallet to {backup}")
            return backup
    raise RuntimeError("Too many PEM backups (max 99)")


WITHDRAWALS_FILE = ".wallet/btc_withdrawals.json"

MEMPOOL_TX_URL = "https://mempool.space/tx/"
MEMPOOL_ADDRESS_URL = "https://mempool.space/address/"


def _withdrawals_path() -> Path:
    """Return the path to the withdrawals tracking file."""
    return Path(_project_root()) / WITHDRAWALS_FILE


def save_withdrawal_status(block_index: int, btc_address: str, amount: int):
    """Append a BTC withdrawal to the tracking list."""
    import json
    path = _withdrawals_path()
    path.parent.mkdir(exist_ok=True)
    withdrawals = load_withdrawal_statuses()
    withdrawals.append({
        "block_index": block_index,
        "btc_address": btc_address,
        "amount": amount,
    })
    path.write_text(json.dumps(withdrawals))


def load_withdrawal_statuses() -> list:
    """Load all tracked BTC withdrawals."""
    import json
    path = _withdrawals_path()
    if not path.exists():
        # Migrate from old single-withdrawal file
        old_path = Path(_project_root()) / ".wallet/last_btc_withdrawal.json"
        if old_path.exists():
            try:
                data = json.loads(old_path.read_text())
                if isinstance(data, dict):
                    return [data]
                return data if isinstance(data, list) else []
            except Exception:
                return []
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def remove_withdrawal(block_index: int):
    """Remove a confirmed withdrawal from the tracking list."""
    import json
    path = _withdrawals_path()
    withdrawals = load_withdrawal_statuses()
    withdrawals = [w for w in withdrawals if w.get("block_index") != block_index]
    if withdrawals:
        path.write_text(json.dumps(withdrawals))
    elif path.exists():
        path.unlink()
        # Clean up old file too
        old_path = Path(_project_root()) / ".wallet/last_btc_withdrawal.json"
        if old_path.exists():
            old_path.unlink()


def _load_identity():
    """Load the wallet identity from PEM file.

    Returns the Identity object, or exits with an error.
    """
    from icp_identity import Identity

    pem = _pem_path()
    if not pem.exists():
        print(f"Wallet not found at {pem}")
        print("Create it with: iconfucius wallet create")
        raise typer.Exit(1)

    return Identity.from_pem(pem.read_bytes())


@wallet_app.command()
def create(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing wallet"),
):
    """Generate a new Ed25519 wallet identity."""
    from icp_identity import Identity

    pem = _pem_path()
    if pem.exists() and not force:
        print(f"Wallet already exists at {pem}")
        print("Use --force to overwrite (WARNING: this will change your wallet address!)")
        raise typer.Exit(1)

    # Generate Ed25519 keypair
    identity = Identity(type="ed25519")
    pem_bytes = identity.to_pem()

    # Create .wallet/ directory
    wallet_dir = _wallet_dir()
    wallet_dir.mkdir(exist_ok=True)

    # Back up existing PEM before overwriting
    if pem.exists():
        _backup_pem(pem)

    # Atomic-create with 0600 from the start (no race window with world-readable perms)
    fd = os.open(pem, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "wb") as f:
        f.write(pem_bytes)

    print(f"Wallet created: {pem}")
    print()
    print("  External wallet -> iconfucius wallet")
    print("                       |-- fund -> bot-1 -> Odin.Fun trading")
    print("                       |-- fund -> bot-2 -> Odin.Fun trading")
    print("                       +-- fund -> bot-3 -> Odin.Fun trading")
    print()
    print("  Send ckBTC/BTC to your iconfucius wallet address,")
    print("  then use 'iconfucius fund' to distribute to your bots.")
    print()
    print("Next step:")
    print("  iconfucius wallet receive")


@wallet_app.command()
def balance(
    token_id: str = typer.Option("29m8", "--token", "-t", help="Token ID to check"),
    bot: Optional[str] = typer.Option(None, "--bot", "-b", help="Bot name to use"),
    all_bots: bool = typer.Option(False, "--all-bots", help="Show all bots"),
    ckbtc_minter: bool = typer.Option(
        False, "--ckbtc-minter",
        help="Show ckBTC minter status (incoming/outgoing BTC)",
    ),
    monitor: bool = typer.Option(
        False, "--monitor",
        help="Poll until all pending BTC activity completes",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
):
    """Show ckBTC and Odin token balance."""
    from iconfucius.cli import _resolve_bot_names, _resolve_network, state
    from iconfucius.cli.balance import run_all_balances

    _resolve_network(network)

    # --monitor implies --ckbtc-minter
    if monitor:
        ckbtc_minter = True

    if bot is None and not all_bots and state.bot_name is None and not state.all_bots:
        # No bot flag specified — show wallet info only (no bot login needed)
        from iconfucius.cli.balance import run_wallet_balance
        result = run_wallet_balance(monitor=monitor, ckbtc_minter=ckbtc_minter)

        if result:
            print(result.get("_display", ""))

        if not monitor:
            print()
            print("Notes:")
            print(" - Use --ckbtc-minter to see the minting status of incoming and outgoing BTC.")
            print(" - Use --bot <name> or --all-bots to see bot holdings at Odin.Fun")
            return

        if result:
            pending = result.get("pending_sats", 0)
            active_count = result.get("active_withdrawal_count", 0)
            address_btc = result.get("address_btc_sats", 0)
            has_incoming = pending > 0 or address_btc > 0
            has_outgoing = active_count > 0
            if not has_incoming and not has_outgoing:
                print()
                print("All pending BTC activity completed.")
                return
            btc_usd_rate = result.get("btc_usd_rate")
            print()
            if has_incoming and has_outgoing:
                print("Monitoring incoming BTC deposit and outgoing BTC withdrawal...")
            elif has_incoming:
                print("Monitoring incoming BTC deposit — completes when ckBTC minter converts (~6 confirmations)...")
            else:
                print("Monitoring outgoing BTC withdrawal — completes at 6 on-chain confirmations...")
            print("Ctrl+C to stop.")
            print()
            _run_monitor_loop(btc_usd_rate)
    else:
        bot_names = _resolve_bot_names(bot, all_bots)
        result = run_all_balances(bot_names=bot_names, token_id=token_id,
                                  verbose=state.verbose, ckbtc_minter=ckbtc_minter)
        if result:
            print(result.get("_display", ""))


MONITOR_INTERVAL = 30  # seconds between polls


def _run_monitor_loop(btc_usd_rate: float | None):
    """Poll BTC activity with phase-aware in-place line updates.

    Same phase  → overwrite current line(s)
    Phase change → advance to new line
    """
    import time

    from iconfucius.cli.balance import _check_btc_activity

    last_in_phase = None
    last_out_phase = None
    prev_line_count = 0

    try:
        while True:
            sys.stdout.write("\033[2K\rChecking status...")
            sys.stdout.flush()
            status = _check_btc_activity(btc_usd_rate)
            sys.stdout.write("\033[2K\r")
            sys.stdout.flush()

            in_phase = status["incoming_phase"]
            out_phase = status["outgoing_phase"]

            # Detect phase transitions
            in_changed = in_phase != last_in_phase and last_in_phase is not None
            out_changed = out_phase != last_out_phase and last_out_phase is not None

            # Detect outgoing completion (was active, now none)
            if (out_phase == "none"
                    and last_out_phase not in (None, "none", "confirmed")):
                out_phase = "confirmed"
                status["outgoing_phase"] = "confirmed"
                status["outgoing_text"] = "Outgoing BTC: Confirmed!"
                out_changed = True

            # Build lines for this iteration
            lines = []
            if in_phase != "none":
                lines.append(status["incoming_text"])
            if out_phase != "none":
                lines.append(status["outgoing_text"])

            any_changed = in_changed or out_changed

            # Erase previous status lines (overwrite in-place)
            if prev_line_count > 0 and not any_changed:
                for _ in range(prev_line_count):
                    sys.stdout.write("\033[A\033[2K")

            for line in lines:
                print(line)
            prev_line_count = len(lines)

            last_in_phase = in_phase
            last_out_phase = out_phase

            # Check completion
            if (in_phase in ("none", "converted")
                    and out_phase in ("none", "confirmed")):
                print()
                print("All pending BTC activity completed.")
                break

            # Countdown to next check
            for remaining in range(MONITOR_INTERVAL, 0, -1):
                sys.stdout.write(f"\033[2K\rNext check in {remaining}s...")
                sys.stdout.flush()
                time.sleep(1)
            sys.stdout.write("\033[2K\r")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print()
        print("Monitoring stopped.")


@wallet_app.command()
def info(
    ckbtc_minter: bool = typer.Option(
        False, "--ckbtc-minter",
        help="Show ckBTC minter status (incoming/outgoing BTC)",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
):
    """Show wallet address and ckBTC balance."""
    from iconfucius.cli import _resolve_network
    from iconfucius.config import get_pem_file

    _resolve_network(network)
    _load_identity()  # Ensure wallet exists

    from iconfucius.cli.balance import run_wallet_balance

    result = run_wallet_balance(ckbtc_minter=ckbtc_minter)
    if result:
        print(result.get("_display", ""))

    pem_path = get_pem_file()
    print()
    print("Notes:")
    print(" - Use --ckbtc-minter to see the minting status of incoming and outgoing BTC.")
    print(f" - Wallet PEM file: {pem_path}")
    print("   -> Back up .wallet/identity-private.pem securely!")
    print("   -> If lost, you lose access to your wallet and all funds in it.")
    print("   -> If leaked, anyone can control your wallet.")
    print("   -> Treat it like an SSH private key or a Bitcoin seed phrase.")
    if not get_verify_certificates():
        print(CERT_VERIFY_WARNING)


@wallet_app.command()
def receive(
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
):
    """Show wallet address for funding with ckBTC or BTC."""
    from icp_agent import Agent, Client
    from icp_identity import Identity

    from iconfucius.cli import _resolve_network
    from iconfucius.config import fmt_sats, get_btc_to_usd_rate

    _resolve_network(network)
    from iconfucius.transfers import (
        IC_HOST,
        create_ckbtc_minter,
        create_icrc1_canister,
        get_balance,
        get_btc_address,
    )

    identity = _load_identity()
    wallet_principal = str(identity.sender())

    # Get wallet BTC deposit address and balance
    client = Client(url=IC_HOST)
    anon_agent = Agent(Identity(anonymous=True), client)
    minter = create_ckbtc_minter(anon_agent)
    btc_address = get_btc_address(minter, wallet_principal)

    icrc1_canister__anon = create_icrc1_canister(anon_agent)
    balance = get_balance(icrc1_canister__anon, wallet_principal)

    try:
        btc_usd_rate = get_btc_to_usd_rate()
    except Exception:
        btc_usd_rate = None

    print()
    print("=" * 60)
    print("Fund your iconfucius wallet")
    print("=" * 60)
    print()
    print("Option 1: Send BTC from any Bitcoin wallet")
    print(f"  {btc_address}")
    from iconfucius.config import fmt_sats, get_btc_to_usd_rate
    try:
        _rate = get_btc_to_usd_rate()
    except Exception:
        _rate = None
    print(f"  Min deposit: {fmt_sats(10_000, _rate)}.")
    print("  Requires ~6 confirmations (~1 hour).")
    print("  Run 'iconfucius wallet balance --monitor' to track conversion.")
    print()
    print("Option 2: Send ckBTC from any ckBTC wallet")
    print(f"  {wallet_principal}")
    print("  Send from NNS, Plug, Oisy, or any ckBTC wallet.")
    print()
    print(f"Wallet balance: {fmt_sats(balance, btc_usd_rate)}")
    print()
    print("After funding, distribute to your bots:")
    print("  iconfucius fund 5000 --bot bot-1  # fund specific bot")
    print("  iconfucius fund 5000 --all-bots   # fund all bots")


@wallet_app.command()
def send(
    amount: str = typer.Argument(..., help="Amount in sats, or 'all' for entire balance"),
    address: str = typer.Argument(..., help="Destination: IC principal or Bitcoin address (bc1...)"),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
):
    """Send ckBTC to a principal or BTC to a Bitcoin address."""
    from icp_agent import Agent, Client
    from icp_identity import Identity

    from iconfucius.cli import _resolve_network
    _resolve_network(network)

    from iconfucius.transfers import (
        CKBTC_FEE,
        IC_HOST,
        create_icrc1_canister,
        create_ckbtc_minter,
        get_balance,
        get_withdrawal_account,
        estimate_withdrawal_fee,
        retrieve_btc_withdrawal,
        transfer,
        unwrap_canister_result,
    )

    # Detect address type
    from iconfucius.config import is_bech32_btc_address
    is_btc = is_bech32_btc_address(address)

    # Load wallet identity (PEM)
    identity = _load_identity()
    wallet_principal = str(identity.sender())

    client = Client(url=IC_HOST)
    anon_agent = Agent(Identity(anonymous=True), client)
    auth_agent = Agent(identity, client)

    icrc1_canister__anon = create_icrc1_canister(anon_agent)
    icrc1_canister__wallet = create_icrc1_canister(auth_agent)

    from iconfucius.config import fmt_sats, get_btc_to_usd_rate
    try:
        btc_usd_rate = get_btc_to_usd_rate()
    except Exception:
        btc_usd_rate = None

    wallet_balance = get_balance(icrc1_canister__anon, wallet_principal)
    print(f"Wallet balance: {fmt_sats(wallet_balance, btc_usd_rate)}")

    if is_btc:
        result = _send_btc(
            amount, address, wallet_principal, wallet_balance,
            auth_agent, anon_agent, icrc1_canister__anon, icrc1_canister__wallet,
            create_ckbtc_minter, get_withdrawal_account,
            estimate_withdrawal_fee, retrieve_btc_withdrawal,
            transfer, get_balance, unwrap_canister_result, CKBTC_FEE,
            btc_usd_rate,
        )
    else:
        result = _send_ckbtc(
            amount, address, wallet_principal, wallet_balance,
            icrc1_canister__anon, icrc1_canister__wallet,
            transfer, get_balance, CKBTC_FEE,
            btc_usd_rate,
        )

    if result["status"] == "error":
        print(result["error"])
        raise typer.Exit(1)

    # Print success summary
    if result.get("is_send_all"):
        print(f"Sending all: {fmt_sats(result['sent_sats'], btc_usd_rate)}"
              f" (balance {fmt_sats(result['balance_before_sats'], btc_usd_rate)}"
              f" - fee {result.get('ckbtc_fee', '')})")

    if result["type"] == "ckbtc_transfer":
        print(f"Sending {fmt_sats(result['sent_sats'], btc_usd_rate)} to {result['to']}...")
        print(f"Transfer succeeded! Block index: {result['tx_index']}")
    elif result["type"] == "btc_withdrawal":
        print(f"BTC withdrawal initiated! Block index: {result['block_index']}")
        print("BTC will arrive after the transaction is confirmed on the Bitcoin network.")
        print("Check progress with: iconfucius wallet balance --monitor")

    print(f"Wallet balance: {fmt_sats(result['balance_after_sats'], btc_usd_rate)}"
          f" (was {fmt_sats(result['balance_before_sats'], btc_usd_rate)})")


def _send_ckbtc(
    amount, to_principal, wallet_principal, wallet_balance,
    icrc1_canister__anon, icrc1_canister__wallet,
    transfer, get_balance, ckbtc_fee,
    btc_usd_rate=None,
) -> dict:
    """Send ckBTC to an IC principal via ICRC-1 transfer.

    Returns a structured dict:
        {"status": "ok", "tx_index": ..., "sent_sats": ..., ...}
        {"status": "error", "error": "..."}
    """
    from iconfucius.config import fmt_sats
    from iconfucius.logging_config import get_logger
    logger = get_logger()

    is_send_all = amount.lower() == "all"

    # Determine amount
    if is_send_all:
        if wallet_balance <= ckbtc_fee:
            return {"status": "error",
                    "error": f"Insufficient balance. Have {fmt_sats(wallet_balance, btc_usd_rate)}, fee is {fmt_sats(ckbtc_fee, btc_usd_rate)}."}
        send_amount = wallet_balance - ckbtc_fee
    else:
        send_amount = int(amount)

    if send_amount <= 0:
        return {"status": "error", "error": "Nothing to send."}

    total_needed = send_amount + ckbtc_fee
    if wallet_balance < total_needed:
        return {"status": "error",
                "error": f"Insufficient balance. Need {fmt_sats(total_needed, btc_usd_rate)}, have {fmt_sats(wallet_balance, btc_usd_rate)}."}

    # Execute transfer
    logger.info("Sending %s to %s...", fmt_sats(send_amount, btc_usd_rate), to_principal)
    try:
        result = transfer(icrc1_canister__wallet, to_principal, send_amount)

        if isinstance(result, dict) and "Err" in result:
            return {"status": "error", "error": f"Transfer failed: {result['Err']}"}

        tx_index = result.get("Ok", result) if isinstance(result, dict) else result

    except Exception as e:
        return {"status": "error", "error": f"Transfer failed: {e}"}

    # Verify
    wallet_balance_after = get_balance(icrc1_canister__anon, wallet_principal)

    return {
        "status": "ok",
        "type": "ckbtc_transfer",
        "tx_index": tx_index,
        "sent_sats": send_amount,
        "to": to_principal,
        "is_send_all": is_send_all,
        "balance_before_sats": wallet_balance,
        "balance_after_sats": wallet_balance_after,
        "ckbtc_fee": ckbtc_fee,
    }


def _send_btc(
    amount, btc_address, wallet_principal, wallet_balance,
    auth_agent, anon_agent, icrc1_canister__anon, icrc1_canister__wallet,
    create_ckbtc_minter, get_withdrawal_account,
    estimate_withdrawal_fee, retrieve_btc_withdrawal,
    transfer, get_balance, unwrap_canister_result, ckbtc_fee,
    btc_usd_rate=None,
) -> dict:
    """Withdraw BTC to a Bitcoin address via ckBTC minter.

    Returns a structured dict:
        {"status": "ok", "block_index": ..., "sent_sats": ..., ...}
        {"status": "error", "error": "..."}
    """
    from iconfucius.config import fmt_sats, get_verify_certificates
    from iconfucius.logging_config import get_logger
    logger = get_logger()

    # Estimate withdrawal fee
    minter = create_ckbtc_minter(auth_agent)

    logger.info("Estimating withdrawal fee...")
    try:
        fee_info = estimate_withdrawal_fee(minter)
        minter_fee = fee_info.get("minter_fee", 0)
        bitcoin_fee = fee_info.get("bitcoin_fee", 0)
        total_fee = minter_fee + bitcoin_fee
        logger.info("  Minter fee: %s", fmt_sats(minter_fee, btc_usd_rate))
        logger.info("  Bitcoin fee: %s", fmt_sats(bitcoin_fee, btc_usd_rate))
        logger.info("  Total fee: %s", fmt_sats(total_fee, btc_usd_rate))
    except Exception as e:
        logger.warning("Could not estimate fee: %s", e)
        minter_fee = 0
        bitcoin_fee = 0
        total_fee = 0

    # Get withdrawal account and check existing balance
    logger.info("Getting withdrawal account...")
    withdrawal_account = get_withdrawal_account(minter)
    withdrawal_owner = withdrawal_account.get("owner")
    withdrawal_subaccount = withdrawal_account.get("subaccount", [])

    existing_balance = unwrap_canister_result(
        icrc1_canister__anon.icrc1_balance_of({
            "owner": withdrawal_owner,
            "subaccount": withdrawal_subaccount,
        }, verify_certificate=get_verify_certificates())
    )
    if existing_balance > 0:
        logger.info("  Existing balance in withdrawal account: %s",
                     fmt_sats(existing_balance, btc_usd_rate))

    # Determine amount (wallet + existing withdrawal account balance)
    is_send_all = amount.lower() == "all"
    available = wallet_balance + existing_balance
    if is_send_all:
        # ckbtc_fee only charged when we actually transfer to the withdrawal account
        send_amount = available - total_fee
        if existing_balance < available:
            send_amount -= ckbtc_fee  # need a transfer, so deduct transfer fee
        if send_amount <= 0:
            return {"status": "error",
                    "error": f"Insufficient balance. Have {fmt_sats(available, btc_usd_rate)}, fees are {fmt_sats(ckbtc_fee + total_fee, btc_usd_rate)}."}
    else:
        send_amount = int(amount)

    if send_amount <= 0:
        return {"status": "error", "error": "Nothing to send."}

    # Check minimum BTC withdrawal amount (ckBTC minter enforces this)
    from iconfucius.config import MIN_BTC_WITHDRAWAL_SATS
    if send_amount < MIN_BTC_WITHDRAWAL_SATS:
        return {"status": "error",
                "error": (f"BTC withdrawal amount too low: {fmt_sats(send_amount, btc_usd_rate)}.\n"
                          f"Minimum BTC withdrawal via ckBTC minter: {fmt_sats(MIN_BTC_WITHDRAWAL_SATS, btc_usd_rate)}.\n"
                          f"To send smaller amounts, use ckBTC transfer to an IC principal instead.")}

    # How much more needs to go into the withdrawal account?
    needed_in_account = send_amount + total_fee
    transfer_amount = max(0, needed_in_account - existing_balance)

    # Check wallet has enough for the transfer (+ ckbtc transfer fee if needed)
    wallet_needed = transfer_amount + (ckbtc_fee if transfer_amount > 0 else 0)
    if wallet_balance < wallet_needed:
        return {"status": "error",
                "error": f"Insufficient wallet balance. Need {fmt_sats(wallet_needed, btc_usd_rate)}, have {fmt_sats(wallet_balance, btc_usd_rate)}."}

    if transfer_amount == 0:
        logger.info("Withdrawal account already has enough (%s), skipping transfer.",
                     fmt_sats(existing_balance, btc_usd_rate))
    else:
        logger.info("Transferring %s to minter withdrawal account...",
                     fmt_sats(transfer_amount, btc_usd_rate))
        try:
            to_account = {"owner": withdrawal_owner, "subaccount": withdrawal_subaccount}
            result_raw = icrc1_canister__wallet.icrc1_transfer(
                {
                    "to": to_account,
                    "amount": transfer_amount,
                    "fee": [],
                    "memo": [],
                    "from_subaccount": [],
                    "created_at_time": [],
                },
                verify_certificate=get_verify_certificates(),
            )
            result = unwrap_canister_result(result_raw)
            if isinstance(result, dict) and "Err" in result:
                return {"status": "error",
                        "error": f"Transfer to withdrawal account failed: {result['Err']}"}
            logger.info("  Transfer block index: %s",
                         result.get('Ok', result) if isinstance(result, dict) else result)
        except Exception as e:
            return {"status": "error",
                    "error": f"Transfer to withdrawal account failed: {e}"}

    # Call retrieve_btc
    logger.info("Initiating BTC withdrawal of %s to %s...",
                 fmt_sats(send_amount, btc_usd_rate), btc_address)
    try:
        result = retrieve_btc_withdrawal(minter, btc_address, send_amount)

        if isinstance(result, dict) and "Err" in result:
            err = result["Err"]
            if "AmountTooLow" in err:
                return {"status": "error",
                        "error": f"Amount too low. Minimum: {fmt_sats(err['AmountTooLow'], btc_usd_rate)}"}
            elif "InsufficientFunds" in err:
                return {"status": "error",
                        "error": f"Insufficient funds in withdrawal account: {err['InsufficientFunds']}"}
            elif "MalformedAddress" in err:
                return {"status": "error",
                        "error": f"Invalid Bitcoin address: {err['MalformedAddress']}"}
            else:
                return {"status": "error", "error": f"Withdrawal failed: {err}"}

        block_index = result.get("Ok", result) if isinstance(result, dict) else result
        if isinstance(block_index, dict):
            block_index = block_index.get("block_index", block_index)

        # Save for status tracking
        if isinstance(block_index, int):
            save_withdrawal_status(block_index, btc_address, send_amount)

    except Exception as e:
        return {"status": "error", "error": f"Withdrawal failed: {e}"}

    # Verify remaining balance
    wallet_balance_after = get_balance(icrc1_canister__anon, wallet_principal)

    return {
        "status": "ok",
        "type": "btc_withdrawal",
        "block_index": block_index,
        "sent_sats": send_amount,
        "to": btc_address,
        "is_send_all": is_send_all,
        "minter_fee_sats": minter_fee,
        "bitcoin_fee_sats": bitcoin_fee,
        "balance_before_sats": wallet_balance,
        "balance_after_sats": wallet_balance_after,
    }
