from app.database.database import get_connection


DEFAULT_FONT_SIZE = 17
DEFAULT_THEME = "dark"

MIN_FONT_SIZE = 12
MAX_FONT_SIZE = 32


def get_setting(key, default=None):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT value
        FROM settings
        WHERE key = ?
        """,
        (key,),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return default

    return row["value"]


def set_setting(key, value):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO settings (
            key,
            value
        )
        VALUES (?, ?)

        ON CONFLICT(key)
        DO UPDATE SET
            value = excluded.value
        """,
        (
            key,
            str(value),
        ),
    )

    connection.commit()
    connection.close()


def get_reader_font_size():
    value = get_setting(
        "reader_font_size",
        DEFAULT_FONT_SIZE,
    )

    try:
        value = int(value)

    except (TypeError, ValueError):
        value = DEFAULT_FONT_SIZE

    value = max(
        MIN_FONT_SIZE,
        min(
            value,
            MAX_FONT_SIZE,
        ),
    )

    return value


def set_reader_font_size(font_size):
    try:
        font_size = int(font_size)

    except (TypeError, ValueError):
        font_size = DEFAULT_FONT_SIZE

    font_size = max(
        MIN_FONT_SIZE,
        min(
            font_size,
            MAX_FONT_SIZE,
        ),
    )

    set_setting(
        "reader_font_size",
        font_size,
    )


def get_reader_theme():
    theme = get_setting(
        "reader_theme",
        DEFAULT_THEME,
    )

    if theme not in [
        "dark",
        "light",
    ]:
        theme = DEFAULT_THEME

    return theme


def set_reader_theme(theme):
    if theme not in [
        "dark",
        "light",
    ]:
        theme = DEFAULT_THEME

    set_setting(
        "reader_theme",
        theme,
    )