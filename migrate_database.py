import sqlite3
from pathlib import Path


DATABASE_PATH = Path(
    "data/litenova.db"
).resolve()


def main():
    print(
        "Database:",
        DATABASE_PATH,
    )

    if not DATABASE_PATH.exists():
        print(
            "ERROR: Database does not exist."
        )
        return

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    cursor = connection.cursor()

    # ========================================================
    # CURRENT COLUMNS
    # ========================================================

    cursor.execute(
        "PRAGMA table_info(books)"
    )

    existing_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    print(
        "Current columns:",
        sorted(existing_columns),
    )

    # ========================================================
    # ADD file_path
    # ========================================================

    if "file_path" not in existing_columns:
        cursor.execute("""
            ALTER TABLE books
            ADD COLUMN file_path TEXT
        """)

        print(
            "Added: file_path"
        )

    else:
        print(
            "Already exists: file_path"
        )

    # ========================================================
    # ADD file_format
    # ========================================================

    if "file_format" not in existing_columns:
        cursor.execute("""
            ALTER TABLE books
            ADD COLUMN file_format TEXT
            DEFAULT 'epub'
        """)

        print(
            "Added: file_format"
        )

    else:
        print(
            "Already exists: file_format"
        )

    # ========================================================
    # ADD category
    # ========================================================

    if "category" not in existing_columns:
        cursor.execute("""
            ALTER TABLE books
            ADD COLUMN category TEXT
            DEFAULT 'light_novel'
        """)

        print(
            "Added: category"
        )

    else:
        print(
            "Already exists: category"
        )

    # ========================================================
    # ADD page_count
    # ========================================================

    if "page_count" not in existing_columns:
        cursor.execute("""
            ALTER TABLE books
            ADD COLUMN page_count INTEGER
        """)

        print(
            "Added: page_count"
        )

    else:
        print(
            "Already exists: page_count"
        )

    connection.commit()

    # ========================================================
    # MIGRATE EXISTING EPUB DATA
    # ========================================================

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

    connection.commit()

    # ========================================================
    # INDEXES
    # ========================================================

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

    connection.commit()

    # ========================================================
    # VERIFY
    # ========================================================

    cursor.execute(
        "PRAGMA table_info(books)"
    )

    final_columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    print()
    print(
        "Final columns:"
    )

    for column in final_columns:
        print(
            " -",
            column,
        )

    print()

    cursor.execute("""
        SELECT
            id,
            title,
            file_format,
            category,
            file_path,
            page_count
        FROM books
    """)

    books = cursor.fetchall()

    print(
        "Existing books:"
    )

    for book in books:
        print(
            book
        )

    connection.close()

    print()
    print(
        "Migration completed successfully."
    )


if __name__ == "__main__":
    main()