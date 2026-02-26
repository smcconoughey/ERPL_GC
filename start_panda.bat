@echo off
setlocal enableextensions
pushd "%~dp0\panda"

echo.
echo ========================================
echo   ERPL Ground Control - PANDA System
echo ========================================
echo.

set "VENV_DIR=.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "WS_PORT=3941"
set "DEFAULT_PORT=COM4"
set "ARGS=%*"

rem If no --port/-p provided, default to COM4
set "HASPORT=0"
echo %ARGS% | find /I "--port" >nul && set HASPORT=1
echo %ARGS% | find /I "-p" >nul && set HASPORT=1
if "%HASPORT%"=="0" set "ARGS=--port %DEFAULT_PORT% %ARGS%"

if not exist "%PY%" (
    echo Creating Python virtual environment...
    py -3 -m venv "%VENV_DIR%"
)

if not exist "%PY%" set "PY=python"

echo Installing dependencies...
%PY% -m pip install --upgrade pip setuptools wheel >nul 2>&1
%PY% -m pip install websockets pyserial -q

rem Free the websocket port if held
powershell -NoProfile -Command "try{Get-NetTCPConnection -LocalPort %WS_PORT% -State Listen -ErrorAction SilentlyContinue | Select -Expand OwningProcess -Unique | ForEach-Object { try { Stop-Process -Id $_ -ErrorAction SilentlyContinue } catch {} }}catch{}"

echo Regenerating configs from sensor_config.xlsx...
python "%~dp0generate_configs.py"
echo.

echo Starting PANDA bridge...
start "PANDA Bridge" cmd /k "title PANDA Bridge && %PY% -u main.py %ARGS%"

echo.
echo ========================================
echo   PANDA System Started
echo ========================================
echo.
echo Serial Port:       %DEFAULT_PORT%
echo WebSocket Port:    %WS_PORT%
echo HTTP Port:         8080
echo.
echo UI Pages:
echo   http://localhost:8080/panda-daq-ui.html
echo   http://localhost:8080/sequencer.html
echo   http://localhost:8080/pid.html
echo.
echo Use stop_panda.bat to shutdown
echo.

popd
endlocal
