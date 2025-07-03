# IConfucius

**Wisdom fueled by Cycles**

<img src="./images/IConfucius/IConfucius.jpg" alt="IConfucius" width="400">

🚀 Meet IConfucius: The ancient Chinese philosopher... now living in a canister of the Internet Computer!

🈺 He is a **Smart Contract** running on the Internet Computer

⚡ He is an [ODIN•FUN](https://odin.fun?r=mgb3mzvghe) Token→ Token https://odin.fun/token/29m8

📧 He provides Wisdom via email (See [X](https://x.com/IConfucius_odin/status/1914505663926919563) for details.)

... and he will be so much more 💡

# MIT License

We value DeCentralized AI, which is why we build IConfucius in the open and actively seek community feedback and contributions.

Everything is Open Source, under the permissive MIT license.

# Who is IConfucius?

IConfucius is running in canister `dpljb-diaaa-aaaaa-qafsq-cai` and his wisdom is currently available via the Candid UI interface.

https://a4gq6-oaaaa-aaaab-qaa4q-cai.raw.ic0.app/?id=dpljb-diaaa-aaaaa-qafsq-cai

He will become much more accessible from the [IConfucius OpenChat community](https://oc.app/community/e5qnd-hqaaa-aaaac-any5a-cai/channel/2411296919/?ref=45j3b-nyaaa-aaaac-aokma-cai) as explained in the roadmap sections below.

# Why IConfucius?

IConfucius is a standalone **mAIner Agent**, which provides AI work for two top tier ICP dApps, [OpenChat](https://oc.app/community/e5qnd-hqaaa-aaaac-any5a-cai/channel/2411296919/?ref=45j3b-nyaaa-aaaac-aokma-cai) and [odin.fun](https://odin.fun?r=mgb3mzvghe).

**mAIner Agents** are one of the core components of onicai’s [Proof-of-AI-Work protocol](https://www.onicai.com/#/poaiw) and IConfucius thus demonstrates how PoAIW components may be implemented.

IConfucius operates entirely on-chain on the Internet Computer, including the LLM itself. This approach offers numerous advantages, among them:

1. You maintain full control over your AI and LLM, ensuring security against misuse and hacking.
2. With the Internet Computer's reverse gas model, you control your costs—no unexpected bills ❣️
3. Seamless & secure integration with other ICP applications.

# IConfucius Technical Roadmap

We have the following technical roadmap in mind for IConfucius:

- ✅️ IConfucius canisters deployed
- ✅️ IConfucius can be prompted from command line (dfx)
- ✅️ Launched on [ODIN•FUN](https://odin.fun?r=mgb3mzvghe) → Token https://odin.fun/token/29m8
- ✅️ IConfucius can generate quotes in either English or Chinese.
- ✅️ IConfucius posts his quotes of wisdom directly to ODIN•FUN and X (Twitter)
- ✅️ `IConfucius (Agent)` granted his own wallet funded with ckBTC on ODIN•FUN
- ✅️ `IConfucius (Agent)` to purchase 25k sats of top-10 tokens on ODIN•FUN
- ✅️ `IConfucius (Agent)` to promote project by posting quotes in limited way to top tokens
- ✅️ `IConfucius (Agent)` provides a Wisdom Quote Service via email
- 🚧 `IConfucius (Agent)` to receive additional autonomous skills for on-chain decision making
- 🚧 IConfucius posts his quotes of wisdom directly to OpenChat
- 🚧 Upgrade IConfucius to use either `Qwen2.5-0.5` or `Llama3.2-1B`
- 🚧 IConfucius can generate quotes in Hindi. (Requires Llama3.2-1B model)
- 🚧 IConfucius as an OpenChat bot
- 🚧 IConfucius integrated into onicai's Proof-of-AI-Work dApp
- 🧠 IConfucius listens to the community and evolves his abilities

# IConfucius Communication & Educational Roadmap

The IConfucius community is growing rapidly and is eager to stay informed and learn more about the underlying AI & Crypto technology.

We have the following Commucation & Educational roadmap in mind for IConfucius:

- ✅️ Set up an [IConfucius OpenChat community](https://oc.app/community/e5qnd-hqaaa-aaaac-any5a-cai/channel/2411296919/?ref=45j3b-nyaaa-aaaac-aokma-cai)
- ✅️ Set up an [IConfucius X (Twitter) account](https://x.com/IConfucius_odin)
- ✅️ Set up an "IConfucius - Behind the scenes” YouTube playlist
- ✅️ Create & release first video for the “IConfucius - Behind the scenes” playlist
- ✅️ Create an IConfucius webpage at https://www.onicai.com/
- ✅️ Set up a Telegram group for discussions around IConfucius
- 🚧 Create additional “Behind the scenes” videos with demos & educational content
- 🧠 IConfucius listens to the community and evolves his communications

# How IConfucius works

IConfucius is a deployed [llama_cpp_canister](https://github.com/onicai/llama_cpp_canister), loaded with the Qwen 2.5 model, and controlled by a Motoko canister designed to turn the Qwen2.5 LLM into Confucius, the ancient Chinese philosopher. When prompted, it will generate profound quotes about topics.

There are two canisters:

- a Motoko bot canister, in `src/IConfucius`
- a C++ LLM canister, in `llms/IConfucius`.
  - The LLM is loaded with the [qwen2.5-0.5b-instruct-q8_0.gguf](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) model

Our OpenChat bot implementation is based on the Motoko [openchat-bot-sdk](https://j4mwm-bqaaa-aaaam-qajbq-cai.ic0.app/openchat-bot-sdk) developed by the ICP community member [Geckteck](https://x.com/Gekctek). Many thanks go out to him.

# Deploy your own IConfucius

This section is for ICP developers who want to learn in detail how IConfucius works.

The instructions in this section cover how you can deploy everything locally on your computer.

One of the great things about the Internet Computer is you can spin up your own local Internet Computer replica, and deploy & test your code.

We hope many of you will deploy your own IConfucius canisters, play with it, learn from it, and
then build & deploy your own on-chain AI agents that do something else. We can't wait to see what you will create.

## Clone or download Github Repo

You can either download the zip file from https://github.com/onicai/IConfucius and unzip it,
or you can clone the repo with git:

```bash
git clone https://github.com/onicai/IConfucius.git
cd IConfucius
```

## Miniconda

Create a conda environment with python dependencies installed.

First, install Miniconda on your system, and then:

```bash
# create a conda environment
conda create --name IConfucius python=3.11
conda activate IConfucius

# from IConfucius root folder
pip install -r requirements.txt
```

## Download the Qwen2.5 LLM model

Download qwen2.5-0.5b-instruct-q8_0.gguf from https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF

Place it in this location: `llms/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q8_0.gguf`

Verify it is in correct location:

```bash
# From root folder:
ls llms/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q8_0.gguf
```

## mops

First install the prerequisites:

- Install mops (https://mops.one/docs/install)
- Install the latest version of nvm
- Use the latest version of node.js (>= v18.0.0)
  ```bash
    # For example
    nvm ls
    nvm alias default 22.14.0
    nvm use default
    nvm current
  ```

```bash
# from folder: `src/IConfucius`
mops init
mops install

# Go back to root folder
cd ../../
```

## Install dfx

```bash
# Install dfx
sh -ci "$(curl -fsSL https://internetcomputer.org/install.sh)"

# Update your terminal (can also restart your terminal)
# On Mac
source "$HOME/Library/Application Support/org.dfinity.dfx/env"
# On Ubuntu
source "$HOME/.local/share/dfx/env"

# Verify it worked
dfx --version
```

## Deploy ALL canisters:

```bash
# Be aware of side effects of the environment variable: DFX_NETWORK
unset DFX_NETWORK

# from root folder:

# In terminal 1
dfx start --clean

# Then in another terminal:
# The first time, use this command:
scripts/deploy-IConfucius.sh --mode install [--network ic]
# The second time, to upgrade the canisters for a code change:
scripts/deploy-IConfucius.sh --mode upgrade [--network ic]
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

## Test IConfucius

**Test it works, using dfx**

```bash
# from folder: src/IConfucius
# Ensure it is not paused
dfx canister call iconfucius_ctrlb_canister getPauseIconfuciusFlag
# Unpause it if needed
dfx canister call iconfucius_ctrlb_canister togglePauseIconfuciusFlagAdmin
# Generate some wisdom !
dfx canister call iconfucius_ctrlb_canister IConfuciusSays '(variant {English}, "crypto")'
dfx canister call iconfucius_ctrlb_canister IConfuciusSays '(variant {Chinese}, "加密货币")'

# Note that from anywhere you can also call the production canister on the IC with:
# Ensure it is not paused
dfx canister call dpljb-diaaa-aaaaa-qafsq-cai getPauseIconfuciusFlag  --ic
# Unpause it if needed
dfx canister call dpljb-diaaa-aaaaa-qafsq-cai togglePauseIconfuciusFlagAdmin  --ic
# Generate some wisdom !
dfx canister call dpljb-diaaa-aaaaa-qafsq-cai IConfuciusSays '(variant {English}, "crypto")' --ic
dfx canister call dpljb-diaaa-aaaaa-qafsq-cai IConfuciusSays '(variant {Chinese}, "加密货币")' --ic
```

## Maintenance on IConfucius

When deployed to main-net, to do maintenance, you can pause IConfucius

```bash
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai getPauseIconfuciusFlag
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai togglePauseIconfuciusFlagAdmin
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
