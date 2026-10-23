$ErrorActionPreference = "Stop"


# ============================================================
# LITENOVA RELEASE PREPARATION
# ============================================================
#
# This script:
#
# 1. Checks that it is running inside the Litenova project.
# 2. Makes sure local user data is NOT included in Git.
# 3. Removes previously tracked data from Git tracking only.
# 4. Leaves your actual local Library untouched.
# 5. Checks Python source for syntax errors.
# 6. Deletes old PyInstaller build output.
# 7. Builds a fresh Litenova.exe.
# 8. Creates a SHA256 checksum.
# 9. Creates a clean release folder.
# 10. Verifies that only release-safe files are included.
#
# IMPORTANT:
#
# This script does NOT delete:
#
# - Your C:\Projects\Litenova\data folder
# - Your imported EPUB files
# - Your imported CBZ files
# - Your development database
# - Your %LOCALAPPDATA%\Litenova data
#
# ============================================================


$ProjectRoot = $PSScriptRoot

Set-Location $ProjectRoot


Write-Host ""
Write-Host "============================================================"
Write-Host " Litenova v3.0.3 Clean Release Preparation"
Write-Host "============================================================"
Write-Host ""


# ============================================================
# PROJECT CHECK
# ============================================================

$MainFile = Join-Path $ProjectRoot "main.py"

if (-not (Test-Path $MainFile)) {

    Write-Host "ERROR:"
    Write-Host "main.py was not found."
    Write-Host ""
    Write-Host "Save prepare_release.ps1 inside:"
    Write-Host "C:\Projects\Litenova"
    Write-Host ""

    exit 1
}


# ============================================================
# VIRTUAL ENVIRONMENT
# ============================================================

$Python = Join-Path `
    $ProjectRoot `
    ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {

    Write-Host "ERROR:"
    Write-Host "The Litenova virtual environment was not found."
    Write-Host ""
    Write-Host "Expected:"
    Write-Host $Python
    Write-Host ""

    exit 1
}


# ============================================================
# REQUIRED RELEASE FILES
# ============================================================

$RequiredFiles = @(

    "main.py",
    "Litenova.spec",
    "version_info.txt",
    ".gitignore",
    "resources\icons\litenova.ico",
    "app\styles\dark.qss"

)


foreach ($File in $RequiredFiles) {

    $FullPath = Join-Path `
        $ProjectRoot `
        $File

    if (-not (Test-Path $FullPath)) {

        Write-Host "ERROR:"
        Write-Host "Missing required release file:"
        Write-Host $FullPath
        Write-Host ""

        exit 1
    }
}


# ============================================================
# VERIFY GIT
# ============================================================

Write-Host "Checking Git repository..."
Write-Host ""


$GitFolder = Join-Path `
    $ProjectRoot `
    ".git"

if (-not (Test-Path $GitFolder)) {

    Write-Host "WARNING:"
    Write-Host "This folder does not currently contain a .git repository."
    Write-Host ""
    Write-Host "The EXE can still be built."
    Write-Host "Git cleanup will be skipped."
    Write-Host ""

    $GitAvailable = $false

}
else {

    $GitAvailable = $true

}


# ============================================================
# REMOVE LOCAL DATA FROM GIT TRACKING
# ============================================================

if ($GitAvailable) {

    Write-Host "Removing private Library data from Git tracking..."
    Write-Host ""
    Write-Host "Your actual local files will NOT be deleted."
    Write-Host ""


    # --------------------------------------------------------
    # DATA DIRECTORY
    # --------------------------------------------------------

    & git rm `
        -r `
        --cached `
        --ignore-unmatch `
        "data" 2>$null


    # --------------------------------------------------------
    # FIND ACCIDENTALLY TRACKED PRIVATE FILE TYPES
    # --------------------------------------------------------

    $TrackedFiles = @(
        & git ls-files
    )


    $PrivatePatterns = @(

        "*.db",
        "*.db-journal",
        "*.db-wal",
        "*.db-shm",
        "*.epub",
        "*.cbz"

    )


    foreach ($TrackedFile in $TrackedFiles) {

        $ShouldRemove = $false


        foreach ($Pattern in $PrivatePatterns) {

            if ($TrackedFile -like $Pattern) {

                $ShouldRemove = $true

                break
            }
        }


        if ($ShouldRemove) {

            Write-Host "Removing from Git tracking:"
            Write-Host "  $TrackedFile"

            & git rm `
                --cached `
                --ignore-unmatch `
                "--" `
                "$TrackedFile" 2>$null
        }
    }


    Write-Host ""
    Write-Host "Git private-data cleanup finished."
    Write-Host ""
}


