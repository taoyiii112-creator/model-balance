@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "MB_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%MB_PY%" (
  "%MB_PY%" build_exe.py
) else (
  python build_exe.py
)
pause