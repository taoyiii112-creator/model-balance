@echo off
cd /d "%~dp0"
rem 使用 python.exe（控制台模式），窗口保持打开，显示同步令牌与运行状态
set "MB_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%MB_PY%" (
  "%MB_PY%" run.py lan-sync
) else (
  python.exe run.py lan-sync
)
if errorlevel 1 (
  echo.
  echo 启动失败，请检查上面的错误信息后关闭窗口。
  pause
)
