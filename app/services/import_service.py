import re
import shutil
import uuid

from pathlib import Path

from app.services.epub_service import (
    read_epub_metadata,
    extract_cover,
)

from app.services.cbz_service import (
    read_cbz_metadata,
    extract_cbz_cover,
    natural_sort_key,
    InvalidCBZError,
)

from app.services.path_service import (
    get_data_dir,
)

from app.database.books_repository import (
    add_book,
    add_comic_chapter,
    delete_book,
    get_book_by_file_path,
    get_book_by_library_identity,
)


# ============================================================
# STORAGE DIRECTORIES
# ============================================================

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

class BookImportError(Exception):
    """
    Base error for Litenova imports.
    """


class DuplicateBookError(
    BookImportError
):
    """
    Raised when a book or comic series
    already exists in the Library.
    """


class InvalidBookError(
    BookImportError
):
    """
    Raised when the selected book cannot
    be read.
    """


class UnsupportedFormatError(
    BookImportError
):
    """
    Raised when a selected file is not
    EPUB or CBZ.
    """


# ============================================================
# NORMALIZE TITLE
# ============================================================

def normalize_title(
    title,
    fallback,
):
    if title is None:
        return fallback

    title = str(
        title
    ).strip()

    if not title:
        return fallback

    return title


# ============================================================
# NORMALIZE AUTHOR
# ============================================================

def normalize_author(
    author,
):
    if author is None:
        return "Unknown Author"

    author = str(
        author
    ).strip()

    if author.lower() in [
        "",
        "unknown",
        "<unknown>",
        "none",
    ]:
        return "Unknown Author"

    return author


# ============================================================
# CREATE DESTINATION FOR ONE FILE
# ============================================================

def create_destination_path(
    source_path,
):
    """
    Create a unique internal destination for one EPUB/CBZ.

    Duplicate detection is handled separately using Library
    metadata. A filename collision by itself does not mean that
    two books are the same book.
    """

    destination = (
        BOOKS_DIR
        / source_path.name
    )

    if (
        not destination.exists()
        and not get_book_by_file_path(
            str(destination)
        )
    ):
        return destination

    counter = 2

    while True:

        candidate = (
            BOOKS_DIR
            / (
                f"{source_path.stem}_"
                f"{counter}"
                f"{source_path.suffix.lower()}"
            )
        )

        if (
            not candidate.exists()
            and not get_book_by_file_path(
                str(candidate)
            )
        ):
            return candidate

        counter += 1


# ============================================================
# CREATE DESTINATION FOR ONE SERIES
# ============================================================

def create_series_destination(
    safe_folder_name,
):
    """
    Return an unused internal folder for a Manga/Manhwa series.
    """

    destination = (
        BOOKS_DIR
        / safe_folder_name
    )

    if (
        not destination.exists()
        and not get_book_by_file_path(
            str(destination)
        )
    ):
        return destination

    counter = 2

    while True:

        candidate = (
            BOOKS_DIR
            / f"{safe_folder_name}_{counter}"
        )

        if (
            not candidate.exists()
            and not get_book_by_file_path(
                str(candidate)
            )
        ):
            return candidate

        counter += 1


# ============================================================
# SAVE COVER
# ============================================================

def save_cover(
    cover,
):
    """
    Save extracted cover image data.

    Returns the saved cover path,
    or None when no cover exists.
    """

    if not cover:
        return None

    cover_data = cover.get(
        "data"
    )

    if not cover_data:
        return None

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
        f"{extension.lower()}"
    )

    cover_file = (
        COVERS_DIR
        / cover_filename
    )

    cover_file.write_bytes(
        cover_data
    )

    return str(
        cover_file
    )


# ============================================================
# PREPARE EPUB
# ============================================================

