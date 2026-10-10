import sys

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.database.database import initialize_database
from app.windows.main_window import MainWindow
from app.services.theme_service import apply_theme


# ============================================================
# APPLICATION INFORMATION
# ============================================================

APP_NAME = "Litenova"

APP_VERSION = "3.0.0"

ORGANIZATION_NAME = "Litenova"


# ============================================================
# APPLICATION ICON
# ============================================================

def get_application_icon():
    """
    Return the Litenova application icon.

    Supports:

    - python main.py
    - development mode
    - PyInstaller one-file executable
    """

    if hasattr(
        sys,
        "_MEIPASS",
    ):

        base_path = Path(
            sys._MEIPASS
        )

    else:

        base_path = (
            Path(__file__)
            .resolve()
            .parent
        )

    icon_path = (
        base_path
        / "resources"
        / "icons"
        / "litenova.ico"
    )

    if not icon_path.is_file():

        print(
            "Litenova icon not found:",
            icon_path,
        )

        return QIcon()

    return QIcon(
        str(icon_path)
    )


# ============================================================
# MAIN APPLICATION
# ============================================================

def main():

    # --------------------------------------------------------
    # CREATE APPLICATION
    # --------------------------------------------------------

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        APP_NAME
    )

    app.setApplicationVersion(
        APP_VERSION
    )

    app.setOrganizationName(
        ORGANIZATION_NAME
    )

    # --------------------------------------------------------
    # APPLICATION ICON
    # --------------------------------------------------------

    litenova_icon = (
        get_application_icon()
    )

    app.setWindowIcon(
        litenova_icon
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------
    #
    # Database initialization happens on the user's computer.
    #
    # No personal database is bundled inside Litenova.exe.
    #
    # A fresh user therefore gets a fresh database.
    # --------------------------------------------------------

    initialize_database()

    # --------------------------------------------------------
    # THEME
    # --------------------------------------------------------

    apply_theme(
        app
    )

    # --------------------------------------------------------
    # MAIN WINDOW
    # --------------------------------------------------------

    window = MainWindow()

    window.setWindowTitle(
        APP_NAME
    )

    window.setWindowIcon(
        litenova_icon
    )

    window.show()

    return app.exec()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )