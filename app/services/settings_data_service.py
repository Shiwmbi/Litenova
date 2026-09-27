"""
Litenova data management.

Handles:
- Windows startup
- Logging
- Exporting backups
- Importing backups
- Resetting application data
- SQLite-safe backups
- Cleanup of stale temporary data folders
- Recovery backup retention
"""

import json
import logging
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

from contextlib import closing
from datetime import datetime
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QSettings

from app.services.path_service import (
    get_data_dir,
    ensure_data_structure,
)


REGISTRY_VALUE = "Litenova"

BACKUP_FORMAT = "litenova-data-v1"

# Number of automatic safety backups Litenova keeps.
RECOVERY_BACKUPS_TO_KEEP = 2


# ============================================================
# TEMPORARY DATA FOLDERS
# ============================================================

# These are full copies of old application data.
# They can safely be removed after an Import or Reset succeeds.
OLD_DATA_PREFIXES = (
    ".litenova-before-reset-",
    ".litenova-previous-",
)

# Import staging folders are different.
#
# IMPORTANT:
# Never delete a new staging folder while Import is running.
STAGE_PREFIX = ".litenova-stage-"

# Only consider abandoned stage folders stale after 24 hours.
STALE_STAGE_AGE_SECONDS = (
    60
    * 60
    * 24
)


# ============================================================
# APPLICATION SETTINGS
# ============================================================

def application_settings():

    return QSettings(
        "Litenova",
        "Litenova",
    )


# ============================================================
# WINDOWS STARTUP COMMAND
# ============================================================

def _startup_command():

    if getattr(
        sys,
        "frozen",
        False,
    ):

        return subprocess.list2cmdline(
            [
                str(
                    Path(
                        sys.executable
                    ).resolve()
                )
            ]
        )

    executable = (
        Path(
            sys.executable
        )
        .resolve()
    )

    pythonw = (
        executable.with_name(
            "pythonw.exe"
        )
    )

    if pythonw.exists():

        executable = (
            pythonw
        )

    entry = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "main.py"
    )

    if not entry.is_file():

        raise FileNotFoundError(
            (
                "Cannot locate Litenova "
                f"startup file: {entry}"
            )
        )

    return subprocess.list2cmdline(
        [
            str(
                executable
            ),
            str(
                entry.resolve()
            ),
        ]
    )


# ============================================================
# STARTUP ENABLED
# ============================================================

def startup_enabled():

    if sys.platform != "win32":

        return False

    import winreg

    try:

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            (
                r"Software\Microsoft\Windows"
                r"\CurrentVersion\Run"
            ),
        ) as key:

            value, _ = (
                winreg.QueryValueEx(
                    key,
                    REGISTRY_VALUE,
                )
            )

        return (
            value
            == _startup_command()
        )

    except (
        FileNotFoundError,
        OSError,
    ):

        return False


# ============================================================
# CHANGE STARTUP SETTING
# ============================================================

def set_startup_enabled(
    enabled,
):

    if sys.platform != "win32":

        raise RuntimeError(
            (
                "Launch at startup is "
                "supported on Windows only."
            )
        )

    import winreg

    location = (
        r"Software\Microsoft\Windows"
        r"\CurrentVersion\Run"
    )

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        location,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:

        if enabled:

            winreg.SetValueEx(
                key,
                REGISTRY_VALUE,
                0,
                winreg.REG_SZ,
                _startup_command(),
            )

        else:

            try:

                winreg.DeleteValue(
                    key,
                    REGISTRY_VALUE,
                )

            except FileNotFoundError:

                pass


# ============================================================
# READ-ONLY FILE DELETE HANDLER
# ============================================================

def _remove_readonly(
    function,
    path,
    _exc_info,
):

    try:

        os.chmod(
            path,
            stat.S_IWRITE,
        )

        function(
            path
        )

    except OSError:

        pass


# ============================================================
# SAFE DIRECTORY DELETE
# ============================================================

