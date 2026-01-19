SHELL := /bin/bash

# Disable built-in rules and variables
MAKEFLAGS += --no-builtin-rules
MAKEFLAGS += --no-builtin-variables

.PHONY: help
help:
	@echo "Makefile targets:"
	@echo "  build-wasm  - builds wasm and prints wasm-hash"
	@echo "  verify-wasm - builds wasm and verifies it matches deployed canister on IC mainnet"
	@echo "  help        - Show this help message"

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
