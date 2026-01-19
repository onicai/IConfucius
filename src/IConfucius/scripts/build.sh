#!/bin/bash
set -euo pipefail

# Output file (platform-specific for verification)
OUT=out/out_$(uname -s)_$(uname -m).wasm

# Create output directory
mkdir -p out

# Build using dfx
echo "Building with dfx..."
dfx build iconfucius_ctrlb_canister --network ic

# Copy to output location
cp .dfx/ic/canisters/iconfucius_ctrlb_canister/iconfucius_ctrlb_canister.wasm $OUT

# Output hash
echo "Wasm hash:"
sha256sum $OUT
