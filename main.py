import sys

from pathlib import Path

from PySide6.QtGui import QIcon

from PySide6.QtWidgets import QApplication

from app.database.database import initialize_database

from app.windows.main_window import MainWindow

from app.services.theme_service import apply_theme


# ============================================================
# LITENOVA APPLICATION ICON
# ============================================================

def get_application_icon():
    """
    Load Litenova's original application icon.

    Supports:
    - Running from VS Code
    - Running with python main.py
    - Running a packaged application
    """

    if hasattr(sys, "_MEIPASS"):

        base_path = Path(sys._MEIPASS)

    else:

        base_path = Path(__file__).resolve().parent

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

    return QIcon(str(icon_path))


# ============================================================
# START LITENOVA
# ============================================================

def main():

    # Create the application.

    app = QApplication(sys.argv)

    app.setApplicationName("Litenova")

    app.setOrganizationName("Litenova")

    # ========================================================
    # RESTORE ORIGINAL APPLICATION ICON
    # ========================================================

    litenova_icon = get_application_icon()

    app.setWindowIcon(
        litenova_icon
    )

    # ========================================================
    # INITIALIZE DATABASE BEFORE LOADING THE THEME OR PAGES
    # ========================================================

    initialize_database()

    # ========================================================
    # APPLY SAVED THEME
    # ========================================================

    apply_theme(app)

    # ========================================================
    # CREATE MAIN WINDOW
    # ========================================================

    window = MainWindow()

    window.setWindowTitle(
        "Litenova"
    )

    # Restore the original icon in the window title bar.

    window.setWindowIcon(
        litenova_icon
    )

    # ========================================================
    # SHOW APPLICATION
    # ========================================================

    window.show()

    return app.exec()


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":

    sys.exit(main())