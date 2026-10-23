from app.database.database import (
    get_connection,
)


# ============================================================
# CREATE TABLES
# ============================================================

def ensure_custom_category_tables():
    """
    Custom categories are Library organization folders.

    A book can belong to ONE custom category at a time.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # book_id is PRIMARY KEY.
    #
    # That is important because it guarantees
    # that one book can only have one custom
    # category at a time.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS book_custom_category (
            book_id INTEGER PRIMARY KEY,
            category_id INTEGER NOT NULL,

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE,

            FOREIGN KEY (category_id)
                REFERENCES custom_categories(id)
                ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_book_custom_category_category
        ON book_custom_category (
            category_id
        )
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# CREATE CATEGORY
# ============================================================

def create_custom_category(
    name,
):

    name = str(
        name
    ).strip()

    if not name:

        raise ValueError(
            "Category name cannot be empty."
        )

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO custom_categories (
                name
            )
            VALUES (?)
            """,
            (
                name,
            ),
        )

        connection.commit()

        category_id = (
            cursor.lastrowid
        )

    except Exception as error:

        connection.close()

        raise ValueError(
            (
                "A category with this name "
                "already exists."
            )
        ) from error

    connection.close()

    return category_id


# ============================================================
# GET ALL CATEGORIES
# ============================================================

def get_custom_categories():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            custom_categories.id,
            custom_categories.name,
            custom_categories.date_created,
            COUNT(
                book_custom_category.book_id
            ) AS book_count

        FROM custom_categories

        LEFT JOIN book_custom_category
            ON custom_categories.id
            = book_custom_category.category_id

        GROUP BY
            custom_categories.id,
            custom_categories.name,
            custom_categories.date_created

        ORDER BY
            custom_categories.name
            COLLATE NOCASE ASC
        """
    )

    categories = cursor.fetchall()

    connection.close()

    return categories


# ============================================================
# GET ONE CATEGORY
# ============================================================

def get_custom_category(
    category_id,
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM custom_categories
        WHERE id = ?
        """,
        (
            category_id,
        ),
    )

    category = cursor.fetchone()

    connection.close()

    return category


# ============================================================
# GET BOOK CATEGORY
# ============================================================

def get_book_custom_category(
    book_id,
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            custom_categories.id,
            custom_categories.name

        FROM book_custom_category

        INNER JOIN custom_categories
            ON custom_categories.id
            = book_custom_category.category_id

        WHERE
            book_custom_category.book_id = ?
        """,
        (
            book_id,
        ),
    )

    category = cursor.fetchone()

    connection.close()

    return category


# ============================================================
# MOVE BOOK
# ============================================================

def move_book_to_custom_category(
    book_id,
    category_id,
):
    """
    Move a book to a category.

    If the book was previously in another
    category, its old category assignment
    is automatically replaced.

    Example:

        Entrail_Ji
            Novel A

        move Novel A -> Favorites

    Result:

        Entrail_Ji
            empty

        Favorites
            Novel A
    """

    connection = get_connection()
    cursor = connection.cursor()

    # ========================================================
    # VERIFY BOOK
    # ========================================================

    cursor.execute(
        """
        SELECT id
        FROM books
        WHERE id = ?
        """,
        (
            book_id,
        ),
    )

    if cursor.fetchone() is None:

        connection.close()

        raise ValueError(
            "The selected book no longer exists."
        )

    # ========================================================
    # VERIFY CATEGORY
    # ========================================================

    cursor.execute(
        """
        SELECT id
        FROM custom_categories
        WHERE id = ?
        """,
        (
            category_id,
        ),
    )

    if cursor.fetchone() is None:

        connection.close()

        raise ValueError(
            (
                "The selected category "
                "no longer exists."
            )
        )

    # ========================================================
    # REMOVE OLD CATEGORY
    # ========================================================
    #
    # This makes the behavior very explicit.
    #
    # We delete the previous assignment first,
    # then insert the new assignment.
    # ========================================================

    cursor.execute(
        """
        DELETE FROM book_custom_category
        WHERE book_id = ?
        """,
        (
            book_id,
        ),
    )

    # ========================================================
    # ADD NEW CATEGORY
    # ========================================================

    cursor.execute(
        """
        INSERT INTO book_custom_category (
            book_id,
            category_id
        )
        VALUES (?, ?)
        """,
        (
            book_id,
            category_id,
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# REMOVE BOOK FROM CATEGORY
# ============================================================

def remove_book_from_custom_category(
    book_id,
):
    """
    Remove the organizational category only.

    The actual book remains in the Library.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM book_custom_category
        WHERE book_id = ?
        """,
        (
            book_id,
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# BOOKS INSIDE CATEGORY
# ============================================================

def get_books_in_custom_category(
    category_id,
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT books.*

        FROM books

        INNER JOIN book_custom_category
            ON books.id
            = book_custom_category.book_id

        WHERE
            book_custom_category.category_id = ?

        ORDER BY
            books.date_added DESC
        """,
        (
            category_id,
        ),
    )

    books = cursor.fetchall()

    connection.close()

    return books


# ============================================================
# UNCATEGORIZED BOOKS
# ============================================================

def get_uncategorized_books():
    """
    Return books that are not currently inside
    any user-created Library category.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT books.*

        FROM books

        LEFT JOIN book_custom_category
            ON books.id
            = book_custom_category.book_id

        WHERE
            book_custom_category.book_id IS NULL

        ORDER BY
            books.date_added DESC
        """
    )

    books = cursor.fetchall()

    connection.close()

    return books


# ============================================================
# DELETE CATEGORY
# ============================================================

def delete_custom_category(
    category_id,
):
    """
    Delete a custom category.

    Books inside it return to Uncategorized.
    The actual books are NOT deleted.
    """

    connection = get_connection()
    cursor = connection.cursor()

    # Remove assignments.
    cursor.execute(
        """
        DELETE FROM book_custom_category
        WHERE category_id = ?
        """,
        (
            category_id,
        ),
    )

    # Remove category itself.
    cursor.execute(
        """
        DELETE FROM custom_categories
        WHERE id = ?
        """,
        (
            category_id,
        ),
    )

    connection.commit()
    connection.close()