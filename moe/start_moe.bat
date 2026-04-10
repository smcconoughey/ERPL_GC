@echo off
setlocal enableextensions
pushd "%~dp0.."

echo.
echo ================================================
echo   ERPL Ground Control - MOE System Startup
echo ================================================
echo.

echo Regenerating configs from sensor_config.xlsx...
python generate_configs.py
echo.

call start_nidaq.bat
timeout /t 2 /nobreak >nul
call start_panda.bat

echo.
echo ================================================
echo   MOE System Started
echo ================================================
echo.
echo NI DAQ:      http://localhost:3000
echo PANDA:       http://localhost:8080
echo MOE UI:      http://localhost:8080/moeui.html
echo.
echo Use moe\stop_moe.bat to shutdown everything
echo.

timeout /t 3 /nobreak >nul
start http://localhost:8080/moeui.html

popd
endlocal
