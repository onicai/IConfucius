"""Tool definitions for iconfucius agent skills.

Each tool has:
- name, description, input_schema: Standard Anthropic tool format
- requires_confirmation: True for state-changing tools (buy, sell, fund, etc.)
- category: "read" or "write"
"""

TOOLS: list[dict] = [
    # ------------------------------------------------------------------
    # Read-only tools (no confirmation needed)
    # ------------------------------------------------------------------
    {
        "name": "fmt_sats",
        "description": (
            "Format a satoshi amount for display. "
            "Returns the amount with comma separators and current USD value, "
            "e.g. '5,000 sats ($5.00)'. "
            "Always use this tool when displaying BTC or ckBTC amounts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sats": {
                    "type": "integer",
                    "description": "Amount in satoshis to format.",
                },
            },
            "required": ["sats"],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "setup_status",
        "description": (
            "Check if the iconfucius project is initialized and ready. "
            "Returns which setup steps have been completed "
            "(config, wallet, API key)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "bot_list",
        "description": (
            "List all configured bots (names and count). "
            "Fast — reads config only, no network calls. "
            "Use this when the user asks how many bots they have, "
            "or wants to see bot names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "wallet_balance",
        "description": (
            "Refresh wallet ckBTC balance and bot holdings from Odin.fun. "
            "Returns wallet balance, bot balances, and token holdings. "
            "By default shows ALL bots. "
            "Use ckbtc_minter=true to also show incoming/outgoing BTC status "
            "from the ckBTC minter (pending deposits, withdrawal progress)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_name": {
                    "type": "string",
                    "description": (
                        "Specific bot to check (e.g. 'bot-1'). "
                        "Omit to check all bots."
                    ),
                },
                "all_bots": {
                    "type": "boolean",
                    "description": "Check all configured bots. Default true.",
                    "default": True,
                },
                "ckbtc_minter": {
                    "type": "boolean",
                    "description": (
                        "Show ckBTC minter status: incoming BTC deposits "
                        "pending conversion and outgoing BTC withdrawals. "
                        "Use when the user sent BTC and wants to check "
                        "if it arrived or is being converted."
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "wallet_monitor",
        "description": (
            "Check the ckBTC minter for incoming BTC deposit status and "
            "outgoing BTC withdrawal progress. Shows confirmation count, "
            "pending amounts, and auto-triggers BTC-to-ckBTC conversion. "
            "Use when the user sent BTC to their deposit address and wants "
            "to know if it arrived, how many confirmations it has, or when "
            "it will be converted to ckBTC."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "wallet_receive",
        "description": (
            "Show the Bitcoin deposit address for funding the iconfucius wallet. "
            "Users send BTC to this address to get ckBTC."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "wallet_info",
        "description": (
            "Show wallet principal identity and ckBTC balance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "persona_list",
        "description": "List all available trading personas.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "persona_show",
        "description": (
            "Show details of a specific trading persona "
            "(name, voice, risk level, AI backend)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Persona name (e.g. 'iconfucius').",
                },
            },
            "required": ["name"],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "token_lookup",
        "description": (
            "Search for a token by name, ticker, or ID. "
            "Returns token details with safety indicators "
            "(bonded status, verification, holder count). "
            "Use this to find the correct token ID before trading."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Token name, ticker, or ID to search for "
                        "(e.g. 'IConfucius', 'ODINDOG', '29m8')."
                    ),
                },
            },
            "required": ["query"],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "token_discover",
        "description": (
            "Discover tokens on Odin.fun. "
            "Use sort='volume' for trending tokens by 24h trading volume, "
            "or sort='newest' for recently created tokens. "
            "Returns top tokens with price, volume, holder count, and safety info."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sort": {
                    "type": "string",
                    "enum": ["volume", "newest"],
                    "description": "Sort order: 'volume' for trending, 'newest' for recent.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of tokens to return (default 20, max 50).",
                },
            },
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "token_price",
        "description": (
            "Get the current price and recent price changes for a token. "
            "Returns price in sats and USD, price change percentages "
            "(1h, 6h, 24h), market cap, 24h volume, and holder count. "
            "Use this when the user asks about a token's price, "
            "performance, or market data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Token name, ticker, or ID to look up "
                        "(e.g. 'IConfucius', 'ODINDOG', '29m8')."
                    ),
                },
            },
            "required": ["query"],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "security_status",
        "description": (
            "Check the security posture of the iconfucius installation. "
            "Reports whether blst (IC certificate verification) is installed, "
            "whether verify_certificates is enabled, and whether session "
            "caching is on. Use this when the user asks about security, "
            "certificate verification, or when the total holdings across "
            "wallet and bots exceed $500 USD."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    # ------------------------------------------------------------------
    # Memory tools
    # ------------------------------------------------------------------
    {
        "name": "memory_read_strategy",
        "description": (
            "Read your current trading strategy notes from memory. "
            "Use this to review your strategy before making trade decisions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "memory_read_learnings",
        "description": (
            "Read your accumulated trading learnings from memory. "
            "Contains patterns, insights, and lessons from past trades."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "memory_update",
        "description": (
            "Update your trading strategy or learnings in memory. "
            "Use this after trades to record what you learned, "
            "or to revise your trading strategy based on experience. "
            "The content replaces the entire file — include everything "
            "you want to keep."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "enum": ["strategy", "learnings"],
                    "description": "Which memory file to update.",
                },
                "content": {
                    "type": "string",
                    "description": "The full updated content for the file.",
                },
            },
            "required": ["file", "content"],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    # ------------------------------------------------------------------
    # Setup tools (confirmation required — create files on disk)
    # ------------------------------------------------------------------
    {
        "name": "install_blst",
        "description": (
            "Install the blst library (BLS12-381) for IC certificate "
            "verification. Detects the OS, checks for prerequisites "
            "(C compiler, SWIG), builds blst from source, and enables "
            "verify_certificates in iconfucius.toml. Requires git and a "
            "C compiler. Use when the user wants to enable certificate "
            "verification or improve security."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    {
        "name": "init",
        "description": (
            "Initialize an iconfucius project in the current directory. "
            "Creates iconfucius.toml, .env, and .gitignore."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Overwrite existing config if present.",
                    "default": False,
                },
                "num_bots": {
                    "type": "integer",
                    "description": "Number of bots to create (1-1000).",
                    "default": 3,
                },
            },
            "required": [],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    {
        "name": "wallet_create",
        "description": (
            "Create a new Ed25519 wallet identity for iconfucius. "
            "Generates .wallet/identity-private.pem."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": (
                        "Overwrite existing wallet "
                        "(WARNING: changes your wallet address)."
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    {
        "name": "set_bot_count",
        "description": (
            "Change the number of bots in the project configuration. "
            "When increasing, new bot sections are added to iconfucius.toml. "
            "When decreasing, bots are checked for holdings first — "
            "if any bot to be removed has a balance or tokens, "
            "the tool returns the holdings so you can ask the user what to do. "
            "Use force=true to skip the holdings check."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "num_bots": {
                    "type": "integer",
                    "description": "Desired total number of bots (1-1000).",
                },
                "force": {
                    "type": "boolean",
                    "description": (
                        "Skip holdings check when removing bots. "
                        "Only use after the user has confirmed."
                    ),
                    "default": False,
                },
            },
            "required": ["num_bots"],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    # ------------------------------------------------------------------
    # Trading tools (confirmation required)
    # ------------------------------------------------------------------
    {
        "name": "fund",
        "description": (
            "Deposit ckBTC from wallet into bot Odin.fun trading accounts. "
            "Minimum deposit: 5,000 sats per bot. "
            "Provide either amount (sats) or amount_usd (dollars). "
            "Specify bot_names for specific bots or all_bots=true for every bot."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "integer",
                    "description": "Amount in sats to deposit per bot.",
                },
                "amount_usd": {
                    "type": "number",
                    "description": (
                        "Amount in USD to deposit per bot. "
                        "Converted to sats automatically. "
                        "Use this when the user specifies a dollar amount."
                    ),
                },
                "bot_name": {
                    "type": "string",
                    "description": "Single bot name (e.g. 'bot-1').",
                },
                "bot_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bot names to fund (e.g. ['bot-12', 'bot-14']).",
                },
                "all_bots": {
                    "type": "boolean",
                    "description": "Fund all configured bots. Default false.",
                },
            },
            "required": ["amount"],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    {
        "name": "trade_buy",
        "description": (
            "Buy tokens on Odin.fun using BTC from bot trading accounts. "
            "Minimum trade: 500 sats. "
            "Provide either amount (sats) or amount_usd (dollars). "
            "Specify bot_names for specific bots or all_bots=true for every bot."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                    "description": "Token ID to buy (e.g. '29m8').",
                },
                "amount": {
                    "type": "integer",
                    "description": "Amount in sats to spend per bot.",
                },
                "amount_usd": {
                    "type": "number",
                    "description": (
                        "Amount in USD to spend per bot. "
                        "Converted to sats automatically. "
                        "Use this when the user specifies a dollar amount."
                    ),
                },
                "bot_name": {
                    "type": "string",
                    "description": "Single bot name (e.g. 'bot-1').",
                },
                "bot_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bot names to trade with (e.g. ['bot-12', 'bot-14']).",
                },
                "all_bots": {
                    "type": "boolean",
                    "description": "Trade with all configured bots. Default false.",
                },
            },
            "required": ["token_id"],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    {
        "name": "trade_sell",
        "description": (
            "Sell tokens on Odin.fun. "
            "Provide amount (raw tokens), amount_usd (dollars), or 'all'. "
            "Minimum trade value: 500 sats. "
            "Specify bot_names for specific bots or all_bots=true for every bot."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                    "description": "Token ID to sell (e.g. '29m8').",
                },
                "amount": {
                    "type": "string",
                    "description": (
                        "Amount of raw tokens to sell, or 'all' for entire position."
                    ),
                },
                "amount_usd": {
                    "type": "number",
                    "description": (
                        "Amount in USD worth of tokens to sell per bot. "
                        "Converted to token amount automatically. "
                        "Use this when the user specifies a dollar amount."
                    ),
                },
                "bot_name": {
                    "type": "string",
                    "description": "Single bot name (e.g. 'bot-1').",
                },
                "bot_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bot names to trade with (e.g. ['bot-12', 'bot-14']).",
                },
                "all_bots": {
                    "type": "boolean",
                    "description": "Trade with all configured bots. Default false.",
                },
            },
            "required": ["token_id"],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    {
        "name": "withdraw",
        "description": (
            "Withdraw BTC from bot Odin.fun accounts back to the iconfucius wallet. "
            "Provide amount (sats), amount_usd (dollars), or 'all'. "
            "Specify bot_names for specific bots or all_bots=true for every bot."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "string",
                    "description": (
                        "Amount in sats to withdraw per bot, or 'all' for entire balance."
                    ),
                },
                "amount_usd": {
                    "type": "number",
                    "description": (
                        "Amount in USD to withdraw per bot. "
                        "Converted to sats automatically. "
                        "Use this when the user specifies a dollar amount."
                    ),
                },
                "bot_name": {
                    "type": "string",
                    "description": "Single bot name (e.g. 'bot-1').",
                },
                "bot_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bot names to withdraw from (e.g. ['bot-12', 'bot-14']).",
                },
                "all_bots": {
                    "type": "boolean",
                    "description": "Withdraw from all configured bots. Default false.",
                },
            },
            "required": ["amount"],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    {
        "name": "wallet_send",
        "description": (
            "Send ckBTC from the iconfucius wallet to an external Bitcoin address. "
            "Provide amount (sats), amount_usd (dollars), or 'all'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "string",
                    "description": (
                        "Amount in sats to send, or 'all' for entire balance."
                    ),
                },
                "amount_usd": {
                    "type": "number",
                    "description": (
                        "Amount in USD to send. "
                        "Converted to sats automatically. "
                        "Use this when the user specifies a dollar amount."
                    ),
                },
                "address": {
                    "type": "string",
                    "description": "Destination Bitcoin address.",
                },
            },
            "required": ["amount", "address"],
        },
        "requires_confirmation": True,
        "category": "write",
    },
]


def get_tools_for_anthropic() -> list[dict]:
    """Return tool definitions in Anthropic API format.

    Strips internal metadata (requires_confirmation, category) so the
    list can be passed directly to messages.create(tools=...).
    """
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["input_schema"],
        }
        for t in TOOLS
    ]


def get_tool_metadata(name: str) -> dict | None:
    """Return the full tool dict (including metadata) by name.

    Returns None if the tool name is not found.
    """
    for t in TOOLS:
        if t["name"] == name:
            return t
    return None
