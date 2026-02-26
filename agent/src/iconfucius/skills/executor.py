"""Tool executor — dispatches tool calls to underlying iconfucius functions.

Each handler calls the underlying function, which returns a structured dict,
and builds the response for the AI agent.
"""

import json
import os
from pathlib import Path


# Session-level flag for experimental features (set by enable_experimental tool)
_experimental_enabled = False

EXPERIMENTAL_ENABLED = (
    "Experimental features have been enabled for this session. "
    "Type /ai to configure your AI model and backend."
)

EXPERIMENTAL_RISK_WARNING = (
    "WARNING: Changing the AI model is an experimental feature. "
    "Alternative backends \u2014 such as local llama.cpp, Ollama, or other "
    "OpenAI-compatible endpoints \u2014 may not support tool use or may "
    "behave unexpectedly. Use at your own risk."
)


def execute_tool(name: str, args: dict, *, persona_name: str = "") -> dict:
    """Execute a tool by name with the given arguments.

    Args:
        name: Tool name.
        args: Tool arguments.
        persona_name: Persona name for memory operations (trade recording, etc.).

    Returns:
        {"status": "ok", ...} on success,
        {"status": "error", "error": "message"} on failure.
    """
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"status": "error", "error": f"Unknown tool: {name}"}
    try:
        # Memory tools need persona_name
        if name in ("memory_read_strategy", "memory_read_learnings", "memory_read_trades", "memory_update", "memory_read_balances", "memory_archive_balances"):
            result = handler(args, persona_name=persona_name)
        else:
            result = handler(args)

        # Record successful trades
        if name in ("trade_buy", "trade_sell") and result.get("status") == "ok" and persona_name:
            _record_trade(name, args, result, persona_name)

        # Record balance snapshot
        if name == "wallet_balance" and result.get("status") == "ok" and persona_name:
            _record_balance_snapshot(result, persona_name)

        return result
    except SystemExit:
        # get_verify_certificates() raises SystemExit when blst is missing
        return {
            "status": "error",
            "error": (
                "verify_certificates is enabled in iconfucius.toml "
                "but the 'blst' library is not installed. "
                "Either install blst (see https://github.com/onicai/IConfucius/blob/main/agent/README-security.md) "
                "or set verify_certificates = false in [settings]."
            ),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Formatting handlers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Setup handlers
# ---------------------------------------------------------------------------

def _handle_setup_status(args: dict) -> dict:
    from iconfucius.config import find_config, get_pem_file

    config_path = find_config()
    pem_exists = Path(get_pem_file()).exists()
    env_exists = Path(".env").exists()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    has_api_key = bool(api_key) and api_key != "your-api-key-here"

    return {
        "status": "ok",
        "config_exists": config_path is not None,
        "wallet_exists": pem_exists,
        "env_exists": env_exists,
        "has_api_key": has_api_key,
        "ready": all([config_path is not None, pem_exists, has_api_key]),
    }


def _handle_check_update(args: dict) -> dict:
    from iconfucius import __version__

    # Result is cached at module level by chat.py at startup
    return {
        "status": "ok",
        "running_version": __version__,
        "latest_version": _update_cache.get("latest_version"),
        "release_notes": _update_cache.get("release_notes", ""),
        "update_available": _update_cache.get("latest_version") is not None,
        "upgrade_command": "/upgrade",
    }


# Populated by chat.py at startup so the handler doesn't re-fetch
_update_cache: dict = {}


def _handle_enable_experimental(args: dict) -> dict:
    global _experimental_enabled
    _experimental_enabled = True
    return {
        "status": "ok",
        "display": f"\n{EXPERIMENTAL_ENABLED}\n\n{EXPERIMENTAL_RISK_WARNING}",
        "instruction": (
            "Explain to the user that changing the AI model is experimental. "
            "Alternative backends may lack tool-use support, produce lower "
            "quality responses, or behave unexpectedly. Ask if they want to "
            "proceed, and if so, tell them to type /ai."
        ),
    }


def _handle_init(args: dict) -> dict:
    from typer.testing import CliRunner
    from iconfucius.cli import app as cli_app

    cmd = ["init"]
    if args.get("force"):
        cmd.append("--force")
    num_bots = args.get("num_bots")
    if num_bots is not None:
        cmd.extend(["--bots", str(num_bots)])

    runner = CliRunner()
    result = runner.invoke(cli_app, cmd)
    if result.exit_code != 0:
        return {"status": "error", "error": result.output.strip()}

    # Reload config so the rest of the session sees it
    from iconfucius.config import load_config
    load_config(reload=True)

    return {"status": "ok", "display": result.output.strip()}


def _handle_set_bot_count(args: dict) -> dict:
    import re
    from pathlib import Path

    from iconfucius.config import (
        CONFIG_FILENAME,
        add_bots_to_config,
        find_config,
        get_bot_names,
        load_config,
        remove_bots_from_config,
    )

    if not find_config():
        return {"status": "error", "error": "No iconfucius.toml found. Run init first."}

    num_bots = args.get("num_bots")
    if num_bots is None:
        return {"status": "error", "error": "'num_bots' is required."}
    num_bots = max(1, min(1000, int(num_bots)))
    force = args.get("force", False)

    config = load_config(reload=True)
    current_bots = get_bot_names()
    current_count = len(current_bots)

    if num_bots == current_count:
        return {
            "status": "ok",
            "message": f"Already configured with {num_bots} bot(s).",
            "bot_count": num_bots,
        }

    # --- Increasing: add new bots ---
    if num_bots > current_count:
        # Find the highest bot number to continue from
        max_num = 0
        for name in current_bots:
            m = re.search(r'(\d+)$', name)
            if m:
                max_num = max(max_num, int(m.group(1)))
        max_num = max(max_num, current_count)

        added = add_bots_to_config(max_num, max_num + (num_bots - current_count))
        load_config(reload=True)
        return {
            "status": "ok",
            "message": f"Added {len(added)} bot(s). Now at {num_bots}.",
            "bots_added": added,
            "bot_count": num_bots,
        }

    # --- Decreasing: check holdings, then remove ---
    # Sort bots by number, keep lowest, remove highest
    def _sort_key(name):
        m = re.search(r'(\d+)$', name)
        return int(m.group(1)) if m else float('inf')

    sorted_bots = sorted(current_bots, key=_sort_key)
    bots_to_keep = sorted_bots[:num_bots]
    bots_to_remove = sorted_bots[num_bots:]

    if not force:
        # Quick check: only inspect bots that have cached sessions
        # (bots without sessions were never funded)
        cache_dir = Path(".cache")
        bots_to_check = []
        for name in bots_to_remove:
            safe = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
            if (cache_dir / f"session_{safe}.json").exists():
                bots_to_check.append(name)

        if bots_to_check:
            from iconfucius.cli.balance import collect_balances
            from iconfucius.cli.concurrent import run_per_bot

            results = run_per_bot(
                lambda n: collect_balances(n, verbose=False),
                bots_to_check,
            )
            holdings = []
            for bot_name, result in results:
                if isinstance(result, Exception):
                    continue
                if result.odin_sats > 0 or result.token_holdings:
                    holdings.append({
                        "bot_name": result.bot_name,
                        "odin_sats": int(result.odin_sats),
                        "token_holdings": result.token_holdings,
                    })

            if holdings:
                return {
                    "status": "blocked",
                    "reason": "bots_have_holdings",
                    "bots_to_remove": bots_to_remove,
                    "holdings": holdings,
                    "message": (
                        "Some bots have holdings. "
                        "Sweep them first or confirm removal with force=true."
                    ),
                }

    remove_bots_from_config(bots_to_remove)
    load_config(reload=True)
    return {
        "status": "ok",
        "bots_removed": bots_to_remove,
        "message": f"Removed {len(bots_to_remove)} bot(s). Now at {num_bots}.",
        "bot_count": num_bots,
    }


def _handle_wallet_create(args: dict) -> dict:
    from typer.testing import CliRunner
    from iconfucius.cli.wallet import wallet_app

    cmd = ["create"]
    if args.get("force"):
        cmd.append("--force")

    runner = CliRunner()
    result = runner.invoke(wallet_app, cmd)
    if result.exit_code != 0:
        return {"status": "error", "error": result.output.strip()}
    return {"status": "ok", "display": result.output.strip()}


# ---------------------------------------------------------------------------
# Read-only handlers
# ---------------------------------------------------------------------------

def _handle_bot_list(args: dict) -> dict:
    from iconfucius.config import find_config, get_bot_names

    if not find_config():
        return {"status": "error", "error": "No iconfucius.toml found. Run init first."}

    bot_names = get_bot_names()
    names_str = ", ".join(bot_names)
    display = f"{len(bot_names)} bot(s): {names_str}"

    return {
        "status": "ok",
        "display": display,
        "bot_names": bot_names,
        "bot_count": len(bot_names),
    }


def _handle_wallet_balance(args: dict) -> dict:
    from iconfucius.config import (
        MIN_DEPOSIT_SATS,
        MIN_TRADE_SATS,
        get_bot_names,
        require_wallet,
    )

    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    bot_name = args.get("bot_name")
    ckbtc_minter = args.get("ckbtc_minter", False)

    from iconfucius.cli.balance import run_all_balances

    names = [bot_name] if bot_name else get_bot_names()
    data = run_all_balances(names, ckbtc_minter=ckbtc_minter)

    if data is None:
        return {"status": "error", "error": "Balance check failed."}

    display_text = data.pop("_display", "")
    totals = data.get("totals", {})

    result = {
        "status": "ok",
        "wallet_ckbtc_sats": data.get("wallet_ckbtc_sats", 0),
        "total_odin_sats": totals.get("odin_sats", 0),
        "total_token_value_sats": totals.get("token_value_sats", 0),
        "portfolio_sats": totals.get("portfolio_sats", 0),
        "constraints": {
            "min_deposit_sats": MIN_DEPOSIT_SATS,
            "min_trade_sats": MIN_TRADE_SATS,
        },
    }
    # Include per-bot balances so the AI doesn't need individual balance calls
    bots_list = data.get("bots", [])
    if bots_list:
        result["bots"] = [
            {
                "name": bot["name"],
                "principal": bot.get("principal", ""),
                "odin_sats": bot.get("odin_sats", 0),
                "tokens": bot.get("tokens", []),
                "has_odin_account": bot.get("has_odin_account", False),
            }
            for bot in bots_list
        ]
    return result


def _handle_how_to_fund_wallet(args: dict) -> dict:
    from iconfucius.config import require_wallet

    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    from icp_agent import Agent, Client
    from icp_identity import Identity

    from iconfucius.config import IC_HOST, fmt_sats, get_btc_to_usd_rate, get_pem_file
    from iconfucius.transfers import (
        create_ckbtc_minter,
        create_icrc1_canister,
        get_balance,
        get_btc_address,
    )

    pem_path = get_pem_file()
    with open(pem_path, "r") as f:
        pem_content = f.read()
    identity = Identity.from_pem(pem_content)
    principal = str(identity.sender())

    client = Client(url=IC_HOST)
    anon_agent = Agent(Identity(anonymous=True), client)
    minter = create_ckbtc_minter(anon_agent)
    btc_address = get_btc_address(minter, principal)

    icrc1 = create_icrc1_canister(anon_agent)
    balance = get_balance(icrc1, principal)

    try:
        rate = get_btc_to_usd_rate()
    except Exception:
        rate = None

    balance_str = fmt_sats(balance, rate)
    min_deposit = fmt_sats(10_000, rate)
    display = (
        f"Wallet balance: {balance_str}\n"
        f"\n"
        f"Option 1: Send BTC from any Bitcoin wallet\n"
        f"  {btc_address}\n"
        f"  Min deposit: {min_deposit}.\n"
        f"  BTC is converted to ckBTC via the ckBTC minter.\n"
        f"  Requires ~6 Bitcoin confirmations (~1 hour).\n"
        f"  Use wallet_monitor to track the conversion progress.\n"
        f"\n"
        f"Option 2: Send ckBTC from any ckBTC wallet\n"
        f"  {principal}\n"
        f"  Send from NNS, Plug, Oisy, or any ckBTC wallet.\n"
        f"  Arrives instantly, no conversion needed.\n"
        f"\n"
        f"After funding, distribute to bots with the fund tool."
    )

    return {
        "status": "ok",
        "display": display,
        "wallet_principal": principal,
        "btc_deposit_address": btc_address,
        "ckbtc_balance_sats": balance,
    }



def _handle_wallet_monitor(args: dict) -> dict:
    from iconfucius.config import require_wallet

    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    from iconfucius.cli.balance import run_wallet_balance

    data = run_wallet_balance(ckbtc_minter=True)
    if data is None:
        return {"status": "error", "error": "Wallet balance check failed."}

    display_text = data.pop("_display", "")
    return {"status": "ok", "display": display_text.strip()}


def _handle_security_status(args: dict) -> dict:
    from iconfucius.config import find_config, get_cache_sessions, load_config

    config_path = find_config()

    # Check blst availability
    try:
        import blst  # noqa: F401
        blst_installed = True
    except (ImportError, ModuleNotFoundError):
        blst_installed = False

    # Check verify_certificates setting
    verify_certs = False
    if config_path:
        config = load_config()
        verify_certs = config.get("settings", {}).get(
            "verify_certificates", False
        )

    # Check session caching setting
    cache_sessions = get_cache_sessions() if config_path else True

    lines = ["Security status:"]
    # blst / certificate verification
    if blst_installed and verify_certs:
        lines.append("  IC certificate verification: enabled (blst installed)")
    elif blst_installed and not verify_certs:
        lines.append(
            "  IC certificate verification: disabled "
            "(blst installed — enable with verify_certificates = true)"
        )
    else:
        lines.append(
            "  IC certificate verification: disabled "
            "(blst not installed — use install_blst to enable)"
        )

    # Session caching
    if cache_sessions:
        lines.append(
            "  Session caching: enabled "
            "(sessions stored in .cache/ with 0600 permissions)"
        )
    else:
        lines.append(
            "  Session caching: disabled (fresh SIWB login every command)"
        )

    # Recommendations
    recs = []
    if not blst_installed:
        recs.append(
            "Install blst for IC certificate verification "
            "(protects balance checks and address lookups)"
        )
    elif not verify_certs:
        recs.append(
            "Enable verify_certificates = true in iconfucius.toml "
            "(blst is already installed)"
        )

    if recs:
        lines.append("")
        lines.append("Recommendations:")
        for r in recs:
            lines.append(f"  - {r}")

    return {
        "status": "ok",
        "display": "\n".join(lines),
        "blst_installed": blst_installed,
        "verify_certificates": verify_certs,
        "cache_sessions": cache_sessions,
    }


def _enable_verify_certificates() -> dict:
    """Enable verify_certificates = true in iconfucius.toml.

    Returns {"enabled_now": True} if it changed the setting,
    {"enabled_now": False} if already enabled or no config found.
    """
    from iconfucius.config import find_config

    config_path = find_config()
    if not config_path:
        return {"enabled_now": False}

    content = Path(config_path).read_text()
    if "verify_certificates = true" in content:
        return {"enabled_now": False}

    if "verify_certificates = false" in content:
        content = content.replace(
            "verify_certificates = false",
            "verify_certificates = true",
        )
    elif "verify_certificates" not in content:
        if "[settings]" in content:
            content = content.replace(
                "[settings]",
                "[settings]\nverify_certificates = true",
            )
        else:
            content += "\n[settings]\nverify_certificates = true\n"
    else:
        return {"enabled_now": False}

    Path(config_path).write_text(content)
    return {"enabled_now": True}


def _handle_install_blst(args: dict) -> dict:
    import platform
    import shutil
    import subprocess
    import tempfile

    # Check if already installed
    blst_already = False
    try:
        import blst  # noqa: F401
        blst_already = True
    except (ImportError, ModuleNotFoundError):
        pass

    if blst_already:
        # Still ensure verify_certificates is enabled in config
        result = _enable_verify_certificates()
        if result["enabled_now"]:
            return {
                "status": "ok",
                "display": (
                    "blst is already installed.\n"
                    "Enabled verify_certificates = true in iconfucius.toml."
                ),
            }
        return {
            "status": "ok",
            "display": (
                "blst is already installed and "
                "verify_certificates is already enabled."
            ),
        }

    # Check prerequisites
    missing = []
    if not shutil.which("git"):
        missing.append("git")
    if not shutil.which("swig"):
        missing.append("swig")

    # Check for C compiler
    has_cc = bool(
        shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    )
    if not has_cc:
        missing.append("C compiler (gcc/clang)")

    if missing:
        system = platform.system()
        lines = [
            f"Missing prerequisites: {', '.join(missing)}",
            "",
            "Install them first:",
        ]
        if system == "Darwin":
            if "C compiler" in " ".join(missing):
                lines.append("  xcode-select --install")
            if "swig" in missing:
                lines.append("  brew install swig")
        else:
            # Linux
            if shutil.which("apt-get"):
                lines.append(
                    "  sudo apt-get install build-essential swig python3-dev"
                )
            elif shutil.which("dnf"):
                lines.append(
                    "  sudo dnf install gcc gcc-c++ make swig python3-devel"
                )
            else:
                lines.append(
                    "  Install: C compiler, make, swig, python3 headers"
                )
        lines.append("")
        lines.append("Then run install_blst again.")
        return {"status": "error", "error": "\n".join(lines)}

    # Build and install blst from source
    blst_version = "v0.3.16"
    blst_commit = "e7f90de551e8df682f3cc99067d204d8b90d27ad"

    blst_dir = tempfile.mkdtemp(prefix="blst_")
    try:
        # Clone
        subprocess.run(
            ["git", "clone", "--branch", blst_version, "--depth", "1",
             "https://github.com/supranational/blst", blst_dir],
            check=True, capture_output=True, text=True,
        )

        # Verify commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=blst_dir, capture_output=True, text=True, check=True,
        )
        actual_commit = result.stdout.strip()
        if actual_commit != blst_commit:
            return {
                "status": "error",
                "error": (
                    f"Commit mismatch! Expected {blst_commit}, "
                    f"got {actual_commit}. Aborting for safety."
                ),
            }

        # Build Python bindings
        bindings_dir = os.path.join(blst_dir, "bindings", "python")
        env = os.environ.copy()
        if platform.machine().startswith("arm") or platform.machine() == "aarch64":
            env["BLST_PORTABLE"] = "1"
        subprocess.run(
            ["python3", "run.me"],
            cwd=bindings_dir, env=env,
            capture_output=True, text=True,
        )

        # Find install paths
        import sysconfig
        purelib = sysconfig.get_paths()["purelib"]
        platlib = sysconfig.get_paths()["platlib"]

        # Copy built files
        import glob as _glob
        blst_py = os.path.join(bindings_dir, "blst.py")
        if not os.path.exists(blst_py):
            return {
                "status": "error",
                "error": "Build failed — blst.py not found after build.",
            }
        shutil.copy2(blst_py, purelib)

        so_files = _glob.glob(os.path.join(bindings_dir, "_blst*.so"))
        if not so_files:
            return {
                "status": "error",
                "error": "Build failed — _blst*.so not found after build.",
            }
        for so in so_files:
            shutil.copy2(so, platlib)

    finally:
        shutil.rmtree(blst_dir, ignore_errors=True)

    # Verify installation
    try:
        # Clear any cached import failures
        import importlib
        if "blst" in __import__("sys").modules:
            del __import__("sys").modules["blst"]
        importlib.import_module("blst")
    except (ImportError, ModuleNotFoundError):
        return {
            "status": "error",
            "error": "blst was built but could not be imported. Check build output.",
        }

    # Enable verify_certificates in config
    result = _enable_verify_certificates()

    from iconfucius.config import find_config
    config_path = find_config()

    lines = ["blst installed successfully!"]
    lines.append("IC certificate verification is now available.")
    if result["enabled_now"]:
        lines.append("Enabled verify_certificates = true in iconfucius.toml.")
    elif config_path:
        lines.append("verify_certificates is already enabled in iconfucius.toml.")
    else:
        lines.append(
            "Run init first, then set verify_certificates = true "
            "in iconfucius.toml."
        )

    return {"status": "ok", "display": "\n".join(lines)}


