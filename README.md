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

# Connect IConfucius to your OpenChat community

TODO:
- Describe how to do this

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

When running IConfucius locally with open-chat, make sure to first deploy open-chat.
Use the version of dfx prescribed by [open-chat](https://github.com/open-chat-labs/open-chat)

## Download the Qwen2.5 LLM model

Download qwen2.5-0.5b-instruct-q8_0.gguf from https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF

Place it in this location: `llama_cpp_canister/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q8_0.gguf`

Verify it is in correct location:

```bash 
# From root folder:
ls llama_cpp_canister/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q8_0.gguf
```

## Deploy ALL canisters:

Note: The local network in all dfx.json files is defined as in the open-chat repo.

```bash
# from root folder: 
# (-) --mode install is slow, because the LLM model is uploaded.
# (-) --mode upgrade is fast, because the LLM model is NOT uploaded.
#       The canisters are re-build and re-deployed, but the LLM model is still in the canister's stable memory.
# (-) When we deployed to ic, the initial installation of each component was done manually
#     to ensure the LLMs ended up on the correct subnet
scripts/deploy-IConfucius.sh --mode [install/reinstall/upgrade] --network [local/ic]
```

Note: When working on Windows, use WSL Ubuntu. You might first have to run 
```bash
sudo sysctl -w vm.max_map_count=2097152
```
to successfully load the models in the LLM canisters.


## Prompt Design

We designed the prompt using `scripts/prompt-design.ipynb`

That notebook runs llama.cpp directly on your computer, and you can very quickly try out modifications.

Make sure to design your own prompts so that the repetitive part is at the beginning, to benefit from prompt caching. When running LLMs inside a canister, this will help tremendously with cost & latency.



