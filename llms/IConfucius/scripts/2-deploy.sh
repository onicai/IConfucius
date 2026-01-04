#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/2-deploy.sh --network [local|testing|ic]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
NUM_LLMS_DEPLOYED=1
DEPLOY_MODE="install"

# When deploying to IC, we deploy to a specific subnet
# none will not use subnet parameter in deploy to ic
# SUBNET="none"
# llm 0
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
echo "==================================================="
llm_id_start=0
llm_id_end=$((NUM_LLMS_DEPLOYED - 1))

for i in $(seq $llm_id_start $llm_id_end)
do
    echo "--------------------------------------------------"
    echo "Deploying the wasm to llm_$i"
    if [ "$NETWORK_TYPE" = "ic" ]; then
        if [ "$SUBNET" = "none" ]; then
            echo "Deploying llm_$i llms to ic"
            yes | dfx deploy llm_$i --mode $DEPLOY_MODE --yes --network $NETWORK_TYPE
        else
            echo "Deploying llm_$i to ic on subnet $SUBNET"
            yes | dfx deploy llm_$i --mode $DEPLOY_MODE --yes --network $NETWORK_TYPE --subnet $SUBNET
        fi
        if [ "$DEPLOY_MODE" = "install" ]; then
            echo "Initial install to ic: Waiting for 30 seconds before checking health endpoint for llm_$i"
            sleep 30
        fi
    else
        echo "Deploying llm_$i llms to local network"
        yes | dfx deploy llm_$i --mode $DEPLOY_MODE --yes --network $NETWORK_TYPE
    fi 
    
    echo " "
    echo "--------------------------------------------------"
    echo "Checking health endpoint for llm_$i"
    output=$(dfx canister call llm_$i health --network $NETWORK_TYPE )

    if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
        echo "llm_$i health check failed."
        echo $output        
        exit 1
    else
        echo "llm_$i health check succeeded."
        echo 🎉
    fi

done