def _handle_account_lookup(args: dict) -> dict:
    from iconfucius.accounts import lookup_odin_account

    address = args.get("address", "")
    if not address:
        return {"status": "error", "error": "Address is required."}

    account = lookup_odin_account(address)
    if not account:
        return {
            "status": "ok",
            "found": False,
            "display": f"No Odin.fun account found for '{address}'.",
        }

    principal = account.get("principal", "")
    username = account.get("username") or "(no username)"
    lines = [
        f"Odin.fun account: {username}",
        f"  Principal:          {principal}",
    ]
    if account.get("btc_wallet_address"):
        lines.append(f"  BTC wallet:         {account['btc_wallet_address']}")
    if account.get("btc_deposit_address"):
        lines.append(f"  BTC deposit:        {account['btc_deposit_address']}")
    if account.get("bio"):
        lines.append(f"  Bio:                {account['bio']}")
    if account.get("follower_count") is not None:
        lines.append(f"  Followers:          {account['follower_count']:,}")
    if account.get("following_count") is not None:
        lines.append(f"  Following:          {account['following_count']:,}")

    return {
        "status": "ok",
        "found": True,
        "display": "\n".join(lines),
        **account,
    }



def _handle_token_lookup(args: dict) -> dict:
    from iconfucius.tokens import search_token

    query = args.get("query", "")
    if not query:
        return {"status": "error", "error": "Query is required."}

    result = search_token(query)
    search_results = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "ticker": r.get("ticker"),
            "bonded": r.get("bonded"),
            "twitter_verified": r.get("twitter_verified"),
            "holder_count": r.get("holder_count"),
            "volume": r.get("volume"),
            "safety": r.get("safety"),
        }
        for r in result["search_results"]
    ]

    # Build display
    lines = [f"Token search: {query}"]
    km = result["known_match"]
    if km:
        flags = []
        if km.get("bonded"):
            flags.append("bonded")
        if km.get("twitter_verified"):
            flags.append("Twitter verified")
        flags_str = ", ".join(flags) if flags else "unverified"
        holders = km.get("holder_count")
        holder_str = f", {holders:,} holders" if holders else ""
        lines.append(
            f"Known match: {km.get('name')} ({km.get('id')}) "
            f"— {flags_str}{holder_str}"
        )
    if not km and search_results:
        # Only show search results when there's no known match
        lines.append("Search results:")
        for r in search_results:
            lines.append(f"  {r.get('name')} ({r.get('id')}) — {r.get('safety', '')}")
    elif not km and not search_results:
        lines.append("No results found.")

    return {
        "status": "ok",
        "display": "\n".join(lines),
        "query": query,
        "known_match": km,
        "search_results": search_results,
    }


