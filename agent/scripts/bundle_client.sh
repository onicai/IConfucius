#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLIENT_DIR="$AGENT_DIR/src/iconfucius/client"

cd "$CLIENT_DIR"
npm ci --silent
npm run build

echo "Client bundled into $CLIENT_DIR/dist"
du -sh "$CLIENT_DIR/dist"
