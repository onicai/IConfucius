#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/2-deploy.sh --network [local|testing|development|prd]
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
NUM_LLMS_DEPLOYED=1
DEPLOY_MODE="install"

# When deploying to IC, we deploy to a specific subnet
# none will not use subnet parameter in deploy to ic
# SUBNET="none"
# llm 0
SUBNET="qdvhd-os4o2-zzrdw-xrcv4-gljou-eztdp-bj326-e6jgr-tkhuc-ql6v2-yqe"

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
            echo "Usage: $0 --network [local|testing|development|prd]"
            exit 1
            ;;
    esac
done

echo "Using network type: $NETWORK_TYPE"

if [ "$NETWORK_TYPE" = "local" ]; then
    if [ "$DEPLOY_MODE" = "install" ] || [ "$DEPLOY_MODE" = "reinstall" ]; then
        echo "local & $DEPLOY_MODE - cleaning up .dfx"
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
    if [ "$NETWORK_TYPE" = "prd" ] || [ "$NETWORK_TYPE" = "testing" ] || [ "$NETWORK_TYPE" = "development" ]; then
        if [ "$SUBNET" = "none" ]; then
            echo "Deploying llm_$i to $NETWORK_TYPE network"
            yes | dfx deploy llm_$i --mode $DEPLOY_MODE --yes --network $NETWORK_TYPE
        else
            echo "Deploying llm_$i to $NETWORK_TYPE network on subnet $SUBNET"
            yes | dfx deploy llm_$i --mode $DEPLOY_MODE --yes --network $NETWORK_TYPE --subnet $SUBNET
        fi
        if [ "$DEPLOY_MODE" = "install" ] || [ "$DEPLOY_MODE" = "reinstall" ]; then
            echo "Initial $DEPLOY_MODE: Waiting for 30 seconds before checking health endpoint for llm_$i"
            sleep 30
        fi
    else
        echo "Deploying llm_$i to local network"
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