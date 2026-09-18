from pathlib import Path

import shutil
import uuid

from app.services.epub_service import (
    read_epub_metadata,
    extract_cover,
)

from app.services.path_service import (
    get_data_dir,
)

from app.database.books_repository import (
    add_book,
    get_book_by_epub_path,
)


DATA_DIR = get_data_dir()

BOOKS_DIR = (
    DATA_DIR
    / "books"
)

COVERS_DIR = (
    DATA_DIR
    / "covers"
)


# ============================================================
# IMPORT ERRORS
# ============================================================

class EPUBImportError(
    Exception
):
    pass


class DuplicateBookError(
    EPUBImportError
):
    pass


class InvalidEPUBError(
    EPUBImportError
):
    pass


# ============================================================
# DESTINATION PATH
# ============================================================

def create_destination_path(
    source_path,
):
    """
    Create a safe destination path for
    the copied EPUB.
    """

    destination = (
        BOOKS_DIR
        / source_path.name
    )

    if not destination.exists():
        return destination

    existing_book = (
        get_book_by_epub_path(
            str(destination)
        )
    )

    if existing_book:

        raise DuplicateBookError(
            (
                "This EPUB is already "
                "in your library."
            )
        )

    unique_name = (
        f"{source_path.stem}_"
        f"{uuid.uuid4().hex[:8]}"
        f"{source_path.suffix}"
    )

    return (
        BOOKS_DIR
        / unique_name
    )


# ============================================================
# IMPORT EPUB
# ============================================================

def import_epub(
    source_path,
):
    """
    Validate, copy and register an EPUB.
    """

    BOOKS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    COVERS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_path = Path(
        source_path
    )

    # ========================================================
    # VALIDATE SOURCE
    # ========================================================

    if not source_path.exists():

        raise EPUBImportError(
            (
                "The selected file "
                "no longer exists."
            )
        )

    if not source_path.is_file():

        raise EPUBImportError(
            (
                "The selected path "
                "is not a file."
            )
        )

    if (
        source_path.suffix.lower()
        != ".epub"
    ):

        raise InvalidEPUBError(
            (
                "Litenova only supports "
                "EPUB files."
            )
        )

    # ========================================================
    # VALIDATE EPUB
    # ========================================================

    try:

        metadata = (
            read_epub_metadata(
                source_path
            )
        )

    except Exception as error:

        raise InvalidEPUBError(
            (
                "The selected file could not "
                "be read as a valid EPUB."
            )
        ) from error

    # ========================================================
    # CLEAN METADATA
    # ========================================================

    title = (
        metadata.get("title")
        or "Unknown Title"
    )

    author = (
        metadata.get("author")
        or "Unknown Author"
    )

    title = str(
        title
    ).strip()

    author = str(
        author
    ).strip()

    if not title:
        title = (
            "Unknown Title"
        )

    if author.lower() in [
        "",
        "unknown",
        "<unknown>",
        "none",
    ]:

        author = (
            "Unknown Author"
        )

    metadata["title"] = (
        title
    )

    metadata["author"] = (
        author
    )

    # ========================================================
    # DESTINATION
    # ========================================================

    destination_path = (
        create_destination_path(
            source_path
        )
    )

    cover_path = None

    copied_epub = False

    try:

        # ====================================================
        # COPY EPUB
        # ====================================================

        shutil.copy2(
            source_path,
            destination_path,
        )

        copied_epub = True

        # ====================================================
        # COVER
        # ====================================================

        try:

            cover = extract_cover(
                destination_path
            )

        except Exception:

            cover = None

        if cover:

            extension = (
                cover.get(
                    "extension"
                )
                or ".jpg"
            )

            if not extension.startswith(
                "."
            ):

                extension = (
                    "."
                    + extension
                )

            cover_filename = (
                f"{uuid.uuid4().hex}"
                f"{extension}"
            )

            cover_file = (
                COVERS_DIR
                / cover_filename
            )

            cover_file.write_bytes(
                cover["data"]
            )

            cover_path = str(
                cover_file
            )

        # ====================================================
        # DATABASE
        # ====================================================

        added = add_book(
            title=title,
            author=author,
            epub_path=str(
                destination_path
            ),
            cover_path=cover_path,
        )

        if not added:

            raise DuplicateBookError(
                (
                    "This EPUB is already "
                    "in your library."
                )
            )

    except Exception:

        # ====================================================
        # CLEAN FAILED COVER
        # ====================================================

        if cover_path:

            cover_file = Path(
                cover_path
            )

            if cover_file.exists():

                try:
                    cover_file.unlink()

                except OSError:
                    pass

        # ====================================================
        # CLEAN FAILED EPUB
        # ====================================================

        if copied_epub:

            if destination_path.exists():

                try:
                    destination_path.unlink()

                except OSError:
                    pass

        raise

    metadata[
        "epub_path"
    ] = str(
        destination_path
    )

    metadata[
        "cover_path"
    ] = cover_path

    return metadata