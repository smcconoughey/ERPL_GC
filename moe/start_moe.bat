@echo off
setlocal enabledelayedexpansion

echo MOE Ground Control Backend - Startup
echo.

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -q -r requirements.txt

echo.
echo Starting MOE server on port 3942...
python server.py --config configs/moe_system.json

pause
