#!/bin/bash

echo "MOE Ground Control Backend - Startup"
echo ""

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "Starting MOE server on port 3942..."
python3 server.py --config configs/moe_system.json
