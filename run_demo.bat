@echo off
setlocal
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0tools\start_windows.ps1" %*
set "result=%errorlevel%"
if not "%result%"=="0" (
    echo.
    echo Please read the message above before closing this window.
    pause
)
exit /b %result%
