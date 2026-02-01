#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/register-check.sh --network [local|testing|development|prd]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"

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

############################################################################

echo " "
echo "--------------------------------------------------"
echo "Checking if iconfucius_ctrlb_canister is a controller of the LLM canisters"
output=$(dfx canister call iconfucius_ctrlb_canister checkAccessToLLMs --network $NETWORK_TYPE)

if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
    echo "ERROR: iconfucius_ctrlb_canister is not a controller of all LLMs. Make sure to update the LLMs."
    exit 1
else
    echo "iconfucius_ctrlb_canister is a controller of all LLMs."
fi