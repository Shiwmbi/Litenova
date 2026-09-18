from app.database.database import (
    get_connection,
)


def save_progress(
    book_id,
    chapter_index,
    position,
):
    """
    Save the user's current reading position.

    position is stored as a number between
    0.0 and 1.0 representing how far the
    user has scrolled through the chapter.
    """

    try:
        position = float(position)
    except (TypeError, ValueError):
        position = 0.0

    position = max(
        0.0,
        min(position, 1.0),
    )

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO reading_progress (
            book_id,
            chapter_index,
            position,
            last_read
        )
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)

        ON CONFLICT(book_id)
        DO UPDATE SET
            chapter_index = excluded.chapter_index,
            position = excluded.position,
            last_read = CURRENT_TIMESTAMP
        """,
        (
            book_id,
            chapter_index,
            position,
        ),
    )

    connection.commit()

    connection.close()


def get_progress(book_id):
    """
    Get saved progress for a book.

    If the book has never been opened,
    return progress starting at chapter 0.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            chapter_index,
            position,
            last_read
        FROM reading_progress
        WHERE book_id = ?
        """,
        (
            book_id,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return {
            "chapter_index": 0,
            "position": 0.0,
            "last_read": None,
        }

    return {
        "chapter_index": row[
            "chapter_index"
        ],
        "position": row[
            "position"
        ],
        "last_read": row[
            "last_read"
        ],
    }