def _handle_token_discover(args: dict) -> dict:
    from iconfucius.config import fmt_sats, get_btc_to_usd_rate
    from iconfucius.tokens import discover_tokens

    sort = args.get("sort", "volume")
    limit = args.get("limit", 20)

    tokens = discover_tokens(sort=sort, limit=limit)

    if not tokens:
        return {"status": "ok", "display": "No tokens found.", "tokens": [], "sort": sort, "count": 0}

    try:
        btc_usd = get_btc_to_usd_rate()
    except Exception:
        btc_usd = None

    label = "trending (by 24h volume)" if sort == "volume" else "newest"
    lines = [f"Top {len(tokens)} {label} bonded tokens on Odin.fun:"]
    lines.append("")
    for i, t in enumerate(tokens, 1):
        mcap_str = fmt_sats(t["marketcap_sats"], btc_usd)
        vol_str = fmt_sats(t["volume_24h_sats"], btc_usd)
        lines.append(
            f"{i:>2}. {t['name']} ({t['ticker']}) — {t['id']}"
        )
        lines.append(
            f"    Price: {t['price_sats']:,.3f} sats | "
            f"MCap: {mcap_str} | "
            f"Vol 24h: {vol_str} | "
            f"Holders: {t['holder_count']:,}"
        )
        lines.append(f"    {t['safety']}")

    return {
        "status": "ok",
        "display": "\n".join(lines),
        "tokens": tokens,
        "sort": sort,
        "count": len(tokens),
    }


