"""Interactive chat using Rasa CALM backend via SSE channel.

The CLI is a pure HTTP client: POST a user message to the Rasa SSE
endpoint, read the event stream.  Same code path for local development
(Rasa runs as a subprocess) and AWS (Rasa runs remotely).
"""

import asyncio
import json
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path

import httpx

from iconfucius import __version__
from iconfucius.cli.chat import (
    _Spinner,
    _check_pypi_version,
    _handle_upgrade,
    _run_with_spinner,
)
from iconfucius.skills.executor import execute_tool

_log = logging.getLogger(__name__)

# Inside installed package: site-packages/iconfucius/rasa/
_RASA_DIR_PKG = Path(__file__).resolve().parent.parent / "rasa"
# Editable install / dev: agent/src/iconfucius/rasa/
_RASA_DIR_DEV = Path(__file__).resolve().parent.parent.parent.parent / "rasa"


def _find_rasa_dir() -> Path:
    """Locate the rasa/ directory, checking multiple candidate paths."""
    candidates = [
        _RASA_DIR_PKG,
        _RASA_DIR_DEV,
        Path.cwd() / "rasa",
        Path.cwd() / "agent" / "rasa",
    ]
    for p in candidates:
        if (p / "endpoints.yml").exists():
            return p
    raise FileNotFoundError(
        "Cannot find Rasa project directory (expected agent/rasa/ with endpoints.yml)"
    )


# ------------------------------------------------------------------
# Rasa subprocess management
# ------------------------------------------------------------------

def _start_rasa_server(
    rasa_dir: Path, port: int, mcp_url: str,
    llm_provider: str, llm_model: str,
    reph_provider: str, reph_model: str,
    sub_provider: str, sub_model: str,
    debug: bool,
) -> subprocess.Popen:
    """Start Rasa as a subprocess with SSE channel."""
    env = {
        **os.environ,
        "ICONFUCIUS_MCP_URL": mcp_url,
        "RASA_LLM_PROVIDER": llm_provider,
        "RASA_LLM_MODEL": llm_model,
        "RASA_REPHRASER_PROVIDER": reph_provider,
        "RASA_REPHRASER_MODEL": reph_model,
        "RASA_SUBAGENT_PROVIDER": sub_provider,
        "RASA_SUBAGENT_MODEL": sub_model,
        "RASA_SUBAGENT_TOOL_TIMEOUT": os.environ.get(
            "RASA_SUBAGENT_TOOL_TIMEOUT", "120"
        ),
    }
    # Langfuse tracing: forward env vars with safe defaults so Rasa
    # doesn't crash when the user hasn't configured Langfuse yet.
    env.setdefault("LANGFUSE_HOST", "http://localhost:12526")
    env.setdefault("LANGFUSE_PUBLIC_KEY", "placeholder")
    env.setdefault("LANGFUSE_PRIVATE_KEY", "placeholder")


    if not debug:
        env["LOG_LEVEL"] = "ERROR"
        env["SANIC_LOG_LEVEL"] = "ERROR"
        env.setdefault("LLM_API_HEALTH_CHECK", "false")

    cmd = [
        "rasa", "run", "--enable-api",
        "--port", str(port),
        "--credentials", "credentials.yml",
        "--endpoints", "endpoints.yml",
    ]
    if debug:
        cmd.append("--debug")

    return subprocess.Popen(
        cmd,
        cwd=str(rasa_dir),
        env=env,
        stdout=None if debug else subprocess.PIPE,
        stderr=None if debug else subprocess.PIPE,
    )


async def _wait_for_rasa_ready(rasa_url: str, timeout: int = 120, interval: float = 0.5) -> None:
    """Poll the SSE health endpoint until Rasa is ready."""
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(f"{rasa_url}/webhooks/sse/")
                if r.status_code == 200:
                    return
            except httpx.ConnectError:
                pass
            await asyncio.sleep(interval)
    raise RuntimeError(f"Rasa server not ready after {timeout}s")


# ------------------------------------------------------------------
# SSE streaming
# ------------------------------------------------------------------

