from pathlib import Path

from app.database.books_repository import (
    delete_book,
)


def remove_book(
    book,
):
    """
    Completely remove a book from Litenova.

    Removes:
    - local EPUB copy
    - extracted cover
    - reading progress
    - books database record
    """

    book_id = book["id"]

    epub_path = book[
        "epub_path"
    ]

    cover_path = book[
        "cover_path"
    ]

    # ========================================================
    # DELETE EPUB
    # ========================================================

    if epub_path:

        epub_file = Path(
            epub_path
        )

        if epub_file.exists():

            try:
                epub_file.unlink()

            except OSError as error:

                raise RuntimeError(
                    (
                        "The EPUB file could not "
                        "be deleted. It may currently "
                        "be in use."
                    )
                ) from error

    # ========================================================
    # DELETE COVER
    # ========================================================

    if cover_path:

        cover_file = Path(
            cover_path
        )

        if cover_file.exists():

            try:
                cover_file.unlink()

            except OSError:

                # A leftover cover is not serious
                # enough to stop database removal.
                pass

    # ========================================================
    # DELETE DATABASE RECORDS
    # ========================================================

    delete_book(
        book_id
    )