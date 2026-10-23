import io
import re
import zipfile

from pathlib import Path
from xml.etree import ElementTree

from PIL import Image


# ============================================================
# SUPPORTED COMIC IMAGE TYPES
# ============================================================

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
}


# ============================================================
# ERRORS
# ============================================================

class CBZError(Exception):
    """
    Base exception for CBZ-related errors.
    """


class InvalidCBZError(CBZError):
    """
    Raised when a CBZ file cannot be read
    or contains no supported comic pages.
    """


# ============================================================
# NATURAL FILE SORTING
# ============================================================

def natural_sort_key(value):
    """
    Sort comic pages naturally.

    Example:

        1.jpg
        2.jpg
        10.jpg

    instead of:

        1.jpg
        10.jpg
        2.jpg
    """

    parts = re.split(
        r"(\d+)",
        value.lower(),
    )

    return [
        int(part)
        if part.isdigit()
        else part
        for part in parts
    ]


# ============================================================
# IMAGE FILE CHECK
# ============================================================

def is_supported_image(file_name):
    """
    Return True if the archive item is a
    supported comic image.
    """

    suffix = (
        Path(file_name)
        .suffix
        .lower()
    )

    return (
        suffix
        in SUPPORTED_IMAGE_EXTENSIONS
    )


# ============================================================
# GET CBZ PAGES
# ============================================================

def get_cbz_pages(cbz_path):
    """
    Return comic image filenames in
    reading order.
    """

    cbz_path = Path(
        cbz_path
    )

    # --------------------------------------------------------
    # FILE EXISTS
    # --------------------------------------------------------

    if not cbz_path.exists():
        raise InvalidCBZError(
            "The CBZ file does not exist."
        )

    if not cbz_path.is_file():
        raise InvalidCBZError(
            "The selected CBZ path is not a file."
        )

    # --------------------------------------------------------
    # EXTENSION
    # --------------------------------------------------------

    if (
        cbz_path.suffix.lower()
        != ".cbz"
    ):
        raise InvalidCBZError(
            "The selected file is not a CBZ file."
        )

    # --------------------------------------------------------
    # OPEN ARCHIVE
    # --------------------------------------------------------

    try:

        with zipfile.ZipFile(
            cbz_path,
            "r",
        ) as archive:

            archive_names = (
                archive.namelist()
            )

    except (
        zipfile.BadZipFile,
        OSError,
    ) as error:

        raise InvalidCBZError(
            (
                "The selected file is not "
                "a valid CBZ archive."
            )
        ) from error

    # --------------------------------------------------------
    # FIND IMAGES
    # --------------------------------------------------------

    pages = []

    for file_name in archive_names:

        if file_name.endswith("/"):
            continue

        if not is_supported_image(
            file_name
        ):
            continue

        # Ignore common macOS archive metadata.
        if "__MACOSX/" in file_name:
            continue

        if (
            Path(file_name).name
            .startswith(".")
        ):
            continue

        pages.append(
            file_name
        )

    # --------------------------------------------------------
    # SORT PAGES
    # --------------------------------------------------------

    pages.sort(
        key=natural_sort_key
    )

    if not pages:
        raise InvalidCBZError(
            (
                "This CBZ does not contain "
                "any supported image pages."
            )
        )

    return pages


# ============================================================
# COMICINFO.XML
# ============================================================

def read_comic_info(cbz_path):
    """
    Read ComicInfo.xml if it exists.

    ComicInfo.xml is optional, so missing
    metadata is not treated as an error.
    """

    metadata = {
        "title": None,
        "series": None,
        "number": None,
        "author": None,
    }

    try:

        with zipfile.ZipFile(
            cbz_path,
            "r",
        ) as archive:

            comic_info_name = None

            for file_name in archive.namelist():

                if (
                    Path(file_name)
                    .name
                    .lower()
                    == "comicinfo.xml"
                ):
                    comic_info_name = (
                        file_name
                    )

                    break

            # ComicInfo.xml is optional.
            if comic_info_name is None:
                return metadata

            xml_data = archive.read(
                comic_info_name
            )

        root = (
            ElementTree.fromstring(
                xml_data
            )
        )

    except Exception:
        return metadata

    # --------------------------------------------------------
    # XML VALUE HELPER
    # --------------------------------------------------------

    def get_text(tag_name):

        element = root.find(
            tag_name
        )

        if element is None:
            return None

        if element.text is None:
            return None

        value = (
            element.text.strip()
        )

        if not value:
            return None

        return value

    # --------------------------------------------------------
    # METADATA
    # --------------------------------------------------------

    metadata["title"] = (
        get_text("Title")
    )

    metadata["series"] = (
        get_text("Series")
    )

    metadata["number"] = (
        get_text("Number")
    )

    # Try several common creator fields.
    metadata["author"] = (
        get_text("Writer")
        or get_text("Penciller")
        or get_text("Artist")
    )

    return metadata


