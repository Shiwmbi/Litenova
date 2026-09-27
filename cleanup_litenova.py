"""
LITENOVA SAFE PROJECT CLEANER

This script deliberately DOES NOT modify application source code.

It removes only generated development artifacts such as:

    __pycache__
    *.pyc
    *.pyo
    .ruff_cache
    .pytest_cache
    build/

It protects:

    app/
    resources/
    data/
    .venv/
    .git/
    dist/
    main.py
    Litenova.spec
    version_info.txt
    requirements.txt
    README.md

Preview:
    python cleanup_litenova.py

Clean safe generated files:
    python cleanup_litenova.py --apply

Also remove dist/ so it can be rebuilt:
    python cleanup_litenova.py --apply --dist

Show old Litenova reset/import folders:
    python cleanup_litenova.py --show-stale

Delete old Litenova reset/import folders older than 24 hours:
    CLOSE LITENOVA FIRST

    python cleanup_litenova.py --apply --stale-data
"""

import argparse
import os
import shutil
import sys
import time

from pathlib import Path


# ============================================================
# PROJECT
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent


# ============================================================
# PROTECTED ITEMS
# ============================================================

PROTECTED_TOP_LEVEL = {
    "app",
    "resources",
    "data",
    ".venv",
    "venv",
    ".git",
    "dist",
}


IMPORTANT_FILES = {
    "main.py",
    "Litenova.spec",
    "version_info.txt",
    "requirements.txt",
    "README.md",
    ".gitignore",
    "cleanup_litenova.py",
}


# ============================================================
# GENERATED DIRECTORIES
# ============================================================

GENERATED_DIRECTORY_NAMES = {
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
}


# ============================================================
# GENERATED FILE EXTENSIONS
# ============================================================

GENERATED_FILE_EXTENSIONS = {
    ".pyc",
    ".pyo",
}


# ============================================================
# LITENOVA TEMPORARY DATA FOLDERS
# ============================================================

LITENOVA_STALE_PREFIXES = (
    ".litenova-before-reset-",
    ".litenova-previous-",
)


LITENOVA_STAGE_PREFIX = (
    ".litenova-stage-"
)


STALE_AGE_SECONDS = (
    24
    * 60
    * 60
)


# ============================================================
# SIZE HELPERS
# ============================================================

def file_size(
    path,
):

    try:

        return path.stat().st_size

    except OSError:

        return 0


def folder_size(
    folder,
):

    total = 0

    try:

        for root, dirs, files in os.walk(
            folder
        ):

            for name in files:

                path = (
                    Path(root)
                    / name
                )

                total += file_size(
                    path
                )

    except OSError:

        pass

    return total


def human_size(
    size,
):

    size = float(
        size
    )

    for unit in (
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ):

        if size < 1024:

            return (
                f"{size:.1f} {unit}"
            )

        size /= 1024

    return (
        f"{size:.1f} PB"
    )


# ============================================================
# CHECK PROJECT ROOT
# ============================================================

def validate_project():

    required = (
        PROJECT_ROOT
        / "main.py"
    )

    app = (
        PROJECT_ROOT
        / "app"
    )

    if not required.is_file():

        raise RuntimeError(
            "main.py was not found. "
            "Place cleanup_litenova.py in "
            "C:\\Projects\\Litenova."
        )

    if not app.is_dir():

        raise RuntimeError(
            "The app folder was not found."
        )


# ============================================================
# WALK SAFE SOURCE LOCATIONS
# ============================================================

def safe_walk():

    for root, dirs, files in os.walk(
        PROJECT_ROOT
    ):

        root_path = Path(
            root
        )

        if root_path == PROJECT_ROOT:

            dirs[:] = [
                directory
                for directory in dirs
                if directory
                not in {
                    ".venv",
                    "venv",
                    ".git",
                    "data",
                    "resources",
                    "dist",
                }
            ]

        else:

            dirs[:] = [
                directory
                for directory in dirs
                if directory
                not in {
                    ".venv",
                    "venv",
                    ".git",
                    "data",
                    "resources",
                    "dist",
                }
            ]

        yield (
            root_path,
            dirs,
            files,
        )


# ============================================================
# FIND GENERATED CACHE DIRECTORIES
# ============================================================

def find_cache_directories():

    found = set()

    for root, dirs, _files in safe_walk():

        for name in list(
            dirs
        ):

            if (
                name
                in GENERATED_DIRECTORY_NAMES
            ):

                found.add(
                    root
                    / name
                )

    return sorted(
        found,
        key=lambda path: str(
            path
        ).casefold(),
    )


# ============================================================
# FIND GENERATED PYTHON FILES
# ============================================================

