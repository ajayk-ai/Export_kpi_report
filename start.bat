@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv is not installed or not on PATH. Install it: pip install uv
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env not found. Copy .env.example to .env and fill it in.
    pause
    exit /b 1
)

if not exist "config\service.json" (
    echo [ERROR] config\service.json not found. Add the Google service account key first.
    pause
    exit /b 1
)

echo Syncing dependencies...
uv sync
if errorlevel 1 (
    echo [ERROR] uv sync failed.
    pause
    exit /b 1
)

echo Starting Export KPI server...
uv run python -m app.main

pause
