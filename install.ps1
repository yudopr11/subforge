# SubForge Windows Installer / Uninstaller
# Usage:
#   Install:   irm https://raw.githubusercontent.com/yudopr11/subforge/master/install.ps1 | iex
#   Uninstall: & ([scriptblock]::Create((irm https://raw.githubusercontent.com/yudopr11/subforge/master/install.ps1))) --uninstall
#   Uninstall (keep data): ... --uninstall --keep-data

param(
    [switch]$Uninstall,
    [switch]$KeepData
)

$ErrorActionPreference = "Stop"

$AppName   = "subforge"
$Repo      = "yudopr11/subforge"
$InstallDir = Join-Path $env:LOCALAPPDATA "subforge\bin"
$ExePath   = Join-Path $InstallDir "$AppName.exe"
$DataDir   = Join-Path $env:LOCALAPPDATA "subforge"
$ConfigDir = Join-Path $env:APPDATA "subforge"

Write-Host "================================================================" -ForegroundColor Cyan
if ($Uninstall) {
    Write-Host "  SubForge -- Uninstaller" -ForegroundColor White
} else {
    Write-Host "  SubForge -- Local-First Subtitle Generator (Go)" -ForegroundColor White
}
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# ══════════════════════════════════════════════════════════════════════════════
# INSTALL
# ══════════════════════════════════════════════════════════════════════════════
if (-not $Uninstall) {

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    Write-Host "[*] Fetching latest release..." -ForegroundColor Yellow

    $DownloadUrl = $null
    try {
        $Release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" `
            -Headers @{ "User-Agent" = "subforge-installer" } -TimeoutSec 10
        $Asset = $Release.assets | Where-Object { $_.name -like "*windows*.exe" -or $_.name -eq "$AppName.exe" } | Select-Object -First 1
        if ($Asset) { $DownloadUrl = $Asset.browser_download_url }
    } catch {
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
        Write-Host "[OK] Downloaded binary from GitHub Releases." -ForegroundColor Green
    } catch {
        Write-Host "[i] Binary not found. Falling back to go install..." -ForegroundColor DarkGray
        if (Get-Command go -ErrorAction SilentlyContinue) {
            $env:GOBIN = $InstallDir
            go install "github.com/$Repo/cmd/subforge@latest"
            Write-Host "[OK] SubForge installed via go install." -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Could not download binary and 'go' is not installed." -ForegroundColor Red
            exit 1
        }
    } finally {
        if (Test-Path $TempFile) { Remove-Item -Path $TempFile -Force -ErrorAction SilentlyContinue }
    }

    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($UserPath -notlike "*$InstallDir*") {
        Write-Host "[*] Adding $InstallDir to user PATH..." -ForegroundColor Yellow
        [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
        $env:Path += ";$InstallDir"
    }

    Write-Host ""
    Write-Host "[OK] SubForge installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Open a new terminal and type:" -ForegroundColor White
    Write-Host "    subforge" -ForegroundColor Cyan
    Write-Host ""
}

# ══════════════════════════════════════════════════════════════════════════════
# UNINSTALL
# ══════════════════════════════════════════════════════════════════════════════
if ($Uninstall) {

    if (Test-Path $ExePath) {
        Write-Host "[*] Removing $ExePath..." -ForegroundColor Yellow
        Remove-Item -Path $ExePath -Force
        Write-Host "[OK] Removed binary." -ForegroundColor Green
    } else {
        Write-Host "[i] Binary not found at $ExePath, skipping." -ForegroundColor DarkGray
    }

    # Clean temp files
    Get-ChildItem $env:TEMP -Filter "subforge*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Cleaned temporary files." -ForegroundColor Green

    if ($KeepData) {
        Write-Host "[i] --keep-data set: skipping removal of data and config directories." -ForegroundColor DarkGray
    } else {
        if (Test-Path $DataDir) {
            Write-Host "[*] Removing application data ($DataDir)..." -ForegroundColor Yellow
            Remove-Item -Path $DataDir -Recurse -Force
            Write-Host "[OK] Removed $DataDir." -ForegroundColor Green
        }
        if (Test-Path $ConfigDir) {
            Write-Host "[*] Removing config ($ConfigDir)..." -ForegroundColor Yellow
            Remove-Item -Path $ConfigDir -Recurse -Force
            Write-Host "[OK] Removed $ConfigDir." -ForegroundColor Green
        }
    }

    # Remove from PATH
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($UserPath -like "*$InstallDir*") {
        $NewPath = ($UserPath -split ";" | Where-Object { $_ -ne $InstallDir }) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
        Write-Host "[OK] Removed $InstallDir from user PATH." -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "[OK] SubForge fully uninstalled." -ForegroundColor Green
    Write-Host ""
}
