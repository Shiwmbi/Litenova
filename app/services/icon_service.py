"""Load Litenova's PNG icons in development and in a PyInstaller build."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def icon_path(name):
    """Find an icon copied into resources/icons (flat or size subfolders)."""
    filename = f"{name}.png"
    if getattr(sys, "frozen", False):
        roots = [Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))]
    else:
        roots = [Path(__file__).resolve().parents[2]]

    for root in roots:
        base = root / "resources" / "icons"
        for folder in (base, base / "32x32", base / "48x48", base / "64x64", base / "24x24"):
            candidate = folder / filename
            if candidate.is_file():
                return candidate
    return None


def ui_icon(name):
    path = icon_path(name)
    return QIcon(str(path)) if path is not None else QIcon()
