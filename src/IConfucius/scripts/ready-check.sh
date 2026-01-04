#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/ready-check.sh --network [local|testing|ic]
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
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 --network [local|testing|ic]"
            exit 1
            ;;
    esac
done

echo "Using network type: $NETWORK_TYPE"

############################################################################

echo " "
echo "--------------------------------------------------"
echo "Checking readiness endpoint"
output=$(dfx canister call iconfucius_ctrlb_canister ready --network $NETWORK_TYPE)

if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
    echo "iconfucius_ctrlb_canister is not ready. Exiting."
    exit 1
else
    echo "iconfucius_ctrlb_canister is ready for inference."
fi