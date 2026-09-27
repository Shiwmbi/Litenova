from app.database.database import (
    get_connection,
)


# ============================================================
# ADD BOOK / SERIES
# ============================================================

def add_book(
    title,
    author,
    epub_path=None,
    cover_path=None,
    file_path=None,
    file_format="epub",
    category="light_novel",
    page_count=None,
):
    target_path = (
        file_path
        or epub_path
    )

    if not target_path:
        raise ValueError(
            "A book file path is required."
        )

    legacy_path = (
        epub_path
        or target_path
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM books
        WHERE
            file_path = ?
            OR epub_path = ?
        """,
        (
            target_path,
            legacy_path,
        ),
    )

    existing = cursor.fetchone()

    if existing:
        connection.close()
        return False

    cursor.execute(
        """
        INSERT INTO books (
            title,
            author,
            epub_path,
            cover_path,
            file_path,
            file_format,
            category,
            page_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            author,
            legacy_path,
            cover_path,
            target_path,
            file_format,
            category,
            page_count,
        ),
    )

    connection.commit()

    book_id = cursor.lastrowid

    connection.close()

    return book_id


# ============================================================
# UPDATE BOOK DETAILS
# ============================================================

def update_book_details(
    book_id,
    title,
    author,
    cover_path,
):
    """
    Update editable Library information.

    Works with EPUB, Manga and Manhwa.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE books
        SET
            title = ?,
            author = ?,
            cover_path = ?
        WHERE id = ?
        """,
        (
            title,
            author,
            cover_path,
            book_id,
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# ADD COMIC CHAPTER
# ============================================================

def add_comic_chapter(
    book_id,
    chapter_index,
    title,
    file_path,
    page_count,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO comic_chapters (
            book_id,
            chapter_index,
            title,
            file_path,
            page_count
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            book_id,
            chapter_index,
            title,
            file_path,
            page_count,
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# GET COMIC CHAPTERS
# ============================================================

def get_comic_chapters(
    book_id,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM comic_chapters
        WHERE book_id = ?
        ORDER BY chapter_index ASC
        """,
        (
            book_id,
        ),
    )

    chapters = cursor.fetchall()

    connection.close()

    return chapters


# ============================================================
# GET ALL BOOKS
# ============================================================

def get_all_books():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM books
        ORDER BY date_added DESC
        """
    )

    books = cursor.fetchall()

    connection.close()

    return books


# ============================================================
# GET BOOKS BY CATEGORY
# ============================================================

def get_books_by_category(
    category,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM books
        WHERE category = ?
        ORDER BY date_added DESC
        """,
        (
            category,
        ),
    )

    books = cursor.fetchall()

    connection.close()

    return books


# ============================================================
# SEARCH
# ============================================================

def search_books(
    query,
    category=None,
):
    query = (
        query.strip()
        if query
        else ""
    )

    connection = get_connection()
    cursor = connection.cursor()

    if not query:

        if category:

            cursor.execute(
                """
                SELECT *
                FROM books
                WHERE category = ?
                ORDER BY date_added DESC
                """,
                (
                    category,
                ),
            )

        else:

            cursor.execute(
                """
                SELECT *
                FROM books
                ORDER BY date_added DESC
                """
            )

    else:

        search_value = (
            f"%{query}%"
        )

        if category:

            cursor.execute(
                """
                SELECT *
                FROM books
                WHERE
                    category = ?
                    AND (
                        title LIKE ?
                            COLLATE NOCASE

                        OR author LIKE ?
                            COLLATE NOCASE
                    )
                ORDER BY date_added DESC
                """,
                (
                    category,
                    search_value,
                    search_value,
                ),
            )

        else:

            cursor.execute(
                """
                SELECT *
                FROM books
                WHERE
                    title LIKE ?
                        COLLATE NOCASE

                    OR author LIKE ?
                        COLLATE NOCASE

                ORDER BY date_added DESC
                """,
                (
                    search_value,
                    search_value,
                ),
            )

    books = cursor.fetchall()

    connection.close()

    return books


# ============================================================
# GET BY FILE PATH
# ============================================================

def get_book_by_file_path(
    file_path,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM books
        WHERE
            file_path = ?
            OR epub_path = ?
        """,
        (
            file_path,
            file_path,
        ),
    )

    book = cursor.fetchone()

    connection.close()

    return book


def get_book_by_library_identity(
    title,
    author,
    file_format,
    category,
):
    """
    Return an existing Library item that represents the same
    logical book/series.

    The stored file path is intentionally NOT part of this
    comparison. That lets Litenova detect a duplicate even when
    the source file was renamed outside the app.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM books
        WHERE
            TRIM(title) = TRIM(?)
                COLLATE NOCASE
            AND TRIM(COALESCE(author, '')) = TRIM(COALESCE(?, ''))
                COLLATE NOCASE
            AND TRIM(COALESCE(file_format, '')) = TRIM(COALESCE(?, ''))
                COLLATE NOCASE
            AND TRIM(COALESCE(category, '')) = TRIM(COALESCE(?, ''))
                COLLATE NOCASE
        ORDER BY id ASC
        LIMIT 1
        """,
        (
            title,
            author,
            file_format,
            category,
        ),
    )

    book = cursor.fetchone()

    connection.close()

    return book


# ============================================================
# OLD EPUB LOOKUP
# ============================================================

def get_book_by_epub_path(
    epub_path,
):
    return get_book_by_file_path(
        epub_path
    )


# ============================================================
# GET BY ID
# ============================================================

def get_book_by_id(
    book_id,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM books
        WHERE id = ?
        """,
        (
            book_id,
        ),
    )

    book = cursor.fetchone()

    connection.close()

    return book


# ============================================================
# DELETE
# ============================================================

def delete_book(
    book_id,
):
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

    cursor.execute(
        """
        DELETE FROM comic_chapters
        WHERE book_id = ?
        """,
        (
            book_id,
        ),
    )

    cursor.execute(
        """
        DELETE FROM books
        WHERE id = ?
        """,
        (
            book_id,
        ),
    )

    connection.commit()
    connection.close()