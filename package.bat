@echo off
cd /d "%~dp0"
setlocal EnableExtensions

title Package plate-number
echo ========================================
echo   Package release
echo ========================================
echo.

where powershell >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PowerShell is required.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\package.ps1"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo [ERROR] Package failed. Code=%CODE%
)
echo.
pause
exit /b %CODE%
