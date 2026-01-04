#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/deploy.sh --network [local|testing|ic]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
DEPLOY_MODE="install"

# When deploying to IC, we deploy to a specific subnet
# none will not use subnet parameter in deploy to ic
# SUBNET="none"
SUBNET="snjp4-xlbw4-mnbog-ddwy6-6ckfd-2w5a2-eipqo-7l436-pxqkh-l6fuv-vae"

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

if [ "$NETWORK_TYPE" = "local" ]; then
    if [ "$DEPLOY_MODE" == "install" ]; then
        echo "local & install - cleaning up .dfx"
        rm -rf .dfx
    fi
fi

#######################################################################

echo " "
echo "--------------------------------------------------"

if [ "$NETWORK_TYPE" = "ic" ]; then
    if [ "$SUBNET" = "none" ]; then
        echo "Deploying the iconfucius_ctrlb_canister to the ic network"
        dfx deploy iconfucius_ctrlb_canister --mode $DEPLOY_MODE --yes --network $NETWORK_TYPE
    else
        echo "Deploying the iconfucius_ctrlb_canister to the ic network on subnet $SUBNET"
        dfx deploy iconfucius_ctrlb_canister --mode $DEPLOY_MODE --yes --network $NETWORK_TYPE --subnet $SUBNET
    fi
else
    echo "Deploying the iconfucius_ctrlb_canister to the local network"
    dfx deploy iconfucius_ctrlb_canister --mode $DEPLOY_MODE --yes --network $NETWORK_TYPE
fi

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

if [ "$DEPLOY_MODE" != "upgrade" ]; then
    echo " "
    echo "--------------------------------------------------"
    echo "Setting initial quote topics"
    output=$(dfx canister call iconfucius_ctrlb_canister setInitialQuoteTopics --network $NETWORK_TYPE)

    if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
        echo "setInitialQuoteTopics failed. Exiting."
        exit 1
    else
        echo "setInitialQuoteTopics successfull."
    fi
fi

echo " "
echo "--------------------------------------------------"
echo "Generating bindings for a frontend"
dfx generate