@echo off
setlocal enableextensions
pushd "%~dp0"

echo.
echo ================================================
echo   ERPL Ground Control - Full System Startup
echo ================================================
echo.
echo Starting NI DAQ and PANDA systems...
echo.

echo Regenerating configs from sensor_config.xlsx...
python generate_configs.py
echo.

call start_nidaq.bat
timeout /t 2 /nobreak >nul
call start_panda.bat

echo.
echo ================================================
echo   All Systems Started
echo ================================================
echo.
echo NI DAQ:  http://localhost:3000
echo PANDA:   http://localhost:8080/panda-daq-ui.html
echo.
echo Use stop_all.bat to shutdown everything
echo.

popd
endlocal
