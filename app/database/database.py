import sqlite3

from app.services.path_service import (
    get_data_dir,
)


DATA_DIR = get_data_dir()

DATABASE_PATH = (
    DATA_DIR
    / "litenova.db"
)


def get_connection():
    """
    Create a SQLite connection to the
    local Litenova database.
    """

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


def initialize_database():
    """
    Create the required Litenova tables.
    Existing tables and data are preserved.
    """

    connection = (
        get_connection()
    )

    cursor = (
        connection.cursor()
    )

    # ========================================================
    # BOOKS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            epub_path TEXT NOT NULL UNIQUE,
            cover_path TEXT,
            date_added TEXT DEFAULT CURRENT_TIMESTAMP
        )
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