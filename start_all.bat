@echo off
setlocal enableextensions enabledelayedexpansion
pushd "%~dp0"

rem ── Parse arguments ─────────────────────────────────────────────────
set "PROFILE="
set "XLSX="
set "TEST_FLAG="
set "SERIAL_PORT="

:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--profile" (set "PROFILE=%~2" & shift & shift & goto :parse_args)
if /I "%~1"=="--xlsx"    (set "XLSX=%~2"    & shift & shift & goto :parse_args)
if /I "%~1"=="--test"    (set "TEST_FLAG=--test" & shift & goto :parse_args)
if /I "%~1"=="--port"    (set "SERIAL_PORT=%~2" & shift & shift & goto :parse_args)
echo Unknown option: %~1
goto :usage
:args_done

rem ── Interactive menu if no --profile ────────────────────────────────
if not defined PROFILE (
    echo.
    echo ================================================
    echo   ERPL Ground Control
    echo ================================================
    echo.
    echo   1^) MOE     - Panda V2 + NI DAQ  ^(rocket + GSE^)
    echo   2^) Draco   - Panda V1 + NI DAQ  ^(original^)
    echo   3^) GSE V1  - Panda V1 via MOE backend
    echo.
    set /p CHOICE="Select config [1/2/3]: "
    if "!CHOICE!"=="1" set "PROFILE=moe"
    if "!CHOICE!"=="2" set "PROFILE=draco"
    if "!CHOICE!"=="3" set "PROFILE=gse-v1"
    if not defined PROFILE (echo Invalid choice. & goto :eof)
)

rem ── Regen configs if --xlsx given ───────────────────────────────────
if defined XLSX (
    echo Regenerating configs from %XLSX% ...
    python generate_configs.py --xlsx "%XLSX%"
    echo.
)

rem ── Profile dispatch ────────────────────────────────────────────────
if /I "%PROFILE%"=="moe"    goto :launch_moe
if /I "%PROFILE%"=="draco"  goto :launch_draco
if /I "%PROFILE%"=="gse-v1" goto :launch_gse_v1
echo Unknown profile: %PROFILE%
goto :usage

rem ── MOE ─────────────────────────────────────────────────────────────
:launch_moe
echo.
echo Starting MOE...
pushd moe
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv venv
)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo.
echo   WebSocket : ws://localhost:3942
echo   UI        : http://localhost:8081/moeui.html
echo.

timeout /t 3 /nobreak >nul
start http://localhost:8081/moeui.html

python server.py --config "%~dp0configs\moe_system.json" %TEST_FLAG%
popd
goto :eof

rem ── Draco ───────────────────────────────────────────────────────────
:launch_draco
echo.
echo Regenerating configs from sensor_config.xlsx...
python generate_configs.py
echo.
echo Starting Draco (original)...

call start_nidaq.bat
timeout /t 2 /nobreak >nul

if defined SERIAL_PORT (
    call start_panda.bat --port %SERIAL_PORT% %TEST_FLAG%
) else (
    call start_panda.bat %TEST_FLAG%
)

echo.
echo ================================================
echo   Draco Started
echo ================================================
echo.
echo NI DAQ:  http://localhost:3000
echo PANDA:   http://localhost:8080/panda-daq-ui.html
echo MOE UI:  http://localhost:8080/moeui.html
echo.

timeout /t 3 /nobreak >nul
start http://localhost:8080/moeui.html
goto :eof

rem ── GSE V1 ──────────────────────────────────────────────────────────
:launch_gse_v1
echo.
echo Starting GSE V1 (via MOE backend)...
pushd moe
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv venv
)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo.
echo   WebSocket : ws://localhost:3942
echo   UI        : http://localhost:8081/moeui.html
echo.

timeout /t 3 /nobreak >nul
start http://localhost:8081/moeui.html

python server.py --config "%~dp0configs\gse_v1_system.json" %TEST_FLAG%
popd
goto :eof

rem ── Usage ───────────────────────────────────────────────────────────
:usage
echo.
echo Usage: %~nx0 [--profile moe^|draco^|gse-v1] [--xlsx path] [--test] [--port PORT]
echo.
goto :eof

popd
endlocal