def find_compiled_files():

    found = set()

    for root, _dirs, files in safe_walk():

        for name in files:

            path = (
                root
                / name
            )

            if (
                path.suffix.lower()
                in GENERATED_FILE_EXTENSIONS
            ):

                found.add(
                    path
                )

    return sorted(
        found,
        key=lambda path: str(
            path
        ).casefold(),
    )


# ============================================================
# FIND BUILD DIRECTORY
# ============================================================

def find_build_directory():

    build = (
        PROJECT_ROOT
        / "build"
    )

    if build.is_dir():

        return build

    return None


# ============================================================
# FIND DIST DIRECTORY
# ============================================================

def find_dist_directory():

    dist = (
        PROJECT_ROOT
        / "dist"
    )

    if dist.is_dir():

        return dist

    return None


# ============================================================
# FIND OLD LITENOVA DATA COPIES
# ============================================================

def find_stale_data_directories():

    found = []

    now = (
        time.time()
    )

    for item in PROJECT_ROOT.iterdir():

        if not item.is_dir():

            continue

        is_old_data = any(
            item.name.startswith(
                prefix
            )
            for prefix
            in LITENOVA_STALE_PREFIXES
        )

        is_stage = (
            item.name.startswith(
                LITENOVA_STAGE_PREFIX
            )
        )

        if not (
            is_old_data
            or is_stage
        ):

            continue

        try:

            modified = (
                item.stat().st_mtime
            )

        except OSError:

            continue

        age = (
            now
            - modified
        )

        # Stage directories could belong to an active import.
        # Only consider them stale after 24 hours.

        if (
            is_stage
            and age
            < STALE_AGE_SECONDS
        ):

            continue

        found.append(
            (
                item,
                age,
            )
        )

    found.sort(
        key=lambda value: (
            value[0].name.casefold()
        )
    )

    return found


# ============================================================
# COLLECT SAFE CLEANUP TARGETS
# ============================================================

def collect_safe_targets(
    include_dist=False,
):

    targets = []

    for directory in find_cache_directories():

        targets.append(
            (
                "cache directory",
                directory,
                folder_size(
                    directory
                ),
            )
        )

    for file in find_compiled_files():

        targets.append(
            (
                "compiled Python file",
                file,
                file_size(
                    file
                ),
            )
        )

    build = (
        find_build_directory()
    )

    if build is not None:

        targets.append(
            (
                "PyInstaller build",
                build,
                folder_size(
                    build
                ),
            )
        )

    if include_dist:

        dist = (
            find_dist_directory()
        )

        if dist is not None:

            targets.append(
                (
                    "PyInstaller dist",
                    dist,
                    folder_size(
                        dist
                    ),
                )
            )

    return targets


# ============================================================
# DELETE SAFE TARGET
# ============================================================

def remove_target(
    path,
):

    if path.is_dir():

        shutil.rmtree(
            path
        )

    elif path.exists():

        path.unlink()


# ============================================================
# PREVIEW
# ============================================================

def preview(
    include_dist=False,
):

    targets = (
        collect_safe_targets(
            include_dist=include_dist
        )
    )

    print()
    print(
        "=" * 66
    )

    print(
        "LITENOVA SAFE CLEANUP PREVIEW"
    )

    print(
        "=" * 66
    )

    print()

    if not targets:

        print(
            "No generated project files need cleaning."
        )

        return

    total = 0

    for kind, path, size in targets:

        total += size

        try:

            relative = (
                path.relative_to(
                    PROJECT_ROOT
                )
            )

        except ValueError:

            relative = path

        print(
            f"{kind:24} "
            f"{human_size(size):>10}   "
            f"{relative}"
        )

    print()

    print(
        "Space that can be reclaimed:"
    )

    print(
        human_size(
            total
        )
    )

    print()

    print(
        "NO application source files will be changed."
    )

    print(
        "NO books, covers, database files or settings "
        "will be touched."
    )

    if not include_dist:

        print(
            "dist/ is protected and will not be deleted."
        )

    print()

    print(
        "Run this to clean the files above:"
    )

    print()

    print(
        "    python cleanup_litenova.py --apply"
    )

    print()


# ============================================================
# APPLY SAFE CLEANUP
# ============================================================