def _handle_token_price(args: dict) -> dict:
    from iconfucius.config import fmt_sats, get_btc_to_usd_rate
    from iconfucius.tokens import fetch_token_data, lookup_token_with_fallback

    query = args.get("query", "")
    if not query:
        return {"status": "error", "error": "Query is required."}

    token = lookup_token_with_fallback(query)
    if not token:
        return {"status": "error", "error": f"Token not found: {query}"}

    token_id = token["id"]
    token_name = token.get("name", token_id)
    token_ticker = token.get("ticker", "")

    data = fetch_token_data(token_id)
    if not data:
        return {
            "status": "error",
            "error": f"Could not fetch price data for {token_name} ({token_id}).",
        }

    # API returns BTC-denominated fields in millisatoshis (msat)
    MSAT_PER_SAT = 1000
    price_msat = data.get("price", 0)
    price_1h_msat = data.get("price_1h", 0)
    price_6h_msat = data.get("price_6h", 0)
    price_1d_msat = data.get("price_1d", 0)
    marketcap_sats = data.get("marketcap", 0) // MSAT_PER_SAT
    volume_24_sats = data.get("volume_24", 0) // MSAT_PER_SAT
    holder_count = data.get("holder_count", 0)
    btc_liquidity_sats = data.get("btc_liquidity", 0) // MSAT_PER_SAT

    # Price: API gives msat per token, convert to sats
    price_sats = price_msat / MSAT_PER_SAT

    def _pct_change(current: int, previous: int) -> str:
        if not previous or not current:
            return "n/a"
        pct = ((current - previous) / previous) * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    try:
        btc_usd = get_btc_to_usd_rate()
    except Exception:
        btc_usd = None

    # Format price with appropriate precision (can be fractional sats)
    if btc_usd:
        price_usd = (price_sats / 100_000_000) * btc_usd
        price_str = f"{price_sats:,.3f} sats (${price_usd:.5f})"
    else:
        price_str = f"{price_sats:,.3f} sats"

    lines = [
        f"{token_name} ({token_ticker}) — {token_id}",
        f"Price:        {price_str} per token",
        f"Change 1h:    {_pct_change(price_msat, price_1h_msat)}",
        f"Change 6h:    {_pct_change(price_msat, price_6h_msat)}",
        f"Change 24h:   {_pct_change(price_msat, price_1d_msat)}",
        f"Market cap:   {fmt_sats(marketcap_sats, btc_usd)}",
        f"24h volume:   {fmt_sats(volume_24_sats, btc_usd)}",
        f"Liquidity:    {fmt_sats(btc_liquidity_sats, btc_usd)}",
        f"Holders:      {holder_count:,}",
        f"Supply:       21,000,000 (21M)",
    ]

    return {
        "status": "ok",
        "display": "\n".join(lines),
        "token_id": token_id,
        "token_name": token_name,
        "ticker": token_ticker,
        "price_sats": price_sats,
        "price_usd": (price_sats / 100_000_000) * btc_usd if btc_usd else None,
        "change_1h": _pct_change(price_msat, price_1h_msat),
        "change_6h": _pct_change(price_msat, price_6h_msat),
        "change_24h": _pct_change(price_msat, price_1d_msat),
        "marketcap_sats": marketcap_sats,
        "volume_24h_sats": volume_24_sats,
        "holder_count": holder_count,
        "total_supply": 21_000_000,
    }