def prepare_epub(
    source_path,
):
    """
    Read EPUB metadata and cover information.
    """

    try:
        metadata = (
            read_epub_metadata(
                source_path
            )
        )

    except Exception as error:
        raise InvalidBookError(
            (
                "The selected file could not "
                "be read as a valid EPUB."
            )
        ) from error

    title = normalize_title(
        metadata.get(
            "title"
        ),
        source_path.stem,
    )

    author = normalize_author(
        metadata.get(
            "author"
        )
    )

    try:
        cover = extract_cover(
            source_path
        )

    except Exception:
        cover = None

    return {
        "title": title,
        "author": author,
        "file_format": "epub",
        "category": "light_novel",
        "page_count": None,
        "cover": cover,
    }


# ============================================================
# PREPARE CBZ
# ============================================================

def prepare_cbz(
    source_path,
    category,
):
    """
    Read CBZ metadata and cover information.

    category must be:
        manga
        manhwa
    """

    if category not in [
        "manga",
        "manhwa",
    ]:
        raise BookImportError(
            (
                "CBZ files must be categorized "
                "as Manga or Manhwa."
            )
        )

    try:
        metadata = (
            read_cbz_metadata(
                source_path
            )
        )

    except InvalidCBZError as error:
        raise InvalidBookError(
            str(error)
        ) from error

    except Exception as error:
        raise InvalidBookError(
            (
                "The selected file could not "
                "be read as a valid CBZ."
            )
        ) from error

    title = normalize_title(
        metadata.get(
            "title"
        ),
        source_path.stem,
    )

    author = normalize_author(
        metadata.get(
            "author"
        )
    )

    page_count = metadata.get(
        "page_count"
    )

    try:
        page_count = int(
            page_count
        )

    except (
        TypeError,
        ValueError,
    ):
        page_count = None

    try:
        cover = extract_cbz_cover(
            source_path
        )

    except Exception:
        cover = None

    return {
        "title": title,
        "author": author,
        "file_format": "cbz",
        "category": category,
        "page_count": page_count,
        "cover": cover,
    }


# ============================================================
# IMPORT ONE BOOK FILE
# ============================================================

