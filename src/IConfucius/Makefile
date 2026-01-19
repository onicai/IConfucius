SHELL := /bin/bash

# Disable built-in rules and variables
MAKEFLAGS += --no-builtin-rules
MAKEFLAGS += --no-builtin-variables

.PHONY: help
help:
	@echo "Makefile targets:"
	@echo "  build-wasm         - builds wasm using dfx and prints wasm-hash"
	@echo "  verify-wasm        - builds wasm and verifies it matches deployed canister on IC mainnet"
	@echo "  docker-build-base  - builds the Docker base image with moc, ic-wasm, mops-cli"
	@echo "  docker-build-wasm  - builds wasm using Docker (reproducible build)"
	@echo "  docker-verify-wasm - verifies Docker-built wasm matches deployed canister"
	@echo "  help               - Show this help message"

.PHONY: build-wasm
build-wasm:
	dfx build iconfucius_ctrlb_canister --network ic
	@echo "Wasm hash (SHA256):"
	@shasum -a 256 .dfx/ic/canisters/iconfucius_ctrlb_canister/iconfucius_ctrlb_canister.wasm | cut -d ' ' -f 1

.PHONY: verify-wasm
verify-wasm:
	@echo "Building wasm locally..."
	@dfx build iconfucius_ctrlb_canister --network ic
	@LOCAL_HASH=$$(shasum -a 256 .dfx/ic/canisters/iconfucius_ctrlb_canister/iconfucius_ctrlb_canister.wasm | cut -d ' ' -f 1); \
	echo "Local wasm hash:    $$LOCAL_HASH"; \
	DEPLOYED_HASH=$$(dfx canister info iconfucius_ctrlb_canister --network ic | grep "Module hash:" | sed 's/Module hash: 0x//'); \
	echo "Deployed wasm hash: $$DEPLOYED_HASH"; \
	OS=$$(uname -s); \
	if [ "$$LOCAL_HASH" = "$$DEPLOYED_HASH" ]; then \
		echo "✅ MATCH: Wasm hash of build on $$OS matches wasm hash of deployed canister iconfucius_ctrlb_canister"; \
	else \
		echo "❌ MISMATCH: Wasm hash of build on $$OS does NOT match wasm hash of deployed canister iconfucius_ctrlb_canister"; \
		exit 1; \
	fi

###########################################################################
# Docker-based reproducible builds
#
.PHONY: docker-build-base
docker-build-base:
	cd docker && docker compose build base

.PHONY: docker-build-wasm
docker-build-wasm:
	cd docker && docker compose run --rm wasm
	@echo "Wasm hash (Docker build):"
	@shasum -a 256 out/out_Linux_x86_64.wasm | cut -d ' ' -f 1

.PHONY: docker-verify-wasm
docker-verify-wasm:
	@echo "Building wasm with Docker..."
	@cd docker && docker compose run --rm wasm
	@LOCAL_HASH=$$(shasum -a 256 out/out_Linux_x86_64.wasm | cut -d ' ' -f 1); \
	echo "Docker wasm hash:   $$LOCAL_HASH"; \
	DEPLOYED_HASH=$$(dfx canister info iconfucius_ctrlb_canister --network ic | grep "Module hash:" | sed 's/Module hash: 0x//'); \
	echo "Deployed wasm hash: $$DEPLOYED_HASH"; \
	if [ "$$LOCAL_HASH" = "$$DEPLOYED_HASH" ]; then \
		echo "✅ MATCH: Docker build matches deployed canister iconfucius_ctrlb_canister"; \
	else \
		echo "❌ MISMATCH: Docker build does NOT match deployed canister iconfucius_ctrlb_canister"; \
		exit 1; \
	fi
