@echo off
REM ─────────────────────────────────────────────────────────────
REM Pacific Observatory CLI launcher
REM Calls the `po` entry point inside the local .venv without
REM requiring PowerShell activation.
REM ─────────────────────────────────────────────────────────────

set "PO_EXE=%~dp0.venv\Scripts\po.exe"

if not exist "%PO_EXE%" (
    echo [ERROR] Could not find %PO_EXE%
    echo         Run setup.bat first to create the environment.
    exit /b 1
)

"%PO_EXE%" %*
exit /b %errorlevel%
