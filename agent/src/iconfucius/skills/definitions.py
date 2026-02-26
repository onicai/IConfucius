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
        "name": "check_update",
        "description": (
            "Check if a newer version of iconfucius is available. "
            "Returns the running version, latest version, and release notes. "
            "The user can type /upgrade to install the update."
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
        "name": "enable_experimental",
        "description": (
            "Enable experimental features for this session. "
            "Call this when the user asks to change the AI model, "
            "API type, or backend configuration. "
            "After enabling, tell the user to type /ai to configure."
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
            "pending amounts, and auto-triggers BTC-to-ckBTC conversion "
            "when deposits reach ~6 Bitcoin confirmations. "
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
        "name": "how_to_fund_wallet",
        "description": (
            "Show instructions for funding the wallet. "
            "Call when the wallet is empty or has insufficient funds, "
            "or when the user asks how to deposit/fund/top up. "
            "Returns the wallet's receiving addresses and step-by-step instructions."
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
        "name": "token_lookup",
        "description": (
            "Resolve a token name or ticker to its token ID. "
            "ALWAYS call this tool when the user mentions a token by name "
            "(e.g. 'ICONFUCIUS', 'ODINDOG') instead of by ID (e.g. '29m8'). "
            "Use the returned token ID for trade_buy or trade_sell."
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
    {
        "name": "account_lookup",
        "description": (
            "Look up an Odin.fun account by IC principal, BTC deposit address, "
            "or BTC wallet address. Returns account details including principal, "
            "username, BTC addresses, and follower count. "
            "Use this to verify an address before transferring tokens, "
            "or to explore another trader's (human or bot) account or trading "
            "style to anticipate buy or sell predictions on their holdings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": (
                        "Address to look up — IC principal, BTC deposit address, "
                        "or BTC wallet address."
                    ),
                },
            },
            "required": ["address"],
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
        "name": "memory_read_trades",
        "description": (
            "Read recent trade history from memory. Returns the last "
            "N trades with token, amount, price, and bot details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "last_n": {
                    "type": "integer",
                    "description": "Number of recent trades to return (default 5).",
                },
            },
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "memory_read_balances",
        "description": (
            "Read recent portfolio balance snapshots. Returns timestamped "
            "balance history for tracking trading performance. "
            "Snapshots are recorded automatically after each balance check."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "last_n": {
                    "type": "integer",
                    "description": "Number of recent snapshots to return (default 50).",
                },
            },
            "required": [],
        },
        "requires_confirmation": False,
        "category": "read",
    },
    {
        "name": "memory_archive_balances",
        "description": (
            "Archive old balance snapshots. Moves entries older than N days "
            "from balances.jsonl to balances-archive.jsonl. Data is preserved, "
            "not deleted — this limits the data sent to the AI for recent analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keep_days": {
                    "type": "integer",
                    "description": "Keep snapshots from the last N days (default 90). Older entries are archived.",
                },
            },
            "required": [],
        },
        "requires_confirmation": True,
        "category": "write",
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
            "The wallet must retain at least 1,000 sats after the deposit (for signing fees). "
            "If the user asks to deposit 'all', subtract fees and the 1,000 sats reserve first. "
            "REQUIRED: (1) amount or amount_usd, (2) bot_name or bot_names or all_bots. "
            "If the user does not specify which bot, ask them."
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
                    "description": (
                        "REQUIRED: bot name (e.g. 'bot-1'). "
                        "Extract from user message or ask."
                    ),
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
            "Buy tokens on Odin.fun using BTC from a bot's trading account. "
            "Minimum trade: 500 sats. "
            "REQUIRED: (1) token_id, (2) amount or amount_usd, (3) bot_name. "
            "If the user gives a token name, call token_lookup FIRST to get the token_id. "
            "If any parameter is missing, ask the user before calling this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                    "description": (
                        "REQUIRED: token ID to buy (e.g. '29m8'). "
                        "Use token_lookup first if the user gives a name."
                    ),
                },
                "amount": {
                    "type": "integer",
                    "description": "Amount in sats to spend per bot.",
                },
                "amount_usd": {
                    "type": "number",
                    "description": (
                        "Amount in USD to spend per bot. "
                        "Use this when the user specifies a dollar amount."
                    ),
                },
                "bot_name": {
                    "type": "string",
                    "description": (
                        "REQUIRED: bot name (e.g. 'bot-1'). "
                        "Extract from user message or ask."
                    ),
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
            "Minimum trade value: 500 sats. "
            "REQUIRED: (1) token_id, (2) amount or amount_usd or 'all', (3) bot_name. "
            "If the user gives a token name, call token_lookup FIRST to get the token_id. "
            "If any parameter is missing, ask the user before calling this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                    "description": (
                        "REQUIRED: token ID to sell (e.g. '29m8'). "
                        "Use token_lookup first if the user gives a name."
                    ),
                },
                "amount": {
                    "type": "string",
                    "description": (
                        "Number of tokens to sell (e.g. '1000'), or 'all'."
                    ),
                },
                "amount_usd": {
                    "type": "number",
                    "description": (
                        "Amount in USD worth of tokens to sell per bot. "
                        "Use this when the user specifies a dollar amount."
                    ),
                },
                "bot_name": {
                    "type": "string",
                    "description": (
                        "REQUIRED: bot name (e.g. 'bot-1'). "
                        "Extract from user message or ask."
                    ),
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
            "REQUIRED: (1) amount or amount_usd or 'all', (2) bot_name or bot_names or all_bots. "
            "If the user does not specify which bot, ask them."
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
                    "description": (
                        "REQUIRED: bot name (e.g. 'bot-1'). "
                        "Extract from user message or ask."
                    ),
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
        "name": "token_transfer",
        "description": (
            "Transfer tokens from a bot's Odin.fun account to another Odin.fun account. "
            "This is an internal transfer within the platform — no selling/buying involved. "
            "The destination must be a registered Odin.fun user (IC principal). "
            "A 100 sats BTC fee is deducted from the sender's Odin.fun BTC balance. "
            "If the bot has insufficient BTC, the tool returns options — present them "
            "to the user and let them choose. Do NOT pre-fund bots before calling "
            "token_transfer. "
            "WARNING: Transfers are irreversible. Sending to a wrong address means "
            "permanent loss of tokens. Always verify the destination address. "
            "Provide amount as token count (e.g. '1000'), or 'all' for the entire balance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                    "description": "Token ID to transfer (e.g. '29m8').",
                },
                "amount": {
                    "type": "string",
                    "description": (
                        "Number of tokens to transfer (e.g. '1000'), "
                        "or 'all' for entire position."
                    ),
                },
                "to_address": {
                    "type": "string",
                    "description": (
                        "Destination address — IC principal, BTC deposit address, "
                        "or BTC wallet address of a bot's Odin.fun account. "
                        "Resolved to the account's IC principal via the Odin.fun API."
                    ),
                },
                "bot_name": {
                    "type": "string",
                    "description": "Source bot name (e.g. 'bot-1').",
                },
                "bot_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of source bot names.",
                },
                "all_bots": {
                    "type": "boolean",
                    "description": "Transfer from all configured bots.",
                },
            },
            "required": ["token_id", "amount", "to_address"],
        },
        "requires_confirmation": True,
        "category": "write",
    },
    {
        "name": "wallet_send",
        "description": (
            "Send from the iconfucius wallet. Two modes: "
            "(1) To an IC principal — sends ckBTC directly, no minimum. "
            "(2) To a BTC address (bc1...) — converts ckBTC to BTC via the ckBTC minter, "
            "minimum SEND AMOUNT is 50,000 sats (~$34), takes ~6 confirmations. "
            "For mode 2: the amount parameter MUST be at least 50,000 sats. "
            "If the user asks to send less than 50,000 sats to a bc1 address, "
            "tell them the minimum and ask if they want to send 50,000 sats instead. "
            "NEVER call this tool with less than 50,000 sats for a bc1 address. "
            "After a BTC send, use wallet_monitor to track confirmation progress. "
            "Provide amount (sats), amount_usd (dollars), or 'all'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "string",
                    "description": (
                        "Amount in sats to send, or 'all' for entire balance. "
                        "For BTC addresses: must be >= 50000."
                    ),
                },
                "amount_usd": {
                    "type": "number",
                    "description": (
                        "Amount in USD to send. "
                        "Converted to sats automatically. "
                        "Use this when the user specifies a dollar amount. "
                        "For BTC addresses: the converted sats must be >= 50000."
                    ),
                },
                "address": {
                    "type": "string",
                    "description": (
                        "Destination: IC principal (for ckBTC) "
                        "or Bitcoin address (bc1... for BTC)."
                    ),
                },
            },
            "required": ["address"],
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
