import sqlite3

from app.services.path_service import (
    get_data_dir,
)


DATA_DIR = get_data_dir()

DATABASE_PATH = (
    DATA_DIR
    / "litenova.db"
)


# ============================================================
# CONNECTION
# ============================================================

def get_connection():
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# ============================================================
# COLUMN CHECK
# ============================================================

def column_exists(
    connection,
    table_name,
    column_name,
):
    cursor = connection.cursor()

    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    columns = cursor.fetchall()

    for column in columns:

        if (
            column["name"]
            == column_name
        ):
            return True

    return False


# ============================================================
# MIGRATE BOOKS
# ============================================================

def migrate_books_table(
    connection,
):
    cursor = connection.cursor()

    # --------------------------------------------------------
    # GENERIC FILE PATH
    # --------------------------------------------------------

    if not column_exists(
        connection,
        "books",
        "file_path",
    ):
        cursor.execute("""
            ALTER TABLE books
            ADD COLUMN file_path TEXT
        """)

    # --------------------------------------------------------
    # FORMAT
    # --------------------------------------------------------

    if not column_exists(
        connection,
        "books",
        "file_format",
    ):
        cursor.execute("""
            ALTER TABLE books
            ADD COLUMN file_format TEXT
            DEFAULT 'epub'
        """)

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    if not column_exists(
        connection,
        "books",
        "category",
    ):
        cursor.execute("""
            ALTER TABLE books
            ADD COLUMN category TEXT
            DEFAULT 'light_novel'
        """)

    # --------------------------------------------------------
    # PAGE COUNT
    # --------------------------------------------------------

    if not column_exists(
        connection,
        "books",
        "page_count",
    ):
        cursor.execute("""
            ALTER TABLE books
            ADD COLUMN page_count INTEGER
        """)

    # --------------------------------------------------------
    # MIGRATE OLD EPUBS
    # --------------------------------------------------------

    cursor.execute("""
        UPDATE books
        SET file_path = epub_path
        WHERE
            file_path IS NULL
            OR TRIM(file_path) = ''
    """)

    cursor.execute("""
        UPDATE books
        SET file_format = 'epub'
        WHERE
            file_format IS NULL
            OR TRIM(file_format) = ''
    """)

    cursor.execute("""
        UPDATE books
        SET category = 'light_novel'
        WHERE
            category IS NULL
            OR TRIM(category) = ''
    """)

    # --------------------------------------------------------
    # INDEXES
    # --------------------------------------------------------

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_books_file_path
        ON books(file_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_books_file_format
        ON books(file_format)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_books_category
        ON books(category)
    """)


# ============================================================
# INITIALIZE
# ============================================================

def initialize_database():

    connection = get_connection()

    cursor = connection.cursor()

    # ========================================================
    # BOOKS / SERIES
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            author TEXT,

            epub_path TEXT NOT NULL UNIQUE,

            cover_path TEXT,

            date_added TEXT
                DEFAULT CURRENT_TIMESTAMP
        )
    """)

    migrate_books_table(
        connection
    )

    # ========================================================
    # COMIC CHAPTERS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comic_chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            book_id INTEGER NOT NULL,

            chapter_index INTEGER NOT NULL,

            title TEXT NOT NULL,

            file_path TEXT NOT NULL,

            page_count INTEGER DEFAULT 0,

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE,

            UNIQUE (
                book_id,
                chapter_index
            )
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_comic_chapters_book
        ON comic_chapters(book_id)
    """)

    # ========================================================
    # READING PROGRESS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reading_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            book_id INTEGER NOT NULL UNIQUE,

            chapter_index INTEGER DEFAULT 0,

            position REAL DEFAULT 0,

            last_read TEXT,

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE
        )
    """)

    # ========================================================
    # SETTINGS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,

            value TEXT
        )
    """)

    connection.commit()

    connection.close()