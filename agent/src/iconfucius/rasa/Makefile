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
export ICONFUCIUS_MCP_PORT         ?= 5138
export ICONFUCIUS_MCP_URL          ?= http://127.0.0.1:$(ICONFUCIUS_MCP_PORT)/mcp
export LANGFUSE_HOST               ?= http://localhost:12526
export LANGFUSE_PUBLIC_KEY         ?= placeholder
export LANGFUSE_PRIVATE_KEY        ?= placeholder

.PHONY: rasa-inspect rasa-train rasa-train-for-release langfuse-up langfuse-down langfuse-logs

rasa-inspect:
	@echo "Starting MCP server on port $(ICONFUCIUS_MCP_PORT)..."
	@python -c "import os, uvicorn; from iconfucius.mcp_server import create_mcp_server, create_asgi_app; uvicorn.run(create_asgi_app(create_mcp_server()), host='127.0.0.1', port=int(os.environ.get('ICONFUCIUS_MCP_PORT', '5138')), log_level='warning')" & \
		MCP_PID=$$!; \
		cleanup() { kill $$MCP_PID 2>/dev/null || true; wait $$MCP_PID 2>/dev/null || true; }; \
		trap cleanup EXIT; \
		sleep 2; \
		LLM_API_HEALTH_CHECK=false rasa inspect; \
		EXIT_CODE=$$?; \
		exit $$EXIT_CODE

rasa-train:
	rasa train

rasa-train-for-release:
	rm -rf .rasa/ models/
	rasa train --fixed-model-name release-model
	@test -f models/release-model.tar.gz || (echo "ERROR: release-model.tar.gz not found" && exit 1)

# --- Langfuse (LLM tracing) ---
# One-time setup after `make langfuse-up`:
#   1. Open http://localhost:12526
#   2. Create an account (first user becomes admin)
#   3. Create a project → copy the public/private API keys
#   4. Export before running chat:
#        export LANGFUSE_PUBLIC_KEY=pk-lf-...
#        export LANGFUSE_PRIVATE_KEY=sk-lf-...

langfuse-up:
	docker compose -f docker-compose.langfuse.yml up -d

langfuse-down:
	docker compose -f docker-compose.langfuse.yml down

langfuse-logs:
	docker compose -f docker-compose.langfuse.yml logs -f langfuse
