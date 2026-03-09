"""Interactive chat using Rasa CALM backend (in-process agent)."""

import asyncio
import logging
import sys
from pathlib import Path

from iconfucius import __version__
from iconfucius.cli.chat import (
    QUOTE_TOPICS,
    _Spinner,
    _check_pypi_version,
    _handle_upgrade,
    _run_with_spinner,
)
from iconfucius.skills.executor import execute_tool

# Rasa project directory (agent/rasa/ relative to the repo root)
_RASA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "rasa"


def _find_rasa_dir() -> Path:
    """Locate the rasa/ directory, checking multiple candidate paths."""
    candidates = [
        _RASA_DIR,
        Path.cwd() / "rasa",
        Path.cwd() / "agent" / "rasa",
    ]
    for p in candidates:
        if (p / "endpoints.yml").exists():
            return p
    raise FileNotFoundError(
        "Cannot find Rasa project directory (expected agent/rasa/ with endpoints.yml)"
    )


async def _load_rasa_agent(rasa_dir: Path, debug: bool = False):
    """Load the Rasa agent in-process with actions_module support."""
    import os

    if debug:
        os.environ["LOG_LEVEL"] = "DEBUG"
        os.environ.setdefault("LLM_API_HEALTH_CHECK", "false")
    else:
        # Suppress verbose Rasa debug/info logging
        os.environ["LOG_LEVEL"] = "ERROR"
        os.environ.setdefault("LLM_API_HEALTH_CHECK", "false")
        logging.getLogger("rasa").setLevel(logging.ERROR)
        logging.getLogger("matplotlib").setLevel(logging.ERROR)
        logging.getLogger().setLevel(logging.ERROR)

        # Configure structlog to filter debug/info messages
        import structlog
        from rasa.utils.log_utils import configure_structlog
        configure_structlog(logging.ERROR)

    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

    # Make the actions package importable
    if str(rasa_dir) not in sys.path:
        sys.path.insert(0, str(rasa_dir))

    from rasa.core.agent import load_agent
    from rasa.core.config.available_endpoints import AvailableEndpoints
    from rasa.core.config.configuration import Configuration
    from rasa.model import get_local_model

    endpoints_path = rasa_dir / "endpoints.yml"
    Configuration.initialise_endpoints(endpoints_path)

    endpoints = AvailableEndpoints.read_endpoints(endpoints_path)
    model_path = get_local_model(rasa_dir / "models")

    return await load_agent(model_path=model_path, endpoints=endpoints)


async def _handle_message(agent, text: str, sender_id: str) -> list[str]:
    """Send a message to the Rasa agent and return bot response texts."""
    responses = await agent.handle_text(text, sender_id=sender_id)
    return [r.get("text", "") for r in (responses or []) if r.get("text")]


async def _start_goodbye_task(agent, persona, sender_id: str):
    """Schedule goodbye generation as a background asyncio task."""
    async def _generate():
        try:
            responses = await _handle_message(agent, persona.goodbye_prompt, sender_id)
            return responses[0] if responses else "May your path be wise."
        except Exception:
            return "May your path be wise."
    return asyncio.create_task(_generate())


def _get_goodbye(goodbye_task) -> str:
    """Return goodbye if background task completed, else static fallback."""
    if goodbye_task is not None and goodbye_task.done():
        try:
            return goodbye_task.result()
        except Exception:
            pass
    return "May your path be wise."


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
    from iconfucius.config import set_verbose
    set_verbose(verbose)

    from iconfucius.persona import PersonaNotFoundError, load_persona
    try:
        persona = load_persona(persona_name)
    except PersonaNotFoundError as e:
        print(f"Error: {e}")
        return

    # Load Rasa agent
    try:
        rasa_dir = _find_rasa_dir()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        with _Spinner("Loading Rasa agent..."):
            agent = loop.run_until_complete(_load_rasa_agent(rasa_dir, debug=debug))
    except Exception as e:
        print(f"\nError loading Rasa agent: {e}")
        return

    if not agent.is_ready():
        print("Error: Rasa agent failed to load. Run 'rasa train' first.")
        return

    sender_id = f"cli-{persona_name}"

    # Startup greeting & goodbye — route through Rasa chitchat (model from endpoints.yml)
    from iconfucius.cli.chat import _get_language_code
    import random

    lang = _get_language_code()
    entry = random.choice(QUOTE_TOPICS)

    try:
        with _Spinner(f"{persona.name} is thinking..."):
            greeting_prompt = persona.greeting_prompt.format(
                icon=entry["icon"], topic=entry[lang],
            )
            greeting_responses = loop.run_until_complete(
                _handle_message(agent, greeting_prompt, sender_id)
            )

        greeting = greeting_responses[0] if greeting_responses else ""
        if not greeting:
            greeting = f"{entry['icon']} {persona.name} — {entry[lang]}"
    except Exception:
        greeting = f"{entry['icon']} {persona.name} — {entry[lang]}"

    print(f"\n{greeting}\n")

    # Schedule goodbye generation in background (non-blocking)
    goodbye_task = loop.run_until_complete(
        _start_goodbye_task(agent, persona, sender_id)
    )

    # Show wallet balance at startup (same as non-rasa chat)
    setup = execute_tool("setup_and_operational_status", {})
    if setup.get("wallet_exists"):
        from iconfucius.cli.balance import run_wallet_balance
        try:
            wallet_data = _run_with_spinner(
                "Checking wallet...", run_wallet_balance, ckbtc_minter=False,
            )
            if wallet_data:
                display_text = wallet_data.pop("_display", "")
                if display_text:
                    print(f"{display_text}\n")
        except Exception:
            pass

    print(f"\033[2miconfucius v{__version__} · Rasa Pro CALM · exit to quit · Ctrl+C to interrupt\033[0m")

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
        print("\033[2m" + "─" * 60 + "\033[0m")
        if latest_version:
            print(f"\033[2mv{latest_version} available · /upgrade to install\033[0m")
            print("\033[2m" + "─" * 60 + "\033[0m")

    while True:
        try:
            _prompt_banner()
            user_input = input(f"\033[2mv{__version__}\033[0m > ").strip()
        except (KeyboardInterrupt, EOFError):
            goodbye = _get_goodbye(goodbye_task)
            print(f"\n\n{goodbye}")
            break

        if user_input.lower() == "/upgrade":
            _handle_upgrade()
            continue

        if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
            goodbye = _get_goodbye(goodbye_task)
            print(f"\n{goodbye}")
            break

        if not user_input:
            continue

        try:
            with _Spinner(f"{persona.name} is thinking..."):
                responses = loop.run_until_complete(
                    _handle_message(agent, user_input, sender_id)
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

    loop.close()
