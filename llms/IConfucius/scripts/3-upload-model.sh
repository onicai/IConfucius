#!/bin/bash

LLAMA_CPP_CANISTER_PATH="../llama_cpp_canister"
export PYTHONPATH="${PYTHONPATH}:$(realpath $LLAMA_CPP_CANISTER_PATH)"

#######################################################################
# run from parent folder as:
# scripts/3-upload-model.sh --network [local|ic]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
NUM_LLMS_DEPLOYED=1

# The gguf model file to upload (Relative to root folder)
MODEL="../models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q8_0.gguf"

# Parse command line arguments for network type
while [ $# -gt 0 ]; do
    case "$1" in
        --network)
            shift
            if [ "$1" = "local" ] || [ "$1" = "ic" ]; then
                NETWORK_TYPE=$1
            else
                echo "Invalid network type: $1. Use 'local' or 'ic'."
                exit 1
            fi
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 --network [local|ic]"
            exit 1
            ;;
    esac
done

echo "Using network type: $NETWORK_TYPE"

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
    python -m scripts.upload --network $NETWORK_TYPE --canister llm_$i --canister-filename models/model.gguf $MODEL

    if [ $? -ne 0 ]; then
        echo "scripts.upload for llm_$i exited with an error."
        echo $?
        exit 1
    fi
done