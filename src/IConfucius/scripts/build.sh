#!/bin/bash
set -euo pipefail

CANISTER_NAME=iconfucius_ctrlb_canister
# --network is required by dfx build but does not impact the wasm output.
# The wasm binary is identical regardless of network.
NETWORK=ic
OUT_DIR=out
DFX_DIR=.dfx/${NETWORK}/canisters/${CANISTER_NAME}

mkdir -p ${OUT_DIR}
echo "Building ${CANISTER_NAME} with dfx..."
dfx build ${CANISTER_NAME} --network ${NETWORK}
cp -r ${DFX_DIR}/* ${OUT_DIR}/

echo "Wasm hash:"
sha256sum ${OUT_DIR}/${CANISTER_NAME}.wasm
