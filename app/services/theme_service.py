from app.services.path_service import (
    resource_path,
)

from app.services.settings_service import (
    get_reader_theme,
)


def get_theme_stylesheet():
    """
    Load the correct QSS file for the
    currently selected theme.
    """

    theme = (
        get_reader_theme()
    )

    if theme == "light":

        stylesheet_path = (
            resource_path(
                "app/styles/light.qss"
            )
        )

    else:

        stylesheet_path = (
            resource_path(
                "app/styles/dark.qss"
            )
        )

    if not stylesheet_path.exists():
        return ""

    return (
        stylesheet_path.read_text(
            encoding="utf-8"
        )
    )


def apply_theme(
    app,
):
    """
    Apply the selected theme to the
    entire PySide6 application.
    """

    stylesheet = (
        get_theme_stylesheet()
    )

    app.setStyleSheet(
        stylesheet
    )