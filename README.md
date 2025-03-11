# IConfucius

**Wisdom fueled by Cycles**

<img src="./images/confucius.jpg" alt="Confucius" width="400">


Buy [IConfucius at odin.fun](https://odin.fun/token/29m8) !

`IConfucius` is an autonomous OpenChat bot
- We designed a prompt that turns on-chain Qwen2.5 into the philosopher IConfucius.
- IConfucius is a fully on-chain AI agent. (Yes, the LLM is running in a canister too!)


# OpenChat community

TODO: 
- Make public
- Connect IConfucius

The [OpenChat IConfucius channel](https://oc.app/community/e5qnd-hqaaa-aaaac-any5a-cai/channel/2411296919/?ref=45j3b-nyaaa-aaaac-aokma-cai)

# How it works

Their are two canisters:
- a Motoko bot canister, in `src/IConfucius`
- a C++ LLM canister, in `llms/IConfucius`.

The LLM is using a [llama_cpp_canister](https://github.com/onicai/llama_cpp_canister), loaded with 
the qwen2.5-0.5b-instruct-q8_0.gguf model from https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF


# Deploy your own IConfucius

If you want deploy your own IConfucius or develop on top of it, follow these instructions.

## Miniconda

Create a conda environment with python dependencies installed.

```bash
# install Miniconda on your system

# create a conda environment
conda create --name IConfucius python=3.11
conda activate IConfucius

# from IConfucius root folder
pip install -r requirements.txt
```

## mops

Install mops (https://mops.one/docs/install), and then:

```bash
# Do this in all these folders:
# - from folder: `IConfucius/src/IConfucius`
mops install
```

## Install dfx

When running locally, make sure to use the version of dfx prescribed by [open-chat](https://github.com/open-chat-labs/open-chat)

## Download the Qwen2.5 LLM model

Download qwen2.5-0.5b-instruct-q8_0.gguf from https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF

Place it in this location: `llama_cpp_canister/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q8_0.gguf`

Verify it is in correct location:

```bash 
# From root folder:
ls llama_cpp_canister/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q8_0.gguf
```

## Deploy open-chat

When running locally, first deploy [open-chat](https://github.com/open-chat-labs/open-chat)

### Silencing OpenChat's SNS debug logs

This helps reduce logging a lot:

```bash
dfx --identity anonymous canister stop sgymv-uiaaa-aaaaa-aaaia-cai
```

## Set the OpenChat public key

TODO: implement OpenChat bot...

When running locally, find the Open Chat instance public key, by going to:

`Profile settings` > `Advanced` > `Bot client config`

Copy the OpenChat public key and update the variable `openChatPublicKey`.

```JS
// file: src/IConfucius/src/Main.mo

// Update this based on your open chat instance public key
let openChatPublicKey = Text.encodeUtf8("MF...==");
```

## Deploy ALL canisters:

Note: The local network in all dfx.json files is defined as in the open-chat repo.

```bash
# from root folder: 
# (-) --mode install is slow, because the LLM model is uploaded.
# (-) --mode upgrade is fast, because the LLM model is NOT uploaded.
#       The canisters are re-build and re-deployed, but the LLM model 
#       is still in the canister's stable memory.
# (-) When we deployed to ic, the initial installation of each component was done manually
#     to ensure the LLMs ended up on the correct subnet
scripts/deploy-IConfucius.sh --mode [install/reinstall/upgrade] --network [local/ic]

# Only the first time, run it again with:
scripts/deploy-IConfucius.sh --mode upgrade --network [local/ic]
```

Note: When working on Windows, use WSL Ubuntu. You might first have to run 
```bash
sudo sysctl -w vm.max_map_count=2097152
```
to successfully load the models in the LLM canisters.

## IConfucius as a command type bot

**Test it works, using dfx**

```bash
# Trigger a single quote generation manually

# Option 1: Let IConfucius pick a random topic from a predefined list
dfx canister call iconfucius_ctrlb_canister generateNewQuote [--ic]

# Option 2: Specify the topic, for example ask for a quote about chickens
dfx canister call iconfucius_ctrlb_canister generateNewQuote '(opt "chickens")' [--ic]
```

**Test the endpoints with curl**

TODO...

```bash
# OpenChat will first call the execute_command endpoint, sending a JWT token
curl -i -X POST "http://<canister_id>:8080/execute_command" \
     -H "Content-Type: text/plain" \
     -d "-a jwt token-"
```

**Registering the bot with OpenChat**

Follow the instructions in [Registering the bot](https://github.com/open-chat-labs/open-chat-bots?tab=readme-ov-file#installing-the-bot)

- Create two users
- Login as the first user, and search for the second user
- In the Direct Chats chat box, type in `/register_bot` and fill out these fields:
  - Principal = canister_id of IConfucius
    - local: see src/IConfucius/.env
    - ic: see src/IConfucius/canister_ids.json
  - Bot name = IConfucius
  - Bot endpoint
    - local: http://<canister_id>.localhost:8080
      - Note: Check port with `dfx info webserver-port`
    - ic: https://<canister_id>.raw.icp0.io/



## IConfucius as an autonomous type bot

IConfucius can run in autonomous mode, using timers.

However, the Motoko openchat-bot-sdk does not yet support API keys, only Command type bots.

So, for now, just skip this...

**Start the timers**

```bash
# from root folder:
scripts/start-timers.sh --network [local/ic]
scripts/stop-timers.sh --network [local/ic]
```

After starting When using the timers, the quote generation takes a moment. To ensure it works:
```bash
# from folder: src/IConfucius
dfx canister call iconfucius_ctrlb_canister getQuotesAdmin --output json [--ic]
dfx canister call iconfucius_ctrlb_canister getNumQuotesAdmin --output json [--ic]
```

**Connect to OpenChat**

TODO...


## Prompt Design

We designed the prompt using `scripts/prompt-design.ipynb`

That notebook runs llama.cpp directly on your computer, and you can very quickly try out modifications.

Make sure to design your own prompts so that the repetitive part is at the beginning, to benefit from prompt caching. When running LLMs inside a canister, this will help tremendously with cost & latency.

# OpenChat bot 

The Motoko canister of IConfucius is using [openchat-bot-sdk](https://j4mwm-bqaaa-aaaam-qajbq-cai.ic0.app/openchat-bot-sdk)


# Tips & Tricks

## Silencing OpenChat's SNS debug logs

```bash
dfx --identity anonymous canister stop sgymv-uiaaa-aaaaa-aaaia-cai
```

## Adding cycles

NOTE: when working locally, you easily add cycles to the canisters with:
```bash
# From the canister folders: to add 2 trillion cycles
dfx ledger fabricate-cycles --all --t 2
```

