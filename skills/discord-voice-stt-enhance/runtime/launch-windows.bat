@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%HERMES_LOCAL_STT_VENV%"
if "%VENV_DIR%"=="" set "VENV_DIR=%SCRIPT_DIR%.venv"
set "HOST=%HERMES_LOCAL_STT_HOST%"
if "%HOST%"=="" set "HOST=0.0.0.0"
set "PORT=%HERMES_LOCAL_STT_PORT%"
if "%PORT%"=="" set "PORT=8177"
set "LOG_DIR=%HERMES_LOCAL_STT_LOG_DIR%"
if "%LOG_DIR%"=="" set "LOG_DIR=%SCRIPT_DIR%logs"
set "STDOUT_LOG=%LOG_DIR%\server.out.log"
set "STDERR_LOG=%LOG_DIR%\server.err.log"
set "PID_FILE=%LOG_DIR%\server.pid"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "SERVER_PY=%SCRIPT_DIR%server.py"

if not exist "%PYTHON_EXE%" (
  echo Missing uv-managed runtime env: %VENV_DIR%
  echo Run %SCRIPT_DIR%setup-windows.bat first.
  exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if exist "%PID_FILE%" (
  set /p EXISTING_PID=<"%PID_FILE%"
  if not "%EXISTING_PID%"=="" (
    tasklist /FI "PID eq %EXISTING_PID%" | find "%EXISTING_PID%" >nul 2>nul
    if not errorlevel 1 (
      echo Hermes local STT server already running with PID %EXISTING_PID%
      echo stdout: %STDOUT_LOG%
      echo stderr: %STDERR_LOG%
      exit /b 0
    )
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$stdout = [IO.Path]::GetFullPath('%STDOUT_LOG%');" ^
  "$stderr = [IO.Path]::GetFullPath('%STDERR_LOG%');" ^
  "$pidFile = [IO.Path]::GetFullPath('%PID_FILE%');" ^
  "$workdir = [IO.Path]::GetFullPath('%SCRIPT_DIR%');" ^
  "$proc = Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList @('%SERVER_PY%','--host','%HOST%','--port','%PORT%') -WorkingDirectory $workdir -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru;" ^
  "Set-Content -Path $pidFile -Value $proc.Id;" ^
  "Write-Output ('Started Hermes local STT server in background. PID=' + $proc.Id);"
if errorlevel 1 exit /b 1

echo stdout: %STDOUT_LOG%
echo stderr: %STDERR_LOG%
