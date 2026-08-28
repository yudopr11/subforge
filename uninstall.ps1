#!/usr/bin/env pwsh
# SubForge Windows Uninstaller
# Usage: irm https://raw.githubusercontent.com/yudopr11/subforge/master/uninstall.ps1 | iex

param(
    [switch]$Purge = $false,
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"

$AppName = "subforge"
$InstallDir = Join-Path $env:LOCALAPPDATA "subforge\bin"
$SubforgeDir = Join-Path $env:LOCALAPPDATA "subforge"
$ExePath = Join-Path $InstallDir "$AppName.exe"

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  SubForge — Uninstaller" -ForegroundColor White
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. Remove standalone binary if present
if (Test-Path $ExePath) {
    Write-Host "▸ Removing SubForge binary: $ExePath..." -ForegroundColor Yellow
    Remove-Item -Path $ExePath -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Removed binary." -ForegroundColor Green
}

# 2. Check if installed via uv or pipx
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvList = uv tool list 2>&1
    if ($uvList -match "subforge") {
        Write-Host "▸ Uninstalling SubForge from uv tools..." -ForegroundColor Yellow
        uv tool uninstall subforge 2>&1 | Out-Null
        Write-Host "✓ Removed uv tool." -ForegroundColor Green
    }
}

if (Get-Command pipx -ErrorAction SilentlyContinue) {
    $pipxList = pipx list 2>&1
    if ($pipxList -match "package subforge") {
        Write-Host "▸ Uninstalling SubForge from pipx..." -ForegroundColor Yellow
        pipx uninstall subforge 2>&1 | Out-Null
        Write-Host "✓ Removed pipx package." -ForegroundColor Green
    }
}

# 3. Clean user PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -and $UserPath -like "*$InstallDir*") {
    Write-Host "▸ Removing $InstallDir from user PATH..." -ForegroundColor Yellow
    $Paths = $UserPath -split ";" | Where-Object { $_ -ne $InstallDir -and $_ -ne "" }
    $NewPath = $Paths -join ";"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "✓ Updated user PATH." -ForegroundColor Green
}

# 4. Optional Purge of AppData / Models / Config / Projects
if ($Purge) {
    $RemoveData = $true
} elseif ($Force) {
    $RemoveData = $false
} else {
    if (Test-Path $SubforgeDir) {
        $Answer = Read-Host "Do you want to delete models, cache, and configuration in $SubforgeDir? (y/N)"
        if ($Answer -match "^[Yy]") {
            $RemoveData = $true
        } else {
            $RemoveData = $false
        }
    } else {
        $RemoveData = $false
    }
}

if ($RemoveData -and (Test-Path $SubforgeDir)) {
    Write-Host "▸ Cleaning up application data and cache in $SubforgeDir..." -ForegroundColor Yellow
    Remove-Item -Path $SubforgeDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Removed application data." -ForegroundColor Green
}

# Also check ~/.config/subforge if present
$AltConfigDir = Join-Path $env:USERPROFILE ".config\subforge"
if ($RemoveData -and (Test-Path $AltConfigDir)) {
    Remove-Item -Path $AltConfigDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "✓ SubForge has been successfully uninstalled." -ForegroundColor Green
Write-Host ""
