<#
Wrapper invoked by the "ExportKPIDailyReport" scheduled task (see register_task.ps1).

Runs `main.py --send` using the project's own venv interpreter (not a bare
`python`/`uv` on PATH, since the scheduled task runs outside any shell profile)
and appends timestamped output to logs\daily_report.log, so a failed run
(bad Sheets creds, SMTP outage, etc.) is visible after the fact instead of
silently vanishing.
#>
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "daily_report.log"
$python = Join-Path $root ".venv\Scripts\python.exe"

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logFile -Value "`n==== $stamp : starting daily report send ===="

Push-Location $root
try {
    & $python "main.py" "--send" *>> $logFile
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

$stamp2 = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
if ($exitCode -ne 0) {
    Add-Content -Path $logFile -Value "$stamp2 : FAILED (exit code $exitCode)"
    exit $exitCode
}
Add-Content -Path $logFile -Value "$stamp2 : sent OK"
