## IConfucius as an autonomous type bot

🚧 🚧 🚧 🚧 🚧 (Work in progress...)

_SKIP THIS STEP UNTIL FURTHER NOTICE._

IConfucius can run in autonomous mode, using timers, and it will thus be possible to connect it to the OpenChat bot platform as an autonomous bot that automatically posts profound quotes on a regular basis.

However the Motoko openchat-bot-sdk does not yet support API keys, only Command type bots.

As soon as the SDK supports API keys, we will implement this capability.

**Start the timers**

```bash
# from root folder:
scripts/start-timers.sh [--network ic]
scripts/stop-timers.sh [--network ic]
```

After some time, several quotes have been generated.

IConfucius saves all his generated quotes in a stable memory data structure, and as the controller of the canister, you can pull them out:

```bash
# from folder: src/IConfucius
dfx canister call iconfucius_ctrlb_canister getQuotesAdmin --output json [--ic]
dfx canister call iconfucius_ctrlb_canister getNumQuotesAdmin --output json [--ic]
```
