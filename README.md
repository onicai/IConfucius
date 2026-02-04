# IConfucius

**Wisdom fueled by Cycles**

<img src="./images/IConfucius/IConfucius.jpg" alt="IConfucius" width="400">

🚀 Meet IConfucius: The ancient Chinese philosopher... now living in a canister of the Internet Computer!

☕ The community built a caffeineAI UI: https://aiconfucius-w8i.caffeine.xyz/

🈺 He is a **Smart Contract** running on the Internet Computer

⚡ He is an [ODIN•FUN](https://odin.fun?r=mgb3mzvghe) Token→ Token https://odin.fun/token/29m8

... and he will be so much more 💡

# MIT License

We value DeCentralized AI, which is why we build IConfucius in the open and actively seek community feedback and contributions.

Everything is Open Source, under the permissive MIT license.


# Why IConfucius?

IConfucius is a standalone **mAIner Agent**, and a pioneer of the core components of onicai’s [Proof-of-AI-Work protocol](https://www.onicai.com/#/poaiw). IConfucius demonstrates how PoAIW components may be implemented.

IConfucius operates entirely on-chain on the Internet Computer, including the LLM itself. This approach offers numerous advantages, among them:

1. You maintain full control over your AI and LLM, ensuring security against misuse and hacking.
2. With the Internet Computer's reverse gas model, you control your costs—no unexpected bills ❣️
3. Seamless & secure integration with other ICP applications.

# IConfucius Roadmap

We have the following technical roadmap in mind for IConfucius:

- ✅️ Launched on [ODIN•FUN](https://odin.fun?r=mgb3mzvghe) → Token https://odin.fun/token/29m8
- ✅️ IConfucius can generate quotes in either English or Chinese → [Try it out](https://aiconfucius-w8i.caffeine.xyz/)
- ✅️ IConfucius deployed with reproducible builds, in preparation of decentralization
- ✅️ IConfucius daily quote of wisdom posted to [IConfucius X (Twitter) account](https://x.com/IConfucius_odin)
- ✅️ IConfucius daily quote of wisdom posted to OpenChat
- 🚧 IConfucius adds trading on odin.fun via Chain Fusion AI
- 🚧 IConfucius takes a role in [funnAI](https://funnai.onicai.com/)
- 🧠 IConfucius evolves his abilities under governance of the [onicai SNS](https://www.onicai.com/files/onicai_SNS_Whitepaper.pdf)

# How IConfucius works

IConfucius is a deployed [llama_cpp_canister](https://github.com/onicai/llama_cpp_canister), loaded with the Qwen 2.5 model, and controlled by a Motoko canister designed to turn the Qwen2.5 LLM into Confucius, the ancient Chinese philosopher. When prompted, it will generate profound quotes about topics.

There are two canisters:

- a Motoko bot canister, in `src/IConfucius`
- a C++ LLM canister, in `llms/IConfucius`.
  - The LLM is loaded with the [qwen2.5-0.5b-instruct-q8_0.gguf](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) model

# Reproducible Builds

You can verify that the deployed IConfucius canister matches the source code in this repository using Docker-based reproducible builds.

```bash
# Clone the repository
git clone https://github.com/onicai/IConfucius.git
cd IConfucius/src/IConfucius

# Build the wasm using Docker (reproducible build)
make docker-build-base    # Build the base image (first time only)
make docker-build-wasm    # Build the wasm

# Compare with deployed canister
make docker-verify-wasm
```

See [README-reproducible-build.md](README-reproducible-build.md) for more details.

# Threshold Schnorr Signing (OdinBot)

IConfucius uses the IC management canister's threshold Schnorr API (`sign_with_schnorr` with `#bip340secp256k1`) for signing Bitcoin transactions on Odin.Fun. The canister takes a **Schnorr key name** as an init argument, which must match the deployment environment.

## Schnorr Key Names

| Key Name       | Environment                 | Signing Cost    | Subnet                         |
|----------------|-----------------------------|-----------------|--------------------------------|
| `dfx_test_key` | Local replica (`dfx start`) | Free            | Local test subnet              |
| `test_key_1`   | IC mainnet (testing/dev)    | ~10B cycles     | 13-node application subnet     |
| `key_1`        | IC mainnet (production)     | ~26B cycles     | 34-node fiduciary subnet       |

The deploy script (`scripts/deploy.sh`) automatically selects the correct key name based on the `--network` argument:

- `--network local` uses `dfx_test_key`
- `--network testing` or `--network development` uses `test_key_1`
- `--network prd` uses `key_1`

## Key Differences Between `test_key_1` and `key_1`

Both are **real threshold keys** on the IC mainnet with secret shares distributed across subnet nodes. Both produce valid BIP340 Schnorr signatures. The differences are:

- **Security**: `key_1` resides on a 34-node high-replication fiduciary subnet with stronger Byzantine fault tolerance. `test_key_1` resides on a 13-node application subnet.
- **Cost**: `key_1` costs ~26B cycles per signing call (~2.6x more than `test_key_1`). The canister attaches 100B cycles per call; unused cycles are refunded.
- **Longevity**: `test_key_1` may be deleted by DFINITY in the future and should not be used for anything of value.
- **Derived keys**: Different master keys produce completely different public keys and Bitcoin addresses.

## Cycle Cost for Signing

The canister attaches 100B cycles per `sign_with_schnorr` call. The actual cost depends on the key's subnet size:

| Operation            | `test_key_1` (13-node) | `key_1` (34-node) |
|----------------------|------------------------|--------------------|
| `schnorr_public_key` | Standard call fee      | Standard call fee  |
| `sign_with_schnorr`  | ~10B cycles            | ~26B cycles        |

Unused cycles are refunded automatically. The 100B overshoot ensures calls succeed even if the signing subnet grows in the future.

## Smoketests

Run the smoketests locally (uses `dfx_test_key` — all Schnorr tests run on local replica):

```bash
cd src/IConfucius
make smoketest
```

# Deploy your own IConfucius

This section is for ICP developers who want to learn in detail how IConfucius works.

The instructions in this section cover how you can deploy everything locally on your computer.

One of the great things about the Internet Computer is you can spin up your own local Internet Computer replica, and deploy & test your code.

We hope many of you will deploy your own IConfucius canisters, play with it, learn from it, and
then build & deploy your own on-chain AI agents that do something else. We can't wait to see what you will create.

## Docker

Docker is required for reproducible builds of the Motoko canister. Install Docker Desktop from https://www.docker.com/products/docker-desktop/

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
scripts/deploy-IConfucius.sh --mode install   # first install
scripts/deploy-IConfucius.sh --mode upgrade   # to upgrade
scripts/deploy-IConfucius.sh --mode reinstall # CAREFUL !!! : wipes everything and uploads new LLM model
# In case you need to re-upload the LLM model (gguf), run this script
# from folder: llms/IConfucius
scripts/3-upload-model.sh 

# To deploy to mainnet:
NETWORK=testing # There are 3 mainnet networks: testing, development, prd
scripts/deploy-IConfucius.sh --mode install   --network $NETWORK  # first install
scripts/deploy-IConfucius.sh --mode upgrade   --network $NETWORK  # to upgrade
scripts/deploy-IConfucius.sh --mode reinstall --network $NETWORK  # CAREFUL !!! : wipes everything and uploads new LLM model
# In case you need to re-upload the LLM model (gguf), run this script
# from folder: llms/IConfucius
scripts/3-upload-model.sh --network $NETWORK
```

Notes:

- `--mode install` & `--mode reinstall` take several minutes, because the LLM model is uploaded.
- `--mode upgrade` is fast, because the LLM model is NOT uploaded. All the canisters are
  re-build and re-deployed, but the LLM model is still as a virtual file in the canister's
  stable memory.
- When you deploy to the mainnet, it is recommended to do the initial deploy of each
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
# toggle Pause flag if the flag=true
dfx canister call iconfucius_ctrlb_canister togglePauseIconfuciusFlagAdmin
# Generate some wisdom !
dfx canister call iconfucius_ctrlb_canister IConfuciusSays '(variant {English}, "crypto")'
dfx canister call iconfucius_ctrlb_canister IConfuciusSays '(variant {Chinese}, "加密货币")'
```

## Maintenance on IConfucius

### Pause IConfucius

When deployed to main-net, to do maintenance, you can pause IConfucius

```bash
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai getPauseIconfuciusFlag --network prd
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai togglePauseIconfuciusFlagAdmin --network prd
```

### Manage the deployed LLMs

```bash
  # Get the LLMs currently in use
  dfx canister call dpljb-diaaa-aaaaa-qafsq-cai get_llm_canisters --network prd

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
