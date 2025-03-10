#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/status.sh --network [local|ic]
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
echo "NUM_LLMS_DEPLOYED : $NUM_LLMS_DEPLOYED"
echo " "

#######################################################################
llm_id_start=0
llm_id_end=$((NUM_LLMS_DEPLOYED - 1))

echo " "
echo "- dfx identity"
dfx identity whoami

echo " "
echo "- Wallet balance"
dfx wallet --network $NETWORK_TYPE balance

for i in $(seq $llm_id_start $llm_id_end)
do
    echo " "
	echo "- llm_$i "
    dfx canister status llm_$i --network $NETWORK_TYPE
done