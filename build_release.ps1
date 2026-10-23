$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================"
Write-Host " Litenova v3.0.2 Release Build"
Write-Host "========================================"
Write-Host ""

Set-Location $PSScriptRoot


# ============================================================
# VERIFY VIRTUAL ENVIRONMENT
# ============================================================

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "ERROR: .venv was not found."
    Write-Host ""
    Write-Host "Create it with:"
    Write-Host "python -m venv .venv"
    exit 1
}


# ============================================================
# VERIFY RELEASE FILES
# ============================================================

$RequiredFiles = @(
    "main.py",
    "Litenova.spec",
    "version_info.txt",
    "resources\icons\litenova.ico",
    "app\styles\dark.qss"
)

foreach ($File in $RequiredFiles) {

    if (-not (Test-Path $File)) {

        Write-Host "ERROR: Missing release file:"
        Write-Host $File

        exit 1
    }
}


# ============================================================
# COMPILE CHECK
# ============================================================

Write-Host "Checking Python source..."
Write-Host ""

& $Python -m compileall -q main.py app

if ($LASTEXITCODE -ne 0) {

    Write-Host ""
    Write-Host "ERROR: Python syntax check failed."

    exit 1
}

Write-Host "Python syntax check passed."


# ============================================================
# CLEAN OLD BUILD
# ============================================================

Write-Host ""
Write-Host "Removing old PyInstaller output..."

Get-Process Litenova `
    -ErrorAction SilentlyContinue |
    Stop-Process -Force `
    -ErrorAction SilentlyContinue

Remove-Item `
    -Recurse `
    -Force `
    ".\build" `
    -ErrorAction SilentlyContinue

Remove-Item `
    -Recurse `
    -Force `
    ".\dist" `
    -ErrorAction SilentlyContinue


# ============================================================
# BUILD
# ============================================================

Write-Host ""
Write-Host "Building Litenova v3.0.2..."
Write-Host ""

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    ".\Litenova.spec"

if ($LASTEXITCODE -ne 0) {

    Write-Host ""
    Write-Host "ERROR: PyInstaller build failed."

    exit 1
}


# ============================================================
# VERIFY EXE
# ============================================================

$Exe = Join-Path $PSScriptRoot "dist\Litenova.exe"

if (-not (Test-Path $Exe)) {

    Write-Host ""
    Write-Host "ERROR: dist\Litenova.exe was not created."

    exit 1
}


# ============================================================
# SHA256
# ============================================================

$Hash = Get-FileHash `
    $Exe `
    -Algorithm SHA256

$HashFile = Join-Path `
    $PSScriptRoot `
    "dist\Litenova.exe.sha256.txt"

"$($Hash.Hash)  Litenova.exe" |
    Set-Content `
        -Path $HashFile `
        -Encoding ascii


# ============================================================
# RESULT
# ============================================================

$Info = Get-Item $Exe

Write-Host ""
Write-Host "========================================"
Write-Host " RELEASE BUILD COMPLETE"
Write-Host "========================================"
Write-Host ""

Write-Host "EXE:"
Write-Host $Info.FullName

Write-Host ""

Write-Host "Size:"
Write-Host $Info.Length

Write-Host ""

Write-Host "Created:"
Write-Host $Info.LastWriteTime

Write-Host ""

Write-Host "SHA256:"
Write-Host $Hash.Hash

Write-Host ""

Write-Host "Checksum file:"
Write-Host $HashFile

Write-Host ""
Write-Host "Test this exact EXE before uploading it."
Write-Host ""