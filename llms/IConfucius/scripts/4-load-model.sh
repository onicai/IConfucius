#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/4-load-model.sh --network [local|testing|development|prd]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
NUM_LLMS_DEPLOYED=1

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

#######################################################################
echo " "
echo "==================================================="
echo "Loading model for $NUM_LLMS_DEPLOYED llms"
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
    echo "Calling load_model for llm_$i"
    # Gemma-3-1B-it load args per README-Language-Hindi.md: ctx 4096, batch and
    # ubatch 8 (Gemma's larger vocab needs the small batch to stay under the 40B
    # instruction limit), dual q8_0 KV cache. Heap after load ~869 MiB.
    output=$(dfx canister call llm_$i load_model \
            '(record { args = vec {"--model"; "models/model.gguf"; "--cache-type-k"; "q8_0"; "--cache-type-v"; "q8_0"; "--batch-size"; "8"; "--ubatch-size"; "8"; "--ctx-size"; "4096"} })' \
            --network "$NETWORK_TYPE")

    if ! echo "$output" | grep -q " Ok "; then
        echo "llm_$i load_model failed."
        echo $output
        exit 1
    else
        echo "llm_$i load_model succeeded."
        echo 🎉
    fi
done