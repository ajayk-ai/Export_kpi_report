<#
Registers the "ExportKPIDailyReport" Windows scheduled task: runs
run_daily_report.ps1 once a day at 16:00 (4:00 PM) India Standard Time (IST),
as SYSTEM (so it fires even if nobody is logged in).

Run ONCE, from an elevated (Administrator) PowerShell:
    powershell -ExecutionPolicy Bypass -File deploy\register_task.ps1

Safe to re-run any time - it replaces the existing task, e.g. after moving
the project folder or changing the schedule below.
#>
$ErrorActionPreference = "Stop"

# Daily send time, in IST - change these two to move the schedule.
$reportHour = 16
$reportMinute = 0

$taskName = "ExportKPIDailyReport"
$root = Split-Path -Parent $PSScriptRoot
$wrapper = Join-Path $root "deploy\run_daily_report.ps1"

if (-not (Test-Path (Join-Path $root ".venv\Scripts\python.exe"))) {
    throw "No .venv found at $root\.venv - run 'uv sync' first."
}

# The task's daily trigger fires at a fixed local wall-clock time, so convert
# the IST send time to whatever the server's own timezone is (a no-op if the
# server is already set to India Standard Time).
$istZone = [System.TimeZoneInfo]::FindSystemTimeZoneById("India Standard Time")
$localZone = [System.TimeZoneInfo]::Local
$todayAtIst = [System.DateTime]::SpecifyKind((Get-Date -Hour $reportHour -Minute $reportMinute -Second 0), [System.DateTimeKind]::Unspecified)
$utcInstant = [System.TimeZoneInfo]::ConvertTimeToUtc($todayAtIst, $istZone)
$localTime = [System.TimeZoneInfo]::ConvertTimeFromUtc($utcInstant, $localZone)
$istLabel = $todayAtIst.ToString("HH:mm")

Write-Host "Server timezone : $($localZone.Id)"
Write-Host "$istLabel IST is    : $($localTime.ToString('HH:mm')) in the server's local time"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapper`""
$trigger = New-ScheduledTaskTrigger -Daily -At $localTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -DontStopOnIdleEnd
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Sends the Export KPI report email daily at $istLabel IST." `
    -Force | Out-Null

Write-Host "`nRegistered '$taskName': fires daily at $($localTime.ToString('HH:mm')) server time (= $istLabel IST)."
Write-Host "Test it right now with:   Start-ScheduledTask -TaskName '$taskName'"
Write-Host "Then check:               $root\logs\daily_report.log"
Write-Host "Remove it with:           Unregister-ScheduledTask -TaskName '$taskName'"
