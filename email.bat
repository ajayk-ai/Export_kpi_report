@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "TS=%date% %time%"

rem ---- try: create the logs folder; catch: degrade to console-only logging ----
set "LOGFILE=logs\email.log"
if not exist "logs" (
    mkdir "logs" 2>nul
    if errorlevel 1 (
        echo [WARN] Could not create logs\ -- continuing without file logging.
        set "LOGFILE="
    )
)

rem ---- curl must exist, or every send attempt would fail anyway ----
where curl >nul 2>nul
if errorlevel 1 (
    echo [ERROR] curl not found on PATH. Install curl or add it to PATH.
    call :log "[ERROR] curl not found on PATH. Aborted before attempting to send."
    if /I not "%~1"=="scheduled" pause
    exit /b 1
)

rem HOST/PORT: which running server to hit (falls back to localhost:8000 if
rem .env doesn't set them).
set "HOST=localhost"
set "PORT=8000"
rem RECIPIENT: read fresh from .env every run and pass explicitly to the API,
rem instead of relying on the server's EMAIL_RECIPIENT — the server only reads
rem .env once at startup, so without this an .env edit wouldn't take effect
rem until the server is restarted.
set "RECIPIENT="
if exist ".env" (
    for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
        if /I "%%A"=="HOST" if not "%%B"=="" set "HOST=%%B"
        if /I "%%A"=="PORT" if not "%%B"=="" set "PORT=%%B"
        if /I "%%A"=="EMAIL_RECIPIENT" if not "%%B"=="" set "RECIPIENT=%%B"
    )
) else (
    echo [WARN] .env not found -- using default localhost:8000 and the server's own EMAIL_RECIPIENT.
    call :log "[WARN] .env not found -- using default localhost:8000 and no recipient override."
)
rem HOST=0.0.0.0 means "listen on every interface" -- it's a bind address,
rem not something you can actually connect *to*. Since this script always
rem targets the server on this same machine, translate it to localhost.
if "!HOST!"=="0.0.0.0" set "HOST=localhost"
rem Strip spaces so "a@x.com, b@x.com" survives as a single URL query value
rem (the API splits on comma/semicolon regardless of spacing).
if defined RECIPIENT set "RECIPIENT=!RECIPIENT: =!"

set "URL=http://!HOST!:!PORT!/send"
if defined RECIPIENT set "URL=!URL!?recipient=!RECIPIENT!"

call :log "Sending KPI report email via !URL! ..."
echo Sending KPI report email via !URL! ...

if defined LOGFILE (
    curl -f -X POST "!URL!" >> "%LOGFILE%" 2>&1
) else (
    curl -f -X POST "!URL!"
)
set "CURL_RC=%errorlevel%"
call :log ""
if not "%CURL_RC%"=="0" (
    call :log "[ERROR] Send failed - exit code %CURL_RC%, see curl output above in this log."
    echo.
    echo [ERROR] Request failed - exit code %CURL_RC%. Is the server running? Try start.bat first.
    if defined LOGFILE echo See %LOGFILE% for details.
    if /I not "%~1"=="scheduled" pause
    exit /b 1
)

call :log "[OK] Send request completed."
echo Done.
if defined LOGFILE echo See %LOGFILE% for the response.

rem Scheduled runs (Task Scheduler passes "scheduled" as an argument) have no
rem console to press a key on -- pause would hang the task forever. Only
rem pause for an interactive double-click.
if /I not "%~1"=="scheduled" pause
exit /b 0

:log
if defined LOGFILE echo [%TS%] %~1 >> "%LOGFILE%"
exit /b 0
