#!/bin/bash
# ERPL Ground Control — unified launcher
# Prompts for MOE (multi-Panda V2) or Draco (original single-Panda V1) config.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "================================================"
echo "   ERPL Ground Control"
echo "================================================"
echo ""
echo "  1) MOE   — Panda V2 + NI DAQ  (rocket + GSE)"
echo "  2) Draco — Panda V1 + NI DAQ  (original)"
echo ""
read -rp "Select config [1/2]: " CHOICE

case "$CHOICE" in

# ── MOE ──────────────────────────────────────────────────────────────
1)
    echo ""
    echo "Starting MOE..."
    cd "$SCRIPT_DIR/moe"

    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi

    source venv/bin/activate
    pip install -q -r requirements.txt

    echo ""
    echo "  WebSocket : ws://localhost:3942"
    echo "  UI        : http://localhost:8081/moeui.html"
    echo ""

    # Open browser after a short delay so server can bind
    (sleep 2 && open "http://localhost:8081/moeui.html" 2>/dev/null || true) &

    python3 server.py --config "$SCRIPT_DIR/configs/moe_system.json"
    ;;

# ── Draco (original) ─────────────────────────────────────────────────
2)
    echo ""
    echo "Starting Draco (original)..."

    # NI DAQ — Node.js WS server + Python streamer
    cd "$SCRIPT_DIR/ni_daq"
    if [ ! -d "node_modules" ]; then
        echo "Installing Node.js dependencies..."
        npm install --no-fund --no-audit
    fi
    node server.js &
    NIDAQ_NODE_PID=$!
    sleep 2
    python3 daq_streamer.py &
    NIDAQ_PY_PID=$!

    # Panda V1
    cd "$SCRIPT_DIR/panda"
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install -q websockets pyserial

    echo ""
    echo "  NI DAQ UI : http://localhost:3000"
    echo "  Panda UI  : http://localhost:8080/panda-daq-ui.html"
    echo ""
    echo "  Serial port? (e.g. /dev/cu.usbmodem14101, leave blank for COM4 default)"
    read -rp "  Port: " PANDA_PORT
    PANDA_PORT="${PANDA_PORT:-COM4}"

    # Trap so NI DAQ processes die when this script exits
    trap "kill $NIDAQ_NODE_PID $NIDAQ_PY_PID 2>/dev/null || true" EXIT

    (sleep 2 && open "http://localhost:8080/panda-daq-ui.html" 2>/dev/null || true) &

    python3 main.py --port "$PANDA_PORT"
    ;;

*)
    echo "Invalid choice."
    exit 1
    ;;
esac