def apply_cleanup(
    include_dist=False,
):

    targets = (
        collect_safe_targets(
            include_dist=include_dist
        )
    )

    print()
    print(
        "=" * 66
    )

    print(
        "LITENOVA SAFE CLEANUP"
    )

    print(
        "=" * 66
    )

    total = 0

    for kind, path, size in targets:

        try:

            remove_target(
                path
            )

            total += size

            try:

                relative = (
                    path.relative_to(
                        PROJECT_ROOT
                    )
                )

            except ValueError:

                relative = path

            print(
                "Removed:",
                relative,
            )

        except OSError as error:

            print(
                "Could not remove:",
                path,
            )

            print(
                " ",
                error,
            )

    print()

    print(
        "Cleanup complete."
    )

    print(
        "Approximate space reclaimed:",
        human_size(
            total
        ),
    )

    print()

    print(
        "Your application source code was not modified."
    )


# ============================================================
# SHOW STALE DATA DIRECTORIES
# ============================================================

def show_stale_data():

    stale = (
        find_stale_data_directories()
    )

    print()
    print(
        "=" * 66
    )

    print(
        "OLD LITENOVA RESET / IMPORT FOLDERS"
    )

    print(
        "=" * 66
    )

    if not stale:

        print()

        print(
            "No old temporary data folders were found."
        )

        return

    total = 0

    print()

    for path, age in stale:

        size = (
            folder_size(
                path
            )
        )

        total += size

        hours = (
            age
            / 3600
        )

        print(
            f"{human_size(size):>10}  "
            f"{hours:8.1f} hours old  "
            f"{path.name}"
        )

    print()

    print(
        "Total:",
        human_size(
            total
        ),
    )

    print()

    print(
        "These are NOT deleted by normal --apply cleanup."
    )

    print(
        "Close Litenova first, then use:"
    )

    print()

    print(
        "    python cleanup_litenova.py "
        "--apply --stale-data"
    )

    print()


# ============================================================
# CLEAN STALE DATA DIRECTORIES
# ============================================================

def clean_stale_data():

    stale = (
        find_stale_data_directories()
    )

    if not stale:

        print(
            "No stale Litenova data folders found."
        )

        return

    print()

    print(
        "WARNING:"
    )

    print(
        "Litenova must be CLOSED before deleting "
        "old reset/import folders."
    )

    print()

    answer = input(
        "Type CLEAN to continue: "
    ).strip()

    if answer != "CLEAN":

        print(
            "Cancelled."
        )

        return

    total = 0

    for path, _age in stale:

        size = (
            folder_size(
                path
            )
        )

        try:

            shutil.rmtree(
                path
            )

            total += size

            print(
                "Removed:",
                path.name,
            )

        except OSError as error:

            print(
                "Could not remove:",
                path.name,
            )

            print(
                " ",
                error,
            )

    print()

    print(
        "Approximate stale-data space reclaimed:",
        human_size(
            total
        ),
    )


# ============================================================
# PROJECT SIZE REPORT
# ============================================================

def size_report():

    print()
    print(
        "=" * 66
    )

    print(
        "LITENOVA PROJECT SIZE REPORT"
    )

    print(
        "=" * 66
    )

    items = []

    for item in PROJECT_ROOT.iterdir():

        try:

            if item.is_dir():

                size = folder_size(
                    item
                )

            else:

                size = file_size(
                    item
                )

        except OSError:

            continue

        items.append(
            (
                size,
                item,
            )
        )

    items.sort(
        key=lambda value: value[0],
        reverse=True,
    )

    print()

    for size, item in items:

        print(
            f"{human_size(size):>10}   "
            f"{item.name}"
        )

    print()


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Safely clean generated Litenova "
            "development files."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Perform the safe cleanup."
        ),
    )

    parser.add_argument(
        "--dist",
        action="store_true",
        help=(
            "Also delete dist/. "
            "Use this only when you intend to rebuild the EXE."
        ),
    )

    parser.add_argument(
        "--show-stale",
        action="store_true",
        help=(
            "Show old reset/import folders and their sizes."
        ),
    )

    parser.add_argument(
        "--stale-data",
        action="store_true",
        help=(
            "Delete old reset/import folders. "
            "Litenova must be closed."
        ),
    )

    parser.add_argument(
        "--sizes",
        action="store_true",
        help=(
            "Show project disk usage."
        ),
    )

    args = (
        parser.parse_args()
    )

    try:

        validate_project()

    except RuntimeError as error:

        print(
            "ERROR:",
            error,
        )

        sys.exit(
            1
        )

    if args.sizes:

        size_report()

    if args.show_stale:

        show_stale_data()

    if args.stale_data:

        if not args.apply:

            print(
                "--stale-data requires --apply."
            )

            return

        clean_stale_data()

    if args.apply:

        apply_cleanup(
            include_dist=args.dist
        )

    elif not (
        args.sizes
        or args.show_stale
    ):

        preview(
            include_dist=args.dist
        )


if __name__ == "__main__":

    main()