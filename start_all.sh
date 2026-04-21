#!/bin/bash
# ERPL Ground Control — unified launcher
# Usage:
#   ./start_all.sh                   # interactive menu
#   ./start_all.sh --profile moe     # skip menu, launch MOE
#   ./start_all.sh --profile draco   # skip menu, launch Draco
#   ./start_all.sh --profile gse-v1  # skip menu, launch GSE V1
#
# Options:
#   --profile <name>   Profile to launch: moe, draco, gse-v1
#   --xlsx <path>      Config spreadsheet to regenerate from before launch
#   --test             Pass --test to the backend server
#   --port <port>      Serial port override (Draco / GSE-V1 standalone)
#   --no-browser       Don't auto-open browser

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PROFILE=""
XLSX=""
TEST_FLAG=""
SERIAL_PORT=""
NO_BROWSER=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)  PROFILE="$2";      shift 2 ;;
        --xlsx)     XLSX="$2";         shift 2 ;;
        --test)     TEST_FLAG="--test"; shift ;;
        --port)     SERIAL_PORT="$2";  shift 2 ;;
        --no-browser) NO_BROWSER=true; shift ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--profile moe|draco|gse-v1] [--xlsx path] [--test] [--port PORT] [--no-browser]"
            exit 1 ;;
    esac
done

open_browser() {
    if [ "$NO_BROWSER" = true ]; then return; fi
    (sleep 2 && open "$1" 2>/dev/null || xdg-open "$1" 2>/dev/null || true) &
}

regen_configs() {
    if [ -n "$XLSX" ]; then
        echo "Regenerating configs from $XLSX ..."
        python3 "$SCRIPT_DIR/generate_configs.py" --xlsx "$XLSX" "$@"
    fi
}

# ── Interactive menu if no --profile given ────────────────────────────
if [ -z "$PROFILE" ]; then
    echo ""
    echo "================================================"
    echo "   ERPL Ground Control"
    echo "================================================"
    echo ""
    echo "  1) MOE     — Panda V2 + NI DAQ  (rocket + GSE)"
    echo "  2) Draco   — Panda V1 + NI DAQ  (original)"
    echo "  3) GSE V1  — Panda V1 via MOE backend"
    echo ""
    read -rp "Select config [1/2/3]: " CHOICE
    case "$CHOICE" in
        1) PROFILE="moe"    ;;
        2) PROFILE="draco"  ;;
        3) PROFILE="gse-v1" ;;
        *) echo "Invalid choice."; exit 1 ;;
    esac
fi

BG_PIDS=()
cleanup() {
    for pid in "${BG_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT

# ═══════════════════════════════════════════════════════════════════════
case "$PROFILE" in

# ── MOE: Panda V2 multi-device + NI DAQ ──────────────────────────────
moe)
    regen_configs --target moe
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

    open_browser "http://localhost:8081/moeui.html"
    python3 server.py --config "$SCRIPT_DIR/configs/moe_system.json" $TEST_FLAG
    ;;

# ── Draco: Panda V1 + NI DAQ (via MOE backend) ──────────────────────
draco)
    regen_configs --target moe
    echo ""
    echo "Starting Draco (Panda V1 via MOE backend)..."
    cd "$SCRIPT_DIR/moe"

    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install -q -r requirements.txt

    echo ""
    echo "  WebSocket : ws://localhost:3941"
    echo "  UI        : http://localhost:8080/moeui.html"
    echo ""

    open_browser "http://localhost:8080/moeui.html"
    python3 server.py --config "$SCRIPT_DIR/configs/draco_system.json" \
        --ws-port 3941 --http-port 8080 $TEST_FLAG
    ;;

# ── GSE V1: Panda V1 through MOE backend ─────────────────────────────
gse-v1)
    regen_configs --target moe
    echo ""
    echo "Starting GSE V1 (via MOE backend)..."
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

    open_browser "http://localhost:8081/moeui.html"
    python3 server.py --config "$SCRIPT_DIR/configs/gse_v1_system.json" $TEST_FLAG
    ;;

*)
    echo "Unknown profile: $PROFILE"
    echo "Valid profiles: moe, draco, gse-v1"
    exit 1
    ;;
esac
