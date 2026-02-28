"""Interactive chat command for trading personas."""

import itertools
import json
import locale
import random
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from urllib.request import urlopen

from iconfucius import __version__
from iconfucius.ai import APIKeyMissingError, create_backend
from iconfucius.persona import DEFAULT_MODEL, Persona, PersonaNotFoundError, load_persona
from iconfucius.skills.definitions import get_tool_metadata, get_tools_for_anthropic
from iconfucius.skills.executor import execute_tool

# Topics and icons for IConfucius startup quotes (from IConfucius agent)
QUOTE_TOPICS = [
    {"cn": "咖啡", "icon": "☕️", "en": "Coffee"},
    {"cn": "加密货币", "icon": "📈", "en": "Cryptocurrency"},
    {"cn": "天空", "icon": "🌤️", "en": "Sky"},
    {"cn": "花朵", "icon": "🌸", "en": "Flowers"},
    {"cn": "公正之神", "icon": "⚖️", "en": "Justice"},
    {"cn": "进步的颠覆性本质", "icon": "🌱", "en": "The disruptive nature of progress"},
    {"cn": "修养", "icon": "🏋️", "en": "Discipline"},
    {"cn": "耐心", "icon": "🕰️", "en": "Patience"},
    {"cn": "和谐", "icon": "☯️", "en": "Harmony"},
    {"cn": "礼仪", "icon": "🎎", "en": "Ritual and Courtesy"},
    {"cn": "诚信", "icon": "🤝", "en": "Integrity"},
    {"cn": "学习", "icon": "📖", "en": "Lifelong Learning"},
    {"cn": "反思", "icon": "🪞", "en": "Reflection"},
    {"cn": "顺其自然", "icon": "🍃", "en": "Acceptance of Nature"},
    {"cn": "简朴", "icon": "🍂", "en": "Simplicity"},
    {"cn": "平衡", "icon": "⚖️", "en": "Balance"},
    {"cn": "信任", "icon": "🤠", "en": "Trust"},
    {"cn": "积累", "icon": "💰", "en": "Accumulation of Wealth"},
    {"cn": "投资", "icon": "💵", "en": "Investment"},
    {"cn": "风险", "icon": "⚠️", "en": "Risk"},
    {"cn": "创新", "icon": "💡", "en": "Innovation"},
    {"cn": "适应", "icon": "🌌", "en": "Adaptation"},
    {"cn": "坚韧", "icon": "🗿", "en": "Resilience"},
    {"cn": "洞察", "icon": "🔍", "en": "Insight"},
    {"cn": "目标", "icon": "🎯", "en": "Goal Setting"},
    {"cn": "自由", "icon": "🌈", "en": "Freedom"},
    {"cn": "责任", "icon": "👷", "en": "Responsibility"},
    {"cn": "时间", "icon": "⏳", "en": "Time Management"},
    {"cn": "财富", "icon": "💸", "en": "Wealth"},
    {"cn": "节制", "icon": "🏋️", "en": "Moderation"},
    {"cn": "虚拟资产", "icon": "💹", "en": "Digital Assets"},
    {"cn": "共识", "icon": "🔀", "en": "Consensus"},
    {"cn": "去中心化", "icon": "🛠️", "en": "Decentralization"},
    {"cn": "透明", "icon": "👀", "en": "Transparency"},
    {"cn": "智慧", "icon": "🤔", "en": "Wisdom"},
    {"cn": "信用", "icon": "📈", "en": "Credit"},
    {"cn": "安全", "icon": "🔒", "en": "Security"},
    {"cn": "机遇", "icon": "🍀", "en": "Opportunity"},
    {"cn": "成长", "icon": "🌱", "en": "Growth"},
    {"cn": "合作", "icon": "🤝", "en": "Collaboration"},
    {"cn": "选择", "icon": "🔀", "en": "Choice"},
    {"cn": "敬业", "icon": "💼", "en": "Professionalism"},
    {"cn": "审慎", "icon": "📊", "en": "Prudence"},
    {"cn": "理性", "icon": "🤖", "en": "Rationality"},
    {"cn": "契约", "icon": "📑", "en": "Contract"},
    {"cn": "区块链", "icon": "🛠️", "en": "Blockchain"},
    {"cn": "匿名", "icon": "🔎", "en": "Anonymity"},
    {"cn": "竞争", "icon": "🏆", "en": "Competition"},
    {"cn": "领导", "icon": "👑", "en": "Leadership"},
    {"cn": "市场", "icon": "🏢", "en": "Market"},
    {"cn": "社区", "icon": "🏞️", "en": "Community"},
    {"cn": "自我实现", "icon": "🌟", "en": "Self-Actualization"},
    {"cn": "善良", "icon": "💖", "en": "Kindness"},
    {"cn": "信念", "icon": "✨", "en": "Belief"},
    {"cn": "忠诚", "icon": "🦁", "en": "Loyalty"},
    {"cn": "美德", "icon": "🌿", "en": "Virtue"},
    {"cn": "远见", "icon": "🔮", "en": "Vision"},
    {"cn": "成就", "icon": "🌟", "en": "Achievement"},
    {"cn": "共享", "icon": "👥", "en": "Sharing"},
    {"cn": "交流", "icon": "📢", "en": "Communication"},
    {"cn": "执行力", "icon": "🔄", "en": "Execution"},
    {"cn": "算法", "icon": "🔢", "en": "Algorithm"},
    {"cn": "冷静", "icon": "🌧️", "en": "Calmness"},
    {"cn": "奋斗", "icon": "⚔️", "en": "Struggle"},
    {"cn": "信号", "icon": "📶", "en": "Signal"},
    {"cn": "贪婪", "icon": "💶", "en": "Greed"},
    {"cn": "慈善", "icon": "💜", "en": "Charity"},
    {"cn": "艺术", "icon": "🎨", "en": "Art"},
    {"cn": "科技", "icon": "📱", "en": "Technology"},
    {"cn": "策略", "icon": "🔫", "en": "Strategy"},
    {"cn": "耐力", "icon": "🌼", "en": "Endurance"},
    {"cn": "梦想", "icon": "🌟", "en": "Dreams"},
    {"cn": "节奏", "icon": "🎵", "en": "Rhythm"},
    {"cn": "健康", "icon": "🏥", "en": "Health"},
    {"cn": "家庭", "icon": "🏡", "en": "Family"},
    {"cn": "教育", "icon": "🎓", "en": "Education"},
    {"cn": "旅行", "icon": "🛰", "en": "Travel"},
    {"cn": "幸福", "icon": "🎉", "en": "Happiness"},
    {"cn": "机密", "icon": "🔒", "en": "Confidentiality"},
    {"cn": "原则", "icon": "🔄", "en": "Principles"},
    {"cn": "法律", "icon": "🏛️", "en": "Law"},
    {"cn": "效率", "icon": "⏳", "en": "Efficiency"},
    {"cn": "反脆弱", "icon": "💪", "en": "Antifragility"},
    {"cn": "道德", "icon": "📍", "en": "Morality"},
    {"cn": "灵感", "icon": "💡", "en": "Inspiration"},
    {"cn": "公平", "icon": "⚖️", "en": "Fairness"},
    {"cn": "未来", "icon": "🌟", "en": "Future"},
    {"cn": "传统", "icon": "🎐", "en": "Tradition"},
    {"cn": "关系", "icon": "👨‍👨‍👦", "en": "Relationships"},
]




