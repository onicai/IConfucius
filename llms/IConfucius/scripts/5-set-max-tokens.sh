#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/5-set-max-tokens.sh --network [local|testing|development|prd]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
NUM_LLMS_DEPLOYED=1

# gemma-3-1b-it-Q4_K_M.gguf: ceiling is 11 tokens/call (12 → IC0522), same for
# Hindi and English (README-Language-Hindi.md). Use 10, one below the ceiling.
MAX_TOKENS_QUERY=1
MAX_TOKENS_UPDATE=10

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
echo "set_max_tokens to query=$MAX_TOKENS_QUERY update=$MAX_TOKENS_UPDATE for $NUM_LLMS_DEPLOYED llms"
llm_id_start=0
llm_id_end=$((NUM_LLMS_DEPLOYED - 1))

for i in $(seq $llm_id_start $llm_id_end)
do
    echo " "
    echo "--------------------------------------------------"
    echo "Checking health endpoint for llm_$i"
    output=$(dfx canister call llm_$i health --network $NETWORK_TYPE )

    if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
        echo "llm_$i health check failed"
        echo $output
        exit 1
    else
        echo "llm_$i health check succeeded."
    fi

    echo " "
    echo "--------------------------------------------------"
    echo "Setting max tokens to (query=$MAX_TOKENS_QUERY update=$MAX_TOKENS_UPDATE) for llm_$i"
    output=$(dfx canister call llm_$i set_max_tokens \
            '(record { max_tokens_query = '"$MAX_TOKENS_QUERY"' : nat64; max_tokens_update = '"$MAX_TOKENS_UPDATE"' : nat64 })' \
            --network "$NETWORK_TYPE")


    if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
        echo "llm_$i set_max_tokens failed."
        echo $output
        exit 1
    else
        echo "llm_$i set_max_tokens to query=$MAX_TOKENS_QUERY update=$MAX_TOKENS_UPDATE succeeded."
        echo 🎉
    fi
done