# ---------------------------------------------------------------------------
# State-changing handlers
# ---------------------------------------------------------------------------

def _resolve_bot_names(args: dict) -> list[str]:
    """Resolve bot_name / bot_names / all_bots args into a list of bot names."""
    if args.get("all_bots"):
        from iconfucius.config import get_bot_names
        return get_bot_names()
    names = args.get("bot_names")
    if names:
        return list(names)
    bot_name = args.get("bot_name")
    if bot_name:
        return [bot_name]
    return []


def _handle_fund(args: dict) -> dict:
    from iconfucius.config import require_wallet

    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    amount = args.get("amount")
    amount_usd = args.get("amount_usd")
    bot_names = _resolve_bot_names(args)

    # Convert USD to sats if needed
    if amount_usd is not None and not amount:
        try:
            amount = _usd_to_sats(amount_usd)
        except Exception as e:
            return {"status": "error", "error": f"USD conversion failed: {e}"}

    if not amount or not bot_names:
        return {"status": "error", "error": "'amount' (or 'amount_usd') and at least one bot are required."}

    from iconfucius.cli.fund import run_fund

    result = run_fund(bot_names, int(amount))

    if result["status"] == "error":
        return result

    # Build display from structured result
    funded = result.get("funded", [])
    failed = result.get("failed", [])
    lines = []
    if funded:
        from iconfucius.config import fmt_sats, get_btc_to_usd_rate
        try:
            rate = get_btc_to_usd_rate()
        except Exception:
            rate = None
        suffix = " each" if len(funded) > 1 else ""
        lines.append(f"Funded {len(funded)} bot(s) with {fmt_sats(result['amount'], rate)}{suffix}")
    for f in failed:
        lines.append(f"  {f['bot']}: FAILED — {f['error']}")
    display = "\n".join(lines) if lines else "No bots funded"

    return {
        "status": result["status"],
        "display": display,
        "funded": len(funded),
        "failed": len(failed),
        "details": result.get("details", []),
        "notes": result.get("notes", []),
    }


def _usd_to_sats(amount_usd: float) -> int:
    """Convert a USD amount to satoshis using the live BTC/USD rate."""
    from iconfucius.config import get_btc_to_usd_rate

    btc_usd = get_btc_to_usd_rate()
    return int((amount_usd / btc_usd) * 100_000_000)


_MAX_RAW_TOKENS = 2**63  # guard against bogus price data


def _tokens_to_subunits(amount: float, token_id: str) -> int:
    """Convert human-readable token count to raw sub-units.

    Example: 1000.0 tokens with divisibility=8 → 100_000_000_000
    """
    from iconfucius.tokens import fetch_token_data

    data = fetch_token_data(token_id)
    divisibility = data.get("divisibility", 8) if data else 8
    return int(amount * (10 ** divisibility))


def _usd_to_tokens(amount_usd: float, token_id: str) -> int:
    """Convert a USD amount to raw token sub-units using live price data.

    Returns the raw token amount (not display tokens).
    Formula: raw_tokens = sats * 10^6 * 10^div / price
    """
    from iconfucius.tokens import fetch_token_data

    data = fetch_token_data(token_id)
    if not data or not data.get("price"):
        raise ValueError(f"Could not fetch price for token {token_id}")

    sats = _usd_to_sats(amount_usd)
    price = data["price"]
    divisibility = data.get("divisibility", 8)
    raw_tokens = int(sats * 1_000_000 * (10 ** divisibility) / price)

    if raw_tokens > _MAX_RAW_TOKENS:
        raise ValueError(
            f"Token amount too large ({raw_tokens}). "
            f"Token price ({price}) may be stale or incorrect."
        )
    return raw_tokens


def _handle_trade_buy(args: dict) -> dict:
    from iconfucius.config import require_wallet

    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    token_id = args.get("token_id")
    amount = args.get("amount")
    amount_usd = args.get("amount_usd")
    bot_names = _resolve_bot_names(args)

    # Convert USD to sats if needed
    if amount_usd is not None and not amount:
        try:
            amount = _usd_to_sats(amount_usd)
            args["amount"] = amount  # write back for _record_trade
        except Exception as e:
            return {"status": "error", "error": f"USD conversion failed: {e}"}

    if not all([token_id, amount, bot_names]):
        return {"status": "error", "error": "'token_id', 'amount' (or 'amount_usd'), and at least one bot are required."}

    from iconfucius.cli.concurrent import report_status, run_per_bot
    from iconfucius.cli.trade import run_trade

    report_status(f"buying {token_id} for {len(bot_names)} bot(s)...")
    results = run_per_bot(
        lambda name: run_trade(name, "buy", token_id, str(amount)),
        bot_names,
    )
    return _aggregate_trade_results(results, "buy", token_id)