class _Spinner:
    """Animated spinner for the terminal.

    Captures a reference to the real stdout at creation time so the
    animation keeps running on the real terminal regardless of context.
    """

    def __init__(self, message: str = ""):
        """Initialize the instance."""
        self._message = message
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stdout = sys.stdout  # real terminal, before any redirect
        self._lock = threading.Lock()

    def update(self, message: str):
        """Update the spinner message (thread-safe)."""
        with self._lock:
            self._message = message

    def __enter__(self):
        """Enter the context manager."""
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        """Exit the context manager."""
        self._stop.set()
        if self._thread:
            self._thread.join()
        # Clear the spinner line
        self._stdout.write("\r\033[K")
        self._stdout.flush()

    def _spin(self):
        """Run the spinner animation loop."""
        frames = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        while not self._stop.is_set():
            with self._lock:
                msg = self._message
            self._stdout.write(f"\r\033[K{next(frames)} {msg}")
            self._stdout.flush()
            time.sleep(0.08)


def _run_with_spinner(label: str, func, *args, **kwargs):
    """Run *func* inside a spinner with progress/status callbacks wired up."""
    from iconfucius.cli.concurrent import set_progress_callback, set_status_callback

    with _Spinner(label) as sp:
        def _on_progress(done, total):
            w = 20
            filled = int(w * done / total)
            bar = "█" * filled + "░" * (w - filled)
            sp.update(f"{label} [{bar}] {done}/{total}")

        def _on_status(msg):
            sp.update(f"{label} {msg}")

        set_progress_callback(_on_progress)
        set_status_callback(_on_status)
        try:
            return func(*args, **kwargs)
        finally:
            set_progress_callback(None)
            set_status_callback(None)


class _CliWizardIO:
    """CLI implementation of WizardIO — input(), _Spinner, print()."""

    def prompt_yn(self, question: str, default_yes: bool = True) -> bool:
        suffix = "[Y/n]" if default_yes else "[y/N]"
        try:
            answer = input(f"  {question} {suffix} ").strip().lower()
            if default_yes:
                return answer not in ("n", "no")
            return answer in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            print()
            return False

    def run_with_feedback(self, label, func, *args, **kwargs):
        return _run_with_spinner(label, func, *args, **kwargs)

    def display(self, text):
        print(text)


def _get_language_code() -> str:
    """Detect system language. Returns 'cn' for Chinese, 'en' otherwise."""
    try:
        lang = locale.getlocale()[0] or ""
    except ValueError:
        lang = ""
    return "cn" if lang.startswith("zh") else "en"


def _prompt_increase_timeout() -> str:
    """Ask the user if they want to increase the AI timeout. Returns status message."""
    from iconfucius.config import get_ai_timeout
    current = get_ai_timeout()
    new_timeout = current * 2
    try:
        answer = input(
            f"\n  Current timeout: {current}s. "
            f"Increase to {new_timeout}s? [Y/n] "
        ).strip().lower()
    except (KeyboardInterrupt, EOFError):
        return ""
    if answer in ("n", "no"):
        return ""
    _persist_ai_timeout(new_timeout)
    return f"Timeout updated to {new_timeout}s."


def _toml_quote(value: str) -> str:
    """Escape a string for use as a TOML basic-string value (with quotes)."""
    return json.dumps(value)


def _persist_ai_timeout(timeout: int) -> None:
    """Add or update the timeout key in the [ai] section of iconfucius.toml.

    Reads the current [ai] config and re-writes it with the new timeout,
    preserving all other settings.
    """
    import re

    from iconfucius import config as cfg
    from iconfucius.config import AI_TIMEOUT_DEFAULT
    from iconfucius.persona import DEFAULT_MODEL

    config_path = cfg.find_config()
    if config_path is None:
        return

    ai = cfg.load_config().get("ai", {})

    # Build the new [ai] section content
    lines = ["[ai]"]
    api_type = ai.get("api_type", "")
    model = ai.get("model", "")
    base_url = ai.get("base_url", "")
    if api_type and api_type != "claude":
        lines.append(f"api_type = {_toml_quote(api_type)}")
    if model and model not in (DEFAULT_MODEL, "default"):
        lines.append(f"model = {_toml_quote(model)}")
    if base_url:
        lines.append(f"base_url = {_toml_quote(base_url)}")
    if timeout != AI_TIMEOUT_DEFAULT:
        lines.append(f"timeout = {timeout}")
    new_section = "\n".join(lines) + "\n" if len(lines) > 1 else ""

    content = config_path.read_text()

    if re.search(r'^\[ai\]', content, re.MULTILINE):
        if new_section:
            content = re.sub(
                r'^\[ai\]\n(?:[^\[]*?)(?=\n\[|\Z)',
                new_section,
                content,
                count=1,
                flags=re.MULTILINE | re.DOTALL,
            )
        else:
            content = re.sub(
                r'^\[ai\]\n(?:[^\[]*?)(?=\n\[|\Z)',
                '',
                content,
                count=1,
                flags=re.MULTILINE | re.DOTALL,
            )
    elif new_section:
        separator = "" if content.endswith("\n") else "\n"
        content += f'{separator}\n{new_section}'

    config_path.write_text(content)
    cfg.load_config(reload=True)


