# SubForge Windows Complete Uninstaller
# Usage: irm https://raw.githubusercontent.com/yudopr11/subforge/master/uninstall.ps1 | iex

param(
    [switch]$KeepProjects = $false,
    [switch]$Force = $false
)

$ErrorActionPreference = "SilentlyContinue"

$AppName = "subforge"
$InstallDir = Join-Path $env:LOCALAPPDATA "subforge\bin"
$SubforgeDir = Join-Path $env:LOCALAPPDATA "subforge"
$ProjectsDir = Join-Path $SubforgeDir "projects"
$ExePath = Join-Path $InstallDir "$AppName.exe"
$AltConfigDir = Join-Path $env:USERPROFILE ".config\subforge"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  SubForge -- Complete Uninstaller" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Remove standalone executable
if (Test-Path $ExePath) {
    Write-Host "[*] Removing SubForge binary: $ExePath..." -ForegroundColor Yellow
    Remove-Item -Path $ExePath -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Removed executable." -ForegroundColor Green
}

# 2. Uninstall package manager installations (uv / pipx)
if (Get-Command uv -ErrorAction SilentlyContinue) {
    try {
        $uvOut = & uv tool list 2>$null
        if ($uvOut -and ($uvOut -match "subforge")) {
            Write-Host "[*] Uninstalling SubForge tool from uv..." -ForegroundColor Yellow
            & uv tool uninstall subforge 2>$null | Out-Null
            Write-Host "[OK] Uninstalled from uv." -ForegroundColor Green
        }
    } catch {
        # ignore error if uv tool list fails
    }
}

if (Get-Command pipx -ErrorAction SilentlyContinue) {
    try {
        $pipxOut = & pipx list 2>$null
        if ($pipxOut -and ($pipxOut -match "package subforge")) {
            Write-Host "[*] Uninstalling SubForge package from pipx..." -ForegroundColor Yellow
            & pipx uninstall subforge 2>$null | Out-Null
            Write-Host "[OK] Uninstalled from pipx." -ForegroundColor Green
        }
    } catch {
        # ignore error if pipx list fails
    }
}

# 3. Clean user PATH
try {
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($UserPath -and ($UserPath -like "*$InstallDir*")) {
        Write-Host "[*] Removing $InstallDir from user PATH..." -ForegroundColor Yellow
        $Paths = $UserPath -split ";" | Where-Object { $_ -and ($_ -ne $InstallDir) }
        $NewPath = $Paths -join ";"
        [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
        Write-Host "[OK] Cleaned user PATH environment variable." -ForegroundColor Green
    }
} catch {
    # ignore PATH errors
}

# 4. Clean temporary files & audio previews
Write-Host "[*] Cleaning temporary preview files and caches..." -ForegroundColor Yellow
try {
    Get-ChildItem -Path $env:TEMP -Filter "subforge*" -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
} catch {}
Write-Host "[OK] Cleaned temporary files." -ForegroundColor Green

# 5. Clean Application Data, Models, Binaries (whisper.cpp, ffmpeg), Config
if (Test-Path $SubforgeDir) {
    if ($KeepProjects -and (Test-Path $ProjectsDir)) {
        Write-Host "[*] Cleaning models, binaries, and configs (keeping projects)..." -ForegroundColor Yellow
        Get-ChildItem -Path $SubforgeDir -Exclude "projects" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Cleaned models, binaries, and configurations (projects preserved)." -ForegroundColor Green
    } else {
        Write-Host "[*] Removing all application data, models, binaries, and configurations..." -ForegroundColor Yellow
        Remove-Item -Path $SubforgeDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Removed $SubforgeDir." -ForegroundColor Green
    }
}

# 6. Clean alternative config directory (~/.config/subforge) if present
if (Test-Path $AltConfigDir) {
    Remove-Item -Path $AltConfigDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Removed $AltConfigDir." -ForegroundColor Green
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "[OK] SubForge, its dependencies, models, and paths are fully uninstalled!" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
