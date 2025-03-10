#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/ready-check.sh --network [local|ic]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
NUM_LLMS_DEPLOYED=1

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
llm_id_start=0
llm_id_end=$((NUM_LLMS_DEPLOYED - 1))

# verify readiness of all llms in sequential mode
echo " "
echo "--------------------------------------------------"
echo "Checking readiness endpoint for all llms"
for i in $(seq $llm_id_start $llm_id_end)
do
    output=$(dfx canister call llm_$i ready --network $NETWORK_TYPE )

    if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
        echo "llm_$i is not ready. Exiting."
        echo $output
        exit 1
    else
        echo "llm_$i is ready."
    fi
done