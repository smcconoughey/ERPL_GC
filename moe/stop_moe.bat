@echo off
setlocal enableextensions
pushd "%~dp0.."

echo.
echo ================================================
echo   ERPL Ground Control - MOE System Shutdown
echo ================================================
echo.

call stop_nidaq.bat
call stop_panda.bat

echo.
echo ================================================
echo   MOE System Stopped
echo ================================================
echo.

popd
endlocal
pause