def _handle_trade_sell(args: dict) -> dict:
    from iconfucius.config import require_wallet

    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    token_id = args.get("token_id")
    amount = args.get("amount")
    amount_usd = args.get("amount_usd")
    bot_names = _resolve_bot_names(args)

    # Convert USD to raw token amount if needed (already returns sub-units)
    amount_is_subunits = False
    if amount_usd is not None and not amount:
        try:
            amount = _usd_to_tokens(amount_usd, token_id)
            amount_is_subunits = True
            args["amount"] = amount  # write back for _record_trade
        except Exception as e:
            return {"status": "error", "error": f"USD conversion failed: {e}"}

    if not all([token_id, amount, bot_names]):
        return {"status": "error", "error": "'token_id', 'amount' (or 'amount_usd'), and at least one bot are required."}

    # Convert human-readable token count to raw sub-units for the canister
    if not amount_is_subunits and str(amount).lower() != "all":
        amount = _tokens_to_subunits(float(amount), token_id)

    from iconfucius.cli.concurrent import report_status, run_per_bot
    from iconfucius.cli.trade import run_trade

    report_status(f"selling {token_id} for {len(bot_names)} bot(s)...")
    results = run_per_bot(
        lambda name: run_trade(name, "sell", token_id, str(amount)),
        bot_names,
    )
    return _aggregate_trade_results(results, "sell", token_id)


def _aggregate_trade_results(results: list, action: str, token_id: str) -> dict:
    """Aggregate per-bot trade results into a single structured response."""
    succeeded, failed, skipped = [], [], []
    for bot_name, result in results:
        if isinstance(result, Exception):
            failed.append({"bot": bot_name, "error": str(result)})
        elif isinstance(result, dict) and result.get("status") == "skipped":
            skipped.append({"bot": bot_name, "reason": result.get("reason", "")})
        elif isinstance(result, dict) and result.get("status") == "error":
            failed.append({"bot": bot_name, "error": result.get("error", "")})
        elif isinstance(result, dict) and result.get("status") == "ok":
            succeeded.append({"bot": bot_name, **result})
        else:
            failed.append({"bot": bot_name, "error": f"Unexpected result: {result}"})

    # Build terminal summary for the user watching the chat
    verb = "Bought" if action == "buy" else "Sold"
    lines = []
    if succeeded:
        lines.append(f"{verb} {token_id} from {len(succeeded)} bot(s)")
    for s in skipped:
        lines.append(f"  {s['bot']}: skipped — {s['reason']}")
    for f in failed:
        lines.append(f"  {f['bot']}: FAILED — {f['error']}")
    display = "\n".join(lines) if lines else "No trades executed"

    # Collect per-bot details and notes for the AI
    details = []
    notes = []
    for s in succeeded:
        details.append({"bot": s["bot"], "amount": s.get("amount")})
        if s.get("note"):
            notes.append(s["note"])

    all_ok = not failed
    return {
        "status": "ok" if all_ok else "partial",
        "display": display,
        "succeeded": len(succeeded),
        "failed": len(failed),
        "skipped": len(skipped),
        "details": details,
        "notes": notes,
    }


def _handle_withdraw(args: dict) -> dict:
    from iconfucius.config import require_wallet

    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    amount = args.get("amount")
    amount_usd = args.get("amount_usd")
    bot_names = _resolve_bot_names(args)

    # Convert USD to sats if needed
    if amount_usd is not None and not amount:
        try:
            amount = str(_usd_to_sats(amount_usd))
        except Exception as e:
            return {"status": "error", "error": f"USD conversion failed: {e}"}

    if not amount or not bot_names:
        return {"status": "error", "error": "'amount' (or 'amount_usd') and at least one bot are required."}

    from iconfucius.cli.concurrent import report_status, run_per_bot
    from iconfucius.cli.withdraw import run_withdraw

    report_status(f"withdrawing from {len(bot_names)} bot(s)...")
    results = run_per_bot(
        lambda name: run_withdraw(name, str(amount)),
        bot_names,
    )

    succeeded, failed = [], []
    for bot_name, result in results:
        if isinstance(result, Exception):
            failed.append({"bot": bot_name, "error": str(result)})
        elif isinstance(result, dict) and result.get("status") == "error":
            failed.append({"bot": bot_name, "error": result.get("error", "")})
        elif isinstance(result, dict) and result.get("status") == "partial":
            failed.append({"bot": bot_name, "error": result.get("error", "partial")})
        elif isinstance(result, dict) and result.get("status") == "ok":
            succeeded.append({"bot": bot_name, **result})
        else:
            failed.append({"bot": bot_name, "error": f"Unexpected result: {result}"})

    lines = []
    if succeeded:
        lines.append(f"Withdrew from {len(succeeded)} bot(s)")
    for f in failed:
        lines.append(f"  {f['bot']}: FAILED — {f['error']}")
    display = "\n".join(lines) if lines else "No withdrawals executed"

    all_ok = not failed
    resp: dict = {
        "status": "ok" if all_ok else "partial",
        "display": display,
        "succeeded": len(succeeded),
        "failed": len(failed),
    }

    # Include updated wallet balance so the AI knows how much is available
    try:
        from iconfucius.config import get_btc_to_usd_rate, fmt_sats
        from iconfucius.transfers import create_icrc1_canister, get_balance, IC_HOST
        from icp_agent import Agent, Client
        from icp_identity import Identity

        client = Client(url=IC_HOST)
        anon_agent = Agent(Identity(anonymous=True), client)
        canister = create_icrc1_canister(anon_agent)
        identity = Identity.from_pem_file(
            str(require_wallet())
        )
        wallet_sats = get_balance(canister, str(identity.sender()))
        try:
            rate = get_btc_to_usd_rate()
        except Exception:
            rate = None
        resp["wallet_balance_sats"] = wallet_sats
        resp["wallet_balance_display"] = fmt_sats(wallet_sats, rate)
    except Exception:
        pass  # best-effort

    return resp