def _format_api_error(e: Exception) -> str:
    """Return a user-friendly error message for API errors."""
    msg = str(e).lower()
    if "credit balance" in msg or "purchase credits" in msg:
        return (
            "Your Anthropic API credit balance is too low.\n"
            "Add credits at: https://console.anthropic.com/settings/plans"
        )
    if "api_key" in msg or "auth" in msg:
        return "Authentication failed. Check your ANTHROPIC_API_KEY in .env"
    if "rate" in msg and "limit" in msg:
        return "Rate limited. Please wait a moment and try again."
    if "overloaded" in msg:
        return "The API is temporarily overloaded. Please try again."
    if "timed out" in msg or "timeout" in msg:
        return f"{e}\n" + _prompt_increase_timeout()
    return str(e)


def _generate_startup(backend, persona, lang: str) -> tuple[str, str]:
    """Generate greeting and goodbye in one API call.

    Uses the persona's greeting_prompt and goodbye_prompt templates.
    Returns (greeting_text, goodbye_text).
    """
    entry = random.choice(QUOTE_TOPICS)
    icon = entry["icon"]
    topic = entry[lang]

    # Build greeting prompt from persona template
    greeting_prompt = persona.greeting_prompt.format(icon=icon, topic=topic)

    # Combine greeting + goodbye into one request
    user_msg = (
        f"{greeting_prompt}\n\n"
        f"After a blank line, also add:\n"
        f"{persona.goodbye_prompt}"
    )

    messages = [{"role": "user", "content": user_msg}]
    response = backend.chat(messages, system=persona.system_prompt)

    # Split: everything before the last line is greeting, last line is goodbye
    lines = response.strip().split("\n")
    # Find the last non-empty line as goodbye
    goodbye = ""
    greeting_lines = []
    for line in reversed(lines):
        if line.strip() and not goodbye:
            goodbye = line.strip()
        else:
            greeting_lines.insert(0, line)
    greeting = "\n".join(greeting_lines).strip()

    return greeting, goodbye