# ============================================================
# VERIFY DATA IS NOT TRACKED
# ============================================================

if ($GitAvailable) {

    Write-Host "Verifying private files are not tracked..."
    Write-Host ""


    $StillTracked = @(
        & git ls-files |
        Where-Object {

            $_ -match '^data/' -or
            $_ -match '\.db$' -or
            $_ -match '\.db-journal$' -or
            $_ -match '\.db-wal$' -or
            $_ -match '\.db-shm$' -or
            $_ -match '\.epub$' -or
            $_ -match '\.cbz$'

        }
    )


    if ($StillTracked.Count -gt 0) {

        Write-Host "ERROR:"
        Write-Host "Private user files are still tracked by Git:"
        Write-Host ""

        foreach ($Item in $StillTracked) {

            Write-Host "  $Item"
        }

        Write-Host ""
        Write-Host "Release preparation stopped."
        Write-Host ""

        exit 1
    }


    Write-Host "PASS:"
    Write-Host "No Library databases, EPUBs or CBZ files are tracked."
    Write-Host ""
}


# ============================================================
# VERIFY SPEC DOES NOT PACKAGE DATA
# ============================================================

Write-Host "Checking Litenova.spec..."
Write-Host ""


$SpecPath = Join-Path `
    $ProjectRoot `
    "Litenova.spec"


$SpecContent = Get-Content `
    $SpecPath `
    -Raw


$BadSpecPatterns = @(

    "'data'",
    '"data"',
    "data\*",
    "data/*"

)


foreach ($Pattern in $BadSpecPatterns) {

    if ($SpecContent -like "*$Pattern*") {

        Write-Host "ERROR:"
        Write-Host "Litenova.spec appears to package the data folder."
        Write-Host ""
        Write-Host "Detected:"
        Write-Host $Pattern
        Write-Host ""
        Write-Host "Remove the data directory from the spec before releasing."
        Write-Host ""

        exit 1
    }
}


Write-Host "PASS:"
Write-Host "Litenova.spec does not package the development data folder."
Write-Host ""


# ============================================================
# PYTHON SYNTAX CHECK
# ============================================================

Write-Host "Checking Python source..."
Write-Host ""


& $Python `
    -m `
    compileall `
    -q `
    "main.py" `
    "app"


if ($LASTEXITCODE -ne 0) {

    Write-Host ""
    Write-Host "ERROR:"
    Write-Host "Python syntax checking failed."
    Write-Host ""
    Write-Host "Fix the Python errors before building a release."
    Write-Host ""

    exit 1
}


Write-Host "PASS:"
Write-Host "Python syntax checking completed successfully."
Write-Host ""


# ============================================================
# STOP OLD LITENOVA PROCESS
# ============================================================

Write-Host "Stopping an old Litenova.exe if it is still running..."
Write-Host ""


Get-Process `
    "Litenova" `
    -ErrorAction SilentlyContinue |
    Stop-Process `
        -Force `
        -ErrorAction SilentlyContinue


# ============================================================
# CLEAN OLD BUILD
# ============================================================

Write-Host "Removing old build output..."
Write-Host ""


$BuildDirectory = Join-Path `
    $ProjectRoot `
    "build"


$DistDirectory = Join-Path `
    $ProjectRoot `
    "dist"


$ReleaseDirectory = Join-Path `
    $ProjectRoot `
    "release"


Remove-Item `
    -Recurse `
    -Force `
    $BuildDirectory `
    -ErrorAction SilentlyContinue


Remove-Item `
    -Recurse `
    -Force `
    $DistDirectory `
    -ErrorAction SilentlyContinue


Remove-Item `
    -Recurse `
    -Force `
    $ReleaseDirectory `
    -ErrorAction SilentlyContinue


# ============================================================
# BUILD
# ============================================================

Write-Host "============================================================"
Write-Host " Building Litenova.exe"
Write-Host "============================================================"
Write-Host ""


& $Python `
    -m `
    PyInstaller `
    --noconfirm `
    --clean `
    ".\Litenova.spec"


if ($LASTEXITCODE -ne 0) {

    Write-Host ""
    Write-Host "ERROR:"
    Write-Host "PyInstaller failed."
    Write-Host ""

    exit 1
}


# ============================================================
# VERIFY EXE
# ============================================================

$ExePath = Join-Path `
    $DistDirectory `
    "Litenova.exe"


