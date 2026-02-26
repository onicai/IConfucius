"""Lightweight proxy for the Odin.fun API and iconfucius wallet + chat.

Uses curl_cffi with Chrome TLS fingerprint impersonation to bypass
Cloudflare bot detection. Exposes wallet/balance endpoints when the
iconfucius SDK is installed and a project is initialized.

Usage:
    python proxy-server.py                          # default: CWD as project root
    ICONFUCIUS_ROOT=/path/to/project python proxy-server.py

Endpoints:
    /api/odin/*          Proxy to https://api.odin.fun/v1/*
    /api/wallet/info     Wallet principal, ckBTC balance, BTC deposit address
    /api/wallet/balances Full portfolio: wallet + all bot holdings
    /api/wallet/status   SDK + setup status
    /api/setup/*         Project init, wallet create, set bots
    /api/chat/*          AI chat session (start, message, confirm, settings)
"""

import json
import os
import sys
import time
import traceback
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Simple TTL cache for expensive blockchain calls
# ---------------------------------------------------------------------------
_cache = {}
_CACHE_TTL = 45  # seconds


def _cache_get(key):
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key, value):
    _cache[key] = (time.monotonic(), value)


def _cache_clear(key=None):
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()

try:
    from curl_cffi import requests
except ImportError:
    print("curl_cffi is required: pip install curl_cffi")
    sys.exit(1)

PORT = 3001
ODIN_API = "https://api.odin.fun/v1"

if "ICONFUCIUS_ROOT" not in os.environ:
    os.environ["ICONFUCIUS_ROOT"] = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )

# If setup files were previously created in client/, prefer that location so
# setup status and wallet operations point to the same project directory.
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_client_root = os.path.abspath(os.path.dirname(__file__))
_repo_cfg = os.path.join(_repo_root, "iconfucius.toml")
_client_cfg = os.path.join(_client_root, "iconfucius.toml")
_repo_wallet = os.path.join(_repo_root, ".wallet", "identity-private.pem")
_client_wallet = os.path.join(_client_root, ".wallet", "identity-private.pem")

if (not os.path.exists(_repo_cfg) and not os.path.exists(_repo_wallet)) and (
    os.path.exists(_client_cfg) or os.path.exists(_client_wallet)
):
    os.environ["ICONFUCIUS_ROOT"] = _client_root


def _load_env_file():
    """Load simple KEY=VALUE pairs from .env into process env."""
    root = os.environ.get("ICONFUCIUS_ROOT", "")
    env_path = os.path.join(root, ".env") if root else ".env"
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # .env parsing should never prevent proxy startup
        pass


_load_env_file()

_HAS_ICONFUCIUS = False
try:
    from iconfucius.config import get_bot_names, get_btc_to_usd_rate, fmt_sats
    from iconfucius.cli.balance import run_wallet_balance, run_all_balances
    from iconfucius.skills.executor import execute_tool
    _HAS_ICONFUCIUS = True
except ImportError:
    pass


def _sync_project_root():
    """Pick the best project root based on existing config/wallet files."""
    current = os.environ.get("ICONFUCIUS_ROOT", _repo_root)
    candidates = [_repo_root, _client_root]

    def _score(root: str) -> tuple[int, int]:
        cfg = os.path.exists(os.path.join(root, "iconfucius.toml"))
        pem = os.path.exists(os.path.join(root, ".wallet", "identity-private.pem"))
        # Prefer wallet presence first, then config presence.
        return (1 if pem else 0, 1 if cfg else 0)

    best = current
    best_score = _score(current)
    for c in candidates:
        s = _score(c)
        if s > best_score:
            best = c
            best_score = s

    if best != current:
        os.environ["ICONFUCIUS_ROOT"] = best
        _load_env_file()


# ---------------------------------------------------------------------------
# Chat sessions (in-memory)
# ---------------------------------------------------------------------------
_MAX_TOOL_ITERATIONS = 15
_chat_sessions: dict[str, dict] = {}