def import_book(
    source_path,
    category=None,
    allow_duplicate=False,
):
    """
    Import one EPUB or one CBZ.

    EPUB:
        automatically becomes Light Novel

    CBZ:
        must be Manga or Manhwa
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
        raise BookImportError(
            (
                "The selected file "
                "no longer exists."
            )
        )

    if not source_path.is_file():
        raise BookImportError(
            (
                "The selected path "
                "is not a file."
            )
        )

    extension = (
        source_path
        .suffix
        .lower()
    )

    # ========================================================
    # READ METADATA
    # ========================================================

    if extension == ".epub":

        book_data = prepare_epub(
            source_path
        )

    elif extension == ".cbz":

        book_data = prepare_cbz(
            source_path,
            category,
        )

    else:

        raise UnsupportedFormatError(
            (
                "Litenova currently supports "
                "EPUB and CBZ files only."
            )
        )

    # ========================================================
    # DUPLICATE LIBRARY ITEM
    # ========================================================

    existing_book = (
        get_book_by_library_identity(
            title=book_data[
                "title"
            ],
            author=book_data[
                "author"
            ],
            file_format=book_data[
                "file_format"
            ],
            category=book_data[
                "category"
            ],
        )
    )

    if (
        existing_book
        and not allow_duplicate
    ):
        raise DuplicateBookError(
            (
                "This item is already "
                "in your Library."
            )
        )

    # ========================================================
    # DESTINATION
    # ========================================================

    destination_path = (
        create_destination_path(
            source_path
        )
    )

    copied_file = False
    cover_path = None
    book_id = None

    try:

        # ====================================================
        # COPY FILE
        # ====================================================

        shutil.copy2(
            source_path,
            destination_path,
        )

        copied_file = True

        # ====================================================
        # COVER
        # ====================================================

        cover_path = save_cover(
            book_data[
                "cover"
            ]
        )

        # ====================================================
        # DATABASE
        # ====================================================

        book_id = add_book(
            title=book_data[
                "title"
            ],

            author=book_data[
                "author"
            ],

            # Legacy database compatibility.
            epub_path=str(
                destination_path
            ),

            file_path=str(
                destination_path
            ),

            file_format=book_data[
                "file_format"
            ],

            category=book_data[
                "category"
            ],

            cover_path=cover_path,

            page_count=book_data[
                "page_count"
            ],
        )

        if not book_id:
            raise DuplicateBookError(
                (
                    "This book is already "
                    "in your library."
                )
            )

        # ====================================================
        # SINGLE CBZ = ONE COMIC CHAPTER
        # ====================================================

        if (
            book_data[
                "file_format"
            ]
            == "cbz"
        ):
            add_comic_chapter(
                book_id=book_id,
                chapter_index=0,
                title=book_data[
                    "title"
                ],
                file_path=str(
                    destination_path
                ),
                page_count=(
                    book_data[
                        "page_count"
                    ]
                    or 0
                ),
            )

    except Exception:

        # Delete database record if it was created.
        if book_id:

            try:
                delete_book(
                    book_id
                )

            except Exception:
                pass

        # Delete extracted cover.
        if cover_path:

            cover_file = Path(
                cover_path
            )

            if cover_file.exists():

                try:
                    cover_file.unlink()

                except OSError:
                    pass

        # Delete copied book.
        if copied_file:

            if destination_path.exists():

                try:
                    destination_path.unlink()

                except OSError:
                    pass

        raise

    return {
        "title": book_data[
            "title"
        ],

        "author": book_data[
            "author"
        ],

        "file_format": book_data[
            "file_format"
        ],

        "category": book_data[
            "category"
        ],

        "page_count": book_data[
            "page_count"
        ],

        "file_path": str(
            destination_path
        ),

        "cover_path": cover_path,

        "book_id": book_id,
    }


# ============================================================
# IMPORT WHOLE CBZ FOLDER
# ============================================================

def import_cbz_folder(
    folder_path,
    category,
    allow_duplicate=False,
):
    """
    Import a folder where each CBZ file
    represents one Manga/Manhwa chapter.

    Example:

        Solo Leveling/
            Chapter 001.cbz
            Chapter 002.cbz
            Chapter 003.cbz

    becomes ONE Library entry:

        Solo Leveling
            Chapter 001
            Chapter 002
            Chapter 003
    """

    if category not in [
        "manga",
        "manhwa",
    ]:
        raise BookImportError(
            (
                "Comic folders must be "
                "Manga or Manhwa."
            )
        )

    source_folder = Path(
        folder_path
    )

    # ========================================================
    # VALIDATE FOLDER
    # ========================================================

    if not source_folder.exists():

        raise BookImportError(
            (
                "The selected folder "
                "does not exist."
            )
        )

    if not source_folder.is_dir():

        raise BookImportError(
            (
                "The selected path "
                "is not a folder."
            )
        )

    # ========================================================
    # FIND CBZ FILES
    # ========================================================

    cbz_files = [
        path
        for path in source_folder.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            == ".cbz"
        )
    ]

    cbz_files.sort(
        key=lambda path: (
            natural_sort_key(
                path.name
            )
        )
    )

    if not cbz_files:

        raise BookImportError(
            (
                "This folder does not contain "
                "any CBZ files."
            )
        )

    # ========================================================
    # SERIES TITLE
    # ========================================================

    series_title = (
        source_folder.name
    )

    safe_folder_name = re.sub(
        r'[<>:"/\\|?*]+',
        "_",
        series_title,
    ).strip()

    if not safe_folder_name:
        safe_folder_name = (
            "Comic"
        )

    # The actual duplicate decision is made after chapter
    # metadata is read, because the author is part of the
    # Library identity check.

    # ========================================================
    # VALIDATE EVERY CHAPTER BEFORE COPYING
    # ========================================================

    chapter_data = []

    total_pages = 0

    series_author = (
        "Unknown Author"
    )

    first_cover = None

    for index, cbz_file in enumerate(
        cbz_files
    ):

        data = prepare_cbz(
            cbz_file,
            category,
        )

        page_count = (
            data[
                "page_count"
            ]
            or 0
        )

        total_pages += (
            page_count
        )

        # Use the first available author.
        if (
            series_author
            == "Unknown Author"
            and data[
                "author"
            ]
            != "Unknown Author"
        ):
            series_author = (
                data[
                    "author"
                ]
            )

        # First chapter provides the cover.
        if index == 0:
            first_cover = (
                data[
                    "cover"
                ]
            )

        # Prefer the CBZ filename as chapter
        # title because comic metadata sometimes
        # repeats the series title for every file.
        chapter_title = (
            cbz_file.stem
        )

        chapter_data.append(
            {
                "source": cbz_file,
                "title": chapter_title,
                "page_count": page_count,
            }
        )

    # ========================================================
    # DUPLICATE LIBRARY SERIES
    # ========================================================

    existing_series = (
        get_book_by_library_identity(
            title=series_title,
            author=series_author,
            file_format="cbz",
            category=category,
        )
    )

    if (
        existing_series
        and not allow_duplicate
    ):
        raise DuplicateBookError(
            (
                "This Manga/Manhwa series "
                "is already in your Library."
            )
        )

    # ========================================================
    # CREATE DESTINATION FOLDER
    # ========================================================

    destination_folder = (
        create_series_destination(
            safe_folder_name
        )
    )

    destination_folder.mkdir(
        parents=True,
        exist_ok=False,
    )

    cover_path = None
    book_id = None

    try:

        copied_chapters = []

        # ====================================================
        # COPY CHAPTER CBZ FILES
        # ====================================================

        for chapter in chapter_data:

            destination = (
                destination_folder
                / chapter[
                    "source"
                ].name
            )

            shutil.copy2(
                chapter[
                    "source"
                ],
                destination,
            )

            copied_chapters.append(
                {
                    "title": chapter[
                        "title"
                    ],

                    "file_path": str(
                        destination
                    ),

                    "page_count": chapter[
                        "page_count"
                    ],
                }
            )

        # ====================================================
        # SAVE SERIES COVER
        # ====================================================

        cover_path = save_cover(
            first_cover
        )

        # ====================================================
        # CREATE ONE LIBRARY ENTRY
        # ====================================================

        book_id = add_book(
            title=series_title,

            author=series_author,

            # Old epub_path column is still NOT NULL.
            epub_path=str(
                destination_folder
            ),

            file_path=str(
                destination_folder
            ),

            file_format="cbz",

            category=category,

            cover_path=cover_path,

            page_count=total_pages,
        )

        if not book_id:

            raise DuplicateBookError(
                (
                    "This comic series is already "
                    "in your library."
                )
            )

        # ====================================================
        # CREATE CHAPTER DATABASE RECORDS
        # ====================================================

        for index, chapter in enumerate(
            copied_chapters
        ):

            add_comic_chapter(
                book_id=book_id,

                chapter_index=index,

                title=chapter[
                    "title"
                ],

                file_path=chapter[
                    "file_path"
                ],

                page_count=chapter[
                    "page_count"
                ],
            )

    except Exception:

        # ====================================================
        # REMOVE DATABASE ENTRY
        # ====================================================

        if book_id:

            try:
                delete_book(
                    book_id
                )

            except Exception:
                pass

        # ====================================================
        # REMOVE COVER
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
        # REMOVE COPIED SERIES FOLDER
        # ====================================================

        if destination_folder.exists():

            shutil.rmtree(
                destination_folder,
                ignore_errors=True,
            )

        raise

    # ========================================================
    # SUCCESS
    # ========================================================

    return {
        "title": series_title,

        "author": series_author,

        "file_format": "cbz",

        "category": category,

        "chapter_count": len(
            chapter_data
        ),

        "page_count": total_pages,

        "file_path": str(
            destination_folder
        ),

        "cover_path": cover_path,

        "book_id": book_id,
    }


# ============================================================
# OLD EPUB COMPATIBILITY
# ============================================================

def import_epub(
    source_path,
    allow_duplicate=False,
):
    """
    Compatibility wrapper used by older
    parts of Litenova.
    """

    return import_book(
        source_path,
        category="light_novel",
        allow_duplicate=allow_duplicate,
    )