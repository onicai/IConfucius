"""
iconfucius CLI — Unified command-line interface for Odin.Fun trading
"""

import sys
from pathlib import Path
from typing import Optional

import typer

from iconfucius import __version__
from iconfucius.config import (
    CONFIG_FILENAME,
    PEM_FILE,
    create_default_config,
    find_config,
    fmt_sats,
    get_bot_names,
    get_btc_to_usd_rate,
    get_cksigner_canister_id,
    get_network,
    load_config,
    set_network,
)

def _fmt_sats(sats) -> str:
    """Format sats with USD for CLI output. Gracefully degrades."""
    try:
        rate = get_btc_to_usd_rate()
    except Exception:
        rate = None
    return fmt_sats(int(sats), rate)


# ---------------------------------------------------------------------------
# Instructions text (shared by --help, no-args, and 'instructions' command)
# ---------------------------------------------------------------------------

# Click's \b marker prevents paragraph rewrapping in --help
HELP_TEXT = """\
IConfucius | Wisdom for Bitcoin Markets

\b
Three modes:
  iconfucius                    Launch the local Web UI (default)
  iconfucius ui                 Same as above (explicit)
  iconfucius chat               Chat via terminal with IConfucius
  iconfucius chat --rasa        Chat via terminal using Rasa Pro CALM backend
  iconfucius <command>          Execute individual commands directly
\b
Direct commands:
  (Use when AI backend is unavailable)
  All ckBTC amounts are in sats (1 BTC = 100,000,000 sats).
\b
  Step 1. Fund your iconfucius wallet:
          iconfucius wallet receive
          Send ckBTC or BTC to the address shown.
          BTC deposits require min 10,000 sats and ~6 confirmations.
\b
  Step 2. Check your wallet balance:
          iconfucius wallet balance [--monitor]
\b
  Step 3. Fund your bots (deposit ckBTC into Odin.Fun):
          iconfucius fund <amount> --bot <name>          # in sats
          iconfucius fund <amount> --all-bots
\b
  Step 4. Buy Runes on Odin.Fun:
          iconfucius trade buy <token-id> <amount> --bot <name>   # in sats
          iconfucius trade buy <token-id> <amount> --all-bots
\b
  Step 5. Check your balances (wallet + bots):
          iconfucius wallet balance --all-bots [--monitor]
\b
  Step 6. Sell Runes on Odin.Fun:
          iconfucius trade sell <token-id> <amount> --bot <name>
          iconfucius trade sell <token-id> all --bot <name>
          iconfucius trade sell all-tokens all --all-bots
\b
  Step 7. Withdraw ckBTC from Odin.Fun back to wallet:
          iconfucius withdraw <amount> --bot <name>      # in sats
          iconfucius withdraw all --all-bots
\b
  Or use sweep to sell all tokens + withdraw in one command:
          iconfucius sweep --bot <name>
          iconfucius sweep --all-bots
\b
  Step 8. Transfer tokens between Odin.Fun accounts:
          iconfucius transfer <token-id> <amount> <address> --bot <name>
\b
  Step 9. Send ckBTC/BTC from wallet to an external account:
          iconfucius wallet send <amount> <address>      # in sats
          (<address> = ICRC-1 ckBTC address or native BTC address)
"""

INSTRUCTIONS_TEXT = """\

============================================================
How to use your bots
============================================================
All ckBTC amounts are in sats (1 BTC = 100,000,000 sats).

  Step 1. Fund your iconfucius wallet:
          iconfucius wallet receive
          Send ckBTC or BTC to the address shown.
          BTC deposits require min 10,000 sats and ~6 confirmations.

  Step 2. Check your wallet balance:
          iconfucius wallet balance [--monitor]

  Step 3. Fund your bots (deposit ckBTC into Odin.Fun):
          iconfucius fund <amount> --bot <bot-name>          # in sats
          iconfucius fund <amount> --all-bots

  Step 4. Buy Runes on Odin.Fun:
          iconfucius trade buy <token-id> <amount> --bot <bot-name>   # in sats
          iconfucius trade buy <token-id> <amount> --all-bots

  Step 5. Check your balances (wallet + bots):
          iconfucius wallet balance --all-bots [--monitor]

  Step 6. Sell Runes on Odin.Fun:
          iconfucius trade sell <token-id> <amount> --bot <bot-name>
          iconfucius trade sell <token-id> all --bot <bot-name>
          iconfucius trade sell all-tokens all --all-bots

  Step 7. Withdraw ckBTC from Odin.Fun back to wallet:
          iconfucius withdraw <amount> --bot <bot-name>      # in sats
          iconfucius withdraw all --all-bots

  Or use sweep to sell all tokens + withdraw in one command:
          iconfucius sweep --bot <bot-name>
          iconfucius sweep --all-bots

  Step 8. Transfer tokens between Odin.Fun accounts:
          iconfucius transfer <token-id> <amount> <address> --bot <bot-name>

  Step 9. Send ckBTC/BTC from wallet to an external account:
          iconfucius wallet send <amount> <address>          # in sats
          (<address> = ICRC-1 ckBTC address or native BTC address)
"""

