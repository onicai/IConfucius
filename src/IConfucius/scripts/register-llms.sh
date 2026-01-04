#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/register-llms.sh --network [local|testing|ic]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
NUM_LLMS_DEPLOYED=1
NUM_LLMS_ROUND_ROBIN=1 # how many LLMs we actually use
# When deploying local, use canister IDs from .env
source ../../llms/IConfucius/.env

# none will not use subnet parameter in deploy to ic
SUBNET="none"

# Parse command line arguments for network type
while [ $# -gt 0 ]; do
    case "$1" in
        --network)
            shift
            if [ "$1" = "local" ] || [ "$1" = "testing" ] || [ "$1" = "ic" ]; then
                NETWORK_TYPE=$1
                if [ "$NETWORK_TYPE" = "ic" ]; then
                    CANISTER_ID_LLM_0='dikpv-oqaaa-aaaaa-qafsa-cai'
                elif [ "$NETWORK_TYPE" = "testing" ]; then
                    CANISTER_ID_LLM_0='rsoxo-riaaa-aaaag-au3na-cai'
                fi
            else
                echo "Invalid network type: $1. Use 'local', 'testing' or 'ic'."
                exit 1
            fi
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 --network [local|testing|ic]"
            exit 1
            ;;
    esac
done

echo "Using network type: $NETWORK_TYPE"

#######################################################################
echo " "
echo "--------------------------------------------------"
echo "Checking health endpoint"
output=$(dfx canister call iconfucius_ctrlb_canister health --network $NETWORK_TYPE)

if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
    echo "iconfucius_ctrlb_canister is not healthy. Exiting."
    exit 1
else
    echo "iconfucius_ctrlb_canister is healthy."
fi

echo " "
echo "--------------------------------------------------"
echo "Registering $NUM_LLMS_DEPLOYED llm canisterIDs with the iconfucius_ctrlb_canister"
CANISTER_ID_LLMS=(
    $CANISTER_ID_LLM_0
    $CANISTER_ID_LLM_1
    $CANISTER_ID_LLM_2
    $CANISTER_ID_LLM_3
    $CANISTER_ID_LLM_4
    $CANISTER_ID_LLM_5
    $CANISTER_ID_LLM_6
    $CANISTER_ID_LLM_7
    $CANISTER_ID_LLM_8
    $CANISTER_ID_LLM_9
    $CANISTER_ID_LLM_10
    $CANISTER_ID_LLM_11
)
llm_id_start=0
llm_id_end=$((NUM_LLMS_DEPLOYED - 1))

for i in $(seq $llm_id_start $llm_id_end)
do
    CANISTER_ID_LLM=${CANISTER_ID_LLMS[$i]}
    echo "CANISTER_ID_LLM_$i: $CANISTER_ID_LLM"
done

# # Ask user if this is correct, and continue when answer is yes
# read -p "Proceed? (yes/no): " confirm
# if [[ $confirm != "yes" ]]; then
#     echo "Aborting script."
#     exit 1
# fi

echo "Calling reset_llm_canisters."
output=$(dfx canister call iconfucius_ctrlb_canister reset_llm_canisters --network $NETWORK_TYPE)

if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
    echo "Error calling reset_llm_canisters. Exiting."
    exit 1
else
    echo "Successfully called reset_llm_canisters."
fi

for i in $(seq $llm_id_start $llm_id_end)
do
    CANISTER_ID_LLM=${CANISTER_ID_LLMS[$i]}
    echo "Calling add_llm_canister for $CANISTER_ID_LLM."
    output=$(dfx canister call iconfucius_ctrlb_canister add_llm_canister "(record { canister_id = \"$CANISTER_ID_LLM\" })" --network $NETWORK_TYPE)

    if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
        echo "Error calling add_llm_canister for $CANISTER_ID_LLM. Exiting."
        exit 1
    else
        echo "Successfully called add_llm_canister for $CANISTER_ID_LLM."
    fi
done

# Don't set this, so will use all of them.
# echo " "
# echo "--------------------------------------------------"
# echo "Setting NUM_LLMS_ROUND_ROBIN to $NUM_LLMS_ROUND_ROBIN"
# output=$(dfx canister call iconfucius_ctrlb_canister setRoundRobinLLMs "($NUM_LLMS_ROUND_ROBIN)" --network $NETWORK_TYPE)

# if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
#     echo "setRoundRobinLLMs call failed. Exiting."
#     exit 1
# else
#     echo "setRoundRobinLLMs was successful."
# fi