from app.database.database import get_connection


# ============================================================
# ADD BOOK
# ============================================================

def add_book(
    title,
    author,
    epub_path,
    cover_path=None,
):
    """
    Add a book to the local SQLite library.

    Returns:
        True  -> book was added
        False -> book already exists
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM books
        WHERE epub_path = ?
        """,
        (epub_path,),
    )

    existing_book = cursor.fetchone()

    if existing_book:
        connection.close()
        return False

    cursor.execute(
        """
        INSERT INTO books (
            title,
            author,
            epub_path,
            cover_path
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            title,
            author,
            epub_path,
            cover_path,
        ),
    )

    connection.commit()
    connection.close()

    return True


# ============================================================
# GET BOOK BY EPUB PATH
# ============================================================

def get_book_by_epub_path(
    epub_path,
):
    """
    Find a book using its stored EPUB path.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM books
        WHERE epub_path = ?
        """,
        (epub_path,),
    )

    book = cursor.fetchone()

    connection.close()

    return book


# ============================================================
# GET ALL BOOKS
# ============================================================

def get_all_books():
    """
    Return all books in the Library.
    """

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
# SEARCH BOOKS
# ============================================================

def search_books(
    query,
):
    """
    Search by title or author.
    """

    query = query.strip()

    if not query:
        return get_all_books()

    connection = get_connection()
    cursor = connection.cursor()

    search_value = (
        f"%{query}%"
    )

    cursor.execute(
        """
        SELECT *
        FROM books
        WHERE
            title LIKE ? COLLATE NOCASE
            OR author LIKE ? COLLATE NOCASE
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
# DELETE BOOK
# ============================================================

def delete_book(
    book_id,
):
    """
    Delete reading progress and the book record.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM reading_progress
        WHERE book_id = ?
        """,
        (book_id,),
    )

    cursor.execute(
        """
        DELETE FROM books
        WHERE id = ?
        """,
        (book_id,),
    )

    connection.commit()
    connection.close()