#!/bin/bash
# MOE server — can be run directly from moe/ or via start_all.sh at root.
# Config lives at root configs/moe_system.json.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="$ROOT_DIR/configs/moe_system.json"

cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "  Config    : $CONFIG"
echo "  WebSocket : ws://localhost:3942"
echo "  UI        : http://localhost:8081/moeui.html"
echo ""

python3 server.py --config "$CONFIG" "$@"
