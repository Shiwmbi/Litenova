"""
Import one Manga/Manhwa Library series from a folder of
chapter CBZ or image-based EPUB files.

Image-based EPUBs are converted to temporary CBZ chapters.

Original source files are never modified.
"""

import posixpath
import re
import shutil
import tempfile
import zipfile

from pathlib import Path
from urllib.parse import (
    unquote,
    urlsplit,
)
from xml.etree import (
    ElementTree as ET,
)

from app.services.import_service import (
    import_cbz_folder,
)

from app.services.path_service import (
    ensure_data_structure,
)


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
}


CHAPTER_EXTENSIONS = {
    ".cbz",
    ".epub",
}


# ============================================================
# NATURAL SORT
# ============================================================

def _natural_key(
    value,
):

    return [
        (
            int(piece)
            if piece.isdigit()
            else piece.casefold()
        )
        for piece in re.split(
            r"(\d+)",
            str(value),
        )
    ]


# ============================================================
# XML TAG
# ============================================================

def _xml_local_tag(
    element,
):

    return (
        element.tag
        .rsplit(
            "}",
            1,
        )[-1]
        .casefold()
    )


# ============================================================
# SAFE EPUB RESOURCE PATH
# ============================================================

def _archive_path(
    base,
    relative,
):
    """
    Resolve an EPUB-relative resource while preventing
    access outside the archive.
    """

    raw = (
        unquote(
            urlsplit(
                relative
            ).path
        )
        .replace(
            "\\",
            "/",
        )
    )

    path = (
        posixpath.normpath(
            posixpath.join(
                posixpath.dirname(
                    base
                ),
                raw,
            )
        )
    )

    if (
        path.startswith(
            "../"
        )
        or path == ".."
        or path.startswith(
            "/"
        )
    ):

        raise ValueError(
            "EPUB contains an invalid resource path."
        )

    return path


# ============================================================
# IMAGE-BASED EPUB PAGE EXTRACTION
# ============================================================

def _epub_spine_images(
    archive,
):
    """
    Return the image files referenced by an image-based
    EPUB in reading order.
    """

    try:

        container = ET.fromstring(
            archive.read(
                "META-INF/container.xml"
            )
        )

        rootfile = next(
            element
            for element
            in container.iter()
            if _xml_local_tag(
                element
            ) == "rootfile"
        )

        opf_name = (
            rootfile.attrib[
                "full-path"
            ]
        )

        opf = ET.fromstring(
            archive.read(
                opf_name
            )
        )

    except (
        KeyError,
        StopIteration,
        ET.ParseError,
        ValueError,
    ) as error:

        raise ValueError(
            "EPUB has no readable package "
            "or spine information."
        ) from error

    manifest = {}

    for element in opf.iter():

        if (
            _xml_local_tag(
                element
            )
            == "item"
        ):

            item_id = (
                element.get(
                    "id"
                )
            )

            href = (
                element.get(
                    "href"
                )
            )

            if (
                item_id
                and href
            ):

                manifest[item_id] = (
                    _archive_path(
                        opf_name,
                        href,
                    )
                )

    spine = [
        element.get(
            "idref"
        )
        for element
        in opf.iter()
        if (
            _xml_local_tag(
                element
            )
            == "itemref"
            and element.get(
                "idref"
            )
        )
    ]

    if not spine:

        raise ValueError(
            "This EPUB has no readable pages."
        )

    names = set(
        archive.namelist()
    )

    ordered = []

    image_documents = 0

    text_heavy_documents = 0

    for item_id in spine:

        page_path = (
            manifest.get(
                item_id
            )
        )

        if (
            not page_path
            or page_path not in names
        ):

            continue

        # ----------------------------------------------------
        # SPINE ITEM IS DIRECTLY AN IMAGE
        # ----------------------------------------------------

        if (
            Path(
                page_path
            ).suffix.lower()
            in IMAGE_EXTENSIONS
        ):

            ordered.append(
                page_path
            )

            image_documents += 1

            continue

        # ----------------------------------------------------
        # XHTML / HTML PAGE
        # ----------------------------------------------------

        try:

            document = ET.fromstring(
                archive.read(
                    page_path
                )
            )

        except (
            ET.ParseError,
            KeyError,
        ):

            continue

        page_images = []

        for node in document.iter():

            if (
                _xml_local_tag(
                    node
                )
                not in (
                    "img",
                    "image",
                )
            ):

                continue

            reference = (
                node.attrib.get(
                    "src"
                )
                or node.attrib.get(
                    "href"
                )
                or node.attrib.get(
                    (
                        "{http://www.w3.org/"
                        "1999/xlink}href"
                    )
                )
            )

            if (
                not reference
                or reference.startswith(
                    "data:"
                )
            ):

                continue

            resolved = (
                _archive_path(
                    page_path,
                    reference,
                )
            )

            if (
                resolved in names
                and Path(
                    resolved
                ).suffix.lower()
                in IMAGE_EXTENSIONS
            ):

                page_images.append(
                    resolved
                )

        if page_images:

            ordered.extend(
                page_images
            )

            image_documents += 1

        plain_text = " ".join(
            part.strip()
            for part
            in document.itertext()
            if part.strip()
        )

        if len(
            plain_text
        ) > 250:

            text_heavy_documents += 1

    # --------------------------------------------------------
    # DON'T CONVERT NORMAL TEXT NOVELS INTO COMICS
    # --------------------------------------------------------

    if (
        not ordered
        or text_heavy_documents
        or image_documents
        < max(
            1,
            len(spine) * 0.6,
        )
    ):

        raise ValueError(
            "This EPUB is not an image-based Manga/Manhwa "
            "chapter. Only image-based EPUB chapters can be "
            "grouped as comic pages. Text EPUBs should be "
            "imported as normal EPUB books."
        )

    return ordered