def _persist_ai_config(api_type: str = "", model: str = "",
                       base_url: str = "",
                       keep_timeout: bool = False) -> None:
    """Write AI configuration to the [ai] section in iconfucius.toml.

    Replaces the entire [ai] section (or commented-out block) with the
    given settings.  Only writes keys that differ from defaults.

    Args:
        keep_timeout: If True, preserve any existing timeout setting.
    """
    import re

    from iconfucius import config as cfg
    from iconfucius.persona import DEFAULT_MODEL

    config_path = cfg.find_config()
    if config_path is None:
        return

    # Preserve existing timeout if requested
    existing_timeout = None
    if keep_timeout:
        raw_timeout = cfg.load_config().get("ai", {}).get("timeout")
        if raw_timeout is not None:
            try:
                parsed = int(raw_timeout)
            except (TypeError, ValueError):
                parsed = None
            existing_timeout = parsed if parsed and parsed > 0 else None

    # Build the new [ai] section content
    lines = ["[ai]"]
    if api_type and api_type != "claude":
        lines.append(f"api_type = {_toml_quote(api_type)}")
    if model and model not in (DEFAULT_MODEL, "default"):
        lines.append(f"model = {_toml_quote(model)}")
    if base_url:
        lines.append(f"base_url = {_toml_quote(base_url)}")
    if existing_timeout is not None:
        lines.append(f'timeout = {existing_timeout}')

    if len(lines) == 1:
        # Only [ai] header — nothing to write, just model default
        new_section = ""
    else:
        new_section = "\n".join(lines) + "\n"

    content = config_path.read_text()

    if re.search(r'^# ?\[ai\]', content, re.MULTILINE):
        # Commented-out [ai] block → replace entire commented block
        if new_section:
            content = re.sub(
                r'^# ?\[ai\]\n(?:#[^\n]*\n)*',
                new_section,
                content,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            content = re.sub(
                r'^# ?\[ai\]\n(?:#[^\n]*\n)*',
                '',
                content,
                count=1,
                flags=re.MULTILINE,
            )
    elif re.search(r'^\[ai\]', content, re.MULTILINE):
        # Existing [ai] section → replace everything until next [section] or EOF
        if new_section:
            content = re.sub(
                r'^\[ai\]\n(?:[^\[]*?)(?=\n\[|\Z)',
                new_section,
                content,
                count=1,
                flags=re.MULTILINE | re.DOTALL,
            )
        else:
            content = re.sub(
                r'^\[ai\]\n(?:[^\[]*?)(?=\n\[|\Z)',
                '',
                content,
                count=1,
                flags=re.MULTILINE | re.DOTALL,
            )
    elif new_section:
        # No [ai] section → append
        separator = "" if content.endswith("\n") else "\n"
        content += f'{separator}\n{new_section}'

    config_path.write_text(content)
    cfg._cached_config = None


def _persist_ai_model(new_model: str) -> None:
    """Legacy wrapper: persist only the model name."""
    _persist_ai_config(model=new_model, keep_timeout=True)


def _reset_ai_config() -> None:
    """Comment out the [ai] section in iconfucius.toml.

    Prefixes each line with ``# `` so the user can re-enable it later.
    """
    import re

    from iconfucius import config as cfg

    config_path = cfg.find_config()
    if config_path is None:
        return

    content = config_path.read_text()

    def _comment_section(match):
        """Format a comment section header."""
        return "".join(f"# {line}\n" for line in match.group(0).splitlines())

    content = re.sub(
        r'^\[ai\]\n(?:[^\[]*?)(?=\n\[|\Z)',
        _comment_section,
        content,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    config_path.write_text(content)
    cfg._cached_config = None


def _handle_model_interactive(backend) -> None:
    """Show current model and optionally switch via numbered selection."""
    print(f"\n  Current model: {backend.model}")

    models = backend.list_models()
    if not models:
        print()
        return

    print("\n  Available models:\n")
    for i, (model_id, display_name) in enumerate(models, 1):
        marker = " *" if model_id == backend.model else ""
        print(f"    {i}. {display_name} ({model_id}){marker}")

    try:
        answer = input("\n  Change model? [y/N] ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return

    if answer not in ("y", "yes"):
        print()
        return

    try:
        choice = input("  Enter number: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(models):
            print("\n  Invalid selection.\n")
            return
    except ValueError:
        print("\n  Invalid selection.\n")
        return

    new_model = models[idx][0]
    backend.model = new_model
    _persist_ai_model(new_model)
    print(f"\n  Model changed to: {new_model}\n")


def _handle_ai_interactive(backend, persona) -> tuple:
    """Interactive /ai menu. Returns (new_api_type, new_model, new_base_url) or None."""
    from iconfucius.persona import DEFAULT_MODEL

    is_default = (
        persona.ai_api_type == "claude"
        and persona.ai_model == DEFAULT_MODEL
        and not persona.ai_base_url
    )

    print("\n  Current AI configuration:")
    print(f"    API type: {persona.ai_api_type}")
    print(f"    Model:    {backend.model}")
    if persona.ai_base_url:
        print(f"    Base URL: {persona.ai_base_url}")
    print()

    # Build menu options dynamically
    options = []
    options.append(("endpoint", "Change to OpenAI-compatible endpoint"))
    options.append(("model", f"Change {persona.ai_api_type} model"))
    if not is_default:
        options.append(("reset", "Reset to default"))

    for i, (_, label) in enumerate(options, 1):
        print(f"  {i}. {label}")
    print()

    max_choice = len(options)
    try:
        choice = input(f"  Choice [1-{max_choice}]: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return None

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(options):
            raise ValueError
        action = options[idx][0]
    except (ValueError, IndexError):
        print("  Invalid choice.\n")
        return None

    if action == "endpoint":
        default_url = "http://localhost:55128"
        try:
            base_url = input(f"  Base URL [{default_url}]: ").strip() or default_url
        except (KeyboardInterrupt, EOFError):
            print()
            return None
        try:
            model = input("  Model name (Enter for 'default'): ").strip() or "default"
        except (KeyboardInterrupt, EOFError):
            print()
            return None

        _persist_ai_config(api_type="openai", model=model, base_url=base_url)
        print(f"\n  Switched to OpenAI-compatible endpoint: {base_url}\n")
        return ("openai", model, base_url)

    if action == "model":
        old_model = backend.model
        _handle_model_interactive(backend)
        if backend.model != old_model:
            persona.ai_model = backend.model
        return None

    if action == "reset":
        _persist_ai_config()  # empty = remove overrides
        print(f"\n  Reset to default: claude / {DEFAULT_MODEL}\n")
        return ("claude", DEFAULT_MODEL, "")

    print("  Invalid choice.\n")
    return None


_MAX_TOOL_ITERATIONS = 10


def _fmt_sats(val) -> str:
    """Format a sats value with thousands separator and USD, safe for None."""
    if val is None:
        return "?"
    try:
        from iconfucius.config import fmt_sats, get_btc_to_usd_rate
        btc_usd_rate = get_btc_to_usd_rate()
        return fmt_sats(int(val), btc_usd_rate)
    except Exception:
        try:
            return f"{val:,}"
        except (TypeError, ValueError):
            return str(val)


def _fmt_tokens(amount, token_id: str) -> str:
    """Format a human-readable token amount with USD value, safe for None.

    The AI provides token counts in human-readable form (e.g. 60 tokens).
    fmt_tokens expects milli-subunits, so we convert first.
    """
    try:
        from iconfucius.config import fmt_tokens
        from iconfucius.tokens import fetch_token_data
        from iconfucius.units import display_to_millisubunits

        human_amount = float(amount)
        data = fetch_token_data(token_id)
        divisibility = data.get("divisibility", 8) if data else 8
        decimals = data.get("decimals", 3) if data else 3
        msu = display_to_millisubunits(human_amount, divisibility, decimals)
        return fmt_tokens(msu, token_id)
    except Exception:
        return f"{amount} tokens"


def _bot_target(tool_input: dict) -> str:
    """Describe the bot target: 'all bots', a list, or a single bot name."""
    if tool_input.get("all_bots"):
        return "all bots"
    names = tool_input.get("bot_names")
    if names:
        return ", ".join(names)
    return tool_input.get("bot_name", "?")


def _resolve_principal_to_bot_name(principal: str) -> str:
    """If *principal* matches a bot's session cache, return 'bot-N (principal)'."""
    import json as _json
    import os

    try:
        from iconfucius.config import get_bot_names
        from iconfucius.siwb import _session_path

        for bot_name in get_bot_names():
            path = _session_path(bot_name)
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        session = _json.load(f)
                    if session.get("bot_principal_text") == principal:
                        return f"{bot_name} ({principal})"
                except Exception:
                    continue
    except Exception:
        pass
    return principal


def _describe_tool_call(name: str, tool_input: dict) -> str:
    """Return a human-readable description of a tool call for confirmation."""
    if name == "init":
        return "Initialize iconfucius project in current directory"
    if name == "wallet_create":
        return "Create a new wallet identity"
    if name == "fund":
        target = _bot_target(tool_input)
        multi = tool_input.get("all_bots") or (isinstance(tool_input.get("bot_names"), list) and len(tool_input["bot_names"]) > 1)
        suffix = " each" if multi else ""
        return f"Fund {target} with {_fmt_sats(tool_input.get('amount'))}{suffix}"
    if name == "trade_buy":
        return (
            f"Buy {_fmt_sats(tool_input.get('amount'))} of token "
            f"{tool_input.get('token_id')} via {_bot_target(tool_input)}"
        )
    if name == "trade_sell":
        token_id = tool_input.get("token_id", "?")
        if tool_input.get("amount_usd") is not None:
            amt = f"${tool_input['amount_usd']:.3f} worth"
        elif str(tool_input.get("amount", "")).lower() == "all":
            amt = "all"
        else:
            amt = _fmt_tokens(tool_input.get("amount"), token_id)
        return (
            f"Sell {amt} of token "
            f"{token_id} via {_bot_target(tool_input)}"
        )
    if name == "withdraw":
        amt = tool_input.get("amount")
        if str(amt).lower() == "all":
            amt_str = "all ckBTC"
        else:
            amt_str = f"{_fmt_sats(amt)} ckBTC"
        return (
            f"Withdraw {amt_str} from "
            f"{_bot_target(tool_input)}"
        )
    if name == "wallet_send":
        return (
            f"Send {_fmt_sats(tool_input.get('amount'))} to "
            f"{tool_input.get('address')}"
        )
    if name == "set_bot_count":
        n = tool_input.get("num_bots", "?")
        force = tool_input.get("force", False)
        desc = f"Change bot count to {n}"
        if force:
            desc += " (skip holdings check)"
        return desc
    if name == "token_transfer":
        token_id = tool_input.get("token_id", "?")
        amt = tool_input.get("amount", "?")
        if str(amt).lower() == "all":
            amt_str = "all"
        else:
            amt_str = _fmt_tokens(amt, token_id)
        to_addr = tool_input.get("to_address", "?")
        to_display = _resolve_principal_to_bot_name(to_addr)
        return (
            f"Transfer {amt_str} of {token_id} from "
            f"{_bot_target(tool_input)} to {to_display}"
        )
    if name == "install_blst":
        return "Install blst library for IC certificate verification"
    return f"{name}({json.dumps(tool_input)})"


def _run_tool_loop(backend, messages: list[dict], system: str,
                   tools: list[dict], persona_name: str,
                   *, persona_key: str = "") -> None:
    """Run the tool use loop until a text-only response is produced.

    Modifies messages in-place (appends assistant + tool_result messages).
    The persona prefix is only printed once — on the final text-only response.
    Pre-tool reasoning text (e.g. "Let me look that up") is suppressed to
    avoid a double persona prefix.

    Args:
        persona_key: Persona identifier for memory operations (e.g. "iconfucius").
    """
    unconfirmed_iterations = 0
    while unconfirmed_iterations < _MAX_TOOL_ITERATIONS:
        with _Spinner(f"{persona_name} is thinking..."):
            response = backend.chat_with_tools(messages, system, tools)

        # Check if response has any tool_use blocks
        has_tool_use = any(
            block.type == "tool_use" for block in response.content
        )

        if not has_tool_use:
            # Text-only response — extract text and show to user
            text = "".join(
                block.text for block in response.content
                if block.type == "text"
            )
            messages.append({"role": "assistant", "content": text})
            print(f"\n{text}\n")
            return
        # Add the full assistant response to messages
        messages.append({
            "role": "assistant",
            "content": [_block_to_dict(b) for b in response.content],
        })

        # Don't print pre-tool reasoning text — it would show a persona
        # prefix that gets repeated when the final response is printed.

        # Separate tool calls by confirmation requirement
        tool_blocks = [b for b in response.content if b.type == "tool_use"]

        # Enforce one distinct state-changing tool name per response.
        # Multiple calls to the *same* write tool (e.g. 3x fund) are fine;
        # only different write tool names (e.g. fund + trade_buy) are blocked.
        write_names = {
            b.name for b in tool_blocks
            if (get_tool_metadata(b.name) or {}).get("category") == "write"
        }
        deferred_ids: set[str] = set()
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

        # Pre-convert amount_usd → amount (sats) so the rest of the flow
        # works uniformly with sats and fmt_sats shows the USD value.
        # Skip trade_sell: it converts USD to tokens, not sats.
        for b in tool_blocks:
            if b.name == "trade_sell":
                continue
            usd = b.input.get("amount_usd")
            if usd is not None and not b.input.get("amount"):
                try:
                    from iconfucius.config import get_btc_to_usd_rate
                    from iconfucius.units import usd_to_sats
                    rate = get_btc_to_usd_rate()
                    sats = usd_to_sats(float(usd), rate)
                    b.input["amount"] = sats
                    del b.input["amount_usd"]
                except Exception:
                    pass  # handler will convert or report error

        confirm_blocks = []
        for b in tool_blocks:
            meta = get_tool_metadata(b.name)
            if meta and meta.get("requires_confirmation", False):
                confirm_blocks.append(b)

        # Batch confirmation: ask once for all confirmable tools
        batch_approved = True
        if confirm_blocks:
            if len(confirm_blocks) == 1:
                desc = _describe_tool_call(
                    confirm_blocks[0].name, confirm_blocks[0].input,
                )
                try:
                    answer = input(f"\n  {desc} [Y/n] ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    answer = "n"
                if answer in ("n", "no"):
                    batch_approved = False
            else:
                print(f"\n  Planned operations ({len(confirm_blocks)}):")
                for b in confirm_blocks:
                    desc = _describe_tool_call(b.name, b.input)
                    print(f"    • {desc}")
                try:
                    answer = input(
                        f"\n  Proceed with all {len(confirm_blocks)}? [Y/n] "
                    ).strip().lower()
                except (KeyboardInterrupt, EOFError):
                    answer = "n"
                if answer in ("n", "no"):
                    batch_approved = False

        # User-confirmed operations reset the counter — the user is actively
        # supervising, so there's no runaway risk.  Unconfirmed iterations
        # (read-only tools, declined operations) count toward the limit.
        if confirm_blocks and batch_approved:
            unconfirmed_iterations = 0
        else:
            unconfirmed_iterations += 1

        # User explicitly declined — stop the loop immediately instead of
        # letting the AI retry with different parameters.
        if confirm_blocks and not batch_approved:
            declined_results = []
            for block in tool_blocks:
                declined_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(
                        {"status": "declined", "error": "User declined."}
                    ),
                })
            # Also resolve any deferred write tool IDs to keep
            # tool_use/tool_result pairs complete.
            for block in response.content:
                if block.type == "tool_use" and block.id in deferred_ids:
                    declined_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({
                            "status": "deferred",
                            "error": "One state-changing operation at a time. "
                                     "Retry this tool in your next response.",
                        }),
                    })
            messages.append({"role": "user", "content": declined_results})
            print("\n\033[2mOperation declined.\033[0m\n")
            return

        # Execute each tool call
        confirm_ids = {b.id for b in confirm_blocks}
        tool_results = []
        for block in tool_blocks:
            if block.id in confirm_ids and not batch_approved:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(
                        {"status": "declined", "error": "User declined."}
                    ),
                })
                continue

            # Skip spinner for instant tools (read-only, no network)
            meta = get_tool_metadata(block.name) or {}
            use_spinner = meta.get("category") == "write" or block.name in (
                "wallet_balance", "how_to_fund_wallet",
                "wallet_monitor", "token_lookup", "token_price",
                "token_discover", "account_lookup", "public_balance",
                "security_status", "install_blst",
            )

            if use_spinner:
                result = _run_with_spinner(
                    f"Running {block.name}...",
                    execute_tool, block.name, block.input,
                    persona_name=persona_key,
                )
            else:
                result = execute_tool(block.name, block.input,
                                      persona_name=persona_key)

            # Print _terminal_output to user and strip from AI context
            terminal_output = result.pop("_terminal_output", None)
            if terminal_output:
                print(f"\n{terminal_output}")
            result.pop("_display", None)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })

        # Append deferred results for write tools that were blocked
        for block in response.content:
            if block.type == "tool_use" and block.id in deferred_ids:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps({
                        "status": "deferred",
                        "error": "One state-changing operation at a time. "
                                 "Retry this tool in your next response.",
                    }),
                })

        messages.append({"role": "user", "content": tool_results})

    # Loop exhausted without user confirmation — warn about incomplete work
    print(
        f"\n\033[33m⚠ Tool loop limit reached ({_MAX_TOOL_ITERATIONS} iterations "
        f"without confirmation). The operation may be incomplete.\033[0m"
    )
    print("\033[2mType 'continue' to resume, or ask a new question.\033[0m\n")