def _remove_directory(
    directory,
):
    """
    Best-effort removal.

    Windows can briefly keep SQLite or image files locked.
    Retry a few times instead of failing immediately.
    """

    directory = Path(
        directory
    )

    if not directory.exists():

        return True

    for attempt in range(
        4
    ):

        try:

            shutil.rmtree(
                directory,
                onerror=_remove_readonly,
            )

        except OSError:

            pass

        if not directory.exists():

            return True

        if attempt < 3:

            time.sleep(
                0.20
            )

    return (
        not directory.exists()
    )


# ============================================================
# RECOVERY BACKUP DIRECTORY
# ============================================================

def recovery_backup_directory():

    directory = (
        get_data_dir().parent
        / "Litenova_Recovery_Backups"
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


# ============================================================
# RECOVERY BACKUP CLEANUP
# ============================================================

def cleanup_old_recovery_backups(
    keep=RECOVERY_BACKUPS_TO_KEEP,
):
    """
    Keep only the newest automatic recovery ZIPs.

    Manually exported backups are NOT touched.
    """

    directory = (
        recovery_backup_directory()
    )

    backups = []

    for path in directory.glob(
        "*.zip"
    ):

        if not path.is_file():

            continue

        if not (
            path.name.startswith(
                "before_reset_"
            )
            or path.name.startswith(
                "before_restore_"
            )
        ):

            continue

        try:

            modified = (
                path.stat().st_mtime
            )

        except OSError:

            continue

        backups.append(
            (
                modified,
                path,
            )
        )

    backups.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    keep = max(
        0,
        int(keep),
    )

    for (
        _modified,
        path,
    ) in backups[
        keep:
    ]:

        try:

            path.unlink()

        except OSError:

            pass


# ============================================================
# CLEAN OLD TEMPORARY DATA
# ============================================================

def cleanup_stale_data_folders():
    """
    Remove abandoned data copies from old Reset/Import jobs.

    IMPORTANT:

    Active .litenova-stage-* folders are NOT deleted.

    This was the cause of the Import error in the previous
    version.
    """

    data = (
        get_data_dir()
        .resolve()
    )

    parent = (
        data.parent
    )

    now = (
        time.time()
    )

    if not parent.is_dir():

        return

    for item in parent.iterdir():

        if not item.is_dir():

            continue

        # ----------------------------------------------------
        # NEVER TOUCH ACTIVE DATA
        # ----------------------------------------------------

        try:

            if (
                item.resolve()
                == data
            ):

                continue

        except OSError:

            continue

        # ----------------------------------------------------
        # PREVIOUS / PRE-RESET DIRECTORIES
        # ----------------------------------------------------

        should_remove = any(
            item.name.startswith(
                prefix
            )
            for prefix
            in OLD_DATA_PREFIXES
        )

        # ----------------------------------------------------
        # STAGING DIRECTORIES
        # ----------------------------------------------------

        if item.name.startswith(
            STAGE_PREFIX
        ):

            try:

                age = (
                    now
                    - item.stat().st_mtime
                )

            except OSError:

                age = 0

            # Only abandoned OLD stages are removed.
            # A current Import stage remains untouched.

            should_remove = (
                age
                >= STALE_STAGE_AGE_SECONDS
            )

        if should_remove:

            _remove_directory(
                item
            )

    cleanup_old_recovery_backups()


# ============================================================
# LOG DIRECTORY
# ============================================================

def log_directory():

    location = (
        get_data_dir().parent
        / "Litenova_Logs"
    )

    location.mkdir(
        parents=True,
        exist_ok=True,
    )

    return location


# ============================================================
# LOGGING
# ============================================================

def configure_logging():
    """
    Configure persistent logging.

    Also removes abandoned data directories from previous
    completed/failed sessions.
    """

    try:

        cleanup_stale_data_folders()

    except Exception:

        # Cleanup should never prevent Litenova from starting.

        pass

    from logging.handlers import (
        RotatingFileHandler,
    )

    file = (
        log_directory()
        / "litenova.log"
    )

    logger = logging.getLogger(
        "litenova"
    )

    if not logger.handlers:

        handler = RotatingFileHandler(
            file,
            maxBytes=1_500_000,
            backupCount=3,
            encoding="utf-8",
        )

        handler.setFormatter(
            logging.Formatter(
                (
                    "%(asctime)s | "
                    "%(levelname)s | "
                    "%(name)s | "
                    "%(message)s"
                )
            )
        )

        logger.addHandler(
            handler
        )

    verbose = (
        application_settings()
        .value(
            "advanced/verbose",
            False,
            type=bool,
        )
    )

    logger.setLevel(
        logging.DEBUG
        if verbose
        else logging.INFO
    )

    return file


# ============================================================
# SQLITE SAFE BACKUP
# ============================================================

def _write_sqlite_snapshot(
    source,
    output,
):
    """
    Copy a live SQLite database.

    Connections are explicitly closed to avoid WinError 32.
    """

    with closing(
        sqlite3.connect(
            str(source),
            timeout=30,
        )
    ) as database:

        with closing(
            sqlite3.connect(
                str(output),
                timeout=30,
            )
        ) as snapshot:

            database.backup(
                snapshot
            )


# ============================================================
# CREATE / EXPORT BACKUP
# ============================================================

def create_backup(
    destination,
):
    """
    Create a Litenova ZIP backup.

    IMPORTANT:

    This function intentionally DOES NOT run
    cleanup_stale_data_folders().

    Import calls this function while an active staging
    directory exists.

    Running cleanup here was what caused Import to delete its
    own staging directory.
    """

    destination = (
        Path(
            destination
        )
        .expanduser()
        .resolve()
    )

    data = (
        get_data_dir()
        .resolve()
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # DON'T BACK UP INTO ACTIVE APP DATA
    # --------------------------------------------------------

    if (
        destination
        == data
        or data
        in destination.parents
    ):

        raise ValueError(
            (
                "Choose a backup location "
                "outside the Litenova data folder."
            )
        )

    # --------------------------------------------------------
    # FORCE ZIP EXTENSION
    # --------------------------------------------------------

    if (
        destination.suffix.lower()
        != ".zip"
    ):

        destination = (
            destination.with_suffix(
                ".zip"
            )
        )

    partial = (
        destination.with_name(
            destination.name
            + ".partial"
        )
    )

    settings = (
        application_settings()
    )

    settings.sync()

    preferences = {}

    for key in settings.allKeys():

        value = (
            settings.value(
                key
            )
        )

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):

            preferences[
                key
            ] = value

        else:

            preferences[
                key
            ] = str(
                value
            )

    try:

        with tempfile.TemporaryDirectory(
            prefix="litenova-snapshot-"
        ) as temp:

            with zipfile.ZipFile(
                partial,
                "w",
                zipfile.ZIP_DEFLATED,
                compresslevel=5,
                allowZip64=True,
            ) as archive:

                # --------------------------------------------
                # MANIFEST
                # --------------------------------------------

                archive.writestr(
                    "manifest.json",
                    json.dumps(
                        {
                            "format": (
                                BACKUP_FORMAT
                            ),
                            "created": (
                                datetime.now()
                                .isoformat(
                                    timespec="seconds"
                                )
                            ),
                        }
                    ),
                )

                # --------------------------------------------
                # USER PREFERENCES
                # --------------------------------------------

                archive.writestr(
                    "preferences.json",
                    json.dumps(
                        preferences
                    ),
                )

                # --------------------------------------------
                # EMPTY REQUIRED DIRECTORIES
                # --------------------------------------------

                archive.writestr(
                    "data/books/",
                    b"",
                )

                archive.writestr(
                    "data/covers/",
                    b"",
                )

                # --------------------------------------------
                # APPLICATION DATA
                # --------------------------------------------

                for item in data.rglob(
                    "*"
                ):

                    if (
                        item.is_symlink()
                        or not item.is_file()
                    ):

                        continue

                    try:

                        resolved_item = (
                            item.resolve()
                        )

                    except OSError:

                        continue

                    if resolved_item in (
                        destination,
                        partial,
                    ):

                        continue

                    # Don't copy temporary SQLite files.

                    if item.name.endswith(
                        (
                            "-wal",
                            "-shm",
                            "-journal",
                        )
                    ):

                        continue

                    relative = (
                        item.relative_to(
                            data
                        )
                    )

                    archive_name = (
                        "data/"
                        + relative.as_posix()
                    )

                    # ----------------------------------------
                    # SQLITE
                    # ----------------------------------------

                    if item.suffix.lower() in (
                        ".db",
                        ".sqlite",
                        ".sqlite3",
                    ):

                        snapshot = (
                            Path(temp)
                            / (
                                uuid.uuid4().hex
                                + ".db"
                            )
                        )

                        _write_sqlite_snapshot(
                            item,
                            snapshot,
                        )

                        archive.write(
                            snapshot,
                            archive_name,
                        )

                    else:

                        archive.write(
                            item,
                            archive_name,
                        )

        # ----------------------------------------------------
        # ATOMIC FINISH
        # ----------------------------------------------------

        os.replace(
            partial,
            destination,
        )

    finally:

        if partial.exists():

            try:

                partial.unlink()

            except OSError:

                pass

    return destination


# ============================================================
# VALIDATE AND EXTRACT BACKUP
# ============================================================

def _validate_archive(
    source,
    stage,
):

    preferences = None

    found_data_entry = False

    with zipfile.ZipFile(
        source,
        "r",
    ) as archive:

        # ----------------------------------------------------
        # ZIP INTEGRITY CHECK
        # ----------------------------------------------------

        bad_file = (
            archive.testzip()
        )

        if bad_file is not None:

            raise ValueError(
                (
                    "The backup ZIP contains "
                    "a corrupted file:\n"
                    f"{bad_file}"
                )
            )

        # ----------------------------------------------------
        # READ MANIFEST
        # ----------------------------------------------------

        try:

            manifest = json.loads(
                archive.read(
                    "manifest.json"
                )
            )

            preferences = json.loads(
                archive.read(
                    "preferences.json"
                )
            )

        except (
            KeyError,
            ValueError,
            UnicodeDecodeError,
        ) as error:

            raise ValueError(
                (
                    "This is not a valid "
                    "Litenova backup."
                )
            ) from error

        if (
            manifest.get(
                "format"
            )
            != BACKUP_FORMAT
            or not isinstance(
                preferences,
                dict,
            )
        ):

            raise ValueError(
                (
                    "Unsupported Litenova "
                    "backup format."
                )
            )

        # ----------------------------------------------------
        # EXTRACT DATA
        # ----------------------------------------------------

        for info in archive.infolist():

            path = PurePosixPath(
                info.filename
            )

            if info.filename in (
                "manifest.json",
                "preferences.json",
            ):

                continue

            # -----------------------------------------------
            # SECURITY CHECK
            # -----------------------------------------------

            if (
                info.filename.startswith(
                    "/"
                )
                or "\\"
                in info.filename
                or ".."
                in path.parts
                or not path.parts
                or path.parts[
                    0
                ]
                != "data"
            ):

                raise ValueError(
                    (
                        "Backup contains an "
                        "unsafe file path."
                    )
                )

            relative_parts = (
                path.parts[
                    1:
                ]
            )

            if not relative_parts:

                continue

            relative = Path(
                *relative_parts
            )

            target = (
                stage
                / relative
            )

            found_data_entry = True

            # -----------------------------------------------
            # DIRECTORY
            # -----------------------------------------------

            if info.is_dir():

                target.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                continue

            # -----------------------------------------------
            # BLOCK SYMBOLIC LINKS
            # -----------------------------------------------

            if (
                (
                    info.external_attr
                    >> 16
                )
                & 0o170000
            ) == 0o120000:

                raise ValueError(
                    (
                        "Backup contains an unsupported "
                        "symbolic link."
                    )
                )

            # -----------------------------------------------
            # FILE
            # -----------------------------------------------

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with (
                archive.open(
                    info,
                    "r",
                ) as infile,
                target.open(
                    "wb"
                ) as outfile,
            ):

                shutil.copyfileobj(
                    infile,
                    outfile,
                    length=1024 * 1024,
                )

    # ========================================================
    # ENSURE REQUIRED STRUCTURE EXISTS
    # ========================================================

    if not found_data_entry:

        ensure_data_structure(
            stage
        )

    # Always ensure folders like covers and books exist.

    ensure_data_structure(
        stage
    )

    # ========================================================
    # VERIFY DATABASES
    # ========================================================

    for db in stage.rglob(
        "*"
    ):

        if (
            db.is_file()
            and db.suffix.lower()
            in (
                ".db",
                ".sqlite",
                ".sqlite3",
            )
        ):

            with closing(
                sqlite3.connect(
                    (
                        db.as_uri()
                        + "?mode=ro"
                    ),
                    uri=True,
                )
            ) as connection:

                result = (
                    connection.execute(
                        "PRAGMA quick_check"
                    ).fetchone()
                )

                if (
                    result is None
                    or result[
                        0
                    ]
                    != "ok"
                ):

                    raise ValueError(
                        (
                            "Invalid SQLite database "
                            "inside backup: "
                            f"{db.name}"
                        )
                    )

    return preferences


# ============================================================
# RESTORE / IMPORT BACKUP
# ============================================================

def restore_backup(
    source,
):
    """
    Safely restore a Litenova backup.

    The active staging directory cannot be deleted by the
    cleanup system.
    """

    source = (
        Path(
            source
        )
        .expanduser()
        .resolve()
    )

    data = (
        get_data_dir()
        .resolve()
    )

    # ========================================================
    # VALIDATE SELECTED FILE
    # ========================================================

    if (
        not source.is_file()
        or source.suffix.lower()
        != ".zip"
    ):

        raise ValueError(
            "Select a Litenova ZIP backup."
        )

    if data in source.parents:

        raise ValueError(
            (
                "Move the backup outside "
                "the data folder before restoring."
            )
        )

    # ========================================================
    # CLEAN PREVIOUS ABANDONED OPERATIONS
    # ========================================================

    # Safe here because THIS import's stage has not yet
    # been created.

    try:

        cleanup_stale_data_folders()

    except Exception:

        pass

    # ========================================================
    # UNIQUE STAGING / ROLLBACK PATHS
    # ========================================================

    stage = (
        data.parent
        / (
            STAGE_PREFIX
            + uuid.uuid4().hex
        )
    )

    old = (
        data.parent
        / (
            ".litenova-previous-"
            + uuid.uuid4().hex
        )
    )

    stage.mkdir(
        parents=True,
        exist_ok=False,
    )

    moved_old = False

    stage_moved_into_place = False

    try:

        # ====================================================
        # EXTRACT AND VALIDATE FIRST
        # ====================================================

        preferences = (
            _validate_archive(
                source,
                stage,
            )
        )

        # ====================================================
        # SAFETY BACKUP OF CURRENT DATA
        # ====================================================

        safety_dir = (
            recovery_backup_directory()
        )

        safety = (
            safety_dir
            / (
                "before_restore_"
                + datetime.now().strftime(
                    "%Y%m%d_%H%M%S"
                )
                + ".zip"
            )
        )

        # IMPORTANT:
        #
        # create_backup() does NOT run temporary cleanup.
        # Therefore the active staging directory above will
        # remain present.

        create_backup(
            safety
        )

        # ====================================================
        # MOVE LIVE DATA ASIDE
        # ====================================================

        os.replace(
            data,
            old,
        )

        moved_old = True

        # ====================================================
        # INSTALL RESTORED DATA
        # ====================================================

        try:

            os.replace(
                stage,
                data,
            )

            stage_moved_into_place = True

            ensure_data_structure(
                data
            )

        except Exception:

            # -----------------------------------------------
            # ROLLBACK
            # -----------------------------------------------

            if data.exists():

                _remove_directory(
                    data
                )

            if (
                moved_old
                and old.exists()
            ):

                os.replace(
                    old,
                    data,
                )

                moved_old = False

            raise

        # ====================================================
        # RESTORE USER SETTINGS
        # ====================================================

        settings = (
            application_settings()
        )

        settings.clear()

        for (
            key,
            value,
        ) in preferences.items():

            if (
                isinstance(
                    key,
                    str,
                )
                and isinstance(
                    value,
                    (
                        str,
                        int,
                        float,
                        bool,
                    ),
                )
            ):

                settings.setValue(
                    key,
                    value,
                )

        settings.sync()

        # ====================================================
        # REMOVE REDUNDANT FULL-SIZE OLD DATA
        # ====================================================

        removed_old = (
            _remove_directory(
                old
            )
        )

        moved_old = (
            not removed_old
        )

        cleanup_old_recovery_backups()

        if removed_old:

            previous_result = (
                "Temporary previous-data "
                "copy cleaned automatically."
            )

        else:

            previous_result = str(
                old
            )

        return (
            safety,
            previous_result,
        )

    except Exception:

        # ====================================================
        # FINAL ROLLBACK ATTEMPT
        # ====================================================

        if (
            moved_old
            and old.exists()
            and not data.exists()
        ):

            try:

                os.replace(
                    old,
                    data,
                )

                moved_old = False

            except OSError:

                pass

        raise

    finally:

        # ====================================================
        # REMOVE STAGE ONLY IF IT WAS NOT INSTALLED
        # ====================================================

        if (
            not stage_moved_into_place
            and stage.exists()
        ):

            _remove_directory(
                stage
            )


# ============================================================
# RESET DATA
# ============================================================

def reset_data():
    """
    Reset Litenova without closing the application.

    A recovery ZIP is created first.
    """

    data = (
        get_data_dir()
        .resolve()
    )

    # ========================================================
    # CLEAN OLD LEFTOVERS
    # ========================================================

    try:

        cleanup_stale_data_folders()

    except Exception:

        pass

    # ========================================================
    # RECOVERY BACKUP
    # ========================================================

    safety_dir = (
        recovery_backup_directory()
    )

    backup = (
        safety_dir
        / (
            "before_reset_"
            + datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
            + ".zip"
        )
    )

    create_backup(
        backup
    )

    # ========================================================
    # OLD DATA TEMP LOCATION
    # ========================================================

    old = (
        data.parent
        / (
            ".litenova-before-reset-"
            + uuid.uuid4().hex
        )
    )

    # ========================================================
    # MOVE EXISTING DATA
    # ========================================================

    os.replace(
        data,
        old,
    )

    # ========================================================
    # CREATE FRESH DATA
    # ========================================================

    try:

        ensure_data_structure(
            data
        )

    except Exception:

        if data.exists():

            _remove_directory(
                data
            )

        os.replace(
            old,
            data,
        )

        raise

    # ========================================================
    # CLEAR SETTINGS
    # ========================================================

    settings = (
        application_settings()
    )

    settings.clear()

    settings.sync()

    # ========================================================
    # REMOVE FULL OLD DATA COPY
    # ========================================================

    removed_old = (
        _remove_directory(
            old
        )
    )

    cleanup_old_recovery_backups()

    if removed_old:

        previous_result = (
            "Temporary pre-reset data "
            "copy cleaned automatically."
        )

    else:

        previous_result = str(
            old
        )

    return (
        backup,
        previous_result,
    )