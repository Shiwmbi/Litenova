import html
import mimetypes
import re
from pathlib import Path

import ebooklib
from ebooklib import epub


# ============================================================
# EPUB METADATA
# ============================================================

def read_epub_metadata(epub_path):
    """
    Read basic metadata from an EPUB file.

    Returns:
        {
            "title": "...",
            "author": "..."
        }
    """

    book = epub.read_epub(epub_path)

    title_metadata = book.get_metadata(
        "DC",
        "title",
    )

    author_metadata = book.get_metadata(
        "DC",
        "creator",
    )

    title = (
        title_metadata[0][0]
        if title_metadata
        else "Unknown Title"
    )

    author = (
        author_metadata[0][0]
        if author_metadata
        else "Unknown Author"
    )

    if not title:
        title = "Unknown Title"

    if not author:
        author = "Unknown Author"

    if author.strip().lower() in [
        "",
        "unknown",
        "<unknown>",
    ]:
        author = "Unknown Author"

    return {
        "title": title,
        "author": author,
    }


# ============================================================
# COVER HELPERS
# ============================================================

def _get_extension(item):
    """
    Determine the file extension of an EPUB image.

    For example:
        image/jpeg -> .jpg
        image/png  -> .png
    """

    media_type = getattr(
        item,
        "media_type",
        None,
    )

    extension = mimetypes.guess_extension(
        media_type or ""
    )

    if extension:
        return extension

    file_name = getattr(
        item,
        "file_name",
        "",
    )

    suffix = Path(
        file_name
    ).suffix

    if suffix:
        return suffix

    return ".jpg"


# ============================================================
# EPUB COVER
# ============================================================

def extract_cover(epub_path):
    """
    Try several methods to find the EPUB cover.

    Returns:
        {
            "data": bytes,
            "extension": ".jpg"
        }

    Returns None if no cover can be found.
    """

    book = epub.read_epub(
        epub_path
    )

    # --------------------------------------------------------
    # Method 1:
    # EPUB 3 usually marks the cover using the
    # "cover-image" property.
    # --------------------------------------------------------

    for item in book.get_items():

        properties = getattr(
            item,
            "properties",
            [],
        )

        if "cover-image" in properties:

            return {
                "data": item.get_content(),
                "extension": _get_extension(
                    item
                ),
            }

    # --------------------------------------------------------
    # Method 2:
    # Older EPUB files often store a cover ID
    # inside OPF metadata.
    # --------------------------------------------------------

    cover_metadata = book.get_metadata(
        "OPF",
        "cover",
    )

    if cover_metadata:

        for metadata in cover_metadata:

            attributes = metadata[1]

            cover_id = attributes.get(
                "content"
            )

            if not cover_id:
                continue

            cover_item = (
                book.get_item_with_id(
                    cover_id
                )
            )

            if cover_item:

                return {
                    "data": (
                        cover_item.get_content()
                    ),
                    "extension": (
                        _get_extension(
                            cover_item
                        )
                    ),
                }

    # --------------------------------------------------------
    # Method 3:
    # EbookLib may identify the cover directly.
    # --------------------------------------------------------

    cover_items = list(
        book.get_items_of_type(
            ebooklib.ITEM_COVER
        )
    )

    if cover_items:

        item = cover_items[0]

        return {
            "data": item.get_content(),
            "extension": _get_extension(
                item
            ),
        }

    # --------------------------------------------------------
    # Method 4:
    # Search image file names and IDs for "cover".
    # --------------------------------------------------------

    image_items = list(
        book.get_items_of_type(
            ebooklib.ITEM_IMAGE
        )
    )

    for item in image_items:

        file_name = getattr(
            item,
            "file_name",
            "",
        ).lower()

        item_id = getattr(
            item,
            "id",
            "",
        ).lower()

        if (
            "cover" in file_name
            or "cover" in item_id
        ):

            return {
                "data": item.get_content(),
                "extension": _get_extension(
                    item
                ),
            }

    return None


# ============================================================
# CHAPTER TITLE HELPERS
# ============================================================

def _clean_html_text(value):
    """
    Remove HTML tags, decode HTML entities,
    and clean whitespace.
    """

    value = re.sub(
        r"<[^>]+>",
        "",
        value,
    )

    value = html.unescape(
        value
    )

    value = " ".join(
        value.split()
    )

    return value.strip()


def _find_chapter_title(
    chapter_html,
    file_name,
):
    """
    Attempt to determine a readable chapter title.

    Priority:
        1. <h1>
        2. <h2>
        3. <title>
        4. EPUB filename
    """

    # --------------------------------------------------------
    # Try <h1>
    # --------------------------------------------------------

    h1_match = re.search(
        r"<h1[^>]*>(.*?)</h1>",
        chapter_html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if h1_match:

        chapter_title = (
            _clean_html_text(
                h1_match.group(1)
            )
        )

        if chapter_title:
            return chapter_title

    # --------------------------------------------------------
    # Try <h2>
    # --------------------------------------------------------

    h2_match = re.search(
        r"<h2[^>]*>(.*?)</h2>",
        chapter_html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if h2_match:

        chapter_title = (
            _clean_html_text(
                h2_match.group(1)
            )
        )

        if chapter_title:
            return chapter_title

    # --------------------------------------------------------
    # Try document <title>
    # --------------------------------------------------------

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        chapter_html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if title_match:

        chapter_title = (
            _clean_html_text(
                title_match.group(1)
            )
        )

        if chapter_title:
            return chapter_title

    # --------------------------------------------------------
    # Final fallback:
    # turn the filename into a readable title.
    # --------------------------------------------------------

    chapter_title = Path(
        file_name
    ).stem

    chapter_title = (
        chapter_title
        .replace("_", " ")
        .replace("-", " ")
        .strip()
        .title()
    )

    if not chapter_title:
        chapter_title = "Untitled Chapter"

    return chapter_title


# ============================================================
# EPUB CHAPTERS
# ============================================================

def get_chapters(epub_path):
    """
    Read EPUB documents in spine order.

    The spine represents the normal reading order
    of the EPUB.

    Returns:
        [
            {
                "title": "...",
                "html": "...",
                "file_name": "..."
            },
            ...
        ]
    """

    book = epub.read_epub(
        epub_path
    )

    chapters = []

    try:
        for spine_item in book.spine:

            item_id = spine_item[0]

            item = book.get_item_with_id(
                item_id
            )

            if item is None:
                continue

            if (
                item.get_type()
                != ebooklib.ITEM_DOCUMENT
            ):
                continue

            content = item.get_content()

            chapter_html = content.decode(
                "utf-8",
                errors="ignore",
            )

            chapter_title = (
                _find_chapter_title(
                    chapter_html,
                    item.file_name,
                )
            )

            chapters.append(
                {
                    "title": chapter_title,
                    "html": chapter_html,
                    "file_name": item.file_name,
                }
            )
    finally:
        # EbookLib links every item back to its book. The returned chapter
        # strings need neither object; break that cycle before dropping them.
        for item in book.get_items():
            item.book = None

    return chapters