# ============================================================
# CONVERT IMAGE EPUB TO CBZ
# ============================================================

def _image_epub_to_cbz(
    epub_path,
    cbz_path,
):

    try:

        with zipfile.ZipFile(
            epub_path,
            "r",
        ) as source:

            ordered_images = (
                _epub_spine_images(
                    source
                )
            )

            with zipfile.ZipFile(
                cbz_path,
                "w",
            ) as output:

                for (
                    index,
                    image_path,
                ) in enumerate(
                    ordered_images,
                    start=1,
                ):

                    extension = (
                        Path(
                            image_path
                        ).suffix.lower()
                    )

                    output.writestr(
                        (
                            f"{index:05d}"
                            f"{extension}"
                        ),
                        source.read(
                            image_path
                        ),
                        compress_type=(
                            zipfile.ZIP_STORED
                        ),
                    )

    except (
        zipfile.BadZipFile,
        OSError,
        KeyError,
        ET.ParseError,
    ) as error:

        raise ValueError(
            (
                f"Cannot convert "
                f"{epub_path.name} "
                f"into a comic chapter: "
                f"{error}"
            )
        ) from error


# ============================================================
# IMPORT MANGA / MANHWA FOLDER
# ============================================================

def import_comic_chapter_folder(
    folder,
    category,
    allow_duplicate=False,
):
    """
    Import a folder of CBZ or image-based EPUB chapters
    as one Manga or Manhwa series.

    The important part of this version is that the writable
    data folders are recreated BEFORE import_cbz_folder runs.

    This prevents:
        FileNotFoundError:
        ...\\data\\covers\\xxxxxxxx.jpg
    """

    # --------------------------------------------------------
    # ENSURE DATA/BOOKS AND DATA/COVERS EXIST
    # --------------------------------------------------------

    ensure_data_structure()

    folder = (
        Path(
            folder
        )
        .expanduser()
        .resolve()
    )

    # --------------------------------------------------------
    # VALIDATE CATEGORY
    # --------------------------------------------------------

    if category not in (
        "manga",
        "manhwa",
    ):

        raise ValueError(
            "Choose Manga or Manhwa "
            "before importing this folder."
        )

    # --------------------------------------------------------
    # VALIDATE SOURCE FOLDER
    # --------------------------------------------------------

    if not folder.is_dir():

        raise ValueError(
            "The selected chapter folder "
            "does not exist."
        )

    # --------------------------------------------------------
    # FIND CHAPTERS
    # --------------------------------------------------------

    chapters = sorted(
        (
            path
            for path
            in folder.iterdir()
            if (
                path.is_file()
                and path.suffix.lower()
                in CHAPTER_EXTENSIONS
            )
        ),
        key=lambda path: (
            _natural_key(
                path.name
            )
        ),
    )

    if not chapters:

        raise ValueError(
            "This folder contains no chapter EPUB/CBZ files. "
            "Open the folder containing the chapters "
            "and try again."
        )

    # --------------------------------------------------------
    # ALL CHAPTERS ARE ALREADY CBZ
    # --------------------------------------------------------

    if all(
        path.suffix.lower()
        == ".cbz"
        for path
        in chapters
    ):

        # Make sure the destination structure still exists
        # immediately before the lower-level importer runs.

        ensure_data_structure()

        return import_cbz_folder(
            str(folder),
            category=category,
            allow_duplicate=allow_duplicate,
        )

    # --------------------------------------------------------
    # CONVERT IMAGE EPUB CHAPTERS TO TEMPORARY CBZ FILES
    # --------------------------------------------------------

    with tempfile.TemporaryDirectory(
        prefix=(
            "litenova_chapter_import_"
        )
    ) as temporary:

        staged = (
            Path(
                temporary
            )
            / folder.name
        )

        staged.mkdir(
            parents=True,
            exist_ok=True,
        )

        seen_stems = set()

        for chapter in chapters:

            stem = (
                chapter.stem
                .casefold()
            )

            if stem in seen_stems:

                raise ValueError(
                    (
                        "More than one chapter is named "
                        f"'{chapter.stem}' with different "
                        "extensions. Rename the files to "
                        "unique chapter names."
                    )
                )

            seen_stems.add(
                stem
            )

            destination = (
                staged
                / (
                    chapter.stem
                    + ".cbz"
                )
            )

            if (
                chapter.suffix.lower()
                == ".cbz"
            ):

                shutil.copy2(
                    chapter,
                    destination,
                )

            else:

                _image_epub_to_cbz(
                    chapter,
                    destination,
                )

        # The importer may generate a JPG cover here,
        # so verify the cover directory again immediately
        # before calling it.

        ensure_data_structure()

        return import_cbz_folder(
            str(staged),
            category=category,
            allow_duplicate=allow_duplicate,
        )