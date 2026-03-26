param(
    [int[]]$Ports = @(18080, 55432, 18123, 19000)
)

$ErrorActionPreference = "Stop"

$busy = Get-NetTCPConnection -State Listen |
    Where-Object { $Ports -contains $_.LocalPort } |
    Sort-Object LocalPort, LocalAddress

if ($busy) {
    Write-Host "Busy ports detected:" -ForegroundColor Yellow
    $busy | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table -AutoSize
    exit 1
}

Write-Host "All requested Gym__Data ports are currently free." -ForegroundColor Green

