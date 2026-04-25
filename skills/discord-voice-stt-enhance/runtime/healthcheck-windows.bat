@echo off
setlocal

set "HOST=%HERMES_LOCAL_STT_HOST%"
if "%HOST%"=="" set "HOST=127.0.0.1"
set "PORT=%HERMES_LOCAL_STT_PORT%"
if "%PORT%"=="" set "PORT=8177"

curl -fsS http://%HOST%:%PORT%/health
