@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist "logs" mkdir "logs"
set "LOGFILE=logs\email.log"

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

set "URL=http://localhost:!PORT!/send"
if defined RECIPIENT set "URL=!URL!?recipient=!RECIPIENT!"

set "TS=%date% %time%"
echo. >> "%LOGFILE%"
echo [%TS%] Sending KPI report email via %URL% ... >> "%LOGFILE%"
echo Sending KPI report email via %URL% ...

curl -f -X POST "%URL%" >> "%LOGFILE%" 2>&1
set "CURL_RC=%errorlevel%"
echo. >> "%LOGFILE%"
if not "%CURL_RC%"=="0" (
    echo [%TS%] [ERROR] Send failed - exit code %CURL_RC%, see curl output above in this log. >> "%LOGFILE%"
    echo.
    echo [ERROR] Request failed. Is the server running? Try start.bat first.
    echo See %LOGFILE% for details.
) else (
    echo [%TS%] [OK] Send request completed. >> "%LOGFILE%"
    echo Done. See %LOGFILE% for the response.
)

rem Scheduled runs (Task Scheduler passes "scheduled" as an argument) have no
rem console to press a key on -- pause would hang the task forever. Only
rem pause for an interactive double-click.
if /I not "%~1"=="scheduled" pause
