"""Configuration management for iconfucius.

Loads configuration from iconfucius.toml in the project root.
"""

import os
import re
from pathlib import Path
from typing import Optional

import tomllib


# ---------------------------------------------------------------------------
# Network & canister constants
# ---------------------------------------------------------------------------

IC_HOST = "https://ic0.app"

# onicai ckSigner canister IDs per PoAIW network
CKSIGNER_CANISTER_IDS = {
    "prd": "g7qkb-iiaaa-aaaar-qb3za-cai",
    "testing": "ho2u6-qaaaa-aaaar-qb34q-cai",
    "development": "ho2u6-qaaaa-aaaar-qb34q-cai",
}
VALID_NETWORKS = list(CKSIGNER_CANISTER_IDS.keys())

# Default (prd) — kept for backward compatibility
ONICAI_CKSIGNER_CANISTER_ID = CKSIGNER_CANISTER_IDS["prd"]

# Odin.fun SIWB canister (Sign-In with Bitcoin)
ODIN_SIWB_CANISTER_ID = "bcxqa-kqaaa-aaaak-qotba-cai"

# ckBTC ledger
CKBTC_LEDGER_CANISTER_ID = "mxzaz-hqaaa-aaaar-qaada-cai"

# ckBTC minter (BTC <-> ckBTC)
CKBTC_MINTER_CANISTER_ID = "mqygn-kiaaa-aaaar-qaadq-cai"

# Odin.fun trading canister
ODIN_TRADING_CANISTER_ID = "z2vm5-gaaaa-aaaaj-azw6q-cai"

# Odin.fun ckBTC deposit helper
ODIN_DEPOSIT_CANISTER_ID = "ztwhb-qiaaa-aaaaj-azw7a-cai"

# Odin.fun API
ODIN_API_URL = "https://api.odin.fun/v1"

# ---------------------------------------------------------------------------
# Trading limits (enforced by Odin.fun trading canister)
# ---------------------------------------------------------------------------

MIN_DEPOSIT_SATS = 5000   # minimum ckBTC deposit into Odin.Fun
MIN_TRADE_SATS = 500      # minimum BTC-equivalent for buy/sell on Odin.Fun
MIN_BTC_WITHDRAWAL_SATS = 50_000  # minimum BTC withdrawal via ckBTC minter
WALLET_RESERVE_SATS = 1000  # minimum ckBTC to keep in wallet after deposits (for signing fees)


# Bech32 mainnet: bc1q (segwit v0, 42 chars) or bc1p (taproot v1, 62 chars).
# Bech32 charset (after the separator '1'): qpzry9x8gf2tvdw0s3jn54khce6mua7l
# Notably missing: b, i, o, 1 — these are excluded to avoid visual ambiguity.
# IC principals (e.g. rrkah-fqaaa-aaaaa-aaaaq-cai) contain dashes and don't
# start with bc1, so they are guaranteed to never match this pattern.
_BECH32_CHARS = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_BTC_ADDRESS_RE = re.compile(rf"^bc1[qp][{_BECH32_CHARS}]{{38,58}}$")


def is_bech32_btc_address(address: str) -> bool:
    """Check if a string looks like a Bitcoin bech32 mainnet address.

    The ckBTC minter only supports bech32 (bc1…) addresses. This check also
    serves to cleanly separate BTC addresses from IC principals — principals
    contain dashes and never start with bc1, so they are 100% rejected.
    """
    return isinstance(address, str) and _BECH32_BTC_ADDRESS_RE.match(address) is not None

# ---------------------------------------------------------------------------
# AI defaults
# ---------------------------------------------------------------------------

AI_TIMEOUT_DEFAULT = 600  # seconds

# ---------------------------------------------------------------------------
# BTC/USD rate & sats formatting
# ---------------------------------------------------------------------------

def get_btc_to_usd_rate() -> float:
    """Get the current BTC to USD exchange rate from Coinbase."""
    import requests
    url = "https://api.coinbase.com/v2/exchange-rates?currency=BTC"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    return float(data["data"]["rates"]["USD"])


