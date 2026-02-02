#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/deploy-IConfucius.sh
#######################################################################

# Default network type is local
NETWORK_TYPE="local"
DEPLOY_MODE="install"

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

#######################################################################
echo " "
echo "**************************"
echo "* deploy: IConfucius *"
echo "**************************"

cd src/IConfucius
echo "-src/IConfucius: deploy.sh"
scripts/deploy.sh --network $NETWORK_TYPE --mode $DEPLOY_MODE

cd ../../llms/IConfucius
echo "-llms/IConfucius: 2-deploy.sh:"
scripts/2-deploy.sh --network $NETWORK_TYPE --mode $DEPLOY_MODE

cd ../../src/IConfucius
echo "-src/IConfucius: register-llms.sh"
scripts/register-llms.sh --network $NETWORK_TYPE

cd ../../llms/IConfucius
if [ "$DEPLOY_MODE" != "upgrade" ]; then
    echo "-llms/IConfucius: 3-upload-model.sh"
    scripts/3-upload-model.sh --network $NETWORK_TYPE
fi

echo "-llms/IConfucius: 4-load-model.sh"
scripts/4-load-model.sh --network $NETWORK_TYPE

echo "-llms/IConfucius: 5-set-max-tokens.sh"
scripts/5-set-max-tokens.sh --network $NETWORK_TYPE

echo "-llms/IConfucius: 6-register-ctrlb-canister.sh"
scripts/6-register-ctrlb-canister.sh --network $NETWORK_TYPE

echo "-llms/IConfucius: 7-log-pause.sh"
scripts/7-log-pause.sh --network $NETWORK_TYPE


#######################################################################