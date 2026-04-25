@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%HERMES_LOCAL_STT_VENV%"
if "%VENV_DIR%"=="" set "VENV_DIR=%SCRIPT_DIR%.venv"
set "UV_BIN=%UV_BIN%"
if "%UV_BIN%"=="" set "UV_BIN=uv"
set "PYTHON_VERSION=%HERMES_LOCAL_STT_PYTHON_VERSION%"

where %UV_BIN% >nul 2>nul
if errorlevel 1 (
  echo uv not found: %UV_BIN%
  exit /b 1
)

if not "%PYTHON_VERSION%"=="" (
  %UV_BIN% venv --python %PYTHON_VERSION% "%VENV_DIR%"
) else (
  %UV_BIN% venv "%VENV_DIR%"
)
if errorlevel 1 exit /b 1

%UV_BIN% pip install --python "%VENV_DIR%\Scripts\python.exe" -r "%SCRIPT_DIR%requirements.txt"
if errorlevel 1 exit /b 1

echo Runtime setup complete
echo uv env: %VENV_DIR%
echo model(default): %HERMES_LOCAL_STT_MODEL%
if "%HERMES_LOCAL_STT_MODEL%"=="" echo model(default): large-v3-turbo
echo next: %SCRIPT_DIR%launch-windows.bat
