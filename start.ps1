<#
.SYNOPSIS
  Start QS BOQ AI — 9router + Backend + Excel
.DESCRIPTION
  Launches 9router proxy, backend API server, and opens Excel.
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BackendDir = Join-Path $ScriptDir "backend"

Write-Host "=== QS BOQ AI Starter ===" -ForegroundColor Cyan
Write-Host ""

# Start 9router (if not already running)
$routerProc = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "9router" }
if (-not $routerProc) {
    Write-Host "[...] Starting 9router..." -ForegroundColor Yellow
    $routerJob = Start-Job -ScriptBlock { npx 9router }
    Start-Sleep -Seconds 3
    Write-Host "[OK] 9router running at http://localhost:20128" -ForegroundColor Green
} else {
    Write-Host "[OK] 9router already running" -ForegroundColor Green
}

# Start backend
$backendProc = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "uvicorn" }
if (-not $backendProc) {
    Write-Host "[...] Starting backend server..." -ForegroundColor Yellow
    $backendJob = Start-Job -ScriptBlock {
        param($dir)
        Set-Location $dir
        python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    } -ArgumentList $BackendDir
    Start-Sleep -Seconds 3
    Write-Host "[OK] Backend running at http://localhost:8000" -ForegroundColor Green
    Write-Host "[OK] API Docs at http://localhost:8000/docs" -ForegroundColor Green
} else {
    Write-Host "[OK] Backend already running" -ForegroundColor Green
}

# Open Excel
try {
    $excel = Start-Process "excel" -PassThru
    Write-Host "[OK] Excel opened" -ForegroundColor Green
} catch {
    Write-Host "[!] Could not open Excel. Open manually." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Add-in Install ===" -ForegroundColor Cyan
Write-Host "Excel: Insert -> Get Add-ins -> From URL"
Write-Host "URL:  http://localhost:8000/static/excel-addin/manifest.xml"
Write-Host ""
Write-Host "Press Ctrl+C to stop servers" -ForegroundColor Gray

# Keep running until Ctrl+C
while ($true) {
    Start-Sleep -Seconds 10
}
