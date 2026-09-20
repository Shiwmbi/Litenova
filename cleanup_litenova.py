"""
LITENOVA PROJECT CLEANUP

This script performs a conservative cleanup of the
Litenova Python project.

Features:
    1. Finds unused Python imports.
    2. Removes unused imports when requested.
    3. Removes generated Python cache files.
    4. Creates backups before changing source code.
    5. Checks Python syntax after cleanup.
    6. Restores source files if the cleanup fails.

Protected:
    - Imported EPUB and CBZ books
    - Application database
    - Book covers
    - Resource icons
    - Virtual environment
    - Git repository
    - Application settings
    - Existing application functionality

Usage:

    Preview cleanup:

        python cleanup_litenova.py

    Apply cleanup:

        python cleanup_litenova.py --apply
"""

import argparse
import shutil
import subprocess
import sys

from datetime import datetime
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

APP_FOLDER = PROJECT_ROOT / "app"

BACKUP_ROOT = (
    PROJECT_ROOT.parent
    / "Litenova_cleanup_backups"
)


# ============================================================
# PROTECTED DIRECTORIES
# ============================================================

PROTECTED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "data",
    "resources",
    "build",
    "dist",
    "node_modules",
    "Litenova_cleanup_backups",
}


# ============================================================
# CHECK RUFF
# ============================================================

def ruff_available():

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "--version",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


# ============================================================
# FIND PYTHON SOURCE FILES
# ============================================================

def get_python_files():

    if not APP_FOLDER.is_dir():

        raise RuntimeError(
            "Cannot find the app folder. "
            "Place this script beside main.py."
        )

    python_files = []

    for path in APP_FOLDER.rglob("*.py"):

        if any(
            part in PROTECTED_DIRECTORIES
            for part in path.relative_to(
                PROJECT_ROOT
            ).parts
        ):

            continue

        # Package initialization files can intentionally
        # expose imports to other Python modules.
        #
        # Do not automatically remove imports from them.

        if path.name == "__init__.py":

            continue

        python_files.append(path)

    return sorted(python_files)


# ============================================================
# FIND GENERATED PYTHON CACHE FOLDERS
# ============================================================

def get_cache_folders():

    cache_folders = []

    # Only inspect our own application code.
    # Do not modify the virtual environment,
    # imported books, or resource folders.

    for path in APP_FOLDER.rglob("__pycache__"):

        if path.is_dir():

            cache_folders.append(path)

    root_cache = (
        PROJECT_ROOT
        / "__pycache__"
    )

    if root_cache.is_dir():

        cache_folders.append(
            root_cache
        )

    return cache_folders


# ============================================================
# FIND COMPILED PYTHON FILES
# ============================================================

def get_compiled_files():

    compiled_files = []

    for extension in (
        "*.pyc",
        "*.pyo",
    ):

        for path in APP_FOLDER.rglob(extension):

            if path.is_file():

                compiled_files.append(path)

    return compiled_files


# ============================================================
# CHECK PYTHON SYNTAX
# ============================================================

def check_python_syntax(files):

    print()
    print("Checking Python syntax...")

    errors = []

    for path in files:

        try:

            source = path.read_bytes()

            compile(
                source,
                str(path),
                "exec",
            )

        except Exception as error:

            errors.append(
                (path, error)
            )

    if errors:

        print()

        print(
            "Python syntax errors were detected:"
        )

        for path, error in errors:

            print()
            print(path)
            print(error)

        return False

    print(
        "Python syntax check passed."
    )

    return True


# ============================================================
# CREATE SOURCE CODE BACKUP
# ============================================================

def create_backup(files):

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    backup_folder = (
        BACKUP_ROOT
        / timestamp
    )

    print()
    print("Creating source code backup...")

    for path in files:

        relative_path = (
            path.relative_to(
                PROJECT_ROOT
            )
        )

        destination = (
            backup_folder
            / relative_path
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )

    print(
        f"Backup location: {backup_folder}"
    )

    return backup_folder


# ============================================================
# RESTORE SOURCE CODE BACKUP
# ============================================================

def restore_backup(
    backup_folder,
    files,
):

    print()
    print(
        "Restoring original Python files..."
    )

    for path in files:

        relative_path = (
            path.relative_to(
                PROJECT_ROOT
            )
        )

        backup_file = (
            backup_folder
            / relative_path
        )

        if backup_file.is_file():

            shutil.copy2(
                backup_file,
                path,
            )

    print(
        "Original Python files restored."
    )


# ============================================================
# RUN RUFF
# ============================================================

