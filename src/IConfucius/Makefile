SHELL := /bin/bash

# Disable built-in rules and variables
MAKEFLAGS += --no-builtin-rules
MAKEFLAGS += --no-builtin-variables

CANISTER_NAME  = iconfucius_ctrlb_canister
NETWORKS       = ic testing
VERIFY_NETWORK ?= ic

.PHONY: help
help:
	@echo "Makefile targets:"
	@echo "  smoketest          - Start dfx, deploy canister, and run smoke tests"
	@echo "  build-wasm         - builds wasm using dfx and prints wasm-hash"
	@echo "  docker-build-base  - builds the Docker base image with moc, ic-wasm, mops-cli"
	@echo "  docker-build-wasm  - builds wasm using Docker (reproducible build)"
	@echo "  docker-verify-wasm - verifies Docker-built wasm matches deployed canister"
	@echo "  help               - Show this help message"

###########################################################################
# Smoke tests
#
.PHONY: smoketest
smoketest:
	dfx stop
	dfx start --clean --background
	$(MAKE) docker-build-wasm
	dfx canister create $(CANISTER_NAME)
	dfx canister install --wasm out/$(CANISTER_NAME).wasm \
		--mode install $(CANISTER_NAME) \
		--argument '("dfx_test_key")'
	pytest -vv --exitfirst test/test_iconfucius_canister.py
	dfx stop

###########################################################################
# Local builds
#
.PHONY: build-wasm
build-wasm:
	dfx build $(CANISTER_NAME) --network $(VERIFY_NETWORK)
	@echo "Wasm hash (SHA256):"
	@shasum -a 256 .dfx/$(VERIFY_NETWORK)/canisters/$(CANISTER_NAME)/$(CANISTER_NAME).wasm | cut -d ' ' -f 1

###########################################################################
# Docker-based reproducible builds
#
.PHONY: docker-build-base
docker-build-base:
	cd docker && docker compose build base

.PHONY: docker-build-wasm
docker-build-wasm:
	cd docker && docker compose build --no-cache wasm && docker compose run --rm wasm
	@echo "Wasm hash (Docker build):"
	@shasum -a 256 out/$(CANISTER_NAME).wasm | cut -d ' ' -f 1
	@for net in $(NETWORKS); do \
		mkdir -p .dfx/$$net/canisters/$(CANISTER_NAME); \
		cp -r out/* .dfx/$$net/canisters/$(CANISTER_NAME)/; \
	done
	@echo "Copied dfx build artifacts to .dfx/{$(NETWORKS)}/canisters/$(CANISTER_NAME)/"

.PHONY: docker-verify-wasm
docker-verify-wasm:
	@echo "Building wasm with Docker..."
	@cd docker && docker compose build --no-cache wasm && docker compose run --rm wasm
	@LOCAL_HASH=$$(shasum -a 256 out/$(CANISTER_NAME).wasm | cut -d ' ' -f 1); \
	echo "Docker wasm hash:   $$LOCAL_HASH"; \
	DEPLOYED_HASH=$$(dfx canister info $(CANISTER_NAME) --network $(VERIFY_NETWORK) | grep "Module hash:" | sed 's/Module hash: 0x//'); \
	echo "Deployed wasm hash ($(VERIFY_NETWORK)): $$DEPLOYED_HASH"; \
	if [ "$$LOCAL_HASH" = "$$DEPLOYED_HASH" ]; then \
		echo "✅ MATCH: Docker build matches deployed canister $(CANISTER_NAME) on $(VERIFY_NETWORK)"; \
	else \
		echo "❌ MISMATCH: Docker build does NOT match deployed canister $(CANISTER_NAME) on $(VERIFY_NETWORK)"; \
		exit 1; \
	fi
