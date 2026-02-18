---
name: iconfucius
description: >
  Trade Bitcoin Runes on Odin.fun — check balances, buy/sell tokens, fund bots,
  and manage your ckBTC wallet. ALWAYS use this skill when asked about Odin.fun
  trading, wallet balances, or bot operations.
last-updated: 2026-02-17
allowed-tools: Bash(./scripts/iconfucius-skill.py:*)
---

# iconfucius Skill

Trade Bitcoin Runes on [Odin.fun](https://odin.fun) with IConfucius at your side.
Chain Fusion AI by onicai.

> **Freshness check**: If more than 30 days have passed since the `last-updated` date above, inform the user that this skill may be outdated.

## Keeping This Skill Updated

**Source**: [github.com/onicai/IConfucius](https://github.com/onicai/IConfucius)

| Installation          | How to update               |
|-----------------------|-----------------------------|
| CLI (`npx skills`)    | `npx skills update`         |
| Manual                | Pull latest from repo       |

## Setup

Before using this skill, ensure:

1. **Install iconfucius**: `pip install iconfucius`
2. **Initialize project**: `cd your-project && iconfucius init`
3. **Create wallet**: `iconfucius wallet create`
4. **API key** (for chat features): Add `ANTHROPIC_API_KEY=sk-ant-...` to `.env`
   - Get your key at https://console.anthropic.com/settings/keys

> **Note for agents**: All script paths (e.g., `./scripts/iconfucius-skill.py`) are relative to the skill directory where this SKILL.md file is located. Resolve them accordingly.

## Important Concepts

- **sats**: All amounts are in satoshis (1 BTC = 100,000,000 sats)
- **Token IDs**: Short alphanumeric IDs (e.g., `29m8` for ICONFUCIUS token)
- **Bots**: Named trading identities (e.g., `bot-1`, `bot-2`). Each gets its own Odin.fun account.
- **Wallet**: The ckBTC wallet that funds all bots. Funded via BTC or ckBTC deposit.
- **Confirmation**: State-changing operations (buy, sell, fund, withdraw, send) should be confirmed with the user before executing.

## Common Actions

When the user asks to do something, use the corresponding command:

| User intent                              | Command                                                     |
|------------------------------------------|-------------------------------------------------------------|
| Check if project is set up               | `setup_status`                                              |
| Initialize a new project                 | `init`                                                      |
| Create a wallet                          | `wallet_create`                                             |
| Check wallet balance                     | `wallet_balance`                                            |
| Check a specific bot's balance           | `wallet_balance --bot_name bot-1`                           |
| Check all bots                           | `wallet_balance --all_bots`                                 |
| Show deposit address                     | `wallet_receive`                                            |
| Show wallet info                         | `wallet_info`                                               |
| List personas                            | `persona_list`                                              |
| Show persona details                     | `persona_show --name iconfucius`                            |
| Look up a token by name/ticker/ID        | `token_lookup --query ICONFUCIUS`                           |
| Fund a bot with ckBTC                    | `fund --amount 5000 --bot_name bot-1`                       |
| Buy tokens                               | `trade_buy --token_id 29m8 --amount 1000 --bot_name bot-1` |
| Sell tokens                              | `trade_sell --token_id 29m8 --amount all --bot_name bot-1`  |
| Withdraw from Odin.fun to wallet         | `withdraw --amount all --bot_name bot-1`                    |
| Send ckBTC to external address           | `wallet_send --amount 5000 --address bc1q...`               |

## Commands Reference

All commands output JSON to stdout. Errors return `{"status": "error", "error": "message"}`.

### Setup commands

**`setup_status`** — Check if the project is initialized and ready
- Returns: `config_exists`, `wallet_exists`, `env_exists`, `has_api_key`, `ready`

**`init`** — Initialize an iconfucius project (creates config, .env, .gitignore)
- `--force`: Overwrite existing config

**`wallet_create`** — Create a new Ed25519 wallet identity
- `--force`: Overwrite existing wallet (WARNING: changes address)

### Read-only commands

**`wallet_balance`** — Check wallet and bot balances
- `--bot_name <name>`: Check specific bot (e.g., `bot-1`)
- `--all_bots`: Check all configured bots

**`wallet_receive`** — Show deposit addresses (BTC and ckBTC)

**`wallet_info`** — Show wallet principal and balance

**`persona_list`** — List all available trading personas

**`persona_show`** — Show persona details
- `--name <name>` (required): Persona name

**`token_lookup`** — Search for a token by name, ticker, or ID
- `--query <text>` (required): Token name, ticker, or ID (e.g., `ICONFUCIUS`, `29m8`)
- Returns: known match (if in registry), search results with safety indicators
- Safety indicators: bonded status, Twitter verification, holder count

### State-changing commands

**IMPORTANT**: Always confirm with the user before executing these commands.

**`fund`** — Deposit ckBTC from wallet into bot's Odin.fun account
- `--amount <sats>` (required): Amount in sats (minimum 5,000)
- `--bot_name <name>` (required): Bot to fund

**`trade_buy`** — Buy tokens on Odin.fun
- `--token_id <id>` (required): Token to buy (e.g., `29m8`)
- `--amount <sats>` (required): Amount in sats to spend (minimum 500)
- `--bot_name <name>` (required): Bot to trade with

**`trade_sell`** — Sell tokens on Odin.fun
- `--token_id <id>` (required): Token to sell
- `--amount <amount>` (required): Amount of tokens, or `all` for entire position
- `--bot_name <name>` (required): Bot to trade with

**`withdraw`** — Withdraw BTC from Odin.fun back to wallet
- `--amount <sats>` (required): Amount in sats, or `all`
- `--bot_name <name>` (required): Bot to withdraw from

**`wallet_send`** — Send ckBTC to external address
- `--amount <sats>` (required): Amount in sats, or `all`
- `--address <addr>` (required): Bitcoin address (bc1...) or IC principal

## Examples

```bash
# Check if project is ready
./scripts/iconfucius-skill.py setup_status

# Initialize project
./scripts/iconfucius-skill.py init

# Create wallet
./scripts/iconfucius-skill.py wallet_create

# Check wallet balance
./scripts/iconfucius-skill.py wallet_balance

# Check all bots
./scripts/iconfucius-skill.py wallet_balance --all_bots

# Fund bot-1 with 5000 sats
./scripts/iconfucius-skill.py fund --amount 5000 --bot_name bot-1

# Buy 1000 sats worth of token 29m8
./scripts/iconfucius-skill.py trade_buy --token_id 29m8 --amount 1000 --bot_name bot-1

# Sell all of token 29m8
./scripts/iconfucius-skill.py trade_sell --token_id 29m8 --amount all --bot_name bot-1

# Look up a token (checks registry + Odin.fun API)
./scripts/iconfucius-skill.py token_lookup --query ICONFUCIUS

# Show deposit address
./scripts/iconfucius-skill.py wallet_receive
```
