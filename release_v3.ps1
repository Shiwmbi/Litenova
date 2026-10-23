$ErrorActionPreference = "Stop"


# ============================================================
# LITENOVA v3.0.1 RELEASE BUILDER
# ============================================================


function Fail {
    param(
        [string]$Message
    )

    Write-Host ""
    Write-Host "============================================================"
    Write-Host " RELEASE STOPPED"
    Write-Host "============================================================"
    Write-Host ""

    Write-Host $Message -ForegroundColor Red

    Write-Host ""

    exit 1
}


function Step {
    param(
        [string]$Message
    )

    Write-Host ""
    Write-Host "------------------------------------------------------------"
    Write-Host $Message
    Write-Host "------------------------------------------------------------"
    Write-Host ""
}


# ============================================================
# PATHS
# ============================================================

$ProjectRoot = $PSScriptRoot

Set-Location $ProjectRoot


$Python = Join-Path `
    $ProjectRoot `
    ".venv\Scripts\python.exe"


$MainFile = Join-Path `
    $ProjectRoot `
    "main.py"


$SpecFile = Join-Path `
    $ProjectRoot `
    "Litenova.spec"


$VersionFile = Join-Path `
    $ProjectRoot `
    "version_info.txt"


$GitIgnoreFile = Join-Path `
    $ProjectRoot `
    ".gitignore"


$IconFile = Join-Path `
    $ProjectRoot `
    "resources\icons\litenova.ico"


$ThemeFile = Join-Path `
    $ProjectRoot `
    "app\styles\dark.qss"


$GitDirectory = Join-Path `
    $ProjectRoot `
    ".git"


$BuildDirectory = Join-Path `
    $ProjectRoot `
    "build"


$DistDirectory = Join-Path `
    $ProjectRoot `
    "dist"


$ReleaseDirectory = Join-Path `
    $ProjectRoot `
    "release"


$BuiltExe = Join-Path `
    $DistDirectory `
    "Litenova.exe"


$ReleaseExe = Join-Path `
    $ReleaseDirectory `
    "Litenova.exe"


$ReleaseChecksum = Join-Path `
    $ReleaseDirectory `
    "Litenova.exe.sha256.txt"


# ============================================================
# HEADER
# ============================================================

Write-Host ""
Write-Host "============================================================"
Write-Host " LITENOVA v3.0.1 CLEAN GITHUB RELEASE"
Write-Host "============================================================"
Write-Host ""

Write-Host "Project:"
Write-Host $ProjectRoot
Write-Host ""


# ============================================================
# 1. VERIFY PROJECT
# ============================================================

Step "1 / 9 - Checking project files"


$RequiredFiles = @(
    $MainFile,
    $SpecFile,
    $VersionFile,
    $GitIgnoreFile,
    $IconFile,
    $ThemeFile
)


foreach ($File in $RequiredFiles) {

    if (-not (Test-Path -LiteralPath $File)) {

        Fail "Required file is missing: $File"
    }
}


if (-not (Test-Path -LiteralPath $Python)) {

    Fail "Virtual environment Python was not found: $Python"
}


Write-Host "PASS"
Write-Host "Required files exist."


# ============================================================
# 2. CHECK VERSION
# ============================================================

Step "2 / 9 - Checking version 3.0.1"


$VersionText = Get-Content `
    -LiteralPath $VersionFile `
    -Raw


if ($VersionText -notmatch '3\.0\.1') {

    Fail "version_info.txt does not contain version 3.0.1."
}


Write-Host "PASS"
Write-Host "version_info.txt contains 3.0.1."


# ============================================================
# 3. CHECK PRIVATE DATA IN CURRENT GIT TRACKING
# ============================================================

Step "3 / 9 - Checking Git for private Library data"


$GitCommand = Get-Command `
    git `
    -ErrorAction SilentlyContinue


$GitAvailable = $false


if ($null -ne $GitCommand) {

    if (Test-Path -LiteralPath $GitDirectory) {

        $GitAvailable = $true
    }
}


if ($GitAvailable) {

    Write-Host "Git repository detected."
    Write-Host ""

    $TrackedFiles = @(
        & git ls-files
    )


    if ($LASTEXITCODE -ne 0) {

        Fail "Could not read Git tracked files."
    }


    $PrivateTracked = @()


    foreach ($TrackedFile in $TrackedFiles) {

        if ($TrackedFile -match '(?i)^data/') {

            $PrivateTracked += $TrackedFile

            continue
        }


        if (
            $TrackedFile -match '(?i)\.(db|db-journal|db-wal|db-shm|epub|cbz)$'
        ) {

            $PrivateTracked += $TrackedFile
        }
    }


    if ($PrivateTracked.Count -gt 0) {

        Write-Host ""
        Write-Host "Private files are still tracked:"
        Write-Host ""


        foreach ($PrivateFile in $PrivateTracked) {

            Write-Host $PrivateFile
        }


        Fail "Private files are tracked. Review the list and remove them from Git tracking manually; local files have not been changed."
    }


    Write-Host ""
    Write-Host "PASS"
    Write-Host "No current private Library files are tracked."
}
else {

    Write-Host "Git repository not detected."
    Write-Host "Git audit skipped."
}


# ============================================================
# 4. CHECK PYTHON SOURCE
# ============================================================

Step "4 / 9 - Checking Python source"


