@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python run.py app
) else (
  "C:\Users\小张\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" run.py app
)
if errorlevel 1 pause