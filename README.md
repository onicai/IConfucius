[![cicd](https://github.com/onicai/IConfucius/actions/workflows/cicd.yml/badge.svg)](https://github.com/onicai/IConfucius/actions/workflows/cicd.yml) ![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/onicai/IConfucius?utm_source=oss&utm_medium=github&utm_campaign=onicai%2FIConfucius&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)

<p align="center">                                                                                          
    <img src="agent/brand/iconfucius_social_preview.png" alt="IConfucius | Wisdom for Bitcoin Markets">       
  </p>  

---

# Setup

## Install

```bash
pip install iconfucius

mkdir my-iconfucius
cd my-iconfucius
iconfucius
```

That's it. The onboarding wizard runs automatically on first launch:

1. Creates iconfucius.toml (asks how many bots)
2. Asks for your Anthropic API key
    
    Get one at: https://console.anthropic.com/settings/keys
3. Creates your wallet (.wallet/identity-private.pem)
4. Shows your deposit address
5. Launches the AI chat

Everything is stored in the current directory — run `iconfucius`
from the same folder next time.

## How to run with llama.cpp server (experimental)

You can run iconfucius with a fully local AI — no API key, no cloud.

### 1. Install & start the server

```bash
# macOS
brew install llama.cpp

# Ubuntu / Debian — build from source
sudo apt-get install -y build-essential cmake libcurl4-openssl-dev
git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp
cmake -B build && cmake --build build --config Release -j
sudo cmake --install build
```

Start the server with the recommended model (~10.4 GB download on first run):

```bash
# Port 55128 = Confucius' birthday (September 28, 551 BC)
llama-server \
  --jinja -fa \
  --port 55128 \
  -np 1 \
  -hf bartowski/Mistral-Nemo-Instruct-2407-GGUF:Q6_K_L
```

Leave that terminal running.

| Flag      | Purpose                                                    |
| --------- | ---------------------------------------------------------- |
| `--jinja` | Enables native tool/function calling via chat templates    |
| `-fa`     | Enables flash attention for faster inference               |
| `-np 1`   | Single slot — optimal for single-user conversations        |

### Why Mistral Nemo 12B?

iconfucius relies heavily on tool calling (buy, sell, fund, withdraw, balance
checks, etc.) and multi-turn conversation to help users trade. In our testing,
**models smaller than 12B were not accurate enough** — they frequently made
incorrect tool calls, lost track of the conversation context, and gave
unreliable trading advice. Mistral Nemo 12B is the smallest model we found
that consistently handles tool use and maintains coherent multi-turn
conversations.

**Recommended quantization: Q6_K_L** (~10.4 GB). With the KV cache for a
16K context window, expect ~12 GB total RAM usage. This fits comfortably on
machines with 16 GB RAM or a GPU with 12+ GB VRAM.

Alternative quantizations if RAM is tight:

| Quant  | Model Size | Total RAM* | `-hf` flag                                            |
| ------ | ---------- | ---------- | ----------------------------------------------------- |
| Q6_K_L | 10.4 GB    | ~12 GB     | `bartowski/Mistral-Nemo-Instruct-2407-GGUF:Q6_K_L`   |
| Q5_K_M | 8.7 GB     | ~11 GB     | `bartowski/Mistral-Nemo-Instruct-2407-GGUF:Q5_K_M`   |
| Q4_K_M | 7.5 GB     | ~9 GB      | `bartowski/Mistral-Nemo-Instruct-2407-GGUF:Q4_K_M`   |

*Total RAM includes the KV cache at the default 16K context window.

### Prompt caching

The llama.cpp server automatically caches conversation prefixes via its
KV cache. Each turn, only new tokens are computed — the system prompt and
prior messages are reused from cache. No client-side configuration needed;
this works out of the box with `--cache-prompt` (enabled by default).

### 2. Configure iconfucius

Add (or uncomment) the `[ai]` section in your `iconfucius.toml`:

```toml
[ai]
api_type = "openai"
base_url = "http://localhost:55128"
```

This works with any OpenAI-compatible endpoint (llama.cpp, Ollama, vLLM,
LM Studio, Together AI, etc.). The `base_url` defaults to
`http://localhost:55128` if omitted.

> **Note**: If you previously configured an Anthropic API key (in `.env`),
> you can keep both. The `[ai]` section in `iconfucius.toml` determines which
> backend is used. Use `/ai` at runtime to switch, or remove the `[ai]`
> section to go back to Claude.

### 3. Chat

In a second terminal:

```bash
iconfucius --experimental   # enables /ai command to switch models at runtime
```

## Project Layout

```
my-iconfucius/
├── .gitignore             # ignores .env, .wallet/, .cache/, .memory/
├── .env                   # API keys (ANTHROPIC_API_KEY=...)
├── iconfucius.toml        # trading bots config
├── .wallet/               # identity key (BACK UP!)
│   └── identity-private.pem
├── .cache/                # delegated identities (auto-created)
│   ├── session_bot-1.json # no backup needed — regenerated
│   ├── session_bot-2.json # when expired (24h lifetime)
│   └── session_bot-3.json
└── .memory/               # AI trading memory
    └── iconfucius/
        ├── trades.md
        ├── learnings.md
        └── strategy.md
```

## Status & Disclaimer

This project is in **alpha**. APIs may change without notice.

The software and hosted services are provided "as is", without warranty of any kind. Use at your own risk. The authors and onicai are not liable for any losses — including but not limited to loss of funds, keys, or data — incurred through use of this software or the hosted canister services. No guarantee of availability, correctness, or security is made. You are solely responsible for evaluating the suitability of these services for your use case and for complying with all applicable laws and regulations in your jurisdiction.

---

# IConfucius Roadmap

## Done

- ✅ Launched on [ODIN•FUN](https://odin.fun?r=mgb3mzvghe) → Token https://odin.fun/token/29m8
- ✅ IConfucius on-chain can generate quotes in either English or Chinese → [Try it out](https://aiconfucius-w8i.caffeine.xyz/)
- ✅ IConfucius on-chain deployed with reproducible builds
- ✅ Daily quote of wisdom posted to [X (@IConfucius_odin)](https://x.com/IConfucius_odin) and OpenChat
- ✅ Chain Fusion AI agent: AI chat, multi-bot trading, wallet management
- ✅ Agent skills with tool use (buy, sell, fund, withdraw, sweep, token lookup, token price)
- ✅ Live market data: token price, 1h/6h/24h price changes, market cap, volume, liquidity
- ✅ USD amount support: "buy $20 of ICONFUCIUS" or "sell $5 worth" with live conversion
- ✅ Enriched trade log: price, estimated tokens/sats, USD values for P&L tracking
- ✅ Memory system: automatic trade recording, per-persona strategy and learnings (`.memory/`)
- ✅ IC certificate verification (blst) for secure balance checks
- ✅ CI/CD pipeline across Python 3.11, 3.12, 3.13
- ✅ Self-upgrade: `/upgrade` command updates and restarts the CLI in-place
- ✅ Version awareness: shows running version in prompt, notifies when updates are available
- ✅ Conversation logs: `ai-cached` JSONL with system/tools deduplication for quick reading
- ✅ Prompt caching: system prompt, tools, and messages cached with Anthropic's ephemeral cache for lower latency and cost (Claude backend only)
- ✅ Default AI model: Claude opus-4-6 with `/ai` command to switch at runtime (experimental)
- ✅ OpenAI-compatible API backend: llama.cpp, Ollama, vLLM, LM Studio, Together AI, etc.

## Coming Next

- 🚧 Learning loop: AI reflects on trades, extracts patterns, revises strategy over time
- 🚧 Auto-pilot mode: autonomous trading with budget limits
- 🚧 More AI backends: Grok, OpenAI, Gemini, etc.
- 🚧 Social integration: trade announcements and market wisdom via X and OpenChat
- 🚧 On-chain memory sync: back up trading experience to mAIner canister on the IC
- 🚧 IConfucius takes a role in [funnAI](https://funnai.onicai.com/) — mAIners become autonomous traders?
- 🚧 funnAI marketplace: buy and sell proven trading strategies (ICRC-7 NFTs)
- 🚧 Multi-language support: full Chinese (中文) UI and AI responses, then more languages
- 🚧 Token launcher: autonomous token creation on Odin.fun


# Reference

[Odin Fun](https://odin.fun/) - Bitcoin Rune memecoin trading platform

# License

MIT
