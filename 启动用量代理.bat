@echo off
cd /d "%~dp0"
set "MB_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%MB_PY%" (
  start "ModelBalance-Proxy" "%MB_PY%" run.py proxy
) else (
  start "ModelBalance-Proxy" python run.py proxy
)