if (-not (Test-Path $ExePath)) {

    Write-Host ""
    Write-Host "ERROR:"
    Write-Host "PyInstaller completed but Litenova.exe was not found."
    Write-Host ""
    Write-Host "Expected:"
    Write-Host $ExePath
    Write-Host ""

    exit 1
}


# ============================================================
# CREATE SHA256 CHECKSUM
# ============================================================

Write-Host ""
Write-Host "Creating SHA256 checksum..."
Write-Host ""


$Hash = Get-FileHash `
    $ExePath `
    -Algorithm SHA256


$ChecksumPath = Join-Path `
    $DistDirectory `
    "Litenova.exe.sha256.txt"


"$($Hash.Hash)  Litenova.exe" |
    Set-Content `
        -Path $ChecksumPath `
        -Encoding ascii


# ============================================================
# CREATE CLEAN RELEASE DIRECTORY
# ============================================================

Write-Host "Creating clean release folder..."
Write-Host ""


New-Item `
    -ItemType Directory `
    -Path $ReleaseDirectory `
    -Force |
    Out-Null


$ReleaseExe = Join-Path `
    $ReleaseDirectory `
    "Litenova.exe"


$ReleaseChecksum = Join-Path `
    $ReleaseDirectory `
    "Litenova.exe.sha256.txt"


Copy-Item `
    $ExePath `
    $ReleaseExe `
    -Force


Copy-Item `
    $ChecksumPath `
    $ReleaseChecksum `
    -Force


# ============================================================
# RELEASE FOLDER SAFETY CHECK
# ============================================================

Write-Host "Checking release folder contents..."
Write-Host ""


$AllowedFiles = @(

    "Litenova.exe",
    "Litenova.exe.sha256.txt"

)


$ReleaseFiles = @(
    Get-ChildItem `
        $ReleaseDirectory `
        -File
)


foreach ($File in $ReleaseFiles) {

    if ($AllowedFiles -notcontains $File.Name) {

        Write-Host "ERROR:"
        Write-Host "Unexpected file inside the release folder:"
        Write-Host $File.FullName
        Write-Host ""

        exit 1
    }
}


$DangerousReleaseFiles = @(
    Get-ChildItem `
        $ReleaseDirectory `
        -Recurse `
        -File |
    Where-Object {

        $_.Extension -in @(

            ".db",
            ".epub",
            ".cbz",
            ".zip"

        )

    }
)


if ($DangerousReleaseFiles.Count -gt 0) {

    Write-Host "ERROR:"
    Write-Host "Private application data was found in the release folder."
    Write-Host ""

    foreach ($File in $DangerousReleaseFiles) {

        Write-Host $File.FullName
    }

    exit 1
}


# ============================================================
# EXE DETAILS
# ============================================================

$ExeInfo = Get-Item `
    $ReleaseExe


$ExeSizeMB = [Math]::Round(
    $ExeInfo.Length / 1MB,
    2
)


# ============================================================
# RESULT
# ============================================================

Write-Host ""
Write-Host "============================================================"
Write-Host " LITENOVA v3.0.3 RELEASE IS READY"
Write-Host "============================================================"
Write-Host ""

Write-Host "Release folder:"
Write-Host $ReleaseDirectory
Write-Host ""

Write-Host "EXE:"
Write-Host $ReleaseExe
Write-Host ""

Write-Host "EXE size:"
Write-Host "$ExeSizeMB MB"
Write-Host ""

Write-Host "SHA256:"
Write-Host $Hash.Hash
Write-Host ""

Write-Host "Checksum:"
Write-Host $ReleaseChecksum
Write-Host ""

Write-Host "Your local Library was NOT deleted."
Write-Host ""

Write-Host "Upload ONLY these GitHub Release assets:"
Write-Host ""
Write-Host "  Litenova.exe"
Write-Host "  Litenova.exe.sha256.txt"
Write-Host ""

Write-Host "Do NOT upload:"
Write-Host ""
Write-Host "  data\"
Write-Host "  *.db"
Write-Host "  *.epub"
Write-Host "  *.cbz"
Write-Host "  backup ZIPs"
Write-Host ""

Write-Host "============================================================"
Write-Host ""


# ============================================================
# SHOW GIT STATUS
# ============================================================

if ($GitAvailable) {

    Write-Host "Git changes waiting to be committed:"
    Write-Host ""

    & git status `
        --short

    Write-Host ""
    Write-Host "If the changes look correct, commit them before creating v3.0.3."
    Write-Host ""
}


exit 0