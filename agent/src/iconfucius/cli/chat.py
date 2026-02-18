"""Interactive chat command for trading personas."""

import itertools
import json
import locale
import random
import sys
import threading
import time

from iconfucius.ai import APIKeyMissingError, create_backend
from iconfucius.memory import read_learnings, read_strategy, read_trades
from iconfucius.persona import Persona, PersonaNotFoundError, load_persona
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
    animation keeps running even when redirect_stdout is active
    (e.g. inside _capture() in the skills executor).
    """

    def __init__(self, message: str = ""):
        self._message = message
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stdout = sys.stdout  # real terminal, before any redirect

    def __enter__(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread:
            self._thread.join()
        # Clear the spinner line
        self._stdout.write("\r\033[K")
        self._stdout.flush()

    def _spin(self):
        frames = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        while not self._stop.is_set():
            self._stdout.write(f"\r{next(frames)} {self._message}")
            self._stdout.flush()
            time.sleep(0.08)


def _get_language_code() -> str:
    """Detect system language. Returns 'cn' for Chinese, 'en' otherwise."""
    try:
        lang = locale.getlocale()[0] or ""
    except ValueError:
        lang = ""
    return "cn" if lang.startswith("zh") else "en"


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


_MAX_TOOL_ITERATIONS = 10


def _fmt_sats(val) -> str:
    """Format a sats value with thousands separator, safe for None."""
    if val is None:
        return "?"
    try:
        return f"{val:,}"
    except (TypeError, ValueError):
        return str(val)


def _bot_target(tool_input: dict) -> str:
    """Describe the bot target: 'all bots', a list, or a single bot name."""
    if tool_input.get("all_bots"):
        return "all bots"
    names = tool_input.get("bot_names")
    if names:
        return ", ".join(names)
    return tool_input.get("bot_name", "?")


def _describe_tool_call(name: str, tool_input: dict) -> str:
    """Return a human-readable description of a tool call for confirmation."""
    if name == "init":
        return "Initialize iconfucius project in current directory"
    if name == "wallet_create":
        return "Create a new wallet identity"
    if name == "fund":
        return f"Fund {_bot_target(tool_input)} with {_fmt_sats(tool_input.get('amount'))} sats each"
    if name == "trade_buy":
        if tool_input.get("amount_usd") is not None:
            amt = f"${tool_input['amount_usd']:.2f}"
        else:
            amt = f"{_fmt_sats(tool_input.get('amount'))} sats"
        return (
            f"Buy {amt} of token "
            f"{tool_input.get('token_id')} via {_bot_target(tool_input)}"
        )
    if name == "trade_sell":
        if tool_input.get("amount_usd") is not None:
            amt = f"${tool_input['amount_usd']:.2f} worth"
        elif str(tool_input.get("amount", "")).lower() == "all":
            amt = "all"
        else:
            amt = f"{_fmt_sats(tool_input.get('amount'))} tokens"
        return (
            f"Sell {amt} of token "
            f"{tool_input.get('token_id')} via {_bot_target(tool_input)}"
        )
    if name == "withdraw":
        return (
            f"Withdraw {tool_input.get('amount')} sats from "
            f"{_bot_target(tool_input)}"
        )
    if name == "wallet_send":
        return (
            f"Send {tool_input.get('amount')} sats to "
            f"{tool_input.get('address')}"
        )
    if name == "set_bot_count":
        n = tool_input.get("num_bots", "?")
        force = tool_input.get("force", False)
        desc = f"Change bot count to {n}"
        if force:
            desc += " (skip holdings check)"
        return desc
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
    for _ in range(_MAX_TOOL_ITERATIONS):
        response = backend.chat_with_tools(messages, system, tools)

        # Check if response has any tool_use blocks
        has_tool_use = any(
            block.type == "tool_use" for block in response.content
        )

        if not has_tool_use:
            # Text-only response — extract and print
            text = "".join(
                block.text for block in response.content
                if block.type == "text"
            )
            messages.append({"role": "assistant", "content": text})
            print(f"\n{text}\n")
            return

        # Has tool calls — process them
        # Add the full assistant response to messages
        messages.append({
            "role": "assistant",
            "content": [_block_to_dict(b) for b in response.content],
        })

        # Don't print pre-tool reasoning text — it would show a persona
        # prefix that gets repeated when the final response is printed.

        # Separate tool calls by confirmation requirement
        tool_blocks = [b for b in response.content if b.type == "tool_use"]
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

            with _Spinner(f"Running {block.name}..."):
                result = execute_tool(block.name, block.input,
                                      persona_name=persona_key)

            # Print large output directly to terminal, strip from AI result
            terminal_output = result.pop("_terminal_output", None)
            if terminal_output:
                print(f"\n{terminal_output}\n")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })

        messages.append({"role": "user", "content": tool_results})


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


def run_chat(persona_name: str, bot_name: str, verbose: bool = False) -> None:
    """Run interactive chat with a trading persona.

    Args:
        persona_name: Name of the persona to load.
        bot_name: Default bot for trading context.
        verbose: Show verbose output.
    """
    try:
        persona = load_persona(persona_name)
    except PersonaNotFoundError as e:
        print(f"Error: {e}")
        return

    try:
        backend = create_backend(persona)
    except APIKeyMissingError as e:
        print(f"\n{e}")
        return
    except Exception as e:
        print(f"\nError creating AI backend: {e}")
        return

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

    strategy = read_strategy(persona_name)
    learnings = read_learnings(persona_name)
    recent_trades = read_trades(persona_name, last_n=5)

    if strategy:
        system += f"\n\n## Current Strategy\n{strategy}"
    if learnings:
        system += f"\n\n## Learnings\n{learnings}"
    if recent_trades:
        system += f"\n\n## Recent Trades\n{recent_trades}"

    # Inject known tokens for name→ID resolution
    from iconfucius.tokens import format_known_tokens_for_prompt

    known_tokens_table = format_known_tokens_for_prompt()
    if known_tokens_table:
        system += f"\n\n## Known Tokens\n{known_tokens_table}"
        system += "\nUse these token IDs directly. For unknown tokens, use token_lookup."

    from iconfucius.config import get_bot_names

    all_bot_names = get_bot_names()
    if len(all_bot_names) > 1:
        names_str = ", ".join(all_bot_names)
        system += (
            f"\n\nYou manage {len(all_bot_names)} bots: {names_str}. "
            f"Default bot for single-bot operations: '{bot_name}'. "
            f"Always use all_bots=true for wallet_balance, fund, trade, and withdraw "
            f"unless the user specifies particular bots."
        )
    else:
        system += f"\n\nYou are trading as bot '{bot_name}'."

    # Verify API access with a startup greeting (also caches goodbye)
    lang = _get_language_code()
    try:
        with _Spinner(f"{persona.name} is thinking..."):
            greeting, goodbye = _generate_startup(backend, persona, lang)
    except Exception as e:
        print(f"\n{_format_api_error(e)}")
        return

    print(f"\n{greeting}\n")
    print("\033[2mexit to quit · Ctrl+C to interrupt\033[0m\n")

    tools = get_tools_for_anthropic()
    messages: list[dict] = []

    while True:
        try:
            print("\033[2m" + "─" * 60 + "\033[0m")
            user_input = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{goodbye}")
            break

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
