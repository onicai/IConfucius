#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/register-ctrlb-canister.sh --network [local|testing|ic]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
NUM_LLMS_DEPLOYED=1
# When deploying local, use CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER ID from .env
source ../../src/IConfucius/.env

# Parse command line arguments for network type
while [ $# -gt 0 ]; do
    case "$1" in
        --network)
            shift
            if [ "$1" = "local" ] || [ "$1" = "testing" ] || [ "$1" = "ic" ]; then
                NETWORK_TYPE=$1
                if [ "$NETWORK_TYPE" = "ic" ]; then
                    CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER="dpljb-diaaa-aaaaa-qafsq-cai"
                elif [ "$NETWORK_TYPE" = "testing" ]; then
                    CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER="r3n4s-haaaa-aaaag-au3mq-cai"
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
echo "NUM_LLMS_DEPLOYED : $NUM_LLMS_DEPLOYED"
echo " "
echo "CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER: $CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER"
echo "Making $CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER a controller of LLMs"
# read -p "Proceed? (yes/no): " confirm
# if [[ $confirm != "yes" ]]; then
#     echo "Aborting script."
#     exit 1
# fi

#######################################################################
llm_id_start=0
llm_id_end=$((NUM_LLMS_DEPLOYED - 1))

for i in $(seq $llm_id_start $llm_id_end)
do
    echo "==================================================="
    echo "Making $CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER a controller of llm_$i"
    dfx canister update-settings llm_$i --add-controller $CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER  --network $NETWORK_TYPE
done