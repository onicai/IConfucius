#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLIENT_DIR="$AGENT_DIR/src/iconfucius/client"
STATIC_DIR="$CLIENT_DIR/static"

cd "$CLIENT_DIR"
npm ci --silent
npm run build

rm -rf "$STATIC_DIR"
mkdir -p "$STATIC_DIR"
cp -r dist/* "$STATIC_DIR/"

echo "Client bundled into $STATIC_DIR"
du -sh "$STATIC_DIR"
