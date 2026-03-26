param(
    [switch]$Bootstrap,
    [switch]$WithReconciliation
)

$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendPort = if ($env:BACKEND_HOST_PORT) { $env:BACKEND_HOST_PORT } else { 18080 }

function Assert-LastExitCode {
    param(
        [string]$Step
    )

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Push-Location $projectRoot

try {
    if ($Bootstrap) {
        & (Join-Path $PSScriptRoot "check_ports.ps1")
        docker compose up -d --build
        Assert-LastExitCode "docker compose up"
        docker compose --profile jobs run --rm ingestion
        Assert-LastExitCode "ingestion load-all"
    }

    if ($Bootstrap -or $WithReconciliation) {
        docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main reconcile
        Assert-LastExitCode "ingestion reconcile"
        Write-Host "[ok] reconciliation"
    }

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/health/live" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/health/live"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/health/" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/health/"

    $workoutsResponse = Invoke-RestMethod -Uri "http://localhost:$backendPort/api/workouts/?limit=3" -TimeoutSec 20
    Write-Host "[ok] /api/workouts/"

    $workoutId = [string]$workoutsResponse.items[0].workout_id
    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/workouts/$workoutId" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/workouts/$workoutId"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/workouts/$workoutId/summary" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/workouts/$workoutId/summary"

    $exercisesResponse = Invoke-RestMethod -Uri "http://localhost:$backendPort/api/exercises/?limit=3" -TimeoutSec 20
    Write-Host "[ok] /api/exercises/"

    @'
import json
import sys
import urllib.parse
import urllib.request

base_url = sys.argv[1]
with urllib.request.urlopen(base_url + "/api/exercises/?limit=1", timeout=20) as response:
    payload = json.load(response)
exercise_name = payload["items"][0]["exercise_name_canonical"]
endpoint = base_url + "/api/exercises/" + urllib.parse.quote(exercise_name, safe="") + "/progress"
with urllib.request.urlopen(endpoint, timeout=20) as response:
    json.load(response)
'@ | python - "http://localhost:$backendPort"
    Assert-LastExitCode "exercise progress smoke check"
    Write-Host "[ok] /api/exercises/{exercise_name_canonical}/progress"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/analytics/weekly-load?limit=4" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/analytics/weekly-load"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/analytics/cardio?limit=4" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/analytics/cardio"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/analytics/recovery?limit=4" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/analytics/recovery"

    $measurementsResponse = Invoke-RestMethod -Uri "http://localhost:$backendPort/api/measurements/?limit=2" -TimeoutSec 20
    Write-Host "[ok] /api/measurements/"

    $measurementSessionId = [string]$measurementsResponse.items[0].measurement_session_id
    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/measurements/$measurementSessionId" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/measurements/$measurementSessionId"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/measurements/latest" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/measurements/latest"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/measurements/progress?measurement_type=waist" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/measurements/progress"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/measurements/overdue" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/measurements/overdue"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/profile/current/overview" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/profile/current/overview"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/profile/current/timeline?limit=10" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/profile/current/timeline"

    Invoke-RestMethod -Uri "http://localhost:$backendPort/api/profile/current/progress-highlights" -TimeoutSec 20 | Out-Null
    Write-Host "[ok] /api/profile/current/progress-highlights"

    @'
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=20) as response:
    html = response.read().decode("utf-8")
if "Gym__Data Workspace" not in html or "Progress Workspace" not in html:
    raise SystemExit("UI shell marker was not found in the HTML response.")
'@ | python - "http://localhost:$backendPort/ui"
    Assert-LastExitCode "UI smoke check"
    Write-Host "[ok] /ui"

    $summaryResponse = Invoke-RestMethod -Uri "http://localhost:$backendPort/api/summary/" -TimeoutSec 20
    Write-Host "[ok] /api/summary/"
    Write-Host ($summaryResponse.totals | ConvertTo-Json -Compress)
}
finally {
    Pop-Location
}
