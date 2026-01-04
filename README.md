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

IConfucius is running in canister `dpljb-diaaa-aaaaa-qafsq-cai` and his wisdom is currently available via:

- Community built caffeineAI UI: https://aiconfucius-w8i.caffeine.xyz/
- The Candid UI interface: https://a4gq6-oaaaa-aaaab-qaa4q-cai.raw.ic0.app/?id=dpljb-diaaa-aaaaa-qafsq-cai


# Why IConfucius?

IConfucius is a standalone **mAIner Agent**, and a pioneer of the core components of onicai’s [Proof-of-AI-Work protocol](https://www.onicai.com/#/poaiw). IConfucius demonstrates how PoAIW components may be implemented.

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
- ✅️ IConfucius posts his quotes of wisdom directly to [IConfucius X (Twitter) account](https://x.com/IConfucius_odin)
- 🚧 IConfucius posts his quotes of wisdom directly to OpenChat
- 🚧 IConfucius integrated into onicai's Proof-of-AI-Work dApp
- 🧠 IConfucius listens to the community and evolves his abilities

# How IConfucius works

IConfucius is a deployed [llama_cpp_canister](https://github.com/onicai/llama_cpp_canister), loaded with the Qwen 2.5 model, and controlled by a Motoko canister designed to turn the Qwen2.5 LLM into Confucius, the ancient Chinese philosopher. When prompted, it will generate profound quotes about topics.

There are two canisters:

- a Motoko bot canister, in `src/IConfucius`
- a C++ LLM canister, in `llms/IConfucius`.
  - The LLM is loaded with the [qwen2.5-0.5b-instruct-q8_0.gguf](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) model

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

```bash
# from folder: `src/IConfucius`
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
# toggle Pause flag if needed
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

### Pause IConfucius

When deployed to main-net, to do maintenance, you can pause IConfucius

```bash
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai getPauseIconfuciusFlag --ic
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai togglePauseIconfuciusFlagAdmin --ic
```

### Manage the deployed LLMs

```bash
  # Get the LLMs currently in use
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai get_llm_canisters --ic

  # Remove an LLM
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai remove_llm '(record {canister_id = "<canister-id>"} })'

  # Add an LLM
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai add_llm '(record {canister_id = "<canister-id>"} })'
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
