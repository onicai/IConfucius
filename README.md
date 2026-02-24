[![cicd](https://github.com/onicai/IConfucius/actions/workflows/cicd.yml/badge.svg)](https://github.com/onicai/IConfucius/actions/workflows/cicd.yml)

<p align="center">                                                                                          
    <img src="agent/brand/iconfucius_social_preview.png" alt="IConfucius | Wisdom for Bitcoin Markets">       
  </p>  

---

# Setup

## Prerequisites

A C compiler is currently required to install iconfucius because one of
its transitive dependencies (`ed25519-blake2b`, pulled in by
`bitcoin-utils` -> `hdwallet`) ships without pre-built wheels and must
be compiled from source. We are working on removing this dependency.

| Platform        | Install build tools                                       |
| --------------- | --------------------------------------------------------- |
| macOS (Homebrew) | `xcode-select --install && brew install automake libtool` |
| Ubuntu / Debian | `sudo apt-get install -y build-essential`                 |
| Fedora / RHEL   | `sudo dnf install gcc gcc-c++ make`                       |
| Windows         | Use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install), then follow the Ubuntu instructions above |

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

## How to run with llama.cpp server

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

# Start with the recommended model (~4.7GB download on first run)
# Port 55128 = Confucius' birthday (September 28, 551 BC)
llama-server --jinja --port 55128 -hf bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M
```

Leave that terminal running.

Pick a different model if you have less (or more) RAM:

| Size   | Model            | `-hf` flag                                                    |
| ------ | ---------------- | ------------------------------------------------------------- |
| ~0.7GB | LFM2.5-1.2B     | `LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M`                |
| ~2.2GB | Ministral-3-3B   | `mistralai/Ministral-3-3B-Instruct-2512-GGUF:Q4_K_M`        |
| ~2.5GB | Phi-4-mini       | `bartowski/microsoft_Phi-4-mini-instruct-GGUF:Q4_K_M`       |
| ~4.7GB | Qwen2.5-Coder-7B | `bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M`          |
| ~7.5GB | Mistral-NeMo-12B | `bartowski/Mistral-Nemo-Instruct-2407-GGUF:Q4_K_M`          |

All models use Q4_K_M quantization and support llama.cpp's native tool calling.

### 2. Configure iconfucius

Add (or uncomment) the `[ai]` section in your `iconfucius.toml`:

```toml
[ai]
backend = "llamacpp"
model = "Qwen2.5-Coder-7B-Instruct"
```

The server URL defaults to `http://localhost:55128` — override with
`llamacpp_url` if needed.

### 3. Chat

In a second terminal:

```bash
iconfucius
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
- ✅ Dual conversation logs: `ai-full` (complete API replay) and `ai-cached` (quick reading)
- ✅ Prompt caching: system prompt and tools cached with Anthropic's ephemeral cache for lower latency and cost
- ✅ Default AI model: Claude opus-4-6 with `/model` command to switch at runtime

## Coming Next

- 🚧 Learning loop: AI reflects on trades, extracts patterns, revises strategy over time
- 🚧 Auto-pilot mode: autonomous trading with budget limits
- 🚧 More AI backends: llama.cpp, Ollama, Grok, OpenAI, Gemini, etc.
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
