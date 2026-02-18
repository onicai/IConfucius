# How iconfucius Works

iconfucius lets you trade Bitcoin Runes on [Odin.fun](https://odin.fun) programmatically. Under the hood, it uses the [Internet Computer](https://internetcomputer.org/) (IC) for key management and authentication.

## Architecture

```
┌─────────────┐       ┌────────────────────────┐       ┌─────────────┐
│  iconfucius  │──────▶│  onicai                │──────▶│  Odin.fun   │
│  (CLI)      │       │  ckSigner  (canister)  │       │  REST API   │
└─────────────┘       └────────────────────────┘       └─────────────┘
       │                      │
       │                      ├── Threshold Schnorr signing (BIP340)
       │                      └── Per-bot Bitcoin key derivation
       │
       ├── SIWB authentication (Sign In With Bitcoin)
       ├── ICRC-1 transfers (ckBTC)
       └── Session caching (JWT + delegation)
```

## Authentication Flow (SIWB)

iconfucius uses [Sign In With Bitcoin](https://github.com/AstroxNetwork/ic-siwb) (SIWB) to authenticate each bot on Odin.fun:

1. **Get public key** — CLI asks the onicai ckSigner canister for the bot's Schnorr public key (BIP340)
2. **Derive address** — Public key is converted to a P2TR (`bc1p...`) Bitcoin address
3. **Prepare login** — SIWB canister issues a challenge message for that address
4. **Sign challenge** — onicai ckSigner canister signs the challenge using threshold Schnorr (BIP322 format)
5. **SIWB login** — Signed proof is submitted to the SIWB canister, which issues a delegation
6. **Get JWT** — Delegation is exchanged with the Odin.fun REST API for a JWT token

After login, the JWT is cached in `.cache/session_{bot_name}.json` (valid for 24 hours).

## Key Derivation

The onicai ckSigner canister derives a unique Bitcoin key for each `(caller, bot_name)` pair using IC threshold Schnorr. This means:

- Different PEM identities get different keys (even for the same bot name)
- Different bot names get different keys (even for the same PEM identity)
- Keys are deterministic — the same inputs always produce the same Bitcoin address

## Token Transfers (ckBTC)

iconfucius uses [ckBTC](https://internetcomputer.org/ckbtc), a 1:1 Bitcoin-backed token on the IC, for deposits and withdrawals. Transfers use the [ICRC-1](https://github.com/dfinity/ICRC-1) token standard:

- **Deposit**: Transfer ckBTC from your wallet into Odin.fun's trading account
- **Withdraw**: Move funds from Odin.fun back to your wallet as ckBTC
- **Wallet send**: Transfer ckBTC to any IC principal, or BTC to any Bitcoin address

## The onicai ckSigner Canister

The onicai ckSigner canister ([`g7qkb-iiaaa-aaaar-qb3za-cai`](https://dashboard.internetcomputer.org/canister/g7qkb-iiaaa-aaaar-qb3za-cai)) is deployed on a **fiduciary subnet** of IC mainnet, which provides access to threshold Schnorr signing. It exposes three endpoints:

- `getPublicKey({ botName })` — Returns the bot's x-only public key and P2TR address
- `sign({ botName, message, payment? })` — Signs a 32-byte hash with the bot's Schnorr key, with optional ICRC-2 fee payment
- `getFeeTokens()` — Returns the configured fee tokens and treasury

The canister source code is [open source with a reproducible build](https://github.com/onicai/ChainFusionAI).