app = typer.Typer(
    name="iconfucius",
    help=HELP_TEXT,
    invoke_without_command=True,
)


# ---------------------------------------------------------------------------
# Upgrade wizard (odin-bots → iconfucius migration)
# ---------------------------------------------------------------------------

def _check_upgrade() -> None:
    """Detect an odin-bots project and offer to upgrade it to iconfucius.

    Checks for:
    1. odin-bots.toml in cwd          → rename to iconfucius.toml
    2. ~/.odin-bots/ global config dir → rename to ~/.iconfucius/
    3. .gitignore comment update
    """
    old_config = Path("odin-bots.toml")
    new_config = Path(CONFIG_FILENAME)
    old_global = Path.home() / ".odin-bots"
    new_global = Path.home() / ".iconfucius"

    if not old_config.exists() or new_config.exists():
        return

    print("Found odin-bots.toml — this project was created with odin-bots.\n")
    print("odin-bots has been renamed to iconfucius. The upgrade will:")
    print("  1. Rename odin-bots.toml → iconfucius.toml")
    if old_global.exists() and not new_global.exists():
        print("  2. Rename ~/.odin-bots/ → ~/.iconfucius/  (global config)")
    print()
    print("Your wallet (.wallet/), cache (.cache/), and memory (.memory/) are unchanged.\n")

    try:
        answer = input("Upgrade now? [Y/n] ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        raise typer.Exit(0)

    if answer in ("n", "no"):
        print("\nTo upgrade later, run 'iconfucius' again from this directory.")
        raise typer.Exit(0)

    # 1. Rename config
    old_config.rename(new_config)
    print(f"Renamed odin-bots.toml → {CONFIG_FILENAME}")

    # 2. Rename global config dir
    if old_global.exists() and not new_global.exists():
        old_global.rename(new_global)
        print("Renamed ~/.odin-bots/ → ~/.iconfucius/")

    # 3. Update .gitignore comment
    gitignore = Path(".gitignore")
    if gitignore.exists():
        content = gitignore.read_text()
        if "# odin-bots project" in content:
            content = content.replace("# odin-bots project", "# iconfucius project")
            gitignore.write_text(content)
            print("Updated .gitignore")

    print("\nUpgrade complete. Continuing...\n")


def _cleanup_obsolete_files() -> None:
    """Silently remove files that are no longer used by iconfucius."""
    obsolete = Path(".logs") / "iconfucius.log"
    if obsolete.exists():
        obsolete.unlink()


# Global state
class State:
    bot_name: Optional[str] = None  # None = not specified
    all_bots: bool = False
    verbose: bool = True
    network: str = "prd"
    rasa: bool = False


state = State()


def _resolve_bot_names(
    bot: Optional[str] = None, all_bots: bool = False
) -> list[str]:
    """Return list of bot names from --bot or --all-bots flags.

    Merges per-command flags with global state so both placements work:
      iconfucius --all-bots fund 1000
      iconfucius fund 1000 --all-bots

    Exits with an error if neither --bot nor --all-bots is provided.
    """
    if state.all_bots or all_bots:
        return get_bot_names()
    effective_bot = bot or state.bot_name
    if effective_bot is not None:
        return [effective_bot]
    print("Please specify which bot(s) to use:\n")
    print("  --bot <name>    Target a specific bot")
    print("  --all-bots      Target all bots")
    raise typer.Exit(1)


def _resolve_network(network: Optional[str] = None) -> None:
    """Apply per-command --network, merging with global state.

    Allows --network to be placed before or after the subcommand:
      iconfucius --network testing fund 1000 --bot bot-1
      iconfucius fund 1000 --bot bot-1 --network testing
    """
    effective = network or state.network
    set_network(effective)




def _version_callback(value: bool):
    """Print the version and exit when the --version flag is set."""
    if value:
        print(f"iconfucius {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    bot: Optional[str] = typer.Option(
        None, "--bot", help="Bot name to use"
    ),
    all_bots: bool = typer.Option(
        False, "--all-bots", help="Target all bots"
    ),
    verbose: bool = typer.Option(
        True, "--verbose/--quiet", help="Show verbose output"
    ),
    network: str = typer.Option(
        "prd", "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    rasa: bool = typer.Option(
        False, "--rasa", help="Use Rasa Pro CALM backend instead of direct LLM tool use - faster, cheaper & avoids business logic hallucinations"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Show Rasa debug logs on screen (only with --rasa)"
    ),
    port: int = typer.Option(55129, "--port", help="Port to serve on"),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't open browser automatically"
    ),
    version: bool = typer.Option(
        False, "--version", help="Show version and exit",
        callback=_version_callback, is_eager=True,
    ),
):
    """Global options for all commands."""
    _check_upgrade()
    _cleanup_obsolete_files()
    state.bot_name = bot  # None when --bot not passed
    state.all_bots = all_bots
    state.verbose = verbose
    state.network = network
    state.rasa = rasa
    state.debug = debug
    set_network(network)
    if ctx.invoked_subcommand is None:
        # Bare invocation: launch the web UI
        from iconfucius.client.server import run_server

        run_server(port=port, open_browser=not no_browser)