def _build_system_prompt(persona):
    """Replicate system prompt construction from run_chat."""
    from iconfucius.memory import read_strategy, read_learnings, read_trades
    from iconfucius.tokens import format_known_tokens_for_prompt
    from iconfucius.config import get_bot_names as _get_bots

    system = persona.system_prompt

    setup = execute_tool("setup_status", {})
    if not setup.get("ready"):
        system += "\n\n## Setup Status\n"
        system += (
            f"Config: {'ready' if setup.get('config_exists') else 'MISSING — use init tool'}\n"
            f"Wallet: {'ready' if setup.get('wallet_exists') else 'MISSING — use wallet_create tool'}\n"
            f"API key: {'ready' if setup.get('has_api_key') else 'MISSING — user must add ANTHROPIC_API_KEY to .env'}\n"
        )
        system += "\nGuide the user through any missing setup steps before trading."

    pname = persona.name.lower().replace(" ", "")
    strategy = read_strategy(pname)
    learnings = read_learnings(pname)
    recent_trades = read_trades(pname, last_n=5)

    if strategy:
        system += f"\n\n## Current Strategy\n{strategy}"
    if learnings:
        system += f"\n\n## Learnings\n{learnings}"
    if recent_trades:
        system += f"\n\n## Recent Trades\n{recent_trades}"

    known = format_known_tokens_for_prompt()
    if known:
        system += f"\n\n## Known Tokens\n{known}"
        system += "\nUse these token IDs directly. For unknown tokens, use token_lookup."

    bots = _get_bots()
    bot_name = persona.bot
    if len(bots) > 1:
        names_str = ", ".join(bots)
        system += (
            f"\n\nYou manage {len(bots)} bots: {names_str}. "
            f"Default bot for single-bot operations: '{bot_name}'. "
            f"When using wallet_balance, use all_bots=true "
            f"unless the user specifies particular bots. "
            f"When using fund, trade, or withdraw, ask the user what bots to use."
        )
    else:
        system += f"\n\nYou are trading as bot '{bot_name}'."

    return system


def _describe_tool_call(name, tool_input):
    """Minimal human-readable description for confirmations."""
    if name == "init":
        return "Initialize iconfucius project in current directory"
    if name == "wallet_create":
        return "Create a new wallet identity"
    if name == "fund":
        amt = tool_input.get("amount", "?")
        return f"Fund bots with {amt} sats"
    if name == "trade_buy":
        return f"Buy {tool_input.get('amount', '?')} sats of token {tool_input.get('token_id', '?')}"
    if name == "trade_sell":
        return f"Sell {tool_input.get('amount', 'some')} of token {tool_input.get('token_id', '?')}"
    if name == "withdraw":
        return f"Withdraw {tool_input.get('amount', '?')} from bots"
    if name == "wallet_send":
        return f"Send {tool_input.get('amount', '?')} to {tool_input.get('address', '?')}"
    if name == "set_bot_count":
        return f"Change bot count to {tool_input.get('num_bots', '?')}"
    if name == "token_transfer":
        return f"Transfer {tool_input.get('amount', '?')} of {tool_input.get('token_id', '?')} to {tool_input.get('to_address', '?')}"
    if name == "install_blst":
        return "Install blst library for IC certificate verification"
    if name == "memory_update":
        return f"Update {tool_input.get('file', '?')} memory"
    return f"{name}({json.dumps(tool_input)})"


def _block_to_dict(block) -> dict:
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": block.type}


