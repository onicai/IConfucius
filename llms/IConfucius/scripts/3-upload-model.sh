#!/bin/bash

LLAMA_CPP_CANISTER_PATH="../llama_cpp_canister"
export PYTHONPATH="${PYTHONPATH}:$(realpath $LLAMA_CPP_CANISTER_PATH)"

#######################################################################
# run from parent folder as:
# scripts/3-upload-model.sh --network [local|testing|development|prd]
#
# Prerequisites (llama_cpp_canister >= v0.16.6 upload flow):
# - icp-cli installed (scripts.upload resolves the network URL and the
#   identity's private key via `icp network status` / `icp identity export`)
# - the dfx deployer identity imported into icp-cli under the same name
#   and set as default, or exported as ICPP_PRO_TEST_IDENTITY=<name>
# - a dedicated conda env with the vendored python deps:
#     pip install -r ../llama_cpp_canister/requirements.txt
#   (icp-py-core conflicts with ic-py used by the root agent scripts, so
#   never install it into the main IConfucius env)
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
NUM_LLMS_DEPLOYED=1

# The gguf model file to upload (Relative to the vendored llama_cpp_canister
# root folder). Models live in the shared models folder of a sibling checkout
# of onicai/llama_cpp_canister: ~/github/repos/llama_cpp_canister/models
MODEL="../../../llama_cpp_canister/models/Qwen/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf"

# Parse command line arguments for network type
while [ $# -gt 0 ]; do
    case "$1" in
        --network)
            shift
            if [ "$1" = "local" ] || [ "$1" = "testing" ] || [ "$1" = "development" ] || [ "$1" = "prd" ]; then
                NETWORK_TYPE=$1
            else
                echo "Invalid network type: $1. Use 'local', 'testing', 'development' or 'prd'."
                exit 1
            fi
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 --network [local|testing|development|prd]"
            exit 1
            ;;
    esac
done

echo "Using network type: $NETWORK_TYPE"

# The upstream scripts.upload takes an icp.yaml environment name:
# "local" for the local replica, "production" for ic mainnet.
if [ "$NETWORK_TYPE" = "local" ]; then
    UPSTREAM_NETWORK_TYPE="local"
else
    UPSTREAM_NETWORK_TYPE="production"
fi

# sha256 of Qwen3-0.6B-Q8_0.gguf, from HuggingFace
HF_SHA256="9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031"

#######################################################################
echo " "
echo "==================================================="
echo "Uploading model for $NUM_LLMS_DEPLOYED llms"
llm_id_start=0
llm_id_end=$((NUM_LLMS_DEPLOYED - 1))

for i in $(seq $llm_id_start $llm_id_end)
do
    echo " "
    echo "--------------------------------------------------"
    echo "Checking health endpoint for llm_$i"
    output=$(dfx canister call llm_$i health --network $NETWORK_TYPE )

    if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
        echo "llm_$i health check failed."
        echo $output
        exit 1
    else
        echo "llm_$i health check succeeded."
    fi

    echo " "
    echo "--------------------------------------------------"
    echo "Upload the model ($MODEL) to llm_$i"
    # --canister-id bypasses the icp.yaml canister-name lookup (llm_$i only
    # exists in our dfx.json); --filetype gguf is required so the canister
    # initializes inference (the upstream default is "other").
    CANISTER_ID=$(dfx canister id llm_$i --network $NETWORK_TYPE)
    # Run from the llama_cpp_canister folder: scripts.upload shells out to
    # `icp network status`, which requires the icp.yaml project manifest in
    # the current working directory. MODEL stays valid — upload.py resolves
    # it against its own repo root, not the CWD.
    (cd $LLAMA_CPP_CANISTER_PATH && python -m scripts.upload --network $UPSTREAM_NETWORK_TYPE --canister-id $CANISTER_ID --filetype gguf --canister-filename models/model.gguf --hf-sha256 $HF_SHA256 $MODEL)

    if [ $? -ne 0 ]; then
        echo "scripts.upload for llm_$i exited with an error."
        echo $?
        exit 1
    fi
done