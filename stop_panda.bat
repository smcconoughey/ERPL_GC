@echo off
echo.
echo ========================================
echo   ERPL Ground Control - Stop PANDA
echo ========================================
echo.

echo Stopping PANDA services...

rem Kill PANDA Bridge window
taskkill /f /fi "WINDOWTITLE eq PANDA Bridge*" >nul 2>&1

echo.
echo PANDA system stopped.
echo.
pause
