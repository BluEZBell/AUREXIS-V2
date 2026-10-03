@echo off
cd /d "%~dp0"
echo INFO: Scanning and sanitizing ports 8000 and 8080...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /c:":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /c:":8080 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
echo INFO: System entering Live Burn-In.
echo TELEMETRY API: http://localhost:8080/status
set AUREXIS_LAUNCHER=1
python run_live.py
pause
