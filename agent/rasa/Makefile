# Rasa Pro development targets
# Requires: conda activate IConfucius

# Placeholders — training doesn't call the LLM, but Rasa validates
# these env vars at init time so they must be set.
export RASA_LLM_PROVIDER        ?= anthropic
export RASA_LLM_MODEL           ?= claude-opus-4-6
export RASA_REPHRASER_PROVIDER  ?= anthropic
export RASA_REPHRASER_MODEL     ?= claude-opus-4-6

.PHONY: rasa-train
rasa-train:
	rasa train
