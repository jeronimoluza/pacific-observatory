@echo off
setlocal enabledelayedexpansion

REM ─────────────────────────────────────────────────────────────
REM Pacific Observatory CLI — Windows bootstrap
REM Creates a local .venv and installs the `po` CLI into it.
REM No PowerShell execution policy required.
REM ─────────────────────────────────────────────────────────────

cd /d "%~dp0"

echo.
echo === Pacific Observatory CLI — Windows setup ===
echo.

REM Pick a Python interpreter: prefer the `py` launcher, fall back to `python`.
set "PY_CMD="
where py >nul 2>&1
if %errorlevel% == 0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>&1
    if !errorlevel! == 0 (
        set "PY_CMD=python"
    )
)

if "%PY_CMD%" == "" (
    echo [ERROR] No Python interpreter found.
    echo         Install Python 3.11+ from https://www.python.org/downloads/
    echo         or from the Microsoft Store, then re-run setup.bat.
    pause
    exit /b 1
)

echo [1/5] Using interpreter: %PY_CMD%
%PY_CMD% --version
if errorlevel 1 (
    echo [ERROR] Failed to run %PY_CMD% --version
    pause
    exit /b 1
)

echo.
echo [2/5] Creating virtual environment in .venv ...
if exist ".venv\Scripts\python.exe" (
    echo       .venv already exists, reusing it.
) else (
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv
        pause
        exit /b 1
    )
)

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

echo.
echo [3/5] Upgrading pip ...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip
    pause
    exit /b 1
)

echo.
echo [4/5] Installing pip_system_certs (handles corporate SSL inspection) ...
"%VENV_PY%" -m pip install pip_system_certs
if errorlevel 1 (
    echo [WARN]  pip_system_certs install failed — continuing anyway.
    echo         If later steps hit SSL errors, that is the likely cause.
)

echo.
echo [5/5] Installing the `po` CLI and dependencies ...
"%VENV_PY%" -m pip install -e .
if errorlevel 1 (
    echo [ERROR] Failed to install editable package
    pause
    exit /b 1
)

if exist "requirements.txt" (
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements.txt
        pause
        exit /b 1
    )
)

echo.
echo === Setup complete! ===
echo.
echo Run the CLI from this directory with:
echo     .\po text status
echo     .\po --help
echo.
pause
endlocal
