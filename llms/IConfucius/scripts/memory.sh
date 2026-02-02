#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/memory.sh --network [local|testing|development|prd]
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
            if [ "$1" = "local" ] || [ "$1" = "testing" ] || [ "$1" = "development" ] || [ "$1" = "prd" ]; then
                NETWORK_TYPE=$1
                if [ "$NETWORK_TYPE" = "prd" ]; then
                    CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER="dpljb-diaaa-aaaaa-qafsq-cai"
                elif [ "$NETWORK_TYPE" = "testing" ]; then
                    CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER="r3n4s-haaaa-aaaag-au3mq-cai"
                elif [ "$NETWORK_TYPE" = "development" ]; then
                    CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER="y7kxj-aiaaa-aaaaj-a3xdq-cai"
                fi
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
echo "NUM_LLMS_DEPLOYED : $NUM_LLMS_DEPLOYED"
echo " "

#######################################################################
llm_id_start=0
llm_id_end=$((NUM_LLMS_DEPLOYED - 1))

echo " "
echo "- dfx identity"
dfx identity whoami

for i in $(seq $llm_id_start $llm_id_end)
do
    echo " "
	echo "- llm_$i "
    dfx canister status llm_$i --network $NETWORK_TYPE 2>&1 | grep "Memory Size: "
done

echo " "
echo "- CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER: $CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER"
dfx canister status $CANISTER_ID_ICONFUCIUS_CTRLB_CANISTER --network $NETWORK_TYPE 2>&1 | grep "Memory Size: "

echo " "