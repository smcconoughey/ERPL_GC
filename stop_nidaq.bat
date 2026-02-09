@echo off
echo.
echo ========================================
echo   ERPL Ground Control - Stop NI DAQ
echo ========================================
echo.

echo Stopping NI DAQ services...

rem Signal Python to shutdown cleanly
echo Signaling shutdown...
powershell -Command "Set-Content -Path 'ni_daq\shutdown_daq.cmd' -Value 'shutdown'" 2>nul
timeout /t 2 /nobreak >nul

rem Kill Node.js (NI DAQ Server)
echo Stopping NI DAQ Server...
taskkill /f /fi "WINDOWTITLE eq NI DAQ Server*" >nul 2>&1

rem Kill Python (NI DAQ Streamer)
echo Stopping NI DAQ Streamer...
taskkill /f /fi "WINDOWTITLE eq NI DAQ Streamer*" >nul 2>&1

rem Clean up
if exist ni_daq\shutdown_daq.cmd del ni_daq\shutdown_daq.cmd

echo.
echo NI DAQ system stopped.
echo.
pause
