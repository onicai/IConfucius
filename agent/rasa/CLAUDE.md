# CLAUDE.md — Rasa Pro Agent Guidelines

## Quick Reference

- **Docs**: Before doing Rasa backend work, fetch `https://rasa.com/docs/llms-full.txt` for capabilities and best practices
- **Train**: `cd agent/rasa && make rasa-train`
- **Run chat**: `iconfucius chat --rasa [--network testing] [--debug]`

## Training

`rasa train` requires env vars for the model groups (`RASA_LLM_*`, `RASA_REPHRASER_*`) because `endpoints.yml` references them. The LLM and rephraser are never called at train time (placeholders are fine). Flow retrieval is currently disabled — all flows are sent directly to the LLM. The Makefile sets placeholder defaults.

## Architecture

| File               | Purpose                                                        |
| ------------------ | -------------------------------------------------------------- |
| `config.yml`       | Pipeline & policies (SingleStepLLMCommandGenerator, etc.)      |
| `domain.yml`       | Slots, actions, responses (utter_* templates)                  |
| `data/flows.yml`   | CALM flow definitions — the LLM reads these to route commands  |
| `endpoints.yml`    | Action server & LLM model group config                         |
| `actions/`         | Custom action implementations (Python)                         |

## Key Lessons

### Flow descriptions are LLM instructions
The `description` field in `flows.yml` is what the LLM reads to decide which flow to trigger and how to fill slots. Adding context hints there (e.g. "use recently discussed token") directly influences slot prefilling behavior.

### Confirmation prompts
Use `(yes/no)` instead of `[Y/n]` in `utter_confirm_*` responses. The chat client (`chat_rasa.py`) skips empty input, so pressing Enter alone does nothing — users must type actual text.

### Env vars in endpoints.yml
`endpoints.yml` uses three model groups via env vars:
- `RASA_LLM_PROVIDER` / `RASA_LLM_MODEL` — command generator (flow routing)
- `RASA_REPHRASER_PROVIDER` / `RASA_REPHRASER_MODEL` — NLG response rephraser (persona voice)
- Flow retrieval (embeddings) is currently disabled — all flows are sent to the LLM directly

These are set at runtime by `chat_rasa.py` from `iconfucius.toml` model group config (defaults: anthropic/claude-opus-4-6 for both command generator and rephraser). For training, the Makefile sets placeholders.

### Persona rephrasing
Responses with `metadata.rephrase: true` get rewritten by the `response_rephraser` model group using the `rephrase_prompt`. The persona voice is defined in domain responses, not in flow descriptions.