def _run_web_tool_loop(session):
    """Run one iteration of the tool loop.

    Returns a dict with either:
      - {"type": "response", "text": ...}  (final text)
      - {"type": "confirm", "tools": [...]} (needs user approval)
      - {"type": "error", "text": ...}
    """
    from iconfucius.skills.definitions import get_tool_metadata, get_tools_for_anthropic

    backend = session["backend"]
    messages = session["messages"]
    system = session["system"]
    tools = session["tools"]
    persona_key = session.get("persona_key", "")
    iterations = 0

    while iterations < _MAX_TOOL_ITERATIONS:
        iterations += 1
        response = backend.chat_with_tools(messages, system, tools)

        has_tool_use = any(b.type == "tool_use" for b in response.content)

        if not has_tool_use:
            text = "".join(b.text for b in response.content if b.type == "text")
            messages.append({"role": "assistant", "content": text})
            return {"type": "response", "text": text}

        messages.append({
            "role": "assistant",
            "content": [_block_to_dict(b) for b in response.content],
        })

        tool_blocks = [b for b in response.content if b.type == "tool_use"]

        # Enforce one distinct state-changing tool name per response
        write_names = {
            b.name for b in tool_blocks
            if (get_tool_metadata(b.name) or {}).get("category") == "write"
        }
        deferred_ids = set()
        if len(write_names) > 1:
            first_write_name = next(
                b.name for b in tool_blocks
                if (get_tool_metadata(b.name) or {}).get("category") == "write"
            )
            for b in tool_blocks:
                meta = get_tool_metadata(b.name) or {}
                if meta.get("category") == "write" and b.name != first_write_name:
                    deferred_ids.add(b.id)
            tool_blocks = [b for b in tool_blocks if b.id not in deferred_ids]

        # USD→sats conversion
        for b in tool_blocks:
            if b.name == "trade_sell":
                continue
            usd = b.input.get("amount_usd")
            if usd is not None and not b.input.get("amount"):
                try:
                    rate = get_btc_to_usd_rate()
                    sats = int((usd / rate) * 100_000_000)
                    b.input["amount"] = sats
                    del b.input["amount_usd"]
                except Exception:
                    pass

        confirm_blocks = []
        for b in tool_blocks:
            meta = get_tool_metadata(b.name)
            if meta and meta.get("requires_confirmation", False):
                confirm_blocks.append(b)

        if confirm_blocks:
            session["pending_confirm"] = {
                "tool_blocks": tool_blocks,
                "confirm_blocks": confirm_blocks,
                "deferred_ids": deferred_ids,
                "response": response,
            }
            return {
                "type": "confirm",
                "tools": [
                    {"name": b.name, "description": _describe_tool_call(b.name, b.input), "input": b.input}
                    for b in confirm_blocks
                ],
            }

        # Execute read-only tools
        tool_results = _execute_tool_blocks(tool_blocks, set(), True, persona_key)

        # Append deferred results
        for block in response.content:
            if block.type == "tool_use" and block.id in deferred_ids:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps({"status": "deferred", "error": "Deferred: only one write tool type per turn."}),
                })

        messages.append({"role": "user", "content": tool_results})

    return {"type": "response", "text": "(Tool loop limit reached)"}


def _execute_tool_blocks(tool_blocks, confirm_ids, approved, persona_key):
    """Execute tool blocks and return tool_result list."""
    tool_results = []
    for block in tool_blocks:
        if block.id in confirm_ids and not approved:
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps({"status": "declined", "error": "User declined."}),
            })
            continue

        result = execute_tool(block.name, block.input, persona_name=persona_key)
        result.pop("_terminal_output", None)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": json.dumps(result, default=str),
        })
    return tool_results


def _handle_chat_start(body):
    """Create a new chat session."""
    if not _HAS_ICONFUCIUS:
        return 503, {"error": "iconfucius SDK not installed"}

    try:
        from iconfucius.persona import load_persona
        from iconfucius.ai import ClaudeBackend, APIKeyMissingError
        from iconfucius.skills.definitions import get_tools_for_anthropic
    except ImportError as e:
        return 503, {"error": f"Missing dependency: {e}"}

    api_key = body.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    persona_name = body.get("persona", "iconfucius")

    try:
        persona = load_persona(persona_name)
    except Exception as e:
        return 400, {"error": f"Persona not found: {e}"}

    model = body.get("model") or persona.ai_model
    try:
        backend = ClaudeBackend(model=model, api_key=api_key)
    except APIKeyMissingError as e:
        return 400, {"error": str(e), "needs_api_key": True}
    except Exception as e:
        return 500, {"error": f"Backend error: {e}"}

    system = _build_system_prompt(persona)
    tools = get_tools_for_anthropic()
    session_id = str(uuid.uuid4())
    persona_key = persona_name.lower().replace(" ", "")

    _chat_sessions[session_id] = {
        "backend": backend,
        "messages": [],
        "system": system,
        "tools": tools,
        "persona_name": persona.name,
        "persona_key": persona_key,
        "pending_confirm": None,
    }

    return 200, {
        "session_id": session_id,
        "persona": persona.name,
        "model": model,
    }


