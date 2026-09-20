"""Import one Manga/Manhwa Library series from a folder of chapter CBZ/EPUB files.

Image-based EPUBs are converted to CBZ chapters in a temporary directory.
The original EPUB/CBZ files are never modified or removed.
Text-oriented EPUB chapters cannot be rendered as comic pages by the CBZ reader;
those EPUB files produce a clear error instead of being silently mis-imported.
"""

import posixpath
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from app.services.import_service import import_cbz_folder


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
CHAPTER_EXTENSIONS = {".cbz", ".epub"}


def _natural_key(value):
    import re
    return [int(piece) if piece.isdigit() else piece.casefold()
            for piece in re.split(r"(\d+)", str(value))]


def _xml_local_tag(element):
    return element.tag.rsplit("}", 1)[-1].casefold()


def _archive_path(base, relative):
    """Resolve a relative EPUB resource without accessing paths outside ZIP."""
    raw = unquote(urlsplit(relative).path).replace("\\", "/")
    path = posixpath.normpath(posixpath.join(posixpath.dirname(base), raw))
    if path.startswith("../") or path == ".." or path.startswith("/"):
        raise ValueError("EPUB contains an invalid resource path.")
    return path


def _epub_spine_images(archive):
    """Return referenced image archive paths in the order of EPUB spine items."""
    try:
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next(e for e in container.iter() if _xml_local_tag(e) == "rootfile")
        opf_name = rootfile.attrib["full-path"]
        opf = ET.fromstring(archive.read(opf_name))
    except (KeyError, StopIteration, ET.ParseError, ValueError) as error:
        raise ValueError("EPUB has no readable package/spine information.") from error

    manifest = {}
    for element in opf.iter():
        if _xml_local_tag(element) == "item":
            item_id = element.get("id")
            href = element.get("href")
            if item_id and href:
                manifest[item_id] = _archive_path(opf_name, href)
    spine = [e.get("idref") for e in opf.iter()
             if _xml_local_tag(e) == "itemref" and e.get("idref")]
    if not spine:
        raise ValueError("This EPUB has no readable pages.")

    names = set(archive.namelist())
    ordered = []
    image_documents = 0
    text_heavy_documents = 0
    for item_id in spine:
        page_path = manifest.get(item_id)
        if not page_path or page_path not in names:
            continue
        if Path(page_path).suffix.lower() in IMAGE_EXTENSIONS:
            ordered.append(page_path)
            image_documents += 1
            continue
        try:
            document = ET.fromstring(archive.read(page_path))
        except (ET.ParseError, KeyError):
            # Do not blindly extract every image from an EPUB; cover art and
            # illustrations in a text novel do not make it an image comic.
            continue
        page_images = []
        for node in document.iter():
            if _xml_local_tag(node) not in ("img", "image"):
                continue
            reference = (node.attrib.get("src") or node.attrib.get("href")
                         or node.attrib.get("{http://www.w3.org/1999/xlink}href"))
            if not reference or reference.startswith("data:"):
                continue
            resolved = _archive_path(page_path, reference)
            if resolved in names and Path(resolved).suffix.lower() in IMAGE_EXTENSIONS:
                page_images.append(resolved)
        if page_images:
            ordered.extend(page_images)
            image_documents += 1
        # EPUBs with prose and occasional illustrations should be imported
        # as regular EPUB books, not converted into incomplete comic chapters.
        plain_text = " ".join(part.strip() for part in document.itertext() if part.strip())
        if len(plain_text) > 250:
            text_heavy_documents += 1

    if not ordered or text_heavy_documents or image_documents < max(1, len(spine) * .6):
        raise ValueError(
            "This EPUB is not an image-based Manga/Manhwa chapter. "
            "Only image-based EPUB chapters can be grouped as comic pages; "
            "text EPUBs must currently be imported as individual EPUB books."
        )
    return ordered


def _image_epub_to_cbz(epub_path, cbz_path):
    try:
        with zipfile.ZipFile(epub_path, "r") as source:
            ordered_images = _epub_spine_images(source)
            with zipfile.ZipFile(cbz_path, "w") as output:
                for index, image_path in enumerate(ordered_images, start=1):
                    extension = Path(image_path).suffix.lower()
                    output.writestr(
                        f"{index:05d}{extension}", source.read(image_path),
                        compress_type=zipfile.ZIP_STORED,
                    )
    except (zipfile.BadZipFile, OSError, KeyError, ET.ParseError) as error:
        raise ValueError(f"Cannot convert {epub_path.name} into a comic chapter: {error}") from error


def import_comic_chapter_folder(folder, category):
    """Import chapter CBZ files and image-based EPUB chapter files as one series.

    Uses Litenova's existing import_cbz_folder so chapter navigation, cover,
    progress, series metadata, and Manga/Manhwa category all work as usual.
    """
    folder = Path(folder).expanduser().resolve()
    if category not in ("manga", "manhwa"):
        raise ValueError("Choose Manga or Manhwa before importing this folder.")
    if not folder.is_dir():
        raise ValueError("The selected chapter folder does not exist.")
    chapters = sorted(
        (path for path in folder.iterdir()
         if path.is_file() and path.suffix.lower() in CHAPTER_EXTENSIONS),
        key=lambda path: _natural_key(path.name),
    )
    if not chapters:
        raise ValueError(
            "This folder contains no chapter EPUB/CBZ files. "
            "Open the folder containing the chapters and try again."
        )
    if all(path.suffix.lower() == ".cbz" for path in chapters):
        # Keep the existing zero-conversion, direct Manga/Manhwa folder import.
        return import_cbz_folder(str(folder), category=category)

    # The existing importer accepts chapter CBZ archives. Convert image-based
    # EPUB chapters into temporary CBZ chapters, then import as one series.
    # Never delete or modify the original source files.
    with tempfile.TemporaryDirectory(prefix="litenova_chapter_import_") as temporary:
        staged = Path(temporary) / folder.name
        staged.mkdir()
        seen_stems = set()
        for chapter in chapters:
            stem = chapter.stem.casefold()
            if stem in seen_stems:
                raise ValueError(
                    f"More than one chapter is named '{chapter.stem}' with "
                    "different extensions. Rename the files to unique chapter names."
                )
            seen_stems.add(stem)
            destination = staged / f"{chapter.stem}.cbz"
            if chapter.suffix.lower() == ".cbz":
                shutil.copy2(chapter, destination)
            else:
                _image_epub_to_cbz(chapter, destination)
        return import_cbz_folder(str(staged), category=category)
