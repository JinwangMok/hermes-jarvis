@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "LOG_DIR=%HERMES_LOCAL_STT_LOG_DIR%"
if "%LOG_DIR%"=="" set "LOG_DIR=%SCRIPT_DIR%logs"
set "PID_FILE=%LOG_DIR%\server.pid"

if not exist "%PID_FILE%" (
  echo No PID file found: %PID_FILE%
  exit /b 1
)

set /p SERVER_PID=<"%PID_FILE%"
if "%SERVER_PID%"=="" (
  echo Empty PID file: %PID_FILE%
  exit /b 1
)

tasklist /FI "PID eq %SERVER_PID%" | find "%SERVER_PID%" >nul 2>nul
if errorlevel 1 (
  echo Process %SERVER_PID% is not running.
  del "%PID_FILE%" >nul 2>nul
  exit /b 0
)

taskkill /PID %SERVER_PID% /T /F
if errorlevel 1 exit /b 1

del "%PID_FILE%" >nul 2>nul
echo Stopped Hermes local STT server PID %SERVER_PID%
