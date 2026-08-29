# SubForge Windows One-Line Installer
# Usage: irm https://raw.githubusercontent.com/yudopr11/subforge/master/install.ps1 | iex

$ErrorActionPreference = "Stop"

$AppName = "subforge"
$Repo = "yudopr11/subforge"
$InstallDir = Join-Path $env:LOCALAPPDATA "subforge\bin"
$ExePath = Join-Path $InstallDir "$AppName.exe"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  SubForge -- Local-First Subtitle Generator (Go)" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Create install directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# 2. Determine latest release download URL
Write-Host "[*] Fetching latest release information..." -ForegroundColor Yellow

$DownloadUrl = $null
try {
    $ReleaseApi = "https://api.github.com/repos/$Repo/releases/latest"
    $Release = Invoke-RestMethod -Uri $ReleaseApi -Headers @{ "User-Agent" = "subforge-installer" } -TimeoutSec 10
    $Asset = $Release.assets | Where-Object { $_.name -like "*windows*.exe" -or $_.name -eq "$AppName.exe" } | Select-Object -First 1
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

Write-Host "[*] Downloading SubForge to $InstallDir..." -ForegroundColor Yellow

$TempFile = Join-Path $env:TEMP "subforge-setup-download.tmp"
try {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $TempFile -UseBasicParsing
    Move-Item -Path $TempFile -Destination $ExePath -Force
} catch {
    Write-Host "[i] Standalone binary not found. Trying go install..." -ForegroundColor DarkGray
    if (Get-Command go -ErrorAction SilentlyContinue) {
        $env:GOBIN = $InstallDir
        go install "github.com/$Repo/cmd/subforge@latest"
        Write-Host "[OK] SubForge installed via go install." -ForegroundColor Green
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
    Write-Host "[*] Adding $InstallDir to user PATH..." -ForegroundColor Yellow
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
    $env:Path += ";$InstallDir"
}

Write-Host ""
Write-Host "[OK] SubForge installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "  To get started, open a new terminal and type:" -ForegroundColor White
Write-Host "    subforge" -ForegroundColor Cyan
Write-Host ""