def _handle_chat_message(body):
    """Send a user message and run the tool loop."""
    sid = body.get("session_id")
    text = body.get("text", "").strip()
    if not sid or sid not in _chat_sessions:
        return 400, {"error": "Invalid or expired session_id"}
    if not text:
        return 400, {"error": "Message text is required"}

    session = _chat_sessions[sid]
    session["pending_confirm"] = None
    session["messages"].append({"role": "user", "content": text})

    try:
        result = _run_web_tool_loop(session)
        return 200, result
    except Exception as e:
        traceback.print_exc()
        return 500, {"error": str(e)}


def _handle_chat_confirm(body):
    """Handle user confirmation for pending tool calls."""
    sid = body.get("session_id")
    approved = body.get("approved", False)
    if not sid or sid not in _chat_sessions:
        return 400, {"error": "Invalid or expired session_id"}

    session = _chat_sessions[sid]
    pending = session.get("pending_confirm")
    if not pending:
        return 400, {"error": "No pending confirmation"}

    tool_blocks = pending["tool_blocks"]
    confirm_blocks = pending["confirm_blocks"]
    deferred_ids = pending["deferred_ids"]
    response = pending["response"]
    session["pending_confirm"] = None
    persona_key = session.get("persona_key", "")

    confirm_ids = {b.id for b in confirm_blocks}
    try:
        tool_results = _execute_tool_blocks(tool_blocks, confirm_ids, approved, persona_key)
    except Exception as e:
        traceback.print_exc()
        return 500, {"error": str(e)}

    for block in response.content:
        if block.type == "tool_use" and block.id in deferred_ids:
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps({"status": "deferred", "error": "Deferred: only one write tool type per turn."}),
            })

    session["messages"].append({"role": "user", "content": tool_results})

    try:
        result = _run_web_tool_loop(session)
        return 200, result
    except Exception as e:
        traceback.print_exc()
        return 500, {"error": str(e)}


def _handle_chat_settings(body):
    """Save API key to .env file."""
    api_key = body.get("api_key", "").strip()
    if not api_key:
        return 400, {"error": "api_key is required"}

    root = os.environ.get("ICONFUCIUS_ROOT", "")
    env_path = os.path.join(root, ".env") if root else ".env"

    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    lines.append(f"ANTHROPIC_API_KEY={api_key}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"ANTHROPIC_API_KEY={api_key}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)

    os.environ["ANTHROPIC_API_KEY"] = api_key
    return 200, {"status": "ok", "message": "API key saved"}


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_response(handler, status, data):
    handler.send_response(status)
    handler._cors_headers()
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps(data, default=str).encode())


# ---------------------------------------------------------------------------
# Wallet / setup handlers
# ---------------------------------------------------------------------------

def _handle_wallet_backup(handler):
    """Stream the wallet PEM file as a download."""
    _sync_project_root()
    root = os.environ.get("ICONFUCIUS_ROOT", "")
    pem_path = os.path.join(root, ".wallet", "identity-private.pem") if root else ".wallet/identity-private.pem"
    if not os.path.exists(pem_path):
        _json_response(handler, 404, {"error": "Wallet file not found. Create a wallet first."})
        return
    with open(pem_path, "rb") as f:
        data = f.read()
    handler.send_response(200)
    handler._cors_headers()
    handler.send_header("Content-Type", "application/x-pem-file")
    handler.send_header("Content-Disposition", 'attachment; filename="iconfucius-identity-private.pem"')
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _chdir_to_root():
    """chdir to ICONFUCIUS_ROOT so SDK finds config/wallet files."""
    root = os.environ.get("ICONFUCIUS_ROOT", "")
    if root and os.path.isdir(root):
        os.chdir(root)


def _handle_wallet_info(*, bypass_cache=False):
    if not _HAS_ICONFUCIUS:
        return 503, {"error": "iconfucius SDK not installed. Run: pip install iconfucius"}
    if not bypass_cache:
        cached = _cache_get("wallet_info")
        if cached:
            return cached
    _sync_project_root()
    _chdir_to_root()
    result = run_wallet_balance(ckbtc_minter=True)
    if result is None:
        try:
            from iconfucius.config import get_pem_file
            expected = get_pem_file()
        except Exception:
            expected = os.path.join(os.environ.get("ICONFUCIUS_ROOT", ""), ".wallet", "identity-private.pem")
        return 404, {
            "error": "Wallet not found. Run: iconfucius wallet create",
            "expected_wallet_path": expected,
            "project_root": os.environ.get("ICONFUCIUS_ROOT", ""),
        }
    btc_usd = result.get("btc_usd_rate")
    balance = result.get("balance_sats", 0)
    pending = result.get("pending_sats", 0)
    resp = 200, {
        "principal": result.get("principal", ""),
        "btc_address": result.get("btc_address", ""),
        "balance_sats": balance,
        "balance_usd": (balance / 1e8) * btc_usd if btc_usd else None,
        "pending_sats": pending,
        "pending_usd": (pending / 1e8) * btc_usd if btc_usd else None,
        "btc_usd_rate": btc_usd,
    }
    _cache_set("wallet_info", resp)
    return resp


