import os
import sys
from pathlib import Path


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]


# ============================================================
# DATA DIRECTORY PATH
# ============================================================

def _get_data_directory_path():
    """
    Return Litenova's writable data directory without
    creating anything yet.

    Development:
        C:\\Projects\\Litenova\\data

    Packaged EXE:
        %LOCALAPPDATA%\\Litenova
    """

    if getattr(
        sys,
        "frozen",
        False,
    ):

        local_app_data = os.getenv(
            "LOCALAPPDATA"
        )

        if local_app_data:

            return (
                Path(local_app_data)
                / "Litenova"
            )

        return (
            Path.home()
            / ".litenova"
        )

    return (
        PROJECT_ROOT
        / "data"
    )


# ============================================================
# ENSURE DATA STRUCTURE
# ============================================================

def ensure_data_structure(
    data_directory=None,
):
    """
    Make sure all writable folders required by Litenova exist.

    This is safe to call repeatedly.

    It is especially important after:
        - Reset app data
        - Importing a backup
        - First launch
        - Running the packaged EXE
    """

    if data_directory is None:

        data_dir = (
            _get_data_directory_path()
        )

    else:

        data_dir = Path(
            data_directory
        )

    data_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # IMPORTED BOOK FILES
    # --------------------------------------------------------

    books_dir = (
        data_dir
        / "books"
    )

    books_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # GENERATED / EXTRACTED COVER IMAGES
    # --------------------------------------------------------

    covers_dir = (
        data_dir
        / "covers"
    )

    covers_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return data_dir


# ============================================================
# RESOURCE PATH
# ============================================================

def resource_path(
    relative_path,
):
    """
    Return the correct location for application resources.

    Development:
        C:\\Projects\\Litenova\\...

    Packaged with PyInstaller:
        PyInstaller's temporary _MEIPASS directory
    """

    if getattr(
        sys,
        "frozen",
        False,
    ):

        base_path = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(
                    sys.executable
                ).resolve().parent,
            )
        )

    else:

        base_path = (
            PROJECT_ROOT
        )

    return (
        base_path
        / relative_path
    )


# ============================================================
# GET DATA DIRECTORY
# ============================================================

def get_data_dir():
    """
    Return Litenova's writable application data directory.

    This also recreates required subdirectories if they
    were removed by Reset or are missing on first launch.
    """

    return ensure_data_structure()