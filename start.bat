@echo off
setlocal EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"
set "DRIVE_ROOT=%SCRIPT_DIR%"

echo ============================================================
echo   KYLO File Explorer
echo ============================================================

:: ── Find drive root (walk up until _DRIVE_HOME found) ──
:find_root
if exist "!DRIVE_ROOT!_DRIVE_HOME" goto found_root
for %%I in ("!DRIVE_ROOT!..") do set "PARENT=%%~fI\"
if "!PARENT!"=="!DRIVE_ROOT!" goto found_root
set "DRIVE_ROOT=!PARENT!"
goto find_root
:found_root
echo Drive root: !DRIVE_ROOT!
set "ENV_DIR=!DRIVE_ROOT!_env"

:: ── Python check ──
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause & exit /b 1
)

:: ── Create shared venv if missing ──
if not exist "!ENV_DIR!\Scripts\activate.bat" (
    echo Creating shared Python environment at !ENV_DIR! ...
    python -m venv "!ENV_DIR!"
    if not exist "!ENV_DIR!\Scripts\activate.bat" (
        echo ERROR: Could not create Python environment at !ENV_DIR!
        echo Try running this script as Administrator.
        pause & exit /b 1
    )
    echo Done.
)

:: ── Activate venv ──
call "!ENV_DIR!\Scripts\activate.bat"
echo Using: !ENV_DIR!

:: ── Install / upgrade dependencies ──
echo Installing dependencies (first run may take a minute)...
pip install -r "%SCRIPT_DIR%requirements.txt" --quiet --upgrade

:: ── Kill any existing KYLO on this port ──
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8765 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: ── Ollama check ──
curl -s http://localhost:11434 >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: Ollama is not running. AI features will be disabled.
    echo   Install : https://ollama.com
    echo   Models  : ollama pull gemma3:4b
    echo             ollama pull nomic-embed-text
    echo.
    set "KYLO_AI_AVAILABLE=false"
) else (
    echo Ollama: connected
    set "KYLO_AI_AVAILABLE=true"
)

set "KYLO_DRIVE_ROOT=!DRIVE_ROOT!"

:: ── Launch ──
echo.
echo KYLO running at http://localhost:8765
echo Press Ctrl+C to stop.
echo.
start "" http://localhost:8765
python "%SCRIPT_DIR%backend\main.py"
pause