def _block_to_dict(block) -> dict:
    """Convert an Anthropic content block to a plain dict for messages."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    return {"type": block.type}


def _check_pypi_version() -> tuple[str | None, str]:
    """Check PyPI + GitHub for a newer version.

    Returns:
        (latest_version, release_notes) — version is None when up-to-date.
    """
    try:
        with urlopen("https://pypi.org/pypi/iconfucius/json", timeout=3) as resp:
            latest = json.loads(resp.read())["info"]["version"]
        def _ver_tuple(v: str) -> tuple:
            """Parse a version string into a comparable tuple."""
            return tuple(int(x) for x in v.split("."))
        if _ver_tuple(latest) <= _ver_tuple(__version__):
            return None, ""
        # Fetch release notes from GitHub (best-effort)
        notes = ""
        try:
            gh_url = f"https://api.github.com/repos/onicai/IConfucius/releases/tags/v{latest}"
            with urlopen(gh_url, timeout=3) as resp:
                notes = json.loads(resp.read()).get("body", "") or ""
        except Exception:
            pass
        return latest, notes
    except Exception:
        return None, ""


def _handle_upgrade() -> None:
    """Upgrade iconfucius via pip and re-exec the process."""
    import os
    import subprocess

    print(f"\n\033[2mUpgrading iconfucius from v{__version__}...\033[0m\n")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "iconfucius"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Upgrade failed:\n{result.stderr.strip()}\n")
        return

    # Determine the new version from pip output
    new_version = None
    try:
        with urlopen("https://pypi.org/pypi/iconfucius/json", timeout=3) as resp:
            new_version = json.loads(resp.read())["info"]["version"]
    except Exception:
        pass

    label = f"v{new_version}" if new_version else "latest version"
    print(f"\033[2mUpgraded to {label} — restarting...\033[0m\n")
    os.execvp(sys.argv[0], sys.argv)


def _is_non_default_ai(persona: Persona) -> bool:
    """Return True if the persona has any non-default AI configuration."""
    return (
        persona.ai_api_type != "claude"
        or persona.ai_model != DEFAULT_MODEL
        or bool(persona.ai_base_url)
    )


def run_chat(persona_name: str, bot_name: str, verbose: bool = False,
             experimental: bool = False) -> None:
    """Run interactive chat with a trading persona.

    Args:
        persona_name: Name of the persona to load.
        bot_name: Default bot for trading context.
        verbose: Show verbose output.
        experimental: Enable experimental features (/ai command).
    """
    from iconfucius.config import set_verbose
    set_verbose(verbose)

    try:
        persona = load_persona(persona_name)
    except PersonaNotFoundError as e:
        print(f"Error: {e}")
        return

    # Non-default AI config warning
    non_default = _is_non_default_ai(persona)
    if non_default:
        print("\n  \033[33m⚠ Non-default AI configuration detected:\033[0m")
        print(f"    API type: {persona.ai_api_type}")
        if persona.ai_base_url:
            print(f"    Base URL: {persona.ai_base_url}")
        print(f"    Model:    {persona.ai_model}")
        print()
        try:
            answer = input("  Continue with this configuration? [Y/n] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if answer in ("n", "no"):
            _reset_ai_config()
            from iconfucius.config import load_config
            load_config(reload=True)
            persona = load_persona(persona_name)
            non_default = False
            print("  Reset to default configuration.\n")

    try:
        backend = create_backend(persona)
    except APIKeyMissingError as e:
        print(f"\n{e}")
        return
    except Exception as e:
        print(f"\nError creating AI backend: {e}")
        return

    from iconfucius.ai import LoggingBackend
    from iconfucius.conversation_log import ConversationLogger
    conv_logger = ConversationLogger()
    backend = LoggingBackend(backend, conv_logger)

    # One-time migration: trades.md → trades.jsonl
    from iconfucius.memory import migrate_trades_md_to_jsonl
    migrate_trades_md_to_jsonl(persona_name)

    # Build system prompt with memory context
    system = persona.system_prompt

    # Inject setup status so the persona can guide users through setup
    setup = execute_tool("setup_status", {})
    if not setup.get("ready"):
        system += "\n\n## Setup Status\n"
        system += (
            f"Config: {'ready' if setup.get('config_exists') else 'MISSING — use init tool'}\n"
            f"Wallet: {'ready' if setup.get('wallet_exists') else 'MISSING — use wallet_create tool'}\n"
            f"API key: {'ready' if setup.get('has_api_key') else 'MISSING — user must add ANTHROPIC_API_KEY to .env'}\n"
        )
        system += "\nGuide the user through any missing setup steps before trading."

    # Trading context is fetched on-demand via tools, not injected here.
    system += (
        "\n\n## On-Demand Context"
        "\nUse these tools to review your trading context when needed:"
        "\n- memory_read_strategy — read your current trading strategy"
        "\n- memory_read_learnings — read your accumulated trading learnings"
        "\n- memory_read_trades — read recent trade history"
        "\n- token_lookup — resolve token names/tickers to IDs before trading"
        "\n- enable_experimental — enable experimental features (AI model configuration)"
    )

    from iconfucius.config import get_bot_names

    all_bot_names = get_bot_names()
    if len(all_bot_names) > 1:
        names_str = ", ".join(all_bot_names)
        system += (
            f"\n\nYou manage {len(all_bot_names)} bots: {names_str}. "
            f"Default bot for single-bot operations: '{bot_name}'. "
            f"When using wallet_balance, use all_bots=true "
            f"unless the user specifies particular bots. "
            f"When using fund, trade, or withdraw, ask the user what bots to use."
        )
    else:
        system += f"\n\nYou are trading as bot '{bot_name}'."

    # Start wallet-only balance in background (no minter, no bots — fast)
    wallet_future: Future | None = None
    _bg_pool: ThreadPoolExecutor | None = None
    if setup.get("wallet_exists"):
        from iconfucius.cli.balance import run_wallet_balance
        _bg_pool = ThreadPoolExecutor(max_workers=1)
        wallet_future = _bg_pool.submit(run_wallet_balance, ckbtc_minter=False)

    # Verify API access with a startup greeting (also caches goodbye)
    lang = _get_language_code()
    try:
        with _Spinner(f"{persona.name} is thinking..."):
            greeting, goodbye = _generate_startup(backend, persona, lang)
    except Exception as e:
        print(f"\n{_format_api_error(e)}")
        return

    print(f"\n{greeting}\n")

    # Determine if /ai is active for this session
    from iconfucius.skills.executor import _experimental_enabled
    ai_active = experimental or _experimental_enabled or non_default

    print(f"\033[2miconfucius v{__version__} · exit to quit · Ctrl+C to interrupt\033[0m")
    ai_parts = [persona.ai_api_type, str(backend.model)]
    if persona.ai_base_url:
        ai_parts.append(persona.ai_base_url)
    ai_desc = " · ".join(ai_parts)
    if ai_active:
        print(f"\033[2mAI: {ai_desc} · /ai to change\033[0m")
    else:
        print(f"\033[2mAI: {ai_desc}\033[0m")
    if experimental:
        from iconfucius.skills.executor import EXPERIMENTAL_ENABLED, EXPERIMENTAL_RISK_WARNING
        print(f"\033[2m\n{EXPERIMENTAL_ENABLED}\033[0m")
        if backend.model != DEFAULT_MODEL:
            print(f"\033[2mNote: recommended model is {DEFAULT_MODEL}\033[0m")
        print(f"\033[2m\n{EXPERIMENTAL_RISK_WARNING}\033[0m")
    elif backend.model != DEFAULT_MODEL:
        print(f"\033[2mNote: recommended model is {DEFAULT_MODEL}\033[0m")

    # Check PyPI for newer version (non-blocking, best-effort)
    latest_version, release_notes = _check_pypi_version()
    if latest_version:
        print(f"\033[2mUpdate available: v{latest_version} · /upgrade to install\033[0m")
        # Populate executor cache so check_update tool returns fresh data
        from iconfucius.skills.executor import _update_cache
        _update_cache["latest_version"] = latest_version
        _update_cache["release_notes"] = release_notes
    print()

    # --- Startup balance wizard ---
    startup_balance_result = None
    wallet_data = None
    if wallet_future is not None:
        from iconfucius.config import MIN_DEPOSIT_SATS, MIN_TRADE_SATS
        from iconfucius.logging_config import get_logger
        logger = get_logger()

        # Collect wallet result (likely already done during greeting)
        try:
            if not wallet_future.done():
                with _Spinner("Checking wallet..."):
                    wallet_data = wallet_future.result()
            else:
                wallet_data = wallet_future.result()
            if wallet_data:
                display_text = wallet_data.pop("_display", "")
                if display_text:
                    print(f"\n{display_text}\n")
        except (KeyboardInterrupt, EOFError):
            wallet_future.cancel()
            print()
        except Exception:
            logger.debug("Startup wallet check failed", exc_info=True)
        finally:
            if _bg_pool is not None:
                _bg_pool.shutdown(wait=False)

        # Wizard prompts for optional checks
        if wallet_data:
            from iconfucius.wizard import Wizard
            wiz = Wizard(_CliWizardIO())

            check_bots = wiz.ask("Check bot balances?", default_yes=False)
            check_minter = wiz.ask(
                "Check ckBTC minter status for in/out BTC?",
                default_yes=False,
            )

            if check_bots:
                try:
                    startup_balance_result = wiz.run(
                        "Checking bot balances...",
                        execute_tool, "wallet_balance",
                        {"ckbtc_minter": check_minter},
                        persona_name=persona_name,
                    )
                    if startup_balance_result and \
                            startup_balance_result.get("status") == "ok":
                        display_text = startup_balance_result.pop("_display", "")
                        if display_text:
                            wiz.show(f"\n{display_text}\n")
                except Exception:
                    logger.debug("Bot balance check failed", exc_info=True)
            elif check_minter:
                try:
                    minter_data = wiz.run(
                        "Checking ckBTC minter...",
                        run_wallet_balance, ckbtc_minter=True,
                    )
                    if minter_data:
                        display_text = minter_data.pop("_display", "")
                        if display_text:
                            wiz.show(f"\n{display_text}\n")
                except Exception:
                    logger.debug("Minter check failed", exc_info=True)

            # Build AI seed from best available data
            if startup_balance_result is None:
                startup_balance_result = {
                    "status": "ok",
                    "wallet_ckbtc_sats": wallet_data.get("balance_sats", 0),
                    "total_odin_sats": 0,
                    "total_token_value_sats": 0,
                    "portfolio_sats": wallet_data.get("balance_sats", 0),
                    "constraints": {
                        "min_deposit_sats": MIN_DEPOSIT_SATS,
                        "min_trade_sats": MIN_TRADE_SATS,
                    },
                    "note": (
                        "Bot balances were NOT checked at startup. "
                        "Call wallet_balance with all_bots=true to get "
                        "actual bot balances when the user asks."
                    ),
                }
                if wallet_data.get("balance_sats", 0) == 0:
                    startup_balance_result["next_step"] = (
                        "Wallet is empty. Use how_to_fund_wallet to show "
                        "the user how to deposit funds."
                    )

    tools = get_tools_for_anthropic()
    messages: list[dict] = []

    # Seed conversation with balance data so the AI sees it on its first turn
    if startup_balance_result and startup_balance_result.get("status") == "ok":
        tool_call_id = "startup_wallet_balance"
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": tool_call_id,
                 "name": "wallet_balance", "input": {}},
            ],
        })
        messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_call_id,
                 "content": json.dumps(startup_balance_result)},
            ],
        })

    # Seed conversation with update data so the AI sees it on its first turn
    if latest_version:
        update_result = execute_tool("check_update", {})
        tool_call_id = "startup_check_update"
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": tool_call_id,
                 "name": "check_update", "input": {}},
            ],
        })
        messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_call_id,
                 "content": json.dumps(update_result)},
            ],
        })

    # If balance data has a next_step, trigger an automatic AI response
    if (startup_balance_result
            and startup_balance_result.get("next_step")
            and messages):
        try:
            _run_tool_loop(backend, messages, system, tools, persona.name,
                           persona_key=persona_name)
        except Exception:
            from iconfucius.logging_config import get_logger
            get_logger().debug("Startup auto next_step failed", exc_info=True)

    def _prompt_banner() -> None:
        """Print separator lines with optional upgrade notice."""
        print("\033[2m" + "─" * 60 + "\033[0m")
        if latest_version:
            print(f"\033[2mv{latest_version} available · /upgrade to install\033[0m")
            print("\033[2m" + "─" * 60 + "\033[0m")

    # Enable readline for input history (up/down arrows) and line editing
    try:
        import readline  # noqa: F401
    except ImportError:
        pass

    while True:
        try:
            _prompt_banner()
            user_input = input(f"\033[2mv{__version__}\033[0m > ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{goodbye}")
            break

        if user_input.startswith("/ai"):
            # Re-check ai_active (enable_experimental may have been called)
            from iconfucius.skills.executor import _experimental_enabled
            ai_active = experimental or _experimental_enabled or non_default
            if not ai_active:
                print("\n  /ai is an experimental feature. Start with: iconfucius --experimental\n")
                continue
            parts = user_input.split(maxsplit=1)
            ai_result = None
            if len(parts) == 1:
                ai_result = _handle_ai_interactive(backend, persona)
            elif parts[1].strip() == "reset":
                from iconfucius.persona import DEFAULT_MODEL as _dm
                _persist_ai_config()
                print(f"\n  Reset to default: claude / {_dm}\n")
                ai_result = ("claude", _dm, "")
            elif parts[1].strip().startswith("model "):
                new_model = parts[1].strip()[6:].strip()
                backend.model = new_model
                persona.ai_model = new_model
                _persist_ai_model(new_model)
                print(f"\n  Model changed to: {new_model}\n")
            else:
                new_model = parts[1].strip()
                backend.model = new_model
                persona.ai_model = new_model
                _persist_ai_model(new_model)
                print(f"\n  Model changed to: {new_model}\n")
            # Hot-swap backend when api_type or base_url changed
            if ai_result is not None:
                new_api_type, new_model, new_base_url = ai_result
                prev_api_type = persona.ai_api_type
                prev_model = persona.ai_model
                prev_base_url = persona.ai_base_url
                persona.ai_api_type = new_api_type
                persona.ai_model = new_model
                persona.ai_base_url = new_base_url
                try:
                    new_backend = create_backend(persona)
                except Exception as exc:
                    print(f"\n  Error applying AI configuration: {exc}\n")
                    persona.ai_api_type = prev_api_type
                    persona.ai_model = prev_model
                    persona.ai_base_url = prev_base_url
                    _persist_ai_config(
                        api_type=prev_api_type,
                        model=prev_model,
                        base_url=prev_base_url,
                        keep_timeout=True,
                    )
                    continue
                backend = LoggingBackend(new_backend, conv_logger)
                non_default = _is_non_default_ai(persona)
            continue

        if user_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) == 1:
                old_model = backend.model
                _handle_model_interactive(backend)
                if backend.model != old_model:
                    persona.ai_model = backend.model
                    non_default = _is_non_default_ai(persona)
            else:
                new_model = parts[1].strip()
                backend.model = new_model
                persona.ai_model = new_model
                _persist_ai_model(new_model)
                non_default = _is_non_default_ai(persona)
                print(f"\n  Model changed to: {new_model}\n")
            continue

        if user_input.lower() == "/upgrade":
            _handle_upgrade()
            # If _handle_upgrade returns, the upgrade failed — continue chatting
            continue

        if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
            print(f"\n{goodbye}")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            _run_tool_loop(backend, messages, system, tools, persona.name,
                          persona_key=persona_name)
        except KeyboardInterrupt:
            print("\n\nInterrupted.")
            messages.pop()
            continue
        except SystemExit as e:
            print(f"\nInternal error (exit code {e.code})\n")
            messages.pop()
            continue
        except Exception as e:
            print(f"\n{_format_api_error(e)}\n")
            messages.pop()  # Remove the failed user message
            continue
