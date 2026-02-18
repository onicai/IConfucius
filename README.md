[![cicd](https://github.com/onicai/IConfucius/actions/workflows/cicd.yml/badge.svg)](https://github.com/onicai/IConfucius/actions/workflows/cicd.yml)

<p align="center">                                                                                          
    <img src="agent/brand/iconfucius_social_preview.png" alt="IConfucius | Wisdom for Bitcoin Markets">       
  </p>  

---

# Setup

```bash
pip install iconfucius # Note: On macOS Apple Silicon 
                       # install `automake` and `libtool` 
                       # before running `pip install`:
                       # brew install automake libtool

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