def run_ruff(
    files,
    apply=False,
):

    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--select",
        "F401",
    ]

    if apply:

        command.append(
            "--fix"
        )

    else:

        command.append(
            "--diff"
        )

    command.extend(
        str(path)
        for path in files
    )

    result = subprocess.run(
        command,
        check=False,
    )

    return result.returncode


# ============================================================
# REMOVE PYTHON CACHE FILES
# ============================================================

def remove_python_caches():

    print()
    print(
        "Removing generated Python cache files..."
    )

    cache_folders = (
        get_cache_folders()
    )

    removed_folders = 0

    for folder in cache_folders:

        if folder.is_dir():

            shutil.rmtree(
                folder
            )

            removed_folders += 1

    # Remove standalone compiled files that
    # were not inside a __pycache__ folder.

    compiled_files = (
        get_compiled_files()
    )

    removed_files = 0

    for path in compiled_files:

        if path.is_file():

            path.unlink()

            removed_files += 1

    print(
        f"Removed {removed_folders} cache folders."
    )

    print(
        f"Removed {removed_files} standalone "
        "compiled Python files."
    )


# ============================================================
# PREVIEW CLEANUP
# ============================================================

def preview_cleanup(files):

    print()
    print("=" * 55)
    print("LITENOVA CLEANUP PREVIEW")
    print("=" * 55)

    print()
    print(
        f"Python files found: {len(files)}"
    )

    print(
        "Cache folders found: "
        f"{len(get_cache_folders())}"
    )

    print(
        "Compiled files found: "
        f"{len(get_compiled_files())}"
    )

    print()
    print(
        "Checking for unused Python imports..."
    )

    print()

    run_ruff(
        files,
        apply=False,
    )

    print()
    print("=" * 55)

    print(
        "PREVIEW COMPLETE"
    )

    print()

    print(
        "No files have been modified."
    )

    print()

    print(
        "To apply the cleanup, run:"
    )

    print(
        "python cleanup_litenova.py --apply"
    )

    print("=" * 55)


# ============================================================
# APPLY CLEANUP
# ============================================================

def apply_cleanup(files):

    print()
    print("=" * 55)
    print("LITENOVA CODE CLEANUP")
    print("=" * 55)

    # Check the existing files before changing them.

    if not check_python_syntax(files):

        print()
        print(
            "Cleanup cancelled because existing "
            "Python syntax errors were detected."
        )

        return

    # Create a backup before modifying Python source.

    backup_folder = create_backup(
        files
    )

    print()
    print(
        "Removing unused Python imports..."
    )

    # F401 targets unused imports only.
    #
    # It does not remove functions, classes,
    # application features, or unused variables.

    result = run_ruff(
        files,
        apply=True,
    )

    if result != 0:

        restore_backup(
            backup_folder,
            files,
        )

        print()
        print(
            "Ruff reported a problem."
        )

        print(
            "Source files have been restored."
        )

        return

    # Verify that the modified Python code
    # still has valid syntax.

    if not check_python_syntax(files):

        restore_backup(
            backup_folder,
            files,
        )

        print()
        print(
            "Cleanup was unsuccessful."
        )

        print(
            "Source files have been restored."
        )

        return

    # Remove generated cache files only after
    # source-code cleanup succeeds.

    try:

        remove_python_caches()

    except OSError as error:

        print()
        print(
            "Could not remove every cache file:"
        )

        print(error)

        print(
            "Your cleaned Python source files "
            "have been kept."
        )

    print()
    print("=" * 55)

    print(
        "LITENOVA CLEANUP COMPLETE"
    )

    print()

    print(
        "Unused imports have been removed."
    )

    print(
        "Generated Python caches have been cleaned."
    )

    print()

    print(
        "Your original Python files are backed up at:"
    )

    print(
        backup_folder
    )

    print()

    print(
        "IMPORTANT: Run Litenova and test its features "
        "before committing these changes."
    )

    print("=" * 55)


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Conservative cleanup for "
            "the Litenova Python project."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply unused-import cleanup "
            "and remove generated Python caches."
        ),
    )

    args = parser.parse_args()

    if not (
        PROJECT_ROOT / "main.py"
    ).is_file():

        print(
            "ERROR: Place this script in the "
            "main Litenova project folder."
        )

        return

    if not ruff_available():

        print(
            "Ruff is not installed."
        )

        print()
        print(
            "Install it using:"
        )

        print(
            "python -m pip install ruff"
        )

        return

    try:

        files = get_python_files()

        if not files:

            print(
                "No Python source files were found."
            )

            return

        if args.apply:

            apply_cleanup(
                files
            )

        else:

            preview_cleanup(
                files
            )

    except Exception as error:

        print()
        print(
            "Cleanup stopped:"
        )

        print(error)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()