def _handle_token_transfer(args: dict) -> dict:
    from iconfucius.config import require_wallet

    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    token_id = args.get("token_id")
    amount = args.get("amount")
    to_address = args.get("to_address")
    bot_names = _resolve_bot_names(args)

    if not all([token_id, amount, to_address, bot_names]):
        return {
            "status": "error",
            "error": "token_id, amount, to_address, and at least one bot are required.",
        }

    # Convert human-readable token count to raw sub-units for the canister
    if str(amount).lower() != "all":
        amount = _tokens_to_subunits(float(amount), token_id)

    from iconfucius.cli.concurrent import report_status, run_per_bot
    from iconfucius.cli.transfer import run_transfer

    report_status(f"transferring {token_id} from {len(bot_names)} bot(s)...")
    results = run_per_bot(
        lambda name: run_transfer(name, token_id, str(amount), to_address),
        bot_names,
    )

    succeeded, failed = [], []
    for bot_name, result in results:
        if isinstance(result, Exception):
            failed.append({"bot": bot_name, "error": str(result)})
        elif isinstance(result, dict) and result.get("status") == "error":
            failed.append({"bot": bot_name, "error": result.get("error", "")})
        elif isinstance(result, dict) and result.get("status") == "ok":
            succeeded.append({"bot": bot_name, **result})
        else:
            failed.append({"bot": bot_name, "error": f"Unexpected result: {result}"})

    lines = []
    if succeeded:
        lines.append(f"Transferred {token_id} from {len(succeeded)} bot(s)")
    for f in failed:
        lines.append(f"  {f['bot']}: FAILED — {f['error']}")
    display = "\n".join(lines) if lines else "No transfers executed"

    all_ok = not failed
    return {
        "status": "ok" if all_ok else "partial",
        "display": display,
        "succeeded": len(succeeded),
        "failed": len(failed),
    }


def _handle_wallet_send(args: dict) -> dict:
    from iconfucius.config import require_wallet

    if not require_wallet():
        return {"status": "error", "error": "No wallet found. Run: iconfucius wallet create"}

    amount = args.get("amount")
    amount_usd = args.get("amount_usd")
    address = args.get("address")

    # Convert USD to sats if needed
    if amount_usd is not None and not amount:
        try:
            amount = str(_usd_to_sats(amount_usd))
        except Exception as e:
            return {"status": "error", "error": f"USD conversion failed: {e}"}

    if not amount or not address:
        return {"status": "error", "error": "Both 'amount' (or 'amount_usd') and 'address' are required."}

    # Early validation: BTC address sends must meet the minimum
    is_btc_address = isinstance(address, str) and address.startswith("bc1")
    if is_btc_address and str(amount).lower() != "all":
        from iconfucius.config import MIN_BTC_WITHDRAWAL_SATS
        try:
            send_sats = int(amount)
        except (ValueError, TypeError):
            send_sats = 0
        if 0 < send_sats < MIN_BTC_WITHDRAWAL_SATS:
            # Fetch wallet balance so the AI can suggest the right amount
            wallet_sats = 0
            wallet_display = "unknown"
            try:
                from iconfucius.config import fmt_sats, get_btc_to_usd_rate
                from iconfucius.transfers import (
                    create_icrc1_canister, get_balance, IC_HOST,
                )
                from icp_agent import Agent, Client
                from icp_identity import Identity

                client = Client(url=IC_HOST)
                anon_agent = Agent(Identity(anonymous=True), client)
                canister = create_icrc1_canister(anon_agent)
                identity = Identity.from_pem_file(str(require_wallet()))
                wallet_sats = get_balance(canister, str(identity.sender()))
                try:
                    rate = get_btc_to_usd_rate()
                except Exception:
                    rate = None
                wallet_display = fmt_sats(wallet_sats, rate)
                min_display = fmt_sats(MIN_BTC_WITHDRAWAL_SATS, rate)
            except Exception:
                min_display = f"{MIN_BTC_WITHDRAWAL_SATS:,} sats"

            return {
                "status": "error",
                "error": (
                    f"BTC send amount too low: {send_sats:,} sats. "
                    f"Minimum for BTC address: {min_display}. "
                    f"Current wallet balance: {wallet_display}. "
                    f"Retry with amount={MIN_BTC_WITHDRAWAL_SATS} or amount='all'."
                ),
                "wallet_balance_sats": wallet_sats,
                "minimum_sats": MIN_BTC_WITHDRAWAL_SATS,
            }

    # wallet send uses typer.Exit for errors, so we need to catch it
    import typer

    try:
        from iconfucius.cli.wallet import send
        # Invoke via the underlying Click command
        from typer.testing import CliRunner
        from iconfucius.cli.wallet import wallet_app

        runner = CliRunner()
        result = runner.invoke(wallet_app, ["send", str(amount), address])
        if result.exit_code != 0:
            return {"status": "error", "error": result.output.strip()}
        # Strip CLI-specific hints — the AI has wallet_monitor for this
        display = result.output.strip()
        display = display.replace(
            "Check progress with: iconfucius wallet balance --monitor",
            "",
        ).strip()
        resp = {"status": "ok", "display": display}
        if "BTC withdrawal" in display:
            resp["hint"] = "Use wallet_monitor to check withdrawal progress."
        return resp
    except typer.Exit:
        return {"status": "error", "error": "Command failed."}


# ---------------------------------------------------------------------------
# Trade recording
# ---------------------------------------------------------------------------

def _record_trade(tool_name: str, args: dict, result: dict,
                  persona_name: str) -> None:
    """Record a completed trade to memory. Best-effort — never raises."""
    from datetime import datetime, timezone

    from iconfucius.memory import append_trade

    action = "BUY" if tool_name == "trade_buy" else "SELL"
    token_id = args.get("token_id", "?")

    # Prefer actual amount from result details (may be capped by run_trade)
    details = result.get("details", [])
    if details and details[0].get("amount") is not None:
        amount = details[0]["amount"]
    else:
        amount = args.get("amount", "?")
    bots = _resolve_bot_names(args)

    # Fetch live price and BTC/USD rate for enriched logging
    price = 0
    ticker = token_id
    btc_usd = None
    try:
        from iconfucius.tokens import fetch_token_data

        data = fetch_token_data(token_id)
        if data:
            price = data.get("price", 0)
            ticker = data.get("ticker", token_id)
    except Exception:
        pass
    try:
        from iconfucius.config import get_btc_to_usd_rate

        btc_usd = get_btc_to_usd_rate()
    except Exception:
        pass

    entry: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "token_id": token_id,
        "ticker": ticker,
    }

    is_sell_all = str(amount).lower() == "all"
    if action == "BUY":
        amount_int = 0 if is_sell_all else int(float(amount)) if amount else 0
        entry["amount_sats"] = amount_int
        if price:
            entry["est_tokens"] = round(amount_int * 1_000_000 / price, 2)
    elif is_sell_all:
        entry["tokens_sold"] = "all"
    else:
        display_tokens = float(amount) if amount else 0.0
        entry["tokens_sold"] = display_tokens
        if price:
            entry["est_sats_received"] = round(display_tokens * price / 1_000_000)

    if price:
        entry["price_sats"] = price
    if btc_usd:
        entry["btc_usd_rate"] = btc_usd
    entry["bots"] = bots if bots else ["?"]

    try:
        append_trade(persona_name, entry)
    except Exception:
        pass  # best-effort