def fmt_sats(sats, btc_usd_rate) -> str:
    """Format sats with optional USD value.

    Args:
        sats: Amount in satoshis.
        btc_usd_rate: BTC/USD rate, or None to skip USD.
    """
    if btc_usd_rate:
        usd = (sats / 100_000_000) * btc_usd_rate
        return f"{sats:,} sats (${usd:.3f})"
    return f"{sats:,} sats"


def fmt_tokens(count, token_id: str) -> str:
    """Format a raw token balance with USD value for display.

    Args:
        count: Token count in raw sub-units (as returned by canister getBalance).
        token_id: Odin token ID (e.g. '29m8').

    Returns:
        e.g. '1,000.000 tokens ($5.00)' or '1,000.000 tokens' on failure.
    """
    from decimal import Decimal

    try:
        raw_amount = int(count)
    except (TypeError, ValueError):
        return f"{count} tokens"
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(
            f"{ODIN_API_URL}/token/{token_id}",
            impersonate="chrome",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code != 200:
            return f"{count} tokens"
        info = resp.json()
        price = Decimal(str(info.get("price", 0)))
        divisibility = int(info.get("divisibility", 8))
        # Convert raw sub-units to human-readable token count for display
        scale = Decimal(10) ** divisibility
        display_amount = Decimal(raw_amount) / scale if divisibility > 0 else Decimal(raw_amount)
        label = f"{display_amount:,.3f} tokens"
        btc_usd_rate = get_btc_to_usd_rate()
        value_microsats = (Decimal(raw_amount) * price) / scale
        value_sats = value_microsats / 1_000_000
        usd = (value_sats / Decimal(100_000_000)) * Decimal(str(btc_usd_rate))
        return f"{label} (${usd:,.3f})"
    except Exception:
        return f"{count} tokens"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# PEM file path (always .wallet/identity-private.pem, generated by: iconfucius wallet create)
PEM_FILE = ".wallet/identity-private.pem"

DEFAULT_CONFIG = {
    "settings": {"default_persona": "iconfucius"},
    "bots": {
        "bot-1": {"description": "Bot 1"},
    },
    "ai": {},
}

CONFIG_FILENAME = "iconfucius.toml"

# Module-level cache
_cached_config: Optional[dict] = None
_cached_config_path: Optional[Path] = None

# Module-level verbose flag (controls DEBUG-level logging)
_verbose: bool = False


def set_verbose(enabled: bool) -> None:
    """Set the global verbose flag and switch log level accordingly."""
    global _verbose
    _verbose = enabled
    from iconfucius.logging_config import set_debug
    set_debug(enabled)


def is_verbose() -> bool:
    """Return the current verbose flag."""
    return _verbose


def log(msg: str) -> None:
    """Log a message to .logs/iconfucius.log (file only)."""
    from iconfucius.logging_config import get_logger
    get_logger().debug(msg)


# Module-level network (default: prd)
_network: str = "prd"


def set_network(network: str) -> None:
    """Set the active PoAIW network."""
    global _network
    if network not in CKSIGNER_CANISTER_IDS:
        raise ValueError(f"Unknown network '{network}'. Valid: {VALID_NETWORKS}")
    _network = network


def get_network() -> str:
    """Return the active PoAIW network."""
    return _network


def get_cksigner_canister_id() -> str:
    """Return the ckSigner canister ID for the active network."""
    return CKSIGNER_CANISTER_IDS[_network]


def _project_root() -> str:
    """Return the iconfucius project root directory.

    Resolution order:
    1. ICONFUCIUS_ROOT environment variable (if set)
    2. Current working directory
    """
    return os.environ.get("ICONFUCIUS_ROOT", os.environ.get("PWD", os.getcwd()))


def find_config() -> Optional[Path]:
    """Find iconfucius.toml in cwd or ICONFUCIUS_ROOT.

    Returns:
        Path to config file if found, None otherwise.
    """
    root = Path(_project_root())
    config_path = root / CONFIG_FILENAME
    if config_path.exists():
        return config_path
    return None


def load_config(reload: bool = False) -> dict:
    """Load config from iconfucius.toml or return defaults.

    Args:
        reload: If True, reload config even if cached.

    Returns:
        Configuration dictionary with settings and bots.
    """
    global _cached_config, _cached_config_path

    if _cached_config is not None and not reload:
        return _cached_config

    config_path = find_config()

    if config_path is None:
        _cached_config = DEFAULT_CONFIG.copy()
        _cached_config_path = None
        return _cached_config

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # Merge with defaults for missing keys
    result = DEFAULT_CONFIG.copy()
    if "settings" in config:
        result["settings"] = {**DEFAULT_CONFIG["settings"], **config["settings"]}
    if "bots" in config:
        result["bots"] = config["bots"]
    if "ai" in config:
        result["ai"] = config["ai"]

    _cached_config = result
    _cached_config_path = config_path
    return result


def get_config_path() -> Optional[Path]:
    """Return the path to the loaded config file, or None if using defaults."""
    load_config()  # Ensure config is loaded
    return _cached_config_path


def get_pem_file() -> str:
    """Return the absolute path to the PEM file."""
    return os.path.join(_project_root(), PEM_FILE)


def require_wallet() -> bool:
    """Check that the wallet PEM exists. Print instructions and return False if not."""
    pem_path = get_pem_file()
    if os.path.exists(pem_path):
        return True
    print("No iconfucius wallet found in current directory. Set it up first:\n")
    print("  iconfucius wallet create")
    print("  iconfucius wallet receive   # shows how to fund your bots")
    print()
    print(f"  (expected PEM at {pem_path})")
    return False


def get_cache_sessions() -> bool:
    """Return whether session caching to disk is enabled.

    Reads `cache_sessions` from [settings] in iconfucius.toml.
    Defaults to True. When False, sessions are not written to disk
    and a fresh SIWB login is performed for every command.
    """
    config = load_config()
    return config.get("settings", {}).get("cache_sessions", True)


def get_verify_certificates() -> bool:
    """Return whether IC certificate verification is enabled.

    Reads `verify_certificates` from [settings] in iconfucius.toml.
    Defaults to False (blst not required for basic usage).
    When True, requires the blst library to be installed.
    """
    config = load_config()
    enabled = config.get("settings", {}).get("verify_certificates", False)
    if enabled:
        try:
            import blst  # noqa: F401
        except ImportError:
            print("Error: verify_certificates = true in iconfucius.toml,")
            print("but the 'blst' library is not installed.")
            print()
            print("See README-security.md for installation instructions.")
            raise SystemExit(1)
    return enabled


def get_bot_names() -> list[str]:
    """Return list of configured bot names."""
    config = load_config()
    return list(config["bots"].keys())


def get_bot_description(bot_name: str) -> str:
    """Return the description for a bot, or empty string if not found."""
    config = load_config()
    bot = config["bots"].get(bot_name, {})
    return bot.get("description", "")


def validate_bot_name(name: str) -> bool:
    """Check if bot name exists in config.

    Note: Any non-empty string is valid as a bot name (derivation path).
    This just checks if it's explicitly configured.
    """
    config = load_config()
    return name in config["bots"]


def get_default_persona() -> str:
    """Return the default persona name from config."""
    config = load_config()
    return config.get("settings", {}).get("default_persona", "iconfucius")


def get_ai_config() -> dict:
    """Return project-level [ai] config (overrides persona AI settings)."""
    config = load_config()
    return config.get("ai", {})


def get_ai_timeout() -> int:
    """Return AI request timeout in seconds from config or default.

    Resolution order:
    1. ``timeout`` in [ai] section of iconfucius.toml
    2. AI_TIMEOUT_DEFAULT (600)
    """
    config = load_config()
    val = config.get("ai", {}).get("timeout")
    if val is not None:
        try:
            timeout = int(val)
        except (TypeError, ValueError):
            return AI_TIMEOUT_DEFAULT
        if timeout > 0:
            return timeout
        return AI_TIMEOUT_DEFAULT
    return AI_TIMEOUT_DEFAULT


def get_bot_persona(bot_name: str) -> str:
    """Return the persona assigned to a bot, or default persona."""
    config = load_config()
    bot = config["bots"].get(bot_name, {})
    return bot.get("persona", get_default_persona())


def create_default_config(num_bots: int = 3) -> str:
    """Generate default config file content.

    Args:
        num_bots: Number of bot definitions to create (1-1000, default 3).

    Returns:
        TOML content as string.
    """
    num_bots = max(1, min(1000, num_bots))
    header = '''# iconfucius configuration
# See: https://github.com/onicai/IConfucius

[settings]
# See README-security.md for details
verify_certificates = false
cache_sessions = true
default_persona = "iconfucius"

# AI configuration (overrides persona defaults)
# Default: Claude with claude-opus-4-6 (API key via ANTHROPIC_API_KEY env var)
#
# Claude with a different model:
# [ai]
# model = "claude-sonnet-4-6"
#
# Any OpenAI-compatible endpoint (llama.cpp, Ollama, vLLM, LM Studio, etc.):
# [ai]
# api_type = "openai"
# base_url = "http://localhost:55128"
# # API key via OPENAI_API_KEY env var (optional for local servers)
#
# Start llama.cpp server:
#   llama-server --jinja --port 55128 -hf bartowski/Mistral-Nemo-Instruct-2407-GGUF:Q4_K_M
#
# Recommended local models for tool calling (Q4_K_M quantization):
#   ~7.5GB  Mistral-NeMo-12B    bartowski/Mistral-Nemo-Instruct-2407-GGUF:Q4_K_M
#   ~9 GB   Qwen2.5-14B         bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M
#   ~15GB   Mistral-Small-24B   bartowski/Mistral-Small-24B-Instruct-2501-GGUF:Q4_K_M

# Bot definitions
# Each bot gets its own trading identity on Odin.Fun.
# Optional: persona = "<name>" assigns a trading persona to the bot.
'''
    bots = "\n".join(
        f'[bots.bot-{i}]\ndescription = "Bot {i}"\n'
        for i in range(1, num_bots + 1)
    )
    return header + bots


def add_bots_to_config(current_max: int, target: int) -> list[str]:
    """Append new bot sections to iconfucius.toml.

    Args:
        current_max: Highest existing bot number (e.g. 10 if bot-10 exists).
        target: Desired total bot count.

    Returns:
        List of newly added bot names.
    """
    import re as _re

    config_path = Path(CONFIG_FILENAME)
    content = config_path.read_text()
    new_names = []
    new_sections = []
    for i in range(current_max + 1, target + 1):
        name = f"bot-{i}"
        new_names.append(name)
        new_sections.append(f'[bots.{name}]\ndescription = "Bot {i}"\n')
    if new_sections:
        separator = "" if content.endswith("\n") else "\n"
        content += separator + "\n".join(new_sections)
        config_path.write_text(content)
    return new_names


def remove_bots_from_config(bot_names: list[str]) -> None:
    """Remove bot sections from iconfucius.toml.

    Args:
        bot_names: List of bot names to remove (e.g. ["bot-8", "bot-9"]).
    """
    import re as _re

    config_path = Path(CONFIG_FILENAME)
    content = config_path.read_text()
    for name in bot_names:
        # Match [bots.<name>] and everything until next [section] or EOF
        pattern = rf'\[bots\.{_re.escape(name)}\]\n(?:[^\[]*)'
        content = _re.sub(pattern, '', content)
    # Clean up triple+ blank lines
    content = _re.sub(r'\n{3,}', '\n\n', content)
    config_path.write_text(content)
