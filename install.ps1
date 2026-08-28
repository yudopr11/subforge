#!/usr/bin/env pwsh
# SubForge Windows One-Line Installer
# Usage: irm https://raw.githubusercontent.com/yudoppi/subforge/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$AppName = "subforge"
$Repo = "yudoppi/subforge"
$InstallDir = Join-Path $env:LOCALAPPDATA "subforge\bin"
$ExePath = Join-Path $InstallDir "$AppName.exe"

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  SubForge — Local-First Subtitle Generator" -ForegroundColor White
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. Create install directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# 2. Determine latest release or standalone binary download URL
Write-Host "▸ Fetching latest release information..." -ForegroundColor Yellow

$DownloadUrl = $null
try {
    $ReleaseApi = "https://api.github.com/repos/$Repo/releases/latest"
    $Release = Invoke-RestMethod -Uri $ReleaseApi -Headers @{ "User-Agent" = "subforge-installer" } -TimeoutSec 10
    $Asset = $Release.assets | Where-Object { $_.name -like "*windows*.zip" -or $_.name -like "*windows*.exe" -or $_.name -eq "$AppName.exe" } | Select-Object -First 1
    if ($Asset) {
        $DownloadUrl = $Asset.browser_download_url
    }
} catch {
    # Fallback to direct latest binary release URL
    $DownloadUrl = "https://github.com/$Repo/releases/latest/download/subforge-windows-x64.exe"
}

if (-not $DownloadUrl) {
    $DownloadUrl = "https://github.com/$Repo/releases/latest/download/subforge-windows-x64.exe"
}

Write-Host "▸ Downloading SubForge to $InstallDir..." -ForegroundColor Yellow

$TempFile = Join-Path $env:TEMP "subforge-setup-download.tmp"
try {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $TempFile -UseBasicParsing
    
    if ($DownloadUrl.EndsWith(".zip")) {
        Expand-Archive -Path $TempFile -DestinationPath $InstallDir -Force
    } else {
        Move-Item -Path $TempFile -Destination $ExePath -Force
    }
} catch {
    # If standalone binary not yet published on GitHub, offer uv/pipx bootstrap fallback
    Write-Host "ℹ Standalone binary not found. Bootstrapping via uv tool/pipx..." -ForegroundColor DarkGray
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv tool install "git+https://github.com/$Repo.git" --force
        Write-Host "✓ SubForge installed via uv tool." -ForegroundColor Green
        exit 0
    } elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
        pipx install "git+https://github.com/$Repo.git" --force
        Write-Host "✓ SubForge installed via pipx." -ForegroundColor Green
        exit 0
    } else {
        Write-Host "[ERROR] Could not download subforge binary: $_" -ForegroundColor Red
        exit 1
    }
} finally {
    if (Test-Path $TempFile) {
        Remove-Item -Path $TempFile -Force -ErrorAction SilentlyContinue
    }
}

# 3. Add to user PATH if not present
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    Write-Host "▸ Adding $InstallDir to user PATH..." -ForegroundColor Yellow
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
    $env:Path += ";$InstallDir"
}

Write-Host ""
Write-Host "✓ SubForge installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "  To get started, open a new terminal and type:" -ForegroundColor White
Write-Host "    subforge" -ForegroundColor Cyan
Write-Host ""
