@echo off
cd /d "%~dp0"
setlocal EnableExtensions EnableDelayedExpansion

title Plate Number Keychain
echo ========================================
echo   Plate Number STL Generator
echo ========================================
echo.

set "PYTHON_EXE="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    where py >nul 2>&1 && for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"
    if not defined PYTHON_EXE where python >nul 2>&1 && for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python not found.
    echo.
    echo Please install Python 3.11 or 3.12, then run this script again.
    echo Download:
    echo   https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
    echo.
    echo During install, check "Add python.exe to PATH".
    echo.
    start "" "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
    pause
    exit /b 1
)

echo [INFO] Python: %PYTHON_EXE%

REM Prefer Python 3.11/3.12 for CadQuery wheels
"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)" 2>nul
if errorlevel 1 (
    echo [WARN] Current Python is not 3.11/3.12. CadQuery may fail to install.
    echo [WARN] Recommended download:
    echo   https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
    echo.
)

REM Prefer py -3.12 / py -3.11 when creating venv
set "VENV_BASE=%PYTHON_EXE%"
where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "VENV_BASE=%%I"
    if "!VENV_BASE!"=="%PYTHON_EXE%" (
        for /f "delims=" %%I in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "VENV_BASE=%%I"
    )
)

REM Create venv on first run when using system Python
echo "%PYTHON_EXE%" | findstr /I /C:"\venv\Scripts\python.exe" >nul
if errorlevel 1 (
    if not exist "%~dp0venv\Scripts\python.exe" (
        echo [INFO] Creating venv with: %VENV_BASE%
        "%VENV_BASE%" -m venv "%~dp0venv"
        if errorlevel 1 (
            echo [ERROR] Failed to create venv.
            pause
            exit /b 1
        )
    )
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
)

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo [INFO] Checking dependencies...
echo [INFO] If installing, large packages may take several minutes. Please wait...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_deps.ps1" -PythonExe "%PYTHON_EXE%" -ProjectRoot "%ROOT%"
if errorlevel 1 (
    echo [ERROR] Dependency install failed.
    pause
    exit /b 1
)

if not defined PORT set "PORT=5001"
set "FLASK_DEBUG=0"
echo.
echo [INFO] Starting http://127.0.0.1:%PORT%
echo [INFO] Press Ctrl+C to stop
echo.

start "" "http://127.0.0.1:%PORT%/"
"%PYTHON_EXE%" "%~dp0app.py"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo [ERROR] App exited with code %EXIT_CODE%
    pause
)
exit /b %EXIT_CODE%
