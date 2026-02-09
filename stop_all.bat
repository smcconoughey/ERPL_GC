@echo off
setlocal enableextensions
pushd "%~dp0"

echo.
echo ================================================
echo   ERPL Ground Control - Full System Shutdown
echo ================================================
echo.

call stop_nidaq.bat
call stop_panda.bat

echo.
echo ================================================
echo   All Systems Stopped
echo ================================================
echo.

popd
endlocal
pause
