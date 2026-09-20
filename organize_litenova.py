"""
LITENOVA PROJECT FILE ORGANIZER

Organizes old development scripts and backup files
without changing the application's source code.

Usage:

    Preview:
        python organize_litenova.py

    Apply:
        python organize_litenova.py --apply

IMPORTANT:

This script does NOT move or delete:
    - Application source files
    - Database files
    - Imported books
    - Book covers
    - Resource icons
    - Virtual environment
    - Git repository

Development files are moved to an archive folder
outside the Litenova project.

Archived development scripts are kept for reference
and should not be executed from their new location.
"""

import argparse
import shutil

from pathlib import Path
from datetime import datetime


# ============================================================
# PROJECT LOCATIONS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

ARCHIVE_ROOT = (
    PROJECT_ROOT.parent
    / "Litenova_Development_Archive"
)


# ============================================================
# PROTECTED PROJECT FOLDERS
# ============================================================

PROTECTED_FOLDERS = {
    "app",
    "resources",
    "data",
    ".venv",
    "venv",
    ".git",
    "build",
    "dist",
}


# ============================================================
# DEVELOPMENT FILES
# ============================================================

# Only files matching these specific patterns are
# considered for archiving.

DEVELOPMENT_SCRIPT_PATTERNS = (
    "fix_*.py",
    "diagnose_*.py",
    "install_litenova_*.py",
)


# Only explicitly identified temporary files
# are included.

TEMPORARY_FILE_PATTERNS = (
    "floating_windows_log.txt",
    "floating_windows_log*.txt",
    "diagnostic_*.txt",
    "debug_*.log",
    "fix_*.log",
)


# ============================================================
# FIND DEVELOPMENT SCRIPTS
# ============================================================

def find_development_scripts():

    files = set()

    for pattern in DEVELOPMENT_SCRIPT_PATTERNS:

        for path in PROJECT_ROOT.glob(pattern):

            if path.is_file():

                files.add(path)

    return sorted(files)


# ============================================================
# FIND TEMPORARY FILES
# ============================================================

def find_temporary_files():

    files = set()

    for pattern in TEMPORARY_FILE_PATTERNS:

        for path in PROJECT_ROOT.glob(pattern):

            if path.is_file():

                files.add(path)

    return sorted(files)


# ============================================================
# FIND BACKUP FILES
# ============================================================

def find_backup_files():

    files = set()

    # Look for backup files in the project root
    # and its application source folders.

    for folder in (
        PROJECT_ROOT,
        PROJECT_ROOT / "app",
    ):

        if not folder.exists():

            continue

        for path in folder.rglob("*"):

            if not path.is_file():

                continue

            # Never examine protected application
            # data, icons, Git files, or environments.

            relative = path.relative_to(
                PROJECT_ROOT
            )

            if any(
                part in {
                    "data",
                    "resources",
                    ".venv",
                    "venv",
                    ".git",
                    "build",
                    "dist",
                }
                for part in relative.parts
            ):

                continue

            name = path.name.lower()

            if (
                name.endswith(".bak")
                or ".before_" in name
                and name.endswith(".py")
            ):

                files.add(path)

    return sorted(files)


# ============================================================
# BUILD ORGANIZATION PLAN
# ============================================================

def create_plan():

    plan = []

    # --------------------------------------------------------
    # Development scripts
    # --------------------------------------------------------

    for path in find_development_scripts():

        destination = (
            ARCHIVE_ROOT
            / "old_fix_scripts"
            / path.name
        )

        plan.append(
            (path, destination)
        )

    # --------------------------------------------------------
    # Diagnostic files
    # --------------------------------------------------------

    for path in find_temporary_files():

        destination = (
            ARCHIVE_ROOT
            / "diagnostics"
            / path.name
        )

        plan.append(
            (path, destination)
        )

    # --------------------------------------------------------
    # Backup files
    # --------------------------------------------------------

    for path in find_backup_files():

        relative = path.relative_to(
            PROJECT_ROOT
        )

        destination = (
            ARCHIVE_ROOT
            / "old_backups"
            / relative
        )

        plan.append(
            (path, destination)
        )

    # Avoid duplicate source files.

    unique_plan = {}

    for source, destination in plan:

        unique_plan[source] = destination

    return sorted(
        unique_plan.items(),
        key=lambda item: str(item[0]),
    )


# ============================================================
# PREVIEW
# ============================================================

def preview(plan):

    print()
    print("=" * 60)
    print("LITENOVA FILE ORGANIZATION PREVIEW")
    print("=" * 60)

    print()

    if not plan:

        print(
            "No matching development files were found."
        )

        print(
            "Your project does not need this cleanup."
        )

        return

    print(
        f"Files that can be archived: {len(plan)}"
    )

    print()

    for source, destination in plan:

        print(
            f"FROM: {source.relative_to(PROJECT_ROOT)}"
        )

        print(
            f"TO:   {destination}"
        )

        print("-" * 60)

    print()

    print(
        "Preview complete. No files were moved."
    )

    print()

    print(
        "Review the list before applying the changes."
    )

    print(
        "To organize these files, run:"
    )

    print(
        "python organize_litenova.py --apply"
    )


# ============================================================
# APPLY ORGANIZATION
# ============================================================

def apply_organization(plan):

    if not plan:

        print(
            "Nothing to organize."
        )

        return

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    archive_session = (
        ARCHIVE_ROOT
        / timestamp
    )

    print()
    print(
        "Organizing Litenova development files..."
    )

    print()

    moved = 0

    for source, destination in plan:

        # Place files inside a timestamped archive
        # to avoid overwriting older backups.

        relative_destination = (
            destination.relative_to(
                ARCHIVE_ROOT
            )
        )

        final_destination = (
            archive_session
            / relative_destination
        )

        final_destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.move(
            str(source),
            str(final_destination),
        )

        print(
            "Archived:",
            source.relative_to(
                PROJECT_ROOT
            ),
        )

        moved += 1

    print()

    print("=" * 60)

    print(
        "LITENOVA ORGANIZATION COMPLETE"
    )

    print()

    print(
        f"Files archived: {moved}"
    )

    print()

    print(
        "Archive location:"
    )

    print(
        archive_session
    )

    print()

    print(
        "Your main application files were not changed."
    )

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Organize Litenova development files."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move matching files into the archive.",
    )

    args = parser.parse_args()

    if not (
        PROJECT_ROOT / "main.py"
    ).is_file():

        print(
            "ERROR: Put this script beside main.py "
            "inside your Litenova project folder."
        )

        return

    plan = create_plan()

    if args.apply:

        apply_organization(
            plan
        )

    else:

        preview(
            plan
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()