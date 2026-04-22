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

rem Kill NI DAQ console windows first
echo Stopping NI DAQ console windows...
taskkill /f /fi "WINDOWTITLE eq NI DAQ Server*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq NI DAQ Streamer*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq NI DAQ Streamer V2*" >nul 2>&1

rem Kill orphaned NI DAQ processes by command line (more reliable than title)
echo Stopping orphaned NI DAQ python/node processes...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { " ^
  "  ($_.Name -match '^(python|pythonw|node|cmd)\.exe$') -and " ^
  "  ($_.CommandLine -match 'ni_daq(\\|/)daq_streamer\.py' -or " ^
  "   $_.CommandLine -match 'ni_daq(\\|/)server\.js' -or " ^
  "   $_.CommandLine -match 'NI DAQ Streamer' -or " ^
  "   $_.CommandLine -match 'NI DAQ Server')" ^
  "};" ^
  "foreach($p in $procs){ try { Stop-Process -Id $p.ProcessId -Force } catch {} }"

rem Best-effort NI-DAQmx resource cleanup (close lingering tasks)
echo Cleaning up lingering NI-DAQmx tasks...
python -c "import nidaqmx, nidaqmx.system; s=nidaqmx.system.System.local(); names=list(getattr(s.tasks,'task_names',[])); [ (lambda t:(t.stop(), t.close()))(nidaqmx.Task(n)) for n in names if n ]" >nul 2>&1

rem Clean up
if exist ni_daq\shutdown_daq.cmd del ni_daq\shutdown_daq.cmd

echo.
echo NI DAQ system stopped.
echo.
pause
