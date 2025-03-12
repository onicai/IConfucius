# IConfucius

**Wisdom fueled by Cycles**

<img src="./images/confucius.jpg" alt="Confucius" width="400">

🚀 Meet IConfucius: The ancient Chinese philosopher... now living in a canister of the Internet Computer!

⚡ He is also on odin_fun → Token https://odin.fun/token/29m8

🤖 And an OpenChat bot

# IConfucius Roadmap

IConfucius is an odin.fun token that demonstrates the on-chain AI technology of [onicai](https://www.onicai.com/).

We created it to showcase what you can do with LLMs that run completely in canisters of the [Internet Computer](https://internetcomputer.org/).

There are many benefits to running your AI fully on-chain on the Internet Computer. One of them is that interacting with other applications, like [OpenChat](https://oc.app/) and [odin.fun](https://odin.fun), becomes very easy. In addition, your AI and LLM are fully under your control, easily protected against misuse and hacking, and using the Internet Computer's reverse gas models, you decide how much you want to spent (no surprise bills ❣️ ).

We have the following roadmap in mind for IConfucius:

- ✅️ IConfucius canisters deployed
- ✅️ IConfucius can be prompted from command line (dfx)
- ✅️ Launched on odin.fun → Token https://odin.fun/token/29m8
- ✅️ Set up the [IConfucius OpenChat community](https://oc.app/community/e5qnd-hqaaa-aaaac-any5a-cai/channel/2411296919/?ref=45j3b-nyaaa-aaaac-aokma-cai)
- 🚧 IConfucius as an OpenChat command bot
- 🚧 IConfucius as an OpenChat autonomous bot
- 🚧 IConfucius posting his quotes of wisdom directly to odin.fun
- 🚧 IConfucius posting his quotes of wisdom directly to X
- 🚧 IConfucius 孔夫子创智慧，载道于母语之文，传世于天下。
- 🧠 IConfucius listens to his followers and evolves

# How IConfucius works

IConfucius is a deployed [llama_cpp_canister](https://github.com/onicai/llama_cpp_canister), loaded with the Qwen 2.5 model, and controlled by a Motoko canister designed to turn the Qwen2.5 LLM into Confucius, the ancient Chinese philosopher. When prompted, it will generate profound quotes about topics.

Their are two canisters:
- a Motoko bot canister, in `src/IConfucius`
- a C++ LLM canister, in `llms/IConfucius`.
  - The LLM is loaded with the [qwen2.5-0.5b-instruct-q8_0.gguf](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) model

Our OpenChat bot implementation is based on the Motoko [openchat-bot-sdk](https://j4mwm-bqaaa-aaaam-qajbq-cai.ic0.app/openchat-bot-sdk) developed by the ICP community member [Geckteck](https://x.com/Gekctek). Many thanks go out to him.


# Deploy your own IConfucius

The instructions in this section cover how you can deploy everything locally on your computer.

We value DeCentralized AI, and one of the great things about the Internet Computer is that it
allows anyone to spin up their own software applications, including AI agents that run 100% in canisters, under your control.

That is why we are building IConfucius in the open, and everything is Open Source.

We hope many of you will deploy your own IConfucius canisters, play with it, learn from it, and
then build & deploy your own on-chain AI agents that do something else. We can't wait to see what you will create.


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

## Download the Qwen2.5 LLM model

Download qwen2.5-0.5b-instruct-q8_0.gguf from https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF

Place it in this location: `llms/llama_cpp_canister/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q8_0.gguf`

Verify it is in correct location:

```bash 
# From root folder:
ls llms/llama_cpp_canister/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q8_0.gguf
```

## mops

Install mops (https://mops.one/docs/install), and then:

```bash
# from folder: `IConfucius/src/IConfucius`
mops install
```

## Install dfx

Since IConfucius is an OpenChat bot, make sure to use the version of dfx prescribed by [open-chat](https://github.com/open-chat-labs/open-chat)

## Deploy open-chat

When running locally, first deploy [open-chat](https://github.com/open-chat-labs/open-chat):

```bash
# from folder: open-chat (repo)
rm -rf .dfx
dfx start --clean
./scripts/deploy-local.sh

# Silence OpenChat's SNS debug logs
dfx --identity anonymous canister stop sgymv-uiaaa-aaaaa-aaaia-cai
```

## Set the OpenChat public key

🚧 🚧 🚧 🚧 🚧 (Work in progress...)

*SKIP THIS STEP UNTIL FURTHER NOTICE.*

Get the public key of your locally running Open Chat instance, by going to:

`Profile settings` > `Advanced` > `Bot client config`

Copy the OpenChat public key and update the variable `openChatPublicKey`.

```JS
// file: src/IConfucius/src/Main.mo

// Update this based on your open chat instance public key
let openChatPublicKey = Text.encodeUtf8("MF...==");
```

## Deploy ALL canisters:

```bash
# from root folder: 

# The first time, use this command:
scripts/deploy-IConfucius.sh --mode install --network [local/ic]

# After this, to upgrade the canisters for a code change:
scripts/deploy-IConfucius.sh --mode upgrade --network [local/ic]
```

Notes: 
- `--mode install` & `--mode reinstall` take several minutes, because the LLM model is uploaded.
- `--mode upgrade` is fast, because the LLM model is NOT uploaded. All the canisters are 
re-build and re-deployed, but the LLM model is still as a virtual file in the canister's 
stable memory.
- When you deploy to the ic mainnet, it is recommended to do the initial deploy of each 
component manually and specify the subnet. Pick one that is not so busy, because LLMs use a lot of computations.

- When working on Windows, use WSL Ubuntu. To successfully load the LLM model into the LLM canister, you might first have to run 
  ```bash
  sudo sysctl -w vm.max_map_count=2097152
  ```


## IConfucius as a command type bot

**Test it works, using dfx**

```bash
# from folder: src/IConfucius

# Option 1: Let IConfucius pick a random topic from a predefined list
dfx canister call iconfucius_ctrlb_canister IConfuciusSays [--ic]

# Option 2: Specify the topic, for example ask for a quote about crypto
dfx canister call iconfucius_ctrlb_canister IConfuciusSays '(opt "crypto")' [--ic]
```

**Registering the bot with OpenChat**

🚧 🚧 🚧 🚧 🚧 (Work in progress...)

*SKIP THIS STEP UNTIL FURTHER NOTICE.*

Follow the instructions in [Registering the bot](https://github.com/open-chat-labs/open-chat-bots?tab=readme-ov-file#installing-the-bot)

- Create two users
- Login as the first user, and search for the second user
- In the Direct Chats chat box, type in `/register_bot` and fill out these fields:
  - Principal = canister_id of IConfucius
    - local: see src/IConfucius/.env
    - ic: see src/IConfucius/canister_ids.json
  - Bot name = IConfucius
  - Bot endpoint
    - local: http://<canister_id>.raw.localhost:8080
      - Note: Check port with `dfx info webserver-port`
    - ic: https://<canister_id>.raw.icp0.io/



## IConfucius as an autonomous type bot

🚧 🚧 🚧 🚧 🚧 (Work in progress...)

*SKIP THIS STEP UNTIL FURTHER NOTICE.*

IConfucius can run in autonomous mode, using timers, and it will thus be possible to connect it to the OpenChat bot platform as an autonomous bot that automatically posts profound quotes on a regular basis.

However the Motoko openchat-bot-sdk does not yet support API keys, only Command type bots.

As soon as the SDK supports API keys, we will implement this capability.

**Start the timers**

```bash
# from root folder:
scripts/start-timers.sh --network [local/ic]
scripts/stop-timers.sh --network [local/ic]
```

After some time, several quotes have been generated. 

IConfucius saves all his generated quotes in a stable memory data structure, and as the controller of the canister, you can pull them out:
```bash
# from folder: src/IConfucius
dfx canister call iconfucius_ctrlb_canister getQuotesAdmin --output json [--ic]
dfx canister call iconfucius_ctrlb_canister getNumQuotesAdmin --output json [--ic]
```

# Prompt Design

We designed the prompt using [scripts/prompt-design.ipynb](https://github.com/onicai/IConfucius/blob/main/scripts/prompt-design.ipynb).

The python notebook runs llama.cpp directly on your computer, and you can very quickly try out modifications.

Make sure to design your own prompts so that the repetitive part is at the beginning, to benefit from prompt caching. When running LLMs inside a canister, this will help tremendously with cost & latency.


# Tips & Tricks

## Adding cycles

The LLM canister burns a lot of cycles, and you will quickly run out.

When working locally, you easily add cycles to all the deployed canisters with:
```bash
# From the canister folders: to add 2 trillion cycles
dfx ledger fabricate-cycles --all --t 2
```

**Test the endpoint called by OpenChat with curl**

🚧 🚧 🚧 🚧 🚧 (Work in progress...)

*SKIP THIS STEP UNTIL FURTHER NOTICE.*

Executing these commands is very helpful to debug things and to understand what goes on under the hood of the OpenChat bot platform and the Motoko bot SDK.

Some useful curl commands:

```bash
# OpenChat will first call the execute_command endpoint, sending a JWT token
curl -i -X POST "http://<canister_id>.raw.localhost:8080/execute_command" \
     -H "Content-Type: text/plain" \
     -d "-a jwt token-"
```
