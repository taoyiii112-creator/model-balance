@echo off
cd /d "%~dp0"
set "MB_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%MB_PY%" (
  start "ModelBalance-Web" "%MB_PY%" run.py web
) else (
  start "ModelBalance-Web" python run.py web
)
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8000