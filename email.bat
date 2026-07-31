@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem PORT: which running server to hit (falls back to 8000 if .env doesn't set it).
set "PORT=8000"
rem RECIPIENT: read fresh from .env every run and pass explicitly to the API,
rem instead of relying on the server's EMAIL_RECIPIENT — the server only reads
rem .env once at startup, so without this an .env edit wouldn't take effect
rem until the server is restarted.
set "RECIPIENT="
if exist ".env" (
    for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
        if /I "%%A"=="PORT" if not "%%B"=="" set "PORT=%%B"
        if /I "%%A"=="EMAIL_RECIPIENT" if not "%%B"=="" set "RECIPIENT=%%B"
    )
)
rem Strip spaces so "a@x.com, b@x.com" survives as a single URL query value
rem (the API splits on comma/semicolon regardless of spacing).
if defined RECIPIENT set "RECIPIENT=!RECIPIENT: =!"

set "URL=http://127.0.0.1:!PORT!/send"
if defined RECIPIENT set "URL=!URL!?recipient=!RECIPIENT!"

echo Sending KPI report email via !URL! ...
curl -f -X POST "!URL!"
if errorlevel 1 (
    echo.
    echo [ERROR] Request failed. Is the server running? Try start.bat first.
)

pause
