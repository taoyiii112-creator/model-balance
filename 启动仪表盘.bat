@echo off
cd /d "%~dp0"
set "MB_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if exist "%MB_PY%" (
  start "" "%MB_PY%" run.py app
) else (
  start "" pythonw.exe run.py app
)