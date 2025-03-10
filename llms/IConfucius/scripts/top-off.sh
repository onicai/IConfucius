#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/top-off.sh --network [local|ic]
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

#######################################################################
llm_id_start=0
llm_id_end=$((NUM_LLMS_DEPLOYED - 1))

# Define the threshold balance in TCycles (When to top off)
TOPPED_OFF_BALANCE_TRESHOLD_TC=18
TOPPED_OFF_BALANCE_TRESHOLD=$(echo "$TOPPED_OFF_BALANCE_TRESHOLD_TC * 1000000000000" | bc)
TOPPED_OFF_BALANCE_TRESHOLD=$(printf "%.0f" $TOPPED_OFF_BALANCE_TRESHOLD)

# Define the target balance in TCycles (To top off too)
TOPPED_OFF_BALANCE_TARGET_TC=20
TOPPED_OFF_BALANCE_TARGET=$(echo "$TOPPED_OFF_BALANCE_TARGET_TC * 1000000000000" | bc)
TOPPED_OFF_BALANCE_TARGET=$(printf "%.0f" $TOPPED_OFF_BALANCE_TARGET)

# top off cycles for all llms in sequential mode
for i in $(seq $llm_id_start $llm_id_end)
do
    CURRENT_BALANCE=$(dfx canister --network $NETWORK_TYPE status llm_$i 2>&1 | grep "Balance:" | awk '{gsub("_", ""); print $2}')
    NEED_CYCLES_THRESHOLD=$(echo "$TOPPED_OFF_BALANCE_TRESHOLD - $CURRENT_BALANCE" | bc)
    NEED_CYCLES_TARGET=$(echo "$TOPPED_OFF_BALANCE_TARGET - $CURRENT_BALANCE" | bc)
    if [ $(echo "$NEED_CYCLES_THRESHOLD > 0" | bc) -eq 1 ]; then
        CANISTER_ID=$(dfx canister --network $NETWORK_TYPE id llm_$i)
        echo "Sending $NEED_CYCLES_TARGET cycles to llm_$i"
        dfx wallet send $CANISTER_ID $NEED_CYCLES_TARGET --network $NETWORK_TYPE
    else
        echo "No need to send cycles to llm_$i. Balance = $(echo "scale=2; $CURRENT_BALANCE / 1000000000000" | bc) TCycles"
    fi
done