# ============================================================
# CBZ METADATA
# ============================================================

def read_cbz_metadata(cbz_path):
    """
    Read normalized CBZ metadata.

    Returns:

        {
            "title": "...",
            "author": "...",
            "page_count": 123
        }
    """

    cbz_path = Path(
        cbz_path
    )

    # This also validates the archive.
    pages = get_cbz_pages(
        cbz_path
    )

    comic_info = (
        read_comic_info(
            cbz_path
        )
    )

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title = (
        comic_info.get("title")
        or comic_info.get("series")
        or cbz_path.stem
    )

    if title is None:
        title = cbz_path.stem

    title = str(
        title
    ).strip()

    if not title:
        title = cbz_path.stem

    # --------------------------------------------------------
    # AUTHOR
    # --------------------------------------------------------

    author = (
        comic_info.get("author")
        or "Unknown Author"
    )

    author = str(
        author
    ).strip()

    if not author:
        author = "Unknown Author"

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {
        "title": title,
        "author": author,
        "page_count": len(pages),
    }


# ============================================================
# READ ONE COMIC PAGE
# ============================================================

def read_cbz_page(
    cbz_path,
    page_name,
    archive=None,
):
    """
    Return the raw bytes for one comic page.
    """

    try:

        if archive is not None:
            return archive.read(page_name)

        with zipfile.ZipFile(
            cbz_path,
            "r",
        ) as archive:

            return archive.read(
                page_name
            )

    except KeyError as error:

        raise CBZError(
            (
                "The requested comic page "
                "could not be found."
            )
        ) from error

    except Exception as error:

        raise CBZError(
            (
                "Litenova could not read "
                "this comic page."
            )
        ) from error


# ============================================================
# EXTRACT CBZ COVER
# ============================================================

def extract_cbz_cover(cbz_path):
    """
    Use the first image in the CBZ
    as the comic cover.

    Returns:

        {
            "data": bytes,
            "extension": ".jpg"
        }
    """

    pages = get_cbz_pages(
        cbz_path
    )

    first_page = pages[0]

    image_data = read_cbz_page(
        cbz_path,
        first_page,
    )

    extension = (
        Path(first_page)
        .suffix
        .lower()
    )

    # --------------------------------------------------------
    # VERIFY IMAGE
    # --------------------------------------------------------

    try:

        with Image.open(
            io.BytesIO(
                image_data
            )
        ) as image:

            image.verify()

    except Exception as error:

        raise InvalidCBZError(
            (
                "The first image in this CBZ "
                "could not be decoded."
            )
        ) from error

    return {
        "data": image_data,
        "extension": extension,
    }


# ============================================================
# VALIDATE CBZ
# ============================================================

def validate_cbz(cbz_path):
    """
    Validate a CBZ and return information
    useful to Litenova.
    """

    pages = get_cbz_pages(
        cbz_path
    )

    metadata = (
        read_cbz_metadata(
            cbz_path
        )
    )

    return {
        "title": metadata[
            "title"
        ],
        "author": metadata[
            "author"
        ],
        "page_count": len(
            pages
        ),
        "pages": pages,
    }

def read_cbz_page_size(archive, page_name):
    """Read image-header dimensions without retaining decompressed pixels."""
    try:
        with archive.open(page_name) as stream:
            with Image.open(stream) as image:
                width, height = image.size
                if width > 0 and height > 0:
                    return width, height
    except Exception:
        pass
    return None