# ---------------------------------------------------------------------------
# Balance snapshot recording
# ---------------------------------------------------------------------------

def _record_balance_snapshot(result: dict, persona_name: str) -> None:
    """Record a portfolio balance snapshot. Best-effort — never raises."""
    from datetime import datetime, timezone

    from iconfucius.memory import append_balance_snapshot

    try:
        from iconfucius.config import get_btc_to_usd_rate
        btc_usd = get_btc_to_usd_rate()
    except Exception:
        btc_usd = None

    wallet_sats = result.get("wallet_ckbtc_sats", 0)
    odin_sats = result.get("total_odin_sats", 0)
    token_value_sats = result.get("total_token_value_sats", 0)
    portfolio_sats = result.get("portfolio_sats", 0)
    bot_count = len(result.get("bots", []))

    portfolio_usd = None
    if btc_usd:
        portfolio_usd = round((portfolio_sats / 100_000_000) * btc_usd, 2)

    snapshot = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "wallet_sats": wallet_sats,
        "odin_sats": odin_sats,
        "token_value_sats": token_value_sats,
        "portfolio_sats": portfolio_sats,
        "btc_usd_rate": btc_usd,
        "portfolio_usd": portfolio_usd,
        "bot_count": bot_count,
    }

    try:
        append_balance_snapshot(persona_name, snapshot)
    except Exception:
        pass  # best-effort


# ---------------------------------------------------------------------------
# Memory handlers
# ---------------------------------------------------------------------------

def _handle_memory_read_strategy(args: dict, *, persona_name: str = "") -> dict:
    from iconfucius.memory import read_strategy

    if not persona_name:
        return {"status": "error", "error": "No persona context available."}
    content = read_strategy(persona_name)
    if not content:
        return {"status": "ok", "display": "No strategy notes yet."}
    return {"status": "ok", "display": content}


def _handle_memory_read_learnings(args: dict, *, persona_name: str = "") -> dict:
    from iconfucius.memory import read_learnings

    if not persona_name:
        return {"status": "error", "error": "No persona context available."}
    content = read_learnings(persona_name)
    if not content:
        return {"status": "ok", "display": "No learnings recorded yet."}
    return {"status": "ok", "display": content}


def _handle_memory_read_trades(args: dict, *, persona_name: str = "") -> dict:
    from iconfucius.memory import read_trades

    if not persona_name:
        return {"status": "error", "error": "No persona context available."}
    last_n = args.get("last_n", 5)
    trades = read_trades(persona_name, last_n=last_n)
    if not trades:
        return {"status": "ok", "display": "No trades recorded yet.", "trades": [], "count": 0}
    return {"status": "ok", "trades": trades, "count": len(trades)}


def _handle_memory_read_balances(args: dict, *, persona_name: str = "") -> dict:
    from iconfucius.memory import read_balance_snapshots

    if not persona_name:
        return {"status": "error", "error": "No persona context available."}
    last_n = args.get("last_n", 50)
    snapshots = read_balance_snapshots(persona_name, last_n=last_n)
    if not snapshots:
        return {"status": "ok", "display": "No balance snapshots recorded yet.", "snapshots": []}
    return {"status": "ok", "snapshots": snapshots, "count": len(snapshots)}


def _handle_memory_archive_balances(args: dict, *, persona_name: str = "") -> dict:
    from iconfucius.memory import archive_balance_snapshots

    if not persona_name:
        return {"status": "error", "error": "No persona context available."}
    keep_days = args.get("keep_days", 90)
    count = archive_balance_snapshots(persona_name, keep_days=keep_days)
    if count == 0:
        return {"status": "ok", "display": "No old snapshots to archive.", "archived": 0}
    return {"status": "ok", "display": f"Archived {count} snapshot(s) older than {keep_days} days.", "archived": count}


def _handle_memory_update(args: dict, *, persona_name: str = "") -> dict:
    from iconfucius.memory import write_learnings, write_strategy

    if not persona_name:
        return {"status": "error", "error": "No persona context available."}

    file = args.get("file")
    content = args.get("content")
    if not file or not content:
        return {"status": "error", "error": "'file' and 'content' are required."}

    if file == "strategy":
        write_strategy(persona_name, content)
        return {"status": "ok", "display": "Strategy updated."}
    elif file == "learnings":
        write_learnings(persona_name, content)
        return {"status": "ok", "display": "Learnings updated."}
    else:
        return {"status": "error", "error": f"Unknown file: {file}. Use 'strategy' or 'learnings'."}


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, callable] = {
    "setup_status": _handle_setup_status,
    "check_update": _handle_check_update,
    "enable_experimental": _handle_enable_experimental,
    "init": _handle_init,
    "set_bot_count": _handle_set_bot_count,
    "bot_list": _handle_bot_list,
    "wallet_create": _handle_wallet_create,
    "wallet_balance": _handle_wallet_balance,
    "how_to_fund_wallet": _handle_how_to_fund_wallet,
    "wallet_monitor": _handle_wallet_monitor,
    "security_status": _handle_security_status,
    "install_blst": _handle_install_blst,
    "account_lookup": _handle_account_lookup,
    "token_lookup": _handle_token_lookup,
    "token_discover": _handle_token_discover,
    "token_price": _handle_token_price,
    "fund": _handle_fund,
    "trade_buy": _handle_trade_buy,
    "trade_sell": _handle_trade_sell,
    "withdraw": _handle_withdraw,
    "token_transfer": _handle_token_transfer,
    "wallet_send": _handle_wallet_send,
    "memory_read_strategy": _handle_memory_read_strategy,
    "memory_read_learnings": _handle_memory_read_learnings,
    "memory_read_trades": _handle_memory_read_trades,
    "memory_read_balances": _handle_memory_read_balances,
    "memory_archive_balances": _handle_memory_archive_balances,
    "memory_update": _handle_memory_update,
}
