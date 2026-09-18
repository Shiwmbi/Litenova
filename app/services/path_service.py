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
# RESOURCE PATH
# ============================================================

def resource_path(
    relative_path,
):
    """
    Return the correct location for application
    resources.

    During development:
        C:\\Projects\\Litenova\\...

    When packaged with PyInstaller:
        PyInstaller's temporary resource folder
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
# DATA DIRECTORY
# ============================================================

def get_data_dir():
    """
    Return the writable Litenova data folder.

    Development:
        C:\\Projects\\Litenova\\data

    Packaged Windows application:
        %LOCALAPPDATA%\\Litenova
    """

    if getattr(
        sys,
        "frozen",
        False,
    ):
        local_app_data = (
            os.getenv(
                "LOCALAPPDATA"
            )
        )

        if local_app_data:

            data_dir = (
                Path(local_app_data)
                / "Litenova"
            )

        else:

            data_dir = (
                Path.home()
                / ".litenova"
            )

    else:

        data_dir = (
            PROJECT_ROOT
            / "data"
        )

    data_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return data_dir