& $Python `
    -m `
    compileall `
    -q `
    "main.py" `
    "app"


if ($LASTEXITCODE -ne 0) {

    Fail "Python syntax checking failed."
}


Write-Host "PASS"
Write-Host "Python syntax check succeeded."


# ============================================================
# 5. STOP OLD LITENOVA
# ============================================================

Step "5 / 9 - Closing running Litenova"


Get-Process `
    -Name "Litenova" `
    -ErrorAction SilentlyContinue |
    Stop-Process `
        -Force `
        -ErrorAction SilentlyContinue


Write-Host "PASS"
Write-Host "Ready to build."


# ============================================================
# 6. CLEAN OLD BUILD
# ============================================================

Step "6 / 9 - Removing old build output"


if (Test-Path -LiteralPath $BuildDirectory) {

    Remove-Item `
        -LiteralPath $BuildDirectory `
        -Recurse `
        -Force
}


if (Test-Path -LiteralPath $DistDirectory) {

    Remove-Item `
        -LiteralPath $DistDirectory `
        -Recurse `
        -Force
}


if (Test-Path -LiteralPath $ReleaseDirectory) {

    Remove-Item `
        -LiteralPath $ReleaseDirectory `
        -Recurse `
        -Force
}


Write-Host "PASS"
Write-Host "Old build files removed."


# ============================================================
# 7. BUILD
# ============================================================

Step "7 / 9 - Building Litenova v3.0.1"


& $Python `
    -m `
    PyInstaller `
    --noconfirm `
    --clean `
    ".\Litenova.spec"


if ($LASTEXITCODE -ne 0) {

    Fail "PyInstaller failed."
}


if (-not (Test-Path -LiteralPath $BuiltExe)) {

    Fail "Litenova.exe was not created."
}


Write-Host ""
Write-Host "PASS"
Write-Host "Litenova.exe was created."


# ============================================================
# 8. VERIFY VERSION
# ============================================================

Step "8 / 9 - Verifying built EXE"


$BuiltExeItem = Get-Item `
    -LiteralPath $BuiltExe


$FileVersion = $BuiltExeItem.VersionInfo.FileVersion

$ProductVersion = $BuiltExeItem.VersionInfo.ProductVersion


Write-Host "FileVersion:"
Write-Host $FileVersion
Write-Host ""

Write-Host "ProductVersion:"
Write-Host $ProductVersion
Write-Host ""


if ($FileVersion -notlike "3.0.1*") {

    Fail "EXE FileVersion is not 3.0.1."
}


if ($ProductVersion -notlike "3.0.1*") {

    Fail "EXE ProductVersion is not 3.0.1."
}


Write-Host "PASS"
Write-Host "EXE version is 3.0.1."


# ============================================================
# 9. CREATE RELEASE FOLDER
# ============================================================

Step "9 / 9 - Creating clean GitHub release"


New-Item `
    -ItemType Directory `
    -Path $ReleaseDirectory `
    -Force |
    Out-Null


Copy-Item `
    -LiteralPath $BuiltExe `
    -Destination $ReleaseExe `
    -Force


# ============================================================
# CHECKSUM
# ============================================================

$Hash = Get-FileHash `
    -LiteralPath $ReleaseExe `
    -Algorithm SHA256


$ChecksumText = "$($Hash.Hash)  Litenova.exe"


Set-Content `
    -LiteralPath $ReleaseChecksum `
    -Value $ChecksumText `
    -Encoding Ascii


# ============================================================
# VERIFY RELEASE CONTENTS
# ============================================================

$ReleaseFiles = @(
    Get-ChildItem `
        -LiteralPath $ReleaseDirectory `
        -File
)


if ($ReleaseFiles.Count -ne 2) {

    Fail "Release folder does not contain exactly two files."
}


$AllowedNames = @(
    "Litenova.exe",
    "Litenova.exe.sha256.txt"
)


foreach ($File in $ReleaseFiles) {

    if ($AllowedNames -notcontains $File.Name) {

        Fail "Unexpected release file: $($File.Name)"
    }
}


# ============================================================
# FINAL INFO
# ============================================================

$FinalExe = Get-Item `
    -LiteralPath $ReleaseExe


$SizeMB = [Math]::Round(
    ($FinalExe.Length / 1MB),
    2
)


Write-Host ""
Write-Host "============================================================"
Write-Host " LITENOVA v3.0.1 IS READY FOR GITHUB"
Write-Host "============================================================"
Write-Host ""

Write-Host "Release folder:"
Write-Host $ReleaseDirectory
Write-Host ""

Write-Host "Files:"
Write-Host "  Litenova.exe"
Write-Host "  Litenova.exe.sha256.txt"
Write-Host ""

Write-Host "EXE size:"
Write-Host "$SizeMB MB"
Write-Host ""

Write-Host "FileVersion:"
Write-Host $FileVersion
Write-Host ""

Write-Host "ProductVersion:"
Write-Host $ProductVersion
Write-Host ""

Write-Host "SHA256:"
Write-Host $Hash.Hash
Write-Host ""

Write-Host "Your personal Library was not included."
Write-Host ""


# ============================================================
# GIT STATUS
# ============================================================

if ($GitAvailable) {

    Write-Host "============================================================"
    Write-Host " GIT STATUS"
    Write-Host "============================================================"
    Write-Host ""

    & git status --short

    Write-Host ""
}


Write-Host "============================================================"
Write-Host " RELEASE BUILD COMPLETE"
Write-Host "============================================================"
Write-Host ""

exit 0