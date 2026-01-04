#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/top-off.sh [--network ic]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"

# Parse command line arguments for network type
while [ $# -gt 0 ]; do
    case "$1" in
        --network)
            shift
            if [ "$1" = "local" ] || [ "$1" = "testing" ] || [ "$1" = "ic" ]; then
                NETWORK_TYPE=$1
            else
                echo "Invalid network type: $1. Use 'local', 'testing' or 'ic'."
                exit 1
            fi
            shift
            ;;
        --mode)
            shift
            if [ "$1" = "install" ] || [ "$1" = "reinstall" ] || [ "$1" = "upgrade" ]; then
                DEPLOY_MODE=$1
            else
                echo "Invalid mode: $1. Use 'install', 'reinstall' or 'upgrade'."
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
echo "==========================================="
echo "dfx identity"
dfx identity whoami

echo " "
echo "==========================================="
echo "Wallet canister for this identity:"
dfx identity get-wallet --network $NETWORK_TYPE

echo " "
echo "==========================================="
echo "Wallet balance before top-off:"
dfx wallet --network $NETWORK_TYPE balance

echo " "
echo "==========================================="
cd llms/IConfucius
echo "Topping off IConfucius LLMs:"
scripts/top-off.sh --network $NETWORK_TYPE

echo "==========================================="
cd ../../src/IConfucius
echo "Topping off IConfucius ctrlb:"
scripts/top-off.sh --network $NETWORK_TYPE

echo "==========================================="
echo " "
echo "Wallet balance after top-off:"
dfx wallet --network $NETWORK_TYPE balance