def _handle_wallet_balances(*, bypass_cache=False):
    if not _HAS_ICONFUCIUS:
        return 503, {"error": "iconfucius SDK not installed. Run: pip install iconfucius"}
    if not bypass_cache:
        cached = _cache_get("wallet_balances")
        if cached:
            return cached
    _sync_project_root()
    _chdir_to_root()
    bot_names = get_bot_names()
    result = run_all_balances(bot_names=bot_names, ckbtc_minter=True)
    if result is None:
        return 404, {"error": "Wallet not found. Run: iconfucius wallet create"}
    btc_usd = result.get("btc_usd_rate") if "btc_usd_rate" in result else None
    if btc_usd is None:
        try:
            btc_usd = get_btc_to_usd_rate()
        except Exception:
            pass
    wallet_sats = result.get("wallet_ckbtc_sats", 0)
    pending_sats = result.get("wallet_pending_sats", 0)
    bots = []
    for b in result.get("bots", []):
        bot_entry = {
            "name": b["name"], "principal": b.get("principal", ""),
            "odin_sats": b.get("odin_sats", 0),
            "has_odin_account": b.get("has_odin_account", False),
            "tokens": b.get("tokens", []),
        }
        if btc_usd:
            bot_entry["odin_usd"] = (b.get("odin_sats", 0) / 1e8) * btc_usd
        bots.append(bot_entry)
    totals = result.get("totals", {})
    resp = 200, {
        "wallet": {
            "principal": result.get("wallet_principal", ""),
            "btc_address": result.get("wallet_btc_address", ""),
            "ckbtc_sats": wallet_sats,
            "ckbtc_usd": (wallet_sats / 1e8) * btc_usd if btc_usd else None,
            "pending_sats": pending_sats,
        },
        "bots": bots,
        "totals": {
            "odin_sats": totals.get("odin_sats", 0),
            "token_value_sats": totals.get("token_value_sats", 0),
            "wallet_sats": totals.get("wallet_sats", 0),
            "portfolio_sats": totals.get("portfolio_sats", 0),
            "portfolio_usd": (totals.get("portfolio_sats", 0) / 1e8) * btc_usd if btc_usd else None,
        },
        "btc_usd_rate": btc_usd,
    }
    _cache_set("wallet_balances", resp)
    return resp


def _require_sdk():
    if not _HAS_ICONFUCIUS:
        return 503, {"error": "iconfucius SDK not installed. Run: pip install -e agent/"}
    return None


def _handle_setup_status():
    err = _require_sdk()
    if err:
        return err
    _sync_project_root()
    _chdir_to_root()
    return 200, execute_tool("setup_status", {})


def _handle_action_init(body):
    err = _require_sdk()
    if err:
        return err
    _sync_project_root()
    _chdir_to_root()
    num_bots = body.get("num_bots", 3)
    force = body.get("force", False)
    project_root = os.environ.get("ICONFUCIUS_ROOT", os.getcwd())
    old_cwd = os.getcwd()
    try:
        os.chdir(project_root)
        result = execute_tool("init", {"num_bots": num_bots, "force": force})
    finally:
        os.chdir(old_cwd)
    if result.get("status") == "error":
        # Even on error, check if config actually exists on disk (covers
        # "already exists" case where the CLI exits non-zero but everything
        # is fine).
        try:
            from iconfucius.config import find_config, load_config
            if find_config() is not None:
                load_config(reload=True)
                return 200, {"status": "ok", "display": "Project already initialized."}
        except Exception:
            pass
        return 400, result
    from iconfucius.config import load_config
    load_config(reload=True)
    return 200, result


