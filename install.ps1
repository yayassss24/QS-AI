<#
.SYNOPSIS
  QS BOQ AI — One-click installer for Excel + Google Sheets
.DESCRIPTION
  Installs prerequisites, registers Excel add-in, creates shortcuts.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BackendDir = Join-Path $ScriptDir "backend"
$ManifestPath = Join-Path $ScriptDir "excel-addin" "manifest.xml"

Write-Host "=== QS BOQ AI Installer ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
try {
    $pyVer = python --version 2>&1
    Write-Host "[OK] Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Python tidak ditemukan. Install dari https://python.org" -ForegroundColor Red
    exit 1
}

# 2. Install Python deps
Write-Host "[...] Install Python dependencies..." -ForegroundColor Yellow
$reqFile = Join-Path $BackendDir "requirements.txt"
if (Test-Path $reqFile) {
    pip install -r $reqFile 2>&1 | Out-Null
    Write-Host "[OK] Python deps installed" -ForegroundColor Green
}

# 3. Check Node.js
try {
    $nodeVer = node --version 2>&1
    Write-Host "[OK] Node.js: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Node.js tidak ditemukan. Install dari https://nodejs.org" -ForegroundColor Red
    exit 1
}

# 4. Install 9router
try {
    $routerVer = npx 9router --version 2>&1
    Write-Host "[OK] 9router: $routerVer" -ForegroundColor Green
} catch {
    Write-Host "[...] Install 9router..." -ForegroundColor Yellow
    npm install -g 9router 2>&1 | Out-Null
    Write-Host "[OK] 9router installed" -ForegroundColor Green
}

# 5. Install office-addin-dev-settings for Excel sideload
try {
    $sideload = npx office-addin-dev-settings --version 2>&1
} catch {
    Write-Host "[...] Install office-addin-dev-settings..." -ForegroundColor Yellow
    npm install -g office-addin-dev-settings 2>&1 | Out-Null
}
Write-Host "[OK] office-addin-dev-settings ready" -ForegroundColor Green

# 6. Register Excel add-in via registry (so it appears in Insert > Add-ins)
$regPath = "HKCU:\Software\Microsoft\Office\16.0\Wef\Developer\"
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}
$addinName = "QS_BOQ_AI"
$regValue = Get-ItemProperty -Path $regPath -Name $addinName -ErrorAction SilentlyContinue
if (-not $regValue) {
    New-ItemProperty -Path $regPath -Name $addinName -Value $ManifestPath -PropertyType String -Force | Out-Null
    Write-Host "[OK] Excel add-in registered (registry)" -ForegroundColor Green
} else {
    Write-Host "[OK] Excel add-in already registered" -ForegroundColor Green
}

# 7. Create desktop shortcut for start.ps1
$startScript = Join-Path $ScriptDir "start.ps1"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "QS BOQ AI.lnk"
if (-not (Test-Path $shortcutPath)) {
    $wshell = New-Object -ComObject WScript.Shell
    $shortcut = $wshell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "powershell.exe"
    $shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$startScript`""
    $shortcut.WorkingDirectory = $ScriptDir
    $shortcut.Description = "QS BOQ AI — Start 9router + Backend + Excel"
    $shortcut.Save()
    Write-Host "[OK] Desktop shortcut created" -ForegroundColor Green
}

# 8. Create manifest URL shortcut (for URL-based install in Excel)
$manifestUrl = "http://localhost:8000/static/excel-addin/manifest.xml"
Write-Host ""
Write-Host "=== Excel Add-in Install ===" -ForegroundColor Cyan
Write-Host "1. Start the server: run 'QS BOQ AI' shortcut on desktop"
Write-Host "2. Open Excel -> Insert -> Get Add-ins -> From URL"
Write-Host "3. Paste: $manifestUrl"
Write-Host "4. Click Add"
Write-Host ""
Write-Host "=== Google Sheets ===" -ForegroundColor Cyan
Write-Host "Buka google-sheets-addin/ folder untuk petunjuk install di Google Sheets"
Write-Host ""
Write-Host "Installasi selesai!" -ForegroundColor Green
