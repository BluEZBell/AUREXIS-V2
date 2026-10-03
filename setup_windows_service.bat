@echo off
:: setup_windows_service.bat
:: Installs aurexis_supervisor.py as a background Windows Service using NSSM.

:: Ensure we are in the script's directory (important when Run as Administrator)
cd /d "%~dp0"

SET SERVICE_NAME=AurexisSupervisor
SET NSSM_EXE=nssm.exe
SET PYTHON_EXE=%~dp0.venv\Scripts\python.exe
SET SCRIPT_PATH=%~dp0aurexis_supervisor.py
:: Remove trailing backslash for AppDirectory to avoid escaping quotes
SET WORK_DIR=%~dp0
IF "%WORK_DIR:~-1%"=="\" SET WORK_DIR=%WORK_DIR:~0,-1%

echo Checking for NSSM (Non-Sucking Service Manager)...
where %NSSM_EXE% >nul 2>nul
if %errorlevel% neq 0 (
    if exist "%~dp0nssm.exe" (
        SET NSSM_EXE="%~dp0nssm.exe"
    ) else (
        echo [ERROR] nssm.exe not found in PATH or current directory.
        echo Please download NSSM from https://nssm.cc/ and extract nssm.exe to this directory.
        pause
        exit /b 1
    )
)

echo Checking for Python Virtual Environment...
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python virtual environment not found at %PYTHON_EXE%
    echo Ensure the .venv exists before setting up the service.
    pause
    exit /b 1
)

:: Create logs directory if it doesn't exist
if not exist "logs" (
    mkdir logs
)

echo Installing Windows Service: %SERVICE_NAME%
%NSSM_EXE% install %SERVICE_NAME% "%PYTHON_EXE%" "%SCRIPT_PATH%"

echo Configuring Service parameters (Auto-start, working directory, logging, restart delay)...
%NSSM_EXE% set %SERVICE_NAME% AppDirectory "%WORK_DIR%"
%NSSM_EXE% set %SERVICE_NAME% AppStdout "%WORK_DIR%\logs\service_stdout.log"
%NSSM_EXE% set %SERVICE_NAME% AppStderr "%WORK_DIR%\logs\service_stderr.log"
%NSSM_EXE% set %SERVICE_NAME% Start SERVICE_AUTO_START
%NSSM_EXE% set %SERVICE_NAME% AppRestartDelay 10000

echo Setup Complete.
echo The service is installed and configured to run on system boot.
pause
