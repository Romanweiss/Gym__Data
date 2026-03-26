param(
    [switch]$Bootstrap
)

$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendPort = if ($env:BACKEND_HOST_PORT) { $env:BACKEND_HOST_PORT } else { 18080 }

Push-Location $projectRoot

try {
    if ($Bootstrap) {
        & (Join-Path $PSScriptRoot "check_ports.ps1")
        docker compose up -d --build
        docker compose --profile jobs run --rm ingestion
    }

    $endpoints = @(
        "http://localhost:$backendPort/api/health/live",
        "http://localhost:$backendPort/api/health/",
        "http://localhost:$backendPort/api/workouts/?limit=3",
        "http://localhost:$backendPort/api/exercises/?limit=3",
        "http://localhost:$backendPort/api/summary/"
    )

    foreach ($endpoint in $endpoints) {
        $response = Invoke-RestMethod -Uri $endpoint -TimeoutSec 20
        Write-Host "[ok] $endpoint"
        if ($endpoint -like "*summary/*") {
            Write-Host ($response.totals | ConvertTo-Json -Compress)
        }
    }
}
finally {
    Pop-Location
}
