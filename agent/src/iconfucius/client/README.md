# IConfucius Dashboard

Web UI for the IConfucius Runes trading agent. Provides wallet management, bot monitoring, trade history, market data, and an AI chat assistant for executing trades on Odin.fun.

## Prerequisites

- **Node.js** 18+
- **Python** 3.10+ (for the proxy server)
- **iconfucius SDK** installed (`pip install -e agent/` from the project root)
- **curl_cffi** Python package (`pip install curl_cffi`)
- **Anthropic API key** (for the AI chat — you'll be prompted on first use)

## Quick Start

```bash
# 1. Install frontend dependencies
cd agent/client
npm install

# 2. Start the proxy server (in one terminal)
npm run proxy

# 3. Start the dev server (in another terminal)
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Architecture

```
Browser  →  Vite dev server (:3000)  →  /api/*  →  Python proxy (:3001)
                                                      ├── Odin.fun REST API (via curl_cffi)
                                                      ├── iconfucius SDK (wallet, bots, trades)
                                                      └── Anthropic API (AI chat)
```

- **Vite** serves the React frontend and proxies `/api/*` requests to the Python backend.
- **proxy-server.py** handles Odin.fun API calls (with Cloudflare bypass via TLS fingerprint impersonation), wallet/bot operations through the iconfucius SDK, and AI chat sessions.

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server on port 3000 |
| `npm run proxy` | Start Python proxy server on port 3001 |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview production build |

## First-Time Setup

If you haven't initialized the project yet, the Wallet tab will walk you through:

1. **Initialize Project** — creates `iconfucius.toml` and bot configurations
2. **Create or Import Wallet** — generate a new Ed25519 identity or import an existing `.pem` backup

## Troubleshooting

**Proxy offline / API errors**
- Make sure `npm run proxy` is running in a separate terminal from within the `client/` directory.

**`ModuleNotFoundError: No module named 'iconfucius'`**
- Install the SDK: `pip install -e agent/` from the project root (not from `client/`).

**`ModuleNotFoundError: No module named 'curl_cffi'`**
- Install it: `pip install curl_cffi`

**Chat says "API key required"**
- Enter your Anthropic API key when prompted. It gets saved to `.env` in the project root.
