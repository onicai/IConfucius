#!/bin/bash

#######################################################################
# run from parent folder as:
# scripts/deploy.sh --network [local|testing|development|prd]
#######################################################################

set -euo pipefail

# Default network type is local
NETWORK_TYPE="local"
DEPLOY_MODE="install"

# When deploying to IC, we deploy to a specific subnet
# none will not use subnet parameter in deploy to ic
# SUBNET="none"
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

# Schnorr key name per environment (init argument for actor class)
if [ "$NETWORK_TYPE" = "prd" ]; then
    SCHNORR_KEY_NAME="key_1"
elif [ "$NETWORK_TYPE" = "testing" ] || [ "$NETWORK_TYPE" = "development" ]; then
    SCHNORR_KEY_NAME="test_key_1"
else
    SCHNORR_KEY_NAME="dfx_test_key"
fi
CANISTER_ARGUMENT="(\"$SCHNORR_KEY_NAME\")"
echo "Using Schnorr key name: $SCHNORR_KEY_NAME"

# install mode is only allowed on local — the IConfucius canister on prd/testing
# must never be recreated because existing principals and bitcoin addresses depend on it.
if [ "$DEPLOY_MODE" = "install" ]; then
    if [ "$NETWORK_TYPE" != "local" ]; then
        echo "ERROR: 'install' mode is only allowed for --network local."
        echo "The IConfucius canister on $NETWORK_TYPE must never be recreated — existing"
        echo "principals and bitcoin addresses depend on it. Use --mode upgrade instead."
        exit 1
    fi
fi

if [ "$NETWORK_TYPE" = "local" ]; then
    if [ "$DEPLOY_MODE" = "install" ] || [ "$DEPLOY_MODE" = "reinstall" ]; then
        echo "local & $DEPLOY_MODE - cleaning up .dfx"
        rm -rf .dfx
    fi
fi

#######################################################################

echo " "
echo "--------------------------------------------------"

# For remote networks, use Docker-based reproducible builds
if [ "$NETWORK_TYPE" = "prd" ] || [ "$NETWORK_TYPE" = "testing" ] || [ "$NETWORK_TYPE" = "development" ]; then
    echo "Building wasm with Docker (reproducible build)..."
    make docker-build-wasm

    WASM_FILE="out/iconfucius_ctrlb_canister.wasm"
    if [ ! -f "$WASM_FILE" ]; then
        echo "ERROR: Docker build failed - wasm file not found: $WASM_FILE"
        exit 1
    fi

    echo "Wasm hash:"
    shasum -a 256 "$WASM_FILE"

    # Create canister if it doesn't exist (for install/reinstall mode)
    if [ "$DEPLOY_MODE" = "install" ] || [ "$DEPLOY_MODE" = "reinstall" ]; then
        echo "Creating canister..."
        if [ "$SUBNET" = "none" ]; then
            dfx canister create iconfucius_ctrlb_canister --network "$NETWORK_TYPE" || true
        else
            dfx canister create iconfucius_ctrlb_canister --network "$NETWORK_TYPE" --subnet "$SUBNET" || true
        fi
    fi

    echo "Installing wasm to iconfucius_ctrlb_canister on $NETWORK_TYPE network..."
    if [ "$DEPLOY_MODE" = "upgrade" ]; then
        # Enhanced orthogonal persistence requires wasm_memory_persistence option for upgrades
        dfx canister install iconfucius_ctrlb_canister \
            --mode "$DEPLOY_MODE" \
            --yes \
            --network "$NETWORK_TYPE" \
            --wasm "$WASM_FILE" \
            --wasm-memory-persistence keep \
            --argument "$CANISTER_ARGUMENT"
    else
        dfx canister install iconfucius_ctrlb_canister \
            --mode "$DEPLOY_MODE" \
            --yes \
            --network "$NETWORK_TYPE" \
            --wasm "$WASM_FILE" \
            --argument "$CANISTER_ARGUMENT"
    fi
else
    # For local network, use dfx deploy (faster iteration)
    echo "Deploying the iconfucius_ctrlb_canister to the local network"
    dfx deploy iconfucius_ctrlb_canister --mode "$DEPLOY_MODE" --yes --network "$NETWORK_TYPE" \
        --argument "$CANISTER_ARGUMENT"
fi

echo " "
echo "--------------------------------------------------"
echo "Checking health endpoint"
output=$(dfx canister call iconfucius_ctrlb_canister health --network "$NETWORK_TYPE")

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
    output=$(dfx canister call iconfucius_ctrlb_canister setInitialQuoteTopics --network "$NETWORK_TYPE")

    if [ "$output" != "(variant { Ok = record { status_code = 200 : nat16 } })" ]; then
        echo "setInitialQuoteTopics failed. Exiting."
        exit 1
    else
        echo "setInitialQuoteTopics successfull."
    fi
fi

echo " "
echo "--------------------------------------------------"
echo "Configuring OdinBot (deriving Schnorr public key)"
output=$(dfx canister call iconfucius_ctrlb_canister configureOdinBot --network "$NETWORK_TYPE")

if echo "$output" | grep -q "Ok"; then
    echo "configureOdinBot successfull."
    echo "$output"
else
    echo "configureOdinBot failed:"
    echo "$output"
    exit 1
fi

# Assign AdminUpdate role to funnai-django-aws (idempotent — overwrites if exists)
FUNNAI_DJANGO_PRINCIPAL="bzqba-mwz5i-rq3oz-iie6i-gf7bi-kqr2x-tjuq4-nblmh-ephou-n27tl-xqe"

echo " "
echo "--------------------------------------------------"
echo "Assigning AdminUpdate role to funnai-django-aws ($FUNNAI_DJANGO_PRINCIPAL)"
output=$(dfx canister call iconfucius_ctrlb_canister assignAdminRole \
    "(record { \"principal\" = \"$FUNNAI_DJANGO_PRINCIPAL\"; role = variant { AdminUpdate }; note = \"funnai-django-aws\" })" \
    --network "$NETWORK_TYPE")

if echo "$output" | grep -q "Ok"; then
    echo "assignAdminRole successfull."
    echo "$output"
else
    echo "assignAdminRole failed:"
    echo "$output"
    exit 1
fi

echo " "
echo "--------------------------------------------------"
echo "Generating bindings for a frontend"
dfx generate
