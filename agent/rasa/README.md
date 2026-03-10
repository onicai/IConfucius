# Rasa Pro CALM Backend

IConfucius uses [Rasa Pro CALM](https://rasa.com/docs/rasa-pro/) for
conversational flow management. The LLM reads flow definitions and routes user
messages to the correct flow, collecting slots and executing actions.

## Prerequisites

- Python environment with Rasa Pro installed (`conda activate IConfucius`)
- API keys in `agent/rasa/.env` (auto-loaded by Rasa):

```
ANTHROPIC_API_KEY=sk-ant-...
```

The Anthropic key is used at **runtime** for the command generator and response
rephraser (both default to `claude-opus-4-6`).

## Quick Start

```bash
cd agent/rasa

# Train the model (requires OPENAI_API_KEY for flow retrieval embeddings)
make rasa-train

# Run the chat
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
