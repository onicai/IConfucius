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

We have the following roadmap in mind for IConfucius:

- ✅️ Launched on [ODIN•FUN](https://odin.fun?r=mgb3mzvghe) → Token https://odin.fun/token/29m8
- ✅️ IConfucius on-chain can generate quotes in either English or Chinese → [Try it out](https://aiconfucius-w8i.caffeine.xyz/)
- ✅️ IConfucius on-chain deployed with reproducible builds, in preparation of decentralization
- ✅️ IConfucius daily quote of wisdom posted to [IConfucius X (Twitter) account](https://x.com/IConfucius_odin)
- ✅️ IConfucius daily quote of wisdom posted to OpenChat
- ✅️ IConfucius Chain Fusion AI agent: trade from the command line
- 🚧 IConfucius takes a role in [funnAI](https://funnai.onicai.com/)
- 🧠 IConfucius evolves his abilities under governance of the [onicai SNS](https://www.onicai.com/files/onicai_SNS_Whitepaper.pdf)


# Reference

The Bitcoin rune trading platform is [Odin Fun](https://odin.fun/)

# License

MIT
