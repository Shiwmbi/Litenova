import sys

from PySide6.QtGui import QIcon

from PySide6.QtWidgets import (
    QApplication,
)

from app.database.database import (
    initialize_database,
)

from app.services.path_service import (
    resource_path,
)

from app.services.theme_service import (
    apply_theme,
)

from app.windows.main_window import (
    MainWindow,
)


def main():
    # ========================================================
    # DATABASE
    # ========================================================

    initialize_database()

    # ========================================================
    # APPLICATION
    # ========================================================

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "Litenova"
    )

    app.setApplicationDisplayName(
        "Litenova"
    )

    app.setOrganizationName(
        "Litenova"
    )

    # ========================================================
    # APPLICATION ICON
    # ========================================================

    icon_path = resource_path(
        "resources/icons/litenova.ico"
    )

    if icon_path.exists():

        app_icon = QIcon(
            str(icon_path)
        )

        app.setWindowIcon(
            app_icon
        )

    else:

        app_icon = QIcon()

    # ========================================================
    # THEME
    # ========================================================

    apply_theme(
        app
    )

    # ========================================================
    # MAIN WINDOW
    # ========================================================

    window = MainWindow()

    if not app_icon.isNull():

        window.setWindowIcon(
            app_icon
        )

    window.show()

    # ========================================================
    # RUN
    # ========================================================

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()