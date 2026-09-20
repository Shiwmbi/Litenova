from datetime import datetime

from app.database.database import get_connection


# ============================================================
# CREATE HISTORY TABLE
# ============================================================

def ensure_history_table():
    """
    Creates the reading history table if it does not
    already exist.

    One book/chapter pair gets one history entry.
    Reading the same chapter again updates the existing
    entry instead of creating hundreds of duplicates.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reading_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            book_id INTEGER NOT NULL,

            chapter_index INTEGER NOT NULL DEFAULT 0,

            position REAL NOT NULL DEFAULT 0.0,

            last_read TEXT NOT NULL,

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE,

            UNIQUE (
                book_id,
                chapter_index
            )
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_reading_history_last_read

        ON reading_history (
            last_read DESC
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_reading_history_book

        ON reading_history (
            book_id
        )
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# RECORD HISTORY
# ============================================================

def record_history(
    book_id,
    chapter_index,
    position,
):
    """
    Record or update the reading-history entry for
    the current chapter.
    """

    ensure_history_table()

    connection = get_connection()
    cursor = connection.cursor()

    try:
        chapter_index = int(
            chapter_index
        )

    except (
        TypeError,
        ValueError,
    ):
        chapter_index = 0

    try:
        position = float(
            position
        )

    except (
        TypeError,
        ValueError,
    ):
        position = 0.0

    position = max(
        0.0,
        min(
            position,
            1.0,
        ),
    )

    last_read = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    cursor.execute(
        """
        INSERT INTO reading_history (
            book_id,
            chapter_index,
            position,
            last_read
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(
            book_id,
            chapter_index
        )
        DO UPDATE SET
            position = excluded.position,
            last_read = excluded.last_read
        """,
        (
            book_id,
            chapter_index,
            position,
            last_read,
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# GET HISTORY
# ============================================================

def get_history_entries():
    """
    Returns reading history newest first.

    CBZ chapter titles are taken from comic_chapters.

    EPUB entries fall back to:
        Chapter 1
        Chapter 2
        etc.
    """

    ensure_history_table()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            reading_history.id AS history_id,

            reading_history.book_id,

            reading_history.chapter_index,

            reading_history.position,

            reading_history.last_read,

            books.title AS book_title,

            books.author AS author,

            books.cover_path AS cover_path,

            books.file_path AS file_path,

            books.epub_path AS epub_path,

            books.file_format AS file_format,

            books.category AS book_category,

            comic_chapters.title AS comic_chapter_title

        FROM reading_history

        INNER JOIN books
            ON books.id
            = reading_history.book_id

        LEFT JOIN comic_chapters
            ON comic_chapters.book_id
            = reading_history.book_id

            AND comic_chapters.chapter_index
            = reading_history.chapter_index

        ORDER BY
            reading_history.last_read DESC
        """
    )

    entries = cursor.fetchall()

    connection.close()

    return entries


# ============================================================
# GET NUMBER OF COMIC CHAPTERS
# ============================================================

def get_comic_chapter_count(
    book_id,
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM comic_chapters
        WHERE book_id = ?
        """,
        (
            book_id,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return 0

    try:
        return int(
            row[0]
        )

    except Exception:
        return 0


# ============================================================
# DELETE ONE HISTORY ENTRY
# ============================================================

def delete_history_entry(
    history_id,
):

    ensure_history_table()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM reading_history
        WHERE id = ?
        """,
        (
            history_id,
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# CLEAR ALL HISTORY
# ============================================================

def clear_history():

    ensure_history_table()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM reading_history
        """
    )

    connection.commit()
    connection.close()