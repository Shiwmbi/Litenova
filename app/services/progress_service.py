from app.database.database import (
    get_connection,
)

from app.database.history_repository import (
    record_history,
)


# ============================================================
# ENSURE PROGRESS TABLE
# ============================================================

def ensure_progress_table():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reading_progress (
            book_id INTEGER PRIMARY KEY,

            chapter_index INTEGER
                NOT NULL
                DEFAULT 0,

            position REAL
                NOT NULL
                DEFAULT 0.0,

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# GET PROGRESS
# ============================================================

def get_progress(
    book_id,
):

    ensure_progress_table()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            book_id,
            chapter_index,
            position

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
            "book_id": book_id,
            "chapter_index": 0,
            "position": 0.0,
        }

    return {
        "book_id": row[
            "book_id"
        ],

        "chapter_index": row[
            "chapter_index"
        ],

        "position": row[
            "position"
        ],
    }


# ============================================================
# SAVE PROGRESS
# ============================================================

def save_progress(
    book_id,
    chapter_index=0,
    position=0.0,
):

    ensure_progress_table()

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

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO reading_progress (
            book_id,
            chapter_index,
            position
        )
        VALUES (?, ?, ?)

        ON CONFLICT(book_id)
        DO UPDATE SET
            chapter_index =
                excluded.chapter_index,

            position =
                excluded.position
        """,
        (
            book_id,
            chapter_index,
            position,
        ),
    )

    connection.commit()
    connection.close()

    # ========================================================
    # READING HISTORY
    # ========================================================

    record_history(
        book_id=book_id,
        chapter_index=chapter_index,
        position=position,
    )


# ============================================================
# DELETE PROGRESS
# ============================================================

def delete_progress(
    book_id,
):

    ensure_progress_table()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM reading_progress
        WHERE book_id = ?
        """,
        (
            book_id,
        ),
    )

    connection.commit()
    connection.close()