async def _sse_stream(client: httpx.AsyncClient, url: str, sender_id: str, text: str):
    """POST a message and yield SSE events from the response stream."""
    async with client.stream(
        "POST", url, json={"message": text, "sender_id": sender_id},
    ) as response:
        event_type = None
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                if event_type == "custom" and data.get("type") == "tool_status":
                    yield {"type": "tool_status", "text": data["text"]}
                elif event_type == "bot_uttered":
                    yield {"type": "bot_uttered", **data}
                event_type = None


async def _send_sse_message(
    client: httpx.AsyncClient, url: str, sender_id: str, text: str,
    spinner_label: str = "",
) -> list[str]:
    """Send a message via SSE and collect all bot_uttered responses."""
    responses = []
    with _Spinner(spinner_label) as sp:
        async for event in _sse_stream(client, url, sender_id, text):
            if event["type"] == "tool_status":
                sp.update(event["text"])
            elif event["type"] == "bot_uttered" and event.get("text"):
                responses.append(event["text"])
    return responses


# ------------------------------------------------------------------
# Async chat loop
# ------------------------------------------------------------------

async def _run_chat_rasa_async(
    persona_name: str, bot_name: str, verbose: bool, debug: bool,
) -> None:
    print("\033[2mLoading IConfucius...\033[0m", end="", flush=True)

    from iconfucius.config import get_rasa_model_group, set_verbose
    from iconfucius.persona import PersonaNotFoundError, load_persona

    set_verbose(verbose)

    try:
        persona = load_persona(persona_name)
    except PersonaNotFoundError as e:
        print(f"Error: {e}")
        return

    # Resolve model groups from config
    llm_provider, llm_model = get_rasa_model_group(
        "command_generator", "anthropic", "claude-opus-4-6",
    )
    reph_provider, reph_model = get_rasa_model_group(
        "response_rephraser", "anthropic", "claude-opus-4-6",
    )
    sub_provider, sub_model = get_rasa_model_group(
        "sub_agent", "anthropic", "claude-opus-4-6",
    )

    # 1. Start MCP server (asyncio task, same process)
    from iconfucius.mcp_server import MCP_DEFAULT_PORT, start_mcp_server

    mcp_port = int(os.environ.get("ICONFUCIUS_MCP_PORT", str(MCP_DEFAULT_PORT)))
    mcp_url = f"http://127.0.0.1:{mcp_port}/mcp"
    os.environ.setdefault("ICONFUCIUS_MCP_URL", mcp_url)

    mcp_task = None
    mcp_uv_server = None
    rasa_process = None

    try:
        try:
            mcp_task, mcp_uv_server = await start_mcp_server(port=mcp_port)
        except SystemExit:
            return

        # 2. Start Rasa server (subprocess) -- skip if RASA_URL provided
        rasa_url = os.environ.get("RASA_URL")
        # Clear the "Loading IConfucius..." line regardless of local/remote Rasa
        print("\r\033[K", end="", flush=True)
        if not rasa_url:
            try:
                rasa_dir = _find_rasa_dir()
            except FileNotFoundError as e:
                print(f"Error: {e}")
                return

            rasa_port = int(os.environ.get("RASA_PORT", "5005"))
            rasa_url = f"http://127.0.0.1:{rasa_port}"

            with _Spinner("Starting Rasa server..."):
                rasa_process = _start_rasa_server(
                    rasa_dir, rasa_port, mcp_url,
                    llm_provider, llm_model,
                    reph_provider, reph_model,
                    sub_provider, sub_model,
                    debug,
                )
                try:
                    await _wait_for_rasa_ready(rasa_url)
                except RuntimeError as e:
                    print(f"\nError: {e}")
                    # Terminate first, then drain stderr — stderr.read() on a
                    # live subprocess waits for EOF and can hang indefinitely.
                    if rasa_process is not None:
                        rasa_process.terminate()
                        try:
                            _out, err = rasa_process.communicate(timeout=5)
                        except subprocess.TimeoutExpired:
                            rasa_process.kill()
                            _out, err = rasa_process.communicate()
                        if err:
                            print(err.decode(errors="replace")[-2000:])
                    return

        sse_url = f"{rasa_url}/webhooks/sse/webhook"
        sender_id = uuid.uuid4().hex

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            # 3. Startup greeting — triggers greeting flow
            greeting_responses = await _send_sse_message(
                client, sse_url, sender_id, "hi",
                spinner_label=f"{persona.name} is thinking...",
            )
            if greeting_responses:
                print(f"\n{greeting_responses[0]}\n")

            # 4. Show wallet balance at startup
            setup = execute_tool("setup_and_operational_status", {})
            if setup.get("wallet_exists"):
                from iconfucius.cli.balance import run_wallet_balance
                try:
                    wallet_data = _run_with_spinner(
                        "Checking wallet...", run_wallet_balance,
                        ckbtc_minter=False,
                    )
                    if wallet_data:
                        display_text = wallet_data.pop("_display", "")
                        if display_text:
                            print(f"{display_text}\n")
                except Exception:
                    pass

            # 5. Status line
            print(f"\033[2miconfucius v{__version__} · Rasa Pro CALM · exit to quit · Ctrl+C to interrupt\033[0m")
            print(f"\033[2mLLM: {llm_provider}/{llm_model} · rephraser: {reph_provider}/{reph_model} · sub-agent: {sub_provider}/{sub_model}\033[0m")
            _lf_active = os.environ.get("LANGFUSE_PUBLIC_KEY", "placeholder") != "placeholder"
            _lf_host = os.environ.get("LANGFUSE_HOST", "http://localhost:12526")
            _lf_label = f"Langfuse: {_lf_host}" if _lf_active else "Langfuse: off"
            _rasa_loc = "local" if rasa_process else "remote"
            print(f"\033[2mRasa: {rasa_url} ({_rasa_loc}) · MCP: http://127.0.0.1:{mcp_port}/mcp · {_lf_label}\033[0m")

            # Check PyPI for newer version
            latest_version, _release_notes = _check_pypi_version()
            if latest_version:
                print(f"\033[2mUpdate available: v{latest_version} · /upgrade to install\033[0m")
                from iconfucius.skills.executor import _update_cache
                _update_cache["latest_version"] = latest_version
                _update_cache["release_notes"] = _release_notes
            print()

            # Enable readline for input history
            try:
                import readline  # noqa: F401
            except ImportError:
                pass

            def _prompt_banner() -> None:
                print("\033[2m" + "-" * 60 + "\033[0m")
                if latest_version:
                    print(f"\033[2mv{latest_version} available · /upgrade to install\033[0m")
                    print("\033[2m" + "-" * 60 + "\033[0m")

            # Suppress uvicorn ASGI teardown errors on Ctrl+C
            logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)
            logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)

            # 6. Chat loop
            while True:
                try:
                    _prompt_banner()
                    user_input = await asyncio.to_thread(
                        input, f"\033[2mv{__version__}\033[0m > ",
                    )
                    user_input = user_input.strip()
                except (KeyboardInterrupt, EOFError):
                    print("\n\nMay your path be wise.")
                    break

                if user_input.lower() == "/upgrade":
                    _handle_upgrade()
                    continue

                if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                    print()
                    break

                if not user_input:
                    continue

                try:
                    responses = await _send_sse_message(
                        client, sse_url, sender_id, user_input,
                        spinner_label=f"{persona.name} is thinking...",
                    )
                    for text in responses:
                        print(f"\n{text}")
                    if responses:
                        print()
                except KeyboardInterrupt:
                    print("\n\nInterrupted.")
                    continue
                except Exception as e:
                    print(f"\nError: {e}\n")
                    continue

    finally:
        if rasa_process is not None:
            rasa_process.terminate()
            try:
                rasa_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                rasa_process.kill()

        if mcp_uv_server is not None:
            mcp_uv_server.should_exit = True
        if mcp_task is not None:
            mcp_task.cancel()

        # Force-exit to avoid hanging on the daemon thread still blocked
        # in input().  All subprocesses have been terminated above.
        os._exit(0)


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def run_chat_rasa(
    persona_name: str, bot_name: str, verbose: bool = False, debug: bool = False,
) -> None:
    """Run interactive chat using the Rasa CALM backend.

    Args:
        persona_name: Name of the persona to load.
        bot_name: Default bot for trading context.
        verbose: Show verbose output.
        debug: Show Rasa debug logs on screen.
    """
    asyncio.run(
        _run_chat_rasa_async(persona_name, bot_name, verbose, debug)
    )
