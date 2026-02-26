@echo off
setlocal enableextensions
pushd "%~dp0"

echo.
echo ========================================
echo   ERPL Ground Control - NI DAQ System
echo ========================================
echo.

rem Locate Node.js
set "NODE_EXE="
for /f "delims=" %%i in ('where node 2^>nul') do (
    set "NODE_EXE=%%i"
    goto :found_node
)

for %%p in ("C:\Program Files\nodejs\node.exe" "%USERPROFILE%\AppData\Local\Programs\nodejs\node.exe") do (
    if exist %%p (
        set "NODE_EXE=%%p"
        goto :found_node
    )
)

echo ERROR: Node.js not found. Install from https://nodejs.org
goto :end

:found_node
for %%i in ("%NODE_EXE%") do set "NODE_DIR=%%~dpi"
set "PATH=%NODE_DIR%;%PATH%"
echo Using Node: %NODE_EXE%

rem Install Node dependencies on first run
if not exist ni_daq\node_modules (
    echo Installing Node.js dependencies...
    pushd ni_daq
    call npm install --no-fund --no-audit
    popd
)

echo Regenerating configs from sensor_config.xlsx...
python "%~dp0generate_configs.py"
echo.

echo Starting NI DAQ WebSocket Server...
start "NI DAQ Server" cmd /k "title NI DAQ Server && cd ni_daq && "%NODE_EXE%" server.js"

echo Waiting 3 seconds for server startup...
timeout /t 3 /nobreak >nul

echo Starting NI DAQ Python Streamer...
start "NI DAQ Streamer" cmd /k "title NI DAQ Streamer && cd ni_daq && python daq_streamer.py"

echo.
echo ========================================
echo   NI DAQ System Started
echo ========================================
echo.
echo Web Interface:     http://localhost:3000
echo DAQ Hardware:      192.168.8.236 (cDAQ9189-2462EFD)
echo WebSocket Port:    3000
echo TCP Data Port:     5001
echo.
echo Use stop_nidaq.bat to shutdown
echo.
start http://localhost:3000

:end
popd
endlocal