def _handle_action_wallet_create(body):
    err = _require_sdk()
    if err:
        return err
    _sync_project_root()
    _chdir_to_root()
    force = body.get("force", False)
    result = execute_tool("wallet_create", {"force": force})
    if result.get("status") == "error":
        # Check if wallet PEM actually exists on disk despite the error.
        try:
            from iconfucius.config import get_pem_file
            from pathlib import Path
            if Path(get_pem_file()).exists():
                return 200, {"status": "ok", "display": "Wallet already exists."}
        except Exception:
            pass
        return 400, result
    return 200, result


def _handle_action_set_bots(body):
    err = _require_sdk()
    if err:
        return err
    num_bots = body.get("num_bots")
    if num_bots is None:
        return 400, {"status": "error", "error": "'num_bots' is required."}
    result = execute_tool("set_bot_count", {"num_bots": num_bots, "force": body.get("force", False)})
    if result.get("status") == "error":
        return 400, result
    return 200, result


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class ProxyHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        routes = {
            "/api/setup/init": _handle_action_init,
            "/api/setup/wallet-create": _handle_action_wallet_create,
            "/api/setup/set-bots": _handle_action_set_bots,
            "/api/chat/start": _handle_chat_start,
            "/api/chat/message": _handle_chat_message,
            "/api/chat/confirm": _handle_chat_confirm,
            "/api/chat/settings": _handle_chat_settings,
        }

        handler = routes.get(path)
        if handler is None:
            _json_response(self, 404, {"error": "Not found"})
            return

        try:
            body = self._read_json_body()
            status, data = handler(body)
        except Exception as e:
            traceback.print_exc()
            status, data = 500, {"error": str(e)}
        _json_response(self, status, data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        refresh = "refresh" in parsed.query

        if path == "/api/wallet/backup":
            try:
                _handle_wallet_backup(self)
            except Exception as e:
                traceback.print_exc()
                _json_response(self, 500, {"error": str(e)})
            return

        if path == "/api/wallet/info":
            try:
                status, data = _handle_wallet_info(bypass_cache=refresh)
            except Exception as e:
                traceback.print_exc()
                status, data = 500, {"error": str(e)}
            _json_response(self, status, data)
            return

        if path == "/api/wallet/balances":
            try:
                status, data = _handle_wallet_balances(bypass_cache=refresh)
            except Exception as e:
                traceback.print_exc()
                status, data = 500, {"error": str(e)}
            _json_response(self, status, data)
            return

        if path == "/api/wallet/status":
            data = {"sdk_available": _HAS_ICONFUCIUS,
                    "project_root": os.environ.get("ICONFUCIUS_ROOT", "")}
            if _HAS_ICONFUCIUS:
                try:
                    _, setup = _handle_setup_status()
                    data.update(setup)
                except Exception:
                    pass
            _json_response(self, 200, data)
            return

        if not path.startswith("/api/odin"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        odin_path = path.replace("/api/odin", "", 1) or "/"
        query = f"?{parsed.query}" if parsed.query else ""
        url = f"{ODIN_API}{odin_path}{query}"

        try:
            resp = requests.get(
                url, impersonate="chrome",
                headers={"Accept": "application/json"}, timeout=15,
            )
            self.send_response(resp.status_code)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp.content)
        except Exception as e:
            _json_response(self, 502, {"error": str(e)})

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        status = args[1] if len(args) > 1 else ""
        print(f"  {args[0]} -> {status}" if args else fmt)


def main():
    server = HTTPServer(("127.0.0.1", PORT), ProxyHandler)
    print(f"IConfucius Dashboard Proxy on http://localhost:{PORT}")
    print(f"  Odin.fun API:  /api/odin/* -> {ODIN_API}/*")
    print(f"  Wallet info:   /api/wallet/info")
    print(f"  Bot balances:  /api/wallet/balances")
    print(f"  SDK status:    /api/wallet/status")
    print(f"  Chat:          /api/chat/start, message, confirm, settings")
    print(f"  SDK available: {_HAS_ICONFUCIUS}")
    print(f"  Project root:  {os.environ.get('ICONFUCIUS_ROOT', 'not set')}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping proxy.")
        server.server_close()


if __name__ == "__main__":
    main()
