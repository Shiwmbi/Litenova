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
APP_VERSION = "3.0.1"
ORGANIZATION_NAME = "Litenova"


# ============================================================
# LITENOVA APPLICATION ICON
# ============================================================

def get_application_icon():
    """
    Load Litenova's application icon.

    Supports:
    - Running from VS Code
    - Running with python main.py
    - Running a packaged application
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
# START LITENOVA
# ============================================================

def main():

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

    litenova_icon = (
        get_application_icon()
    )

    app.setWindowIcon(
        litenova_icon
    )

    # Database must be ready before MainWindow creates pages.

    initialize_database()

    apply_theme(
        app
    )

    window = MainWindow(startup_files=sys.argv[1:])

    window.setWindowTitle(
        APP_NAME
    )

    window.setWindowIcon(
        litenova_icon
    )

    window.show()

    return app.exec()


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )
