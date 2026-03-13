# Rasa Pro development targets
# Requires: conda activate IConfucius

# Placeholders — training doesn't call the LLM, but Rasa validates
# these env vars at init time so they must be set.
export RASA_LLM_PROVIDER        ?= anthropic
export RASA_LLM_MODEL           ?= claude-opus-4-6
export RASA_REPHRASER_PROVIDER  ?= anthropic
export RASA_REPHRASER_MODEL     ?= claude-opus-4-6
export RASA_SUBAGENT_PROVIDER   ?= anthropic
export RASA_SUBAGENT_MODEL      ?= claude-opus-4-6
export RASA_SUBAGENT_TOOL_TIMEOUT ?= 120
export ICONFUCIUS_MCP_URL          ?= http://127.0.0.1:5138/mcp

.PHONY: rasa-train rasa-train-for-release

rasa-train:
	rasa train

rasa-train-for-release:
	rm -rf .rasa/ models/
	rasa train --fixed-model-name release-model
	@test -f models/release-model.tar.gz || (echo "ERROR: release-model.tar.gz not found" && exit 1)
