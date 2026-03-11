# Rasa Pro CALM Backend

IConfucius uses [Rasa Pro CALM](https://rasa.com/docs/rasa-pro/) for
conversational flow management. The LLM reads flow definitions and routes user
messages to the correct flow, collecting slots and executing actions.

## Why CALM over pure tool-calling agents?

Traditional LLM agents with pure tool calling let the model decide which tools
to call, in what order, and with what arguments. This works well for open-ended
tasks, but for business-critical workflows like trading it introduces a serious
risk: the LLM can hallucinate business logic — skipping confirmation steps,
blocking transactions due to hallucinated rules, inventing parameter values,
or calling tools in the wrong sequence.

CALM solves this by separating **what the LLM decides** from **what the system
executes**. The LLM's only job is to understand the user's intent and fill
slots; the actual business logic — step ordering, validations, confirmations —
is defined in deterministic flow definitions (`data/flows.yml`). The LLM cannot
skip a confirmation step or invent a trade amount, because the flow controls
which action runs next.

## Prerequisites

### Conda environment

Regular users install from PyPI:

```bash
pip install "iconfucius[rasa]"
```

For development, create a conda environment and install in editable mode:

```bash
conda create -n IConfucius python=3.11 -y
conda activate IConfucius
cd agent
pip install -e ".[rasa]"
```

### API keys and licenses

- Active conda environment (`conda activate IConfucius`)
- API keys and licenses in `agent/rasa/.env` (auto-loaded by Rasa):

```
ANTHROPIC_API_KEY=sk-ant-...
RASA_LICENSE=ey...
```

| Variable           | Where to get it                                                                                    |
| ------------------ | -------------------------------------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/settings/keys) — create an API key               |
| `RASA_LICENSE`      | [Rasa Developer Edition](https://rasa.com/rasa-pro-developer-edition-license-key-request) — free   |

The onboarding wizard (`iconfucius chat --rasa`) will prompt for both if they
are missing and save them to `.env` automatically.

## Quick Start

```bash
# Train the Rasa model (from agent/rasa/)
cd agent/rasa
make rasa-train

# Run the chat (from your iconfucius project folder, where iconfucius.toml lives)
cd /path/to/my-project
iconfucius chat --rasa --network testing
```

## Training

```bash
make rasa-train
```

The Makefile sets placeholder env vars for the LLM and rephraser model groups
(not called during training). Flow retrieval is currently disabled — all flows
are sent directly to the LLM.

Retrain after changing `data/flows.yml`, `domain.yml`, or `config.yml`.

## Running

```bash
iconfucius chat --rasa [--network testing] [--debug]
```

At runtime, `chat_rasa.py` sets model group env vars from `iconfucius.toml`
(or defaults). The `--debug` flag enables Rasa debug logging.

## Configuration

Model groups are configured in `iconfucius.toml` under
`[ai.rasa.endpoints.model_groups.*]`:

| Model group          | Default                         | Purpose                  |
| -------------------- | ------------------------------- | ------------------------ |
| `command_generator`  | `anthropic` / `claude-opus-4-6` | Flow routing & slot fill |
| `response_rephraser` | `anthropic` / `claude-opus-4-6` | NLG persona voice        |

```toml
[ai.rasa.endpoints.model_groups.command_generator]
provider = "anthropic"
model = "claude-opus-4-6"

[ai.rasa.endpoints.model_groups.response_rephraser]
provider = "anthropic"
model = "claude-opus-4-6"
```

## Architecture

| File             | Purpose                                                       |
| ---------------- | ------------------------------------------------------------- |
| `config.yml`     | Pipeline & policies (CompactLLMCommandGenerator, FlowPolicy)  |
| `domain.yml`     | Slots, actions, responses (`utter_*` templates)               |
| `data/flows.yml` | CALM flow definitions — the LLM reads these to route commands |
| `endpoints.yml`  | Action server & model group config (LLM, rephraser, embeddings) |
| `actions/`       | Custom action implementations (Python)                        |
| `.env`           | API keys (auto-loaded by Rasa, gitignored)                    |

### Response Rephrasing

Responses with `metadata.rephrase: true` in `domain.yml` are rewritten by the
`response_rephraser` model group using the persona voice defined in
`rephrase_prompt`.

### Custom Actions

Actions in `actions/` are loaded in-process via `actions_module: "actions"` in
`endpoints.yml` (no separate action server needed). Each action calls through
to `iconfucius.skills.executor.execute_tool()`.
