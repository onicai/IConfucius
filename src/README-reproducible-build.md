# Verify the Deployed Wasm

You can verify that the deployed IConfucius canister matches the source code in this repository using Docker-based reproducible builds.

## Prerequisites

- Docker installed and running
- dfx installed (for querying the deployed canister)

## Quick Verification

```bash
# Clone the repository
git clone https://github.com/onicai/IConfucius.git
cd IConfucius/src/IConfucius

# Build the wasm using Docker (reproducible build)
make docker-build-base    # Build the base image (first time only)
make docker-build-wasm    # Build the wasm

# Compare with deployed canister
make docker-verify-wasm
```

## Manual Verification

If you want to verify manually:

```bash
# 1. Build wasm with Docker
cd src/IConfucius
make docker-build-base
make docker-build-wasm

# 2. Get the hash of the Docker-built wasm
shasum -a 256 out/out_Linux_x86_64.wasm

# 3. Get the hash of the deployed canister
dfx canister info dpljb-diaaa-aaaaa-qafsq-cai --ic | grep "Module hash"

# 4. Compare the hashes (they should match, ignoring the 0x prefix)
```

## How It Works

The Docker build uses pinned versions of all tools to ensure reproducibility:

| Tool    | Version                  |
|---------|--------------------------|
| Ubuntu  | 22.04 (pinned by digest) |
| dfx     | 0.29.2                   |
| mops    | 2.0.0                    |
| Node.js | 20.x                     |

The build configuration is in `src/IConfucius/docker/`:
- `Dockerfile.base` - Base image with dfx, mops, and Node.js
- `Dockerfile` - Project-specific build
- `docker-compose.yml` - Version configuration
