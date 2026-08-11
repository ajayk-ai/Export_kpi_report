```bat
@echo off
setlocal enabledelayedexpansion

rem ---- Always run from the BAT file's directory ----
cd /d "%~dp0"

rem ---- Timestamp ----
set "TS=%date% %time%"

rem ---- Try to create logs folder ----
set "LOGFILE=logs\email.log"

if not exist "logs" (
    mkdir "logs" 2>nul
    if errorlevel 1 (
        echo [WARN] Could not create logs folder - continuing without file logging.
        set "LOGFILE="
    )
)

rem ---- Check curl exists ----
where curl >nul 2>nul

if errorlevel 1 (
    echo [ERROR] curl not found on PATH.
    call :log "[ERROR] curl not found on PATH. Aborted before attempting to send."
    exit /b 1
)

rem ---- Default HOST and PORT ----
set "HOST=localhost"
set "PORT=8000"

rem ---- Read HOST, PORT and EMAIL_RECIPIENT from .env ----
set "RECIPIENT="

if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if /I "%%A"=="HOST" if not "%%B"=="" set "HOST=%%B"
        if /I "%%A"=="PORT" if not "%%B"=="" set "PORT=%%B"
        if /I "%%A"=="EMAIL_RECIPIENT" if not "%%B"=="" set "RECIPIENT=%%B"
    )
) else (
    echo [WARN] .env not found - using localhost:8000.
    call :log "[WARN] .env not found - using default localhost:8000."
)

rem ---- 0.0.0.0 is a bind address, use localhost for connection ----
if "!HOST!"=="0.0.0.0" set "HOST=localhost"

rem ---- Remove spaces from recipient list ----
if defined RECIPIENT set "RECIPIENT=!RECIPIENT: =!"

rem ---- Build API URL ----
set "URL=http://!HOST!:!PORT!/send"

if defined RECIPIENT (
    set "URL=!URL!?recipient=!RECIPIENT!"
)

echo Sending KPI report email via !URL! ...
call :log "Sending KPI report email via !URL! ..."

rem ---- Send request with 60-second timeout ----
if defined LOGFILE (
    curl --max-time 60 -f -X POST "!URL!" >> "%LOGFILE%" 2>&1
) else (
    curl --max-time 60 -f -X POST "!URL!"
)

set "CURL_RC=%errorlevel%"

call :log ""

rem ---- Check result ----
if not "%CURL_RC%"=="0" (
    echo [ERROR] Request failed - exit code %CURL_RC%.
    call :log "[ERROR] Send failed - exit code %CURL_RC%."
    
    if defined LOGFILE (
        echo See %LOGFILE% for details.
    )

    exit /b 1
)

rem ---- Success ----
call :log "[OK] Send request completed successfully."
echo Done.

if defined LOGFILE (
    echo See %LOGFILE% for the response.
)

rem ---- End task ----
exit /b 0


:log
if defined LOGFILE (
    echo [%TS%] %~1 >> "%LOGFILE%"
)
exit /b 0
```
