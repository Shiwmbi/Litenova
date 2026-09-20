"""Windows startup, diagnostics, and verified backup/restore for Litenova."""

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QSettings

from app.services.path_service import get_data_dir

REGISTRY_VALUE = "Litenova"
BACKUP_FORMAT = "litenova-data-v1"


def application_settings():
    return QSettings("Litenova", "Litenova")


def _startup_command():
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([str(Path(sys.executable).resolve())])
    executable = Path(sys.executable).resolve()
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        executable = pythonw
    entry = Path(__file__).resolve().parents[2] / "main.py"
    if not entry.is_file():
        raise FileNotFoundError(f"Cannot locate Litenova startup file: {entry}")
    return subprocess.list2cmdline([str(executable), str(entry.resolve())])


def startup_enabled():
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            value, _ = winreg.QueryValueEx(key, REGISTRY_VALUE)
        return value == _startup_command()
    except (FileNotFoundError, OSError):
        return False


def set_startup_enabled(enabled):
    if sys.platform != "win32":
        raise RuntimeError("Launch at startup is supported on Windows only.")
    import winreg
    location = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, location, 0,
                            winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, REGISTRY_VALUE, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, REGISTRY_VALUE)
            except FileNotFoundError:
                pass


def log_directory():
    location = get_data_dir().parent / "Litenova_Logs"
    location.mkdir(parents=True, exist_ok=True)
    return location


def configure_logging():
    """Write Litenova's Python warnings/errors to a persistent log."""
    from logging.handlers import RotatingFileHandler
    file = log_directory() / "litenova.log"
    logger = logging.getLogger("litenova")
    if not logger.handlers:
        handler = RotatingFileHandler(file, maxBytes=1_500_000, backupCount=3,
                                      encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if application_settings().value(
        "advanced/verbose", False, type=bool) else logging.INFO)
    return file


def _write_sqlite_snapshot(source, output):
    """Snapshot a live SQLite file so its backup is internally consistent."""
    with sqlite3.connect(str(source)) as database:
        with sqlite3.connect(str(output)) as snapshot:
            database.backup(snapshot)


def create_backup(destination):
    """Create a self-contained ZIP of data and the UI preferences."""
    destination = Path(destination).resolve()
    data = get_data_dir().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination == data or data in destination.parents:
        raise ValueError("Choose a backup location outside the Litenova data folder.")
    partial = destination.with_name(destination.name + ".partial")
    settings = application_settings()
    settings.sync()
    preferences = {}
    for key in settings.allKeys():
        value = settings.value(key)
        preferences[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
    try:
        with tempfile.TemporaryDirectory(prefix="litenova-snapshot-") as temp:
            with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED,
                                 compresslevel=5, allowZip64=True) as archive:
                archive.writestr("manifest.json", json.dumps({
                    "format": BACKUP_FORMAT,
                    "created": datetime.now().isoformat(timespec="seconds"),
                }))
                archive.writestr("preferences.json", json.dumps(preferences))
                for item in data.rglob("*"):
                    if item.is_symlink() or not item.is_file():
                        continue
                    if item.resolve() == destination or item.resolve() == partial:
                        continue
                    if item.name.endswith(("-wal", "-shm", "-journal")):
                        continue
                    # Logs are diagnostic rather than application data.
                    if "logs" in item.relative_to(data).parts:
                        continue
                    name = "data/" + item.relative_to(data).as_posix()
                    if item.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
                        snapshot = Path(temp) / (uuid.uuid4().hex + ".db")
                        _write_sqlite_snapshot(item, snapshot)
                        archive.write(snapshot, name)
                    else:
                        archive.write(item, name)
        os.replace(partial, destination)
    finally:
        if partial.exists():
            partial.unlink()
    return destination


def _validate_archive(source, stage):
    preferences = None
    found_data = False
    with zipfile.ZipFile(source, "r") as archive:
        if archive.testzip() is not None:
            raise ValueError("The backup ZIP has a corrupted file.")
        try:
            manifest = json.loads(archive.read("manifest.json"))
            preferences = json.loads(archive.read("preferences.json"))
        except (KeyError, ValueError, UnicodeDecodeError) as error:
            raise ValueError("This is not a valid Litenova backup.") from error
        if manifest.get("format") != BACKUP_FORMAT or not isinstance(preferences, dict):
            raise ValueError("Unsupported Litenova backup format.")
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if info.filename in ("manifest.json", "preferences.json"):
                continue
            if (info.filename.startswith("/") or "\\" in info.filename
                    or ".." in path.parts or path.parts[0] != "data"):
                raise ValueError("Backup contains an unsafe file path.")
            if info.is_dir():
                continue
            # A Unix ZIP symlink can reference data outside our restore folder.
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError("Backup contains an unsupported symbolic link.")
            relative = Path(*path.parts[1:])
            if not relative.parts:
                raise ValueError("Backup contains an invalid data entry.")
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as infile, target.open("wb") as outfile:
                shutil.copyfileobj(infile, outfile, length=1024 * 1024)
            found_data = True
    if not found_data:
        raise ValueError("Backup contains no application data.")
    for db in stage.rglob("*"):
        if db.is_file() and db.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
            with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as connection:
                result = connection.execute("PRAGMA quick_check").fetchone()
                if result is None or result[0] != "ok":
                    raise ValueError(f"Invalid SQLite database in backup: {db.name}")
    return preferences


def restore_backup(source):
    """Validate and stage all data; make a rollback archive before replacing it.

    The caller must close the app immediately on success; reopen it to reload data.
    """
    source = Path(source).resolve()
    data = get_data_dir().resolve()
    if not source.is_file() or source.suffix.lower() != ".zip":
        raise ValueError("Select a Litenova ZIP backup.")
    if data in source.parents:
        raise ValueError("Move the backup outside the data folder before restoring.")
    stage = data.parent / f".litenova-stage-{uuid.uuid4().hex}"
    old = data.parent / f".litenova-previous-{uuid.uuid4().hex}"
    stage.mkdir()
    moved_old = False
    try:
        prefs = _validate_archive(source, stage)
        safety_dir = data.parent / "Litenova_Recovery_Backups"
        safety_dir.mkdir(exist_ok=True)
        safety = safety_dir / f"before_restore_{datetime.now():%Y%m%d_%H%M%S}.zip"
        create_backup(safety)
        os.replace(data, old)
        moved_old = True
        try:
            os.replace(stage, data)
        except Exception:
            os.replace(old, data)
            moved_old = False
            raise
        # Keep old data on disk as additional rollback protection.
        settings = application_settings()
        settings.clear()
        for key, value in prefs.items():
            if isinstance(key, str) and isinstance(value, (str, int, float, bool)):
                settings.setValue(key, value)
        settings.sync()
        return safety, old
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def reset_data():
    """Back up everything, then create a fresh empty data folder.

    Call only after the user types the explicit confirmation phrase.
    """
    data = get_data_dir().resolve()
    safety_dir = data.parent / "Litenova_Recovery_Backups"
    safety_dir.mkdir(exist_ok=True)
    backup = safety_dir / f"before_reset_{datetime.now():%Y%m%d_%H%M%S}.zip"
    create_backup(backup)
    old = data.parent / f".litenova-before-reset-{uuid.uuid4().hex}"
    data.rename(old)
    try:
        data.mkdir()
    except Exception:
        old.rename(data)
        raise
    application_settings().clear()
    application_settings().sync()
    return backup, old
