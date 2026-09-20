import shutil
import uuid

from pathlib import Path

from PIL import Image

from app.services.path_service import (
    get_data_dir,
)

from app.database.books_repository import (
    delete_book,
    update_book_details,
)


DATA_DIR = get_data_dir()

COVERS_DIR = (
    DATA_DIR
    / "covers"
)


SUPPORTED_COVER_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}


# ============================================================
# SAFE BOOK VALUE
# ============================================================

def get_book_value(
    book,
    key,
    default=None,
):
    try:

        if key in book.keys():

            value = book[
                key
            ]

            if value is not None:
                return value

    except Exception:
        pass

    return default


# ============================================================
# COPY NEW COVER
# ============================================================

def copy_new_cover(
    source_path,
):
    """
    Validate and copy a custom cover into
    Litenova's local covers directory.
    """

    source_path = Path(
        source_path
    )

    if not source_path.exists():

        raise ValueError(
            "The selected cover image does not exist."
        )

    if not source_path.is_file():

        raise ValueError(
            "The selected cover is not a file."
        )

    extension = (
        source_path
        .suffix
        .lower()
    )

    if (
        extension
        not in SUPPORTED_COVER_EXTENSIONS
    ):

        raise ValueError(
            (
                "Cover must be JPG, JPEG, PNG, "
                "WEBP, or BMP."
            )
        )

    # Verify this is actually an image.
    try:

        with Image.open(
            source_path
        ) as image:

            image.verify()

    except Exception as error:

        raise ValueError(
            (
                "The selected file could not "
                "be read as an image."
            )
        ) from error

    COVERS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        COVERS_DIR
        / (
            uuid.uuid4().hex
            + extension
        )
    )

    shutil.copy2(
        source_path,
        destination,
    )

    return str(
        destination
    )


# ============================================================
# CHECK IF COVER BELONGS TO LITENOVA
# ============================================================

def is_litenova_cover(
    cover_path,
):
    if not cover_path:
        return False

    try:

        cover = Path(
            cover_path
        ).resolve()

        covers_directory = (
            COVERS_DIR.resolve()
        )

        return (
            covers_directory
            in cover.parents
        )

    except Exception:

        return False


# ============================================================
# EDIT BOOK
# ============================================================

def edit_book_details(
    book,
    title,
    author,
    new_cover_path=None,
):
    """
    Update title, author and optionally cover.

    If no new cover is selected, the existing
    cover remains unchanged.
    """

    title = str(
        title
    ).strip()

    author = str(
        author
    ).strip()

    if not title:

        raise ValueError(
            "The title cannot be empty."
        )

    if not author:

        author = (
            "Unknown Author"
        )

    old_cover_path = get_book_value(
        book,
        "cover_path"
    )

    final_cover_path = (
        old_cover_path
    )

    created_cover_path = None

    # ========================================================
    # NEW COVER
    # ========================================================

    if new_cover_path:

        created_cover_path = (
            copy_new_cover(
                new_cover_path
            )
        )

        final_cover_path = (
            created_cover_path
        )

    # ========================================================
    # DATABASE UPDATE
    # ========================================================

    try:

        update_book_details(
            book_id=book[
                "id"
            ],
            title=title,
            author=author,
            cover_path=final_cover_path,
        )

    except Exception:

        # Remove newly-created cover if database
        # update fails.
        if created_cover_path:

            new_cover = Path(
                created_cover_path
            )

            if new_cover.exists():

                try:
                    new_cover.unlink()

                except OSError:
                    pass

        raise

    # ========================================================
    # REMOVE OLD COVER
    # ========================================================

    if (
        created_cover_path
        and old_cover_path
        and old_cover_path
        != created_cover_path
        and is_litenova_cover(
            old_cover_path
        )
    ):

        old_cover = Path(
            old_cover_path
        )

        if old_cover.exists():

            try:
                old_cover.unlink()

            except OSError:
                pass


# ============================================================
# REMOVE BOOK
# ============================================================

def remove_book(
    book,
):
    """
    Remove EPUB, single CBZ, or CBZ folder.
    """

    book_id = book[
        "id"
    ]

    stored_path = (
        get_book_value(
            book,
            "file_path"
        )
        or get_book_value(
            book,
            "epub_path"
        )
    )

    cover_path = get_book_value(
        book,
        "cover_path"
    )

    # ========================================================
    # DELETE BOOK FILES
    # ========================================================

    if stored_path:

        stored_file = Path(
            stored_path
        )

        if stored_file.exists():

            try:

                if stored_file.is_dir():

                    shutil.rmtree(
                        stored_file
                    )

                else:

                    stored_file.unlink()

            except OSError as error:

                raise RuntimeError(
                    (
                        "Litenova could not delete "
                        "the stored book files."
                    )
                ) from error

    # ========================================================
    # DELETE COVER
    # ========================================================

    if (
        cover_path
        and is_litenova_cover(
            cover_path
        )
    ):

        cover_file = Path(
            cover_path
        )

        if cover_file.exists():

            try:
                cover_file.unlink()

            except OSError:
                pass

    # ========================================================
    # DELETE DATABASE RECORD
    # ========================================================

    delete_book(
        book_id
    )