# ---------------------------------------------------------------------------
# Wallet subcommand group
# ---------------------------------------------------------------------------

from iconfucius.cli.wallet import wallet_app  # noqa: E402

app.add_typer(wallet_app, name="wallet", help="Manage wallet identity and funds")


# ---------------------------------------------------------------------------
# Chat helper
# ---------------------------------------------------------------------------

def _start_chat():
    """Start interactive chat with the active persona.

    Onboarding wizard: init → API key → wallet → show address → chat.
    """
    from iconfucius.skills.executor import execute_tool

    setup = execute_tool("setup_and_operational_status", {})

    # --- Step 1: Project init ---
    if not setup.get("config_exists"):
        print("No iconfucius project found in this directory.\n")
        try:
            answer = input("Initialize a new project here? [Y/n] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if answer in ("n", "no"):
            print("\nRun 'iconfucius init' when you're ready.")
            return

        # Ask how many bots
        try:
            bots_input = input("How many bots? [3] ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        num_bots = 3
        if bots_input:
            try:
                num_bots = max(1, min(1000, int(bots_input)))
            except ValueError:
                print("Invalid number, using default (3).")

        result = execute_tool("init", {"num_bots": num_bots})
        if result.get("status") != "ok":
            print(f"Error: {result.get('error', 'init failed')}")
            return
        bot_list = ", ".join(f"bot-{i}" for i in range(1, num_bots + 1))
        print(f"Created project with {num_bots} bot(s): {bot_list}")
        print()
        # Re-check after init
        setup = execute_tool("setup_and_operational_status", {})

    # --- Step 2: API key ---
    if not setup.get("has_api_key"):
        print("An Anthropic API key is needed for the AI chat persona.")
        print("Get one at: https://console.anthropic.com/settings/keys\n")
        try:
            api_key = input("Paste your API key (sk-ant-...): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if not api_key:
            print("\nNo key entered. Add it to .env and run 'iconfucius' again.")
            return

        _save_api_key(api_key)
        print("Saved API key to .env")
        print()

    # --- Step 2b: Rasa license (only for --rasa mode) ---
    if getattr(state, "rasa", False):
        import os
        rasa_license = os.environ.get("RASA_LICENSE", "")
        has_rasa_license = bool(rasa_license) and rasa_license != "your-rasa-license-here"
        if not has_rasa_license:
            print("A Rasa Pro license is needed for the CALM backend.")
            print("Get your free Developer Edition license at:")
            print("  https://rasa.com/rasa-pro-developer-edition-license-key-request\n")
            try:
                license_key = input("Paste your Rasa license (ey...): ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                return
            if not license_key:
                print("\nNo license entered. Add RASA_LICENSE to .env and try again.")
                return
            _save_rasa_license(license_key)
            print("Saved Rasa license to .env")
            print()

    # --- Step 3: Wallet create ---
    if not setup.get("wallet_exists"):
        try:
            answer = input("Create a new wallet? [Y/n] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if answer in ("n", "no"):
            print("\nRun 'iconfucius wallet create' when you're ready.")
            return
        result = execute_tool("wallet_create", {})
        if result.get("status") != "ok":
            print(f"Error: {result.get('error', 'wallet create failed')}")
            return
        print("Wallet created.")
        print()
        setup = execute_tool("setup_and_operational_status", {})

    persona_name = "iconfucius"
    bot_name = state.bot_name or "bot-1"

    if getattr(state, "rasa", False):
        from iconfucius.cli.chat_rasa import run_chat_rasa
        run_chat_rasa(persona_name=persona_name, bot_name=bot_name,
                      verbose=state.verbose,
                      debug=getattr(state, "debug", False))
    else:
        from iconfucius.cli.chat import run_chat
        run_chat(persona_name=persona_name, bot_name=bot_name,
                 verbose=state.verbose)


def _save_api_key(api_key: str) -> None:
    """Write an API key to .env (replace placeholder, update existing, or append)."""
    import os
    import re

    env_path = Path(".env")
    if env_path.exists():
        content = env_path.read_text()
        if "your-api-key-here" in content:
            content = content.replace("your-api-key-here", api_key)
        elif "ANTHROPIC_API_KEY" in content:
            content = re.sub(
                r"ANTHROPIC_API_KEY=.*",
                f"ANTHROPIC_API_KEY={api_key}",
                content,
            )
        else:
            separator = "" if content.endswith("\n") else "\n"
            content += f"{separator}ANTHROPIC_API_KEY={api_key}\n"
        env_path.write_text(content)
    else:
        env_path.write_text(f"ANTHROPIC_API_KEY={api_key}\n")

    os.environ["ANTHROPIC_API_KEY"] = api_key


def _save_rasa_license(license_key: str) -> None:
    """Write a Rasa license to .env (replace placeholder, update existing, or append)."""
    import os
    import re

    env_path = Path(".env")
    if env_path.exists():
        content = env_path.read_text()
        if "your-rasa-license-here" in content:
            content = content.replace("your-rasa-license-here", license_key)
        elif "RASA_LICENSE" in content:
            content = re.sub(
                r"RASA_LICENSE=.*",
                f"RASA_LICENSE={license_key}",
                content,
            )
        else:
            separator = "" if content.endswith("\n") else "\n"
            content += f"{separator}RASA_LICENSE={license_key}\n"
        env_path.write_text(content)
    else:
        env_path.write_text(f"RASA_LICENSE={license_key}\n")

    os.environ["RASA_LICENSE"] = license_key


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


GITIGNORE_CONTENT = """\
# iconfucius project
.env
.wallet/
.cache/
.memory/
.logs/
"""


@app.command()
def chat(
    bot: Optional[str] = typer.Option(None, "--bot", help="Bot name to use"),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    rasa: bool = typer.Option(
        False, "--rasa", help="Use Rasa Pro CALM backend instead of direct LLM tool use - faster, cheaper & avoids business logic hallucinations"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Show Rasa debug logs on screen (only with --rasa)"
    ),
):
    """Chat from terminal with IConfucius."""
    _resolve_network(network)
    if bot:
        state.bot_name = bot
    if rasa:
        state.rasa = True
    if debug:
        state.debug = True
    _start_chat()


ENV_TEMPLATE = (
    "# Get your API key at: https://console.anthropic.com/settings/keys\n"
    "ANTHROPIC_API_KEY=your-api-key-here\n"
    "\n"
    "# Get your free Rasa Developer Edition license at: https://rasa.com/rasa-pro-developer-edition-license-key-request\n"
    "RASA_LICENSE=your-rasa-license-here\n"
)


# Required entries in .gitignore — used by both init and upgrade
GITIGNORE_ENTRIES = [".env", ".wallet/", ".cache/", ".memory/", ".logs/"]


def _ensure_env_file() -> None:
    """Create .env if missing, or add ANTHROPIC_API_KEY/RASA_LICENSE if not present."""
    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text(ENV_TEMPLATE)
        print("Created .env with ANTHROPIC_API_KEY and RASA_LICENSE placeholders")
        return

    content = env_path.read_text()
    changed = False
    if "ANTHROPIC_API_KEY" not in content:
        separator = "" if content.endswith("\n") else "\n"
        content += (
            f"{separator}"
            "# Get your API key at: https://console.anthropic.com/settings/keys\n"
            "ANTHROPIC_API_KEY=your-api-key-here\n"
        )
        changed = True
        print("Added ANTHROPIC_API_KEY to .env")
    if "RASA_LICENSE" not in content:
        separator = "" if content.endswith("\n") else "\n"
        content += (
            f"{separator}"
            "# Get your free Rasa Developer Edition license at: https://rasa.com/rasa-pro-developer-edition-license-key-request\n"
            "RASA_LICENSE=your-rasa-license-here\n"
        )
        changed = True
        print("Added RASA_LICENSE to .env")
    if changed:
        env_path.write_text(content)
    else:
        print(".env already contains ANTHROPIC_API_KEY and RASA_LICENSE")


def _ensure_gitignore() -> None:
    """Create .gitignore or add missing entries."""
    gitignore_path = Path(".gitignore")
    if not gitignore_path.exists():
        gitignore_path.write_text(GITIGNORE_CONTENT)
        print("Created .gitignore")
        return

    content = gitignore_path.read_text()
    missing = [e for e in GITIGNORE_ENTRIES if e not in content]
    if missing:
        separator = "" if content.endswith("\n") else "\n"
        additions = "\n".join(missing) + "\n"
        gitignore_path.write_text(content + separator + additions)
        print(f"Added to .gitignore: {', '.join(missing)}")
    else:
        print(".gitignore is up to date")


def _upgrade_config() -> None:
    """Add missing settings to iconfucius.toml without overwriting existing values."""
    config_path = Path(CONFIG_FILENAME)
    content = config_path.read_text()
    additions: list[str] = []

    # Check for default_persona in [settings]
    if "default_persona" not in content:
        additions.append(
            '\n# Default trading persona\n'
            'default_persona = "iconfucius"\n'
        )
        # Insert after [settings] section — find the right spot
        if "[settings]" in content:
            content = content.replace(
                "[settings]",
                "[settings]\n"
                '# Default trading persona\n'
                'default_persona = "iconfucius"',
                1,
            )
            print("Added default_persona to [settings]")
        else:
            # No [settings] section at all — add one
            content = (
                "[settings]\n"
                '# Default trading persona\n'
                'default_persona = "iconfucius"\n\n'
            ) + content
            print("Added [settings] with default_persona")

    # Check for [ai] section (commented out as template)
    if "[ai]" not in content and "# [ai]" not in content:
        content += (
            "\n# AI backend (overrides persona defaults)\n"
            "# API key is read from .env (ANTHROPIC_API_KEY)\n"
            "# [ai]\n"
            '# backend = "claude"\n'
            '# model = "claude-sonnet-4-6"\n'
        )
        print("Added [ai] section template (commented out)")

    config_path.write_text(content)


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
    upgrade: bool = typer.Option(
        False, "--upgrade", "-u", help="Upgrade existing project (add new files/settings)"
    ),
    bots: int = typer.Option(0, "--bots", help="Number of bots to create (0-1000)"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Initialize or upgrade an iconfucius project."""
    if debug:
        state.debug = True
    config_path = Path(CONFIG_FILENAME)

    if upgrade:
        if not config_path.exists():
            print(f"No {CONFIG_FILENAME} found. Run 'iconfucius init' first.")
            raise typer.Exit(1)
        print("Upgrading project...\n")
        _ensure_env_file()
        _ensure_gitignore()
        _upgrade_config()
        print()
        print("Done. Run 'iconfucius' to start chatting.")
        return

    # Always ensure .env exists (even if config already present)
    _ensure_env_file()

    if config_path.exists() and not force:
        print(f"{CONFIG_FILENAME} already exists.")
        print("Use --force to overwrite, or --upgrade to add new features.")
        raise typer.Exit(1)

    _ensure_gitignore()

    # Write config
    config_content = create_default_config(num_bots=bots)
    config_path.write_text(config_content)
    if bots > 0:
        bot_list = ", ".join(f"bot-{i}" for i in range(1, bots + 1))
        print(f"Created {CONFIG_FILENAME} with bots: {bot_list}")
    else:
        print(f"Created {CONFIG_FILENAME} (no bots — add them after funding)")

    print()
    print("Next steps:")
    print("  1. Create your wallet identity:")
    print("     iconfucius wallet create")
    print("  2. Fund your wallet:")
    print("     iconfucius wallet receive")
    print("  3. Launch the web UI:")
    print("     iconfucius")


@app.command()
def config(
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Show current configuration."""
    if debug:
        state.debug = True
    _resolve_network(network)
    cfg = load_config()
    config_path = find_config()

    network = get_network()
    print(f"Config file:   {config_path or 'using defaults'}")
    if network != "prd":
        print(f"Network:       {network}")
    print(f"ckSigner ID:   {get_cksigner_canister_id()}")
    print(f"PEM file:      {PEM_FILE}")
    print()
    print("Bots:")
    for name in get_bot_names():
        desc = cfg["bots"][name].get("description", "")
        print(f"  {name}: {desc}")


@app.command()
def instructions(
    bot: Optional[str] = typer.Option(None, "--bot", help="Bot name to use"),
    all_bots: bool = typer.Option(False, "--all-bots", help="Show all bots"),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Show balance and usage instructions."""
    if debug:
        state.debug = True
    from iconfucius.cli.balance import run_all_balances

    _resolve_network(network)
    bot_names = _resolve_bot_names(bot, all_bots)
    result = run_all_balances(bot_names=bot_names, verbose=state.verbose)
    if result:
        print(result.get("_display", ""))
    print(INSTRUCTIONS_TEXT)


@app.command()
def fund(
    amount: int = typer.Argument(..., help="Amount in sats to send to each bot"),
    bot: Optional[str] = typer.Option(None, "--bot", help="Bot name to use"),
    all_bots: bool = typer.Option(False, "--all-bots", help="Fund all bots"),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Fund bot(s) and deposit into Odin.Fun trading accounts."""
    if debug:
        state.debug = True
    _resolve_network(network)
    from iconfucius.cli.fund import run_fund

    bot_names = _resolve_bot_names(bot, all_bots)
    result = run_fund(bot_names=bot_names, amount=amount, verbose=state.verbose)

    if result["status"] == "error":
        print(f"FAILED: {result['error']}")
        return

    funded = result.get("funded", [])
    failed = result.get("failed", [])
    if funded:
        suffix = " each" if len(funded) > 1 else ""
        print(f"Funded {len(funded)} bot(s) with {_fmt_sats(amount)}{suffix}")
    for f in failed:
        print(f"  {f['bot']}: FAILED — {f['error']}")


@app.command()
def withdraw(
    amount: str = typer.Argument(
        ..., help="Amount in sats, or 'all' for entire balance"
    ),
    bot: Optional[str] = typer.Option(None, "--bot", help="Bot name to use"),
    all_bots: bool = typer.Option(False, "--all-bots", help="Withdraw from all bots"),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Withdraw from Odin.Fun back to the iconfucius wallet."""
    if debug:
        state.debug = True
    _resolve_network(network)
    from iconfucius.cli.concurrent import run_per_bot
    from iconfucius.cli.withdraw import run_withdraw

    bot_names = _resolve_bot_names(bot, all_bots)
    results = run_per_bot(
        lambda name: run_withdraw(bot_name=name, amount=amount, verbose=state.verbose),
        bot_names,
    )
    for bot_name, result in results:
        if isinstance(result, Exception):
            print(f"{bot_name}: FAILED — {result}")
        elif isinstance(result, dict):
            status = result.get("status", "")
            if status == "ok":
                print(f"{bot_name}: withdrawn {_fmt_sats(result.get('withdrawn_sats', 0))}")
            elif status == "error":
                print(f"{bot_name}: FAILED — {result.get('error', '')}")
            elif status == "partial":
                print(f"{bot_name}: partial — {result.get('error', '')}")


def _print_trade_result(bot_name: str, result) -> None:
    """Print a one-line summary for a trade result (dict or list of dicts)."""
    if isinstance(result, list):
        for r in result:
            _print_trade_result(bot_name, r)
        return
    if not isinstance(result, dict):
        return
    status = result.get("status", "")
    if status == "ok":
        action = result.get("action", "?")
        token_id = result.get("token_id", "?")
        token_label = result.get("token_label", token_id)
        amount = result.get("amount", "?")
        if isinstance(amount, int):
            if action == "buy":
                print(f"{bot_name}: {action} {_fmt_sats(amount)} {token_label}")
            else:
                from iconfucius.config import fmt_tokens
                print(f"{bot_name}: {action} {fmt_tokens(amount, token_id)} {token_label}")
        else:
            print(f"{bot_name}: {action} {token_label}")
    elif status == "skipped":
        print(f"{bot_name}: skipped — {result.get('reason', '')}")
    elif status == "error":
        print(f"{bot_name}: FAILED — {result.get('error', '')}")


@app.command()
def trade(
    action: str = typer.Argument(..., help="Trade action: buy or sell"),
    token_id: str = typer.Argument(..., help="Token ID (e.g., 28k1)"),
    amount: str = typer.Argument(
        ..., help="Amount in sats (buy), tokens (sell), or 'all' (sell entire balance)"
    ),
    bot: Optional[str] = typer.Option(None, "--bot", help="Bot name to use"),
    all_bots: bool = typer.Option(False, "--all-bots", help="Trade with all bots"),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Buy or sell tokens on Odin.Fun."""
    if debug:
        state.debug = True
    _resolve_network(network)
    from iconfucius.cli.concurrent import run_per_bot
    from iconfucius.cli.trade import run_trade

    bot_names = _resolve_bot_names(bot, all_bots)

    if token_id == "all-tokens":
        if action != "sell":
            print("Error: 'all-tokens' is only supported for sell, not buy")
            raise typer.Exit(1)
        from iconfucius.cli.balance import collect_balances

        def _sell_all_tokens(bot_name):
            """Sell all token holdings for a single bot and return the results."""
            data = collect_balances(bot_name, verbose=state.verbose)
            if not data.token_holdings:
                return {"status": "skipped", "bot_name": bot_name,
                        "reason": "no token holdings to sell"}
            results = []
            for holding in data.token_holdings:
                if holding["balance"] > 0:
                    r = run_trade(
                        bot_name=bot_name, action="sell",
                        token_id=holding["token_id"], amount="all",
                        verbose=state.verbose,
                    )
                    results.append(r)
            return results

        results = run_per_bot(_sell_all_tokens, bot_names)
        for bot_name, result in results:
            if isinstance(result, Exception):
                print(f"{bot_name}: FAILED — {result}")
            else:
                _print_trade_result(bot_name, result)
    else:
        results = run_per_bot(
            lambda name: run_trade(
                bot_name=name, action=action, token_id=token_id,
                amount=amount, verbose=state.verbose,
            ),
            bot_names,
        )
        for bot_name, result in results:
            if isinstance(result, Exception):
                print(f"{bot_name}: FAILED — {result}")
            else:
                _print_trade_result(bot_name, result)


@app.command()
def transfer(
    token_id: str = typer.Argument(..., help="Token ID to transfer (e.g. 29m8)"),
    amount: str = typer.Argument(
        ..., help="Amount in raw token sub-units, or 'all' for entire balance"
    ),
    to_address: str = typer.Argument(..., help="Destination address (IC principal, BTC deposit, or BTC wallet address of an Odin.fun account)"),
    bot: Optional[str] = typer.Option(None, "--bot", help="Bot name to use"),
    all_bots: bool = typer.Option(False, "--all-bots", help="Transfer from all bots"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Transfer tokens to another Odin.Fun account (irreversible)."""
    if debug:
        state.debug = True
    _resolve_network(network)
    from iconfucius.cli.concurrent import run_per_bot
    from iconfucius.cli.transfer import run_transfer

    bot_names = _resolve_bot_names(bot, all_bots)

    if not yes:
        print("WARNING: Token transfer is irreversible.\n")
        print(f"  From:    {', '.join(bot_names)}")
        print(f"  To:      {to_address}")
        print(f"  Token:   {token_id}")
        print(f"  Amount:  {amount}")
        print(f"  Fee:     100 sats BTC (per bot)\n")
        try:
            answer = input("  Proceed? [Y/n] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            raise typer.Exit(0)
        if answer in ("n", "no"):
            print("Cancelled.")
            raise typer.Exit(0)

    results = run_per_bot(
        lambda name: run_transfer(
            bot_name=name, token_id=token_id, amount=amount,
            to_address=to_address, verbose=state.verbose,
        ),
        bot_names,
    )
    for bot_name, result in results:
        if isinstance(result, Exception):
            print(f"{bot_name}: FAILED — {result}")
        elif isinstance(result, dict):
            status = result.get("status", "")
            if status == "ok":
                from iconfucius.config import fmt_tokens
                print(
                    f"{bot_name}: transferred "
                    f"{fmt_tokens(result.get('amount', 0), token_id)} "
                    f"{result.get('token_label', token_id)} -> {to_address}"
                )
            elif status == "error":
                print(f"{bot_name}: FAILED — {result.get('error', '')}")


@app.command()
def sweep(
    bot: Optional[str] = typer.Option(None, "--bot", help="Bot name to use"),
    all_bots: bool = typer.Option(False, "--all-bots", help="Sweep all bots"),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Sell all tokens and withdraw all ckBTC back to the wallet."""
    if debug:
        state.debug = True
    _resolve_network(network)
    from iconfucius.cli.balance import collect_balances
    from iconfucius.cli.concurrent import run_per_bot
    from iconfucius.cli.trade import run_trade
    from iconfucius.cli.withdraw import run_withdraw

    bot_names = _resolve_bot_names(bot, all_bots)

    # Phase 1: Sell all tokens for each bot (concurrent)
    def _sell_all(bot_name):
        """Sell all holdings of a token for a bot."""
        data = collect_balances(bot_name, verbose=state.verbose)
        if not data.token_holdings:
            return {"status": "skipped", "bot_name": bot_name,
                    "reason": "no token holdings to sell"}
        results = []
        for holding in data.token_holdings:
            if holding["balance"] > 0:
                r = run_trade(
                    bot_name=bot_name, action="sell",
                    token_id=holding["token_id"], amount="all",
                    verbose=state.verbose,
                )
                results.append(r)
        return results

    results = run_per_bot(_sell_all, bot_names)
    for bot_name, result in results:
        if isinstance(result, Exception):
            print(f"{bot_name}: sell FAILED — {result}")
        else:
            _print_trade_result(bot_name, result)

    # Phase 2: Withdraw all ckBTC for each bot (concurrent)
    results = run_per_bot(
        lambda name: run_withdraw(bot_name=name, amount="all", verbose=state.verbose),
        bot_names,
    )
    for bot_name, result in results:
        if isinstance(result, Exception):
            print(f"{bot_name}: withdraw FAILED — {result}")
        elif isinstance(result, dict):
            status = result.get("status", "")
            if status == "ok":
                print(f"{bot_name}: withdrawn {_fmt_sats(result.get('withdrawn_sats', 0))}")
            elif status == "error":
                print(f"{bot_name}: withdraw FAILED — {result.get('error', '')}")
            elif status == "partial":
                print(f"{bot_name}: withdraw partial — {result.get('error', '')}")


@app.command()
def ui(
    port: int = typer.Option(55129, "--port", help="Port to serve on"),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't open browser automatically"
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="PoAIW network of ckSigner: prd, testing, development"
    ),
    verbose: Optional[bool] = typer.Option(
        None, "--verbose/--quiet", help="Show verbose output"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Launch the web UI."""
    if debug:
        state.debug = True
    _resolve_network(network)
    if verbose is not None:
        state.verbose = verbose
    from iconfucius.client.server import run_server

    run_server(port=port, open_browser=not no_browser)


def main():
    """Entry point for the CLI."""
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    # Load .env from current directory (if it exists)
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=True)

    app()
