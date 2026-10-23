import os
import re
import zipfile
import posixpath
import shutil
import tempfile
from functools import lru_cache

from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

from PySide6.QtCore import (
    Qt,
    Signal,
    QSize,
    QSettings,
    QFileInfo,
    QTimer,
)

from PySide6.QtGui import (
    QPixmap,
    QIcon,
    QShortcut,
    QKeySequence,
    QPainter,
    QRegion,
    QTransform,
)

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QToolButton,
    QLineEdit,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QStackedWidget,
    QFileDialog,
    QFileIconProvider,
    QMessageBox,
    QInputDialog,
    QSplitter,
    QApplication,
)

from app.services.import_service import (
    import_book,
    DuplicateBookError,
)

from app.services.icon_service import ui_icon, icon_path
from app.services.comic_folder_service import import_comic_chapter_folder


def browse_resource_icon(*names):
    """Load the first installed resource icon; leave unmatched controls alone."""
    for name in names:
        icon = ui_icon(name)
        if not icon.isNull():
            return icon
    return QIcon()


def set_browse_button_icon(button, names, fallback_text, size=22):
    """Use an installed PNG or retain the button's original text symbol."""
    icon = browse_resource_icon(*names)
    if icon.isNull():
        button.setText(fallback_text)
    else:
        button.setText("")
        button.setIcon(icon)
        button.setIconSize(QSize(size, size))



def browse_navigation_arrow(direction):
    """Use an installed navigation PNG or orient the existing breadcrumb arrow.

    The resource pack has breadcrumb_arrow.png (points right), but no
    dedicated back/forward/up PNGs. Reusing its actual artwork gives these
    buttons matching PNG icons without generating extra resource files.
    """
    names = {
        "back": ("back", "navigate_back"),
        "forward": ("forward", "navigate_forward"),
        "up": ("up", "navigate_up"),
    }
    original = browse_resource_icon(*names.get(direction, (direction,)))
    if not original.isNull():
        return original

    source_path = icon_path("breadcrumb_arrow")
    if source_path is None:
        return QIcon()

    source = QPixmap(str(source_path))
    if source.isNull():
        return QIcon()

    # Transparent padding takes up most of the 256px resource image.
    # Trim it so the arrow is visible at the Browse toolbar's icon size.
    mask = source.mask()
    bounds = QRegion(mask).boundingRect() if not mask.isNull() else source.rect()
    if bounds.isEmpty():
        return QIcon()

    arrow = source.copy(bounds)
    rotation = {"back": 180, "forward": 0, "up": -90}.get(direction, 0)
    arrow = arrow.transformed(QTransform().rotate(rotation), Qt.SmoothTransformation)
    arrow = arrow.scaled(23, 23, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    canvas = QPixmap(26, 26)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.drawPixmap((26 - arrow.width()) // 2, (26 - arrow.height()) // 2, arrow)
    painter.end()
    return QIcon(canvas)


# ============================================================
# CONFIGURATION
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".epub",
    ".cbz",
}

PREVIEW_IMAGE_LIMIT = 20 * 1024 * 1024


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def format_file_size(size):
    """
    Convert a file size into a readable value.
    """

    size = float(size)

    for unit in ("B", "KB", "MB", "GB", "TB"):

        if size < 1024 or unit == "TB":

            if unit == "B":
                return f"{int(size)} B"

            return f"{size:.1f} {unit}"

        size /= 1024

    return "Unknown"


def format_modified_time(timestamp):
    """
    Display the file's last-modified date.
    """

    try:

        value = datetime.fromtimestamp(
            timestamp
        )

        return value.strftime(
            "%d.%m.%y %H:%M"
        )

    except (
        ValueError,
        OSError,
        OverflowError,
    ):

        return "Unknown"


def natural_sort_key(value):
    """
    Sort Chapter 2 before Chapter 10.
    """

    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(
            r"(\d+)",
            str(value),
        )
    ]


def supported_file(path):
    """
    Return True for supported EPUB and CBZ files.
    """

    return (
        path.is_file()
        and path.suffix.lower()
        in SUPPORTED_EXTENSIONS
    )


def get_file_type(path):
    """
    Return a readable file type.
    """

    if path.is_dir():
        return "Folder"

    extension = path.suffix.lower()

    if extension == ".epub":
        return "EPUB"

    if extension == ".cbz":
        return "CBZ"

    if extension:
        return (
            extension[1:].upper()
            + " File"
        )

    return "File"


# ============================================================
# EPUB PREVIEW
# ============================================================

def read_epub_preview(path):
    """
    Read basic EPUB metadata and its embedded cover.

    This is used only for the Browse preview.
    It does not import or modify the EPUB.
    """

    result = {
        "title": path.stem,
        "author": "Unknown Author",
        "cover": None,
    }

    try:

        with zipfile.ZipFile(path, "r") as archive:

            container_data = archive.read(
                "META-INF/container.xml"
            )

            container_root = ElementTree.fromstring(
                container_data
            )

            rootfile = container_root.find(
                ".//{*}rootfile"
            )

            if rootfile is None:
                return result

            package_path = rootfile.attrib.get(
                "full-path"
            )

            if not package_path:
                return result

            package_data = archive.read(
                package_path
            )

            package_root = ElementTree.fromstring(
                package_data
            )

            # ================================================
            # TITLE
            # ================================================

            title_element = package_root.find(
                ".//{http://purl.org/dc/elements/1.1/}title"
            )

            if (
                title_element is not None
                and title_element.text
            ):

                result["title"] = (
                    title_element.text.strip()
                )

            # ================================================
            # AUTHOR
            # ================================================

            author_element = package_root.find(
                ".//{http://purl.org/dc/elements/1.1/}creator"
            )

            if (
                author_element is not None
                and author_element.text
            ):

                result["author"] = (
                    author_element.text.strip()
                )

            # ================================================
            # FIND COVER
            # ================================================

            metadata = package_root.find(
                ".//{*}metadata"
            )

            manifest = package_root.find(
                ".//{*}manifest"
            )

            if manifest is None:
                return result

            cover_id = None

            if metadata is not None:

                for item in metadata:

                    if (
                        item.tag.split("}")[-1]
                        == "meta"
                    ):

                        if (
                            item.attrib.get("name")
                            == "cover"
                        ):

                            cover_id = (
                                item.attrib.get("content")
                            )

                            break

            cover_href = None

            for item in manifest:

                item_id = item.attrib.get(
                    "id"
                )

                properties = item.attrib.get(
                    "properties",
                    "",
                )

                media_type = item.attrib.get(
                    "media-type",
                    "",
                )

                if (
                    cover_id
                    and item_id == cover_id
                ):

                    cover_href = item.attrib.get(
                        "href"
                    )

                    break

                if (
                    "cover-image"
                    in properties.split()
                    and media_type.startswith("image/")
                ):

                    cover_href = item.attrib.get(
                        "href"
                    )

                    break

            if not cover_href:
                return result

            # ================================================
            # COVER FILE LOCATION
            # ================================================

            package_directory = posixpath.dirname(
                package_path
            )

            cover_location = posixpath.normpath(
                posixpath.join(
                    package_directory,
                    unquote(
                        cover_href.split("#")[0]
                    ),
                )
            )

            archive_names = {
                name.lower(): name
                for name in archive.namelist()
            }

            actual_cover_name = archive_names.get(
                cover_location.lower()
            )

            if not actual_cover_name:
                return result

            cover_info = archive.getinfo(
                actual_cover_name
            )

            if (
                cover_info.file_size
                > PREVIEW_IMAGE_LIMIT
            ):

                return result

            image_data = archive.read(
                actual_cover_name
            )

            pixmap = QPixmap()

            pixmap.loadFromData(
                image_data
            )

            if not pixmap.isNull():

                result["cover"] = pixmap

    except Exception:
        pass

    return result


# ============================================================
# CBZ PREVIEW
# ============================================================

def read_cbz_preview(path):
    """
    Read the first image inside a CBZ.

    The original CBZ is not modified.
    """

    result = {
        "title": path.stem,
        "author": "Unknown Author",
        "cover": None,
    }

    try:

        with zipfile.ZipFile(path, "r") as archive:

            # ================================================
            # OPTIONAL COMICINFO METADATA
            # ================================================

            comic_info_path = next(
                (
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(
                        "comicinfo.xml"
                    )
                ),
                None,
            )

            if comic_info_path:

                try:

                    comic_info = ElementTree.fromstring(
                        archive.read(
                            comic_info_path
                        )
                    )

                    title = comic_info.findtext(
                        "Title"
                    )

                    series = comic_info.findtext(
                        "Series"
                    )

                    writer = comic_info.findtext(
                        "Writer"
                    )

                    if title or series:

                        result["title"] = (
                            title or series
                        ).strip()

                    if writer:

                        result["author"] = (
                            writer.strip()
                        )

                except Exception:
                    pass

            # ================================================
            # FIND FIRST IMAGE
            # ================================================

            image_extensions = (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".bmp",
            )

            images = []

            for item in archive.infolist():

                if item.is_dir():
                    continue

                name = item.filename

                if name.startswith(
                    "__MACOSX/"
                ):
                    continue

                if (
                    Path(name).suffix.lower()
                    not in image_extensions
                ):
                    continue

                if item.file_size > PREVIEW_IMAGE_LIMIT:
                    continue

                images.append(
                    item
                )

            images.sort(
                key=lambda item: natural_sort_key(
                    item.filename
                )
            )

            if not images:
                return result

            image_data = archive.read(
                images[0]
            )

            pixmap = QPixmap()

            pixmap.loadFromData(
                image_data
            )

            if not pixmap.isNull():

                result["cover"] = pixmap

    except Exception:
        pass

    return result


# ============================================================
# BROWSE PAGE
# ============================================================



@lru_cache(maxsize=512)
def _cached_folder_chapters(folder_path, modified_ns):
    """Scan a series folder once per filesystem modification, not per widget."""
    del modified_ns  # Included in the key so file changes invalidate the cache.
    try:
        return tuple(sorted(
            (p for p in Path(folder_path).iterdir()
             if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS),
            key=lambda p: natural_sort_key(p.name),
        ))
    except OSError:
        return ()


def folder_chapters(path):
    """Find immediate EPUB/CBZ chapters; other folders remain navigable."""
    folder = Path(path)
    try:
        if not folder.is_dir():
            return []
        modified_ns = folder.stat().st_mtime_ns
    except OSError:
        return []
    return list(_cached_folder_chapters(str(folder), modified_ns))


def supported_target(path):
    """Individual EPUB/CBZ or a series folder with chapter EPUB/CBZ files."""
    return supported_file(path) or bool(folder_chapters(path))


class BrowsePage(QWidget):

    book_imported = Signal()

    def __init__(self):
        super().__init__()

        # ====================================================
        # FILE BROWSER STATE
        # ====================================================

        self.settings = QSettings(
            "Litenova",
            "Litenova",
        )

        saved_directory = self.settings.value(
            "last_browser_directory",
            "",
        )

        if saved_directory:

            starting_directory = Path(
                str(saved_directory)
            )

        else:

            starting_directory = (
                Path.home() / "Documents"
            )

            if not starting_directory.is_dir():

                starting_directory = Path.home()

        if not starting_directory.is_dir():

            starting_directory = Path.home()

        self.current_directory = (
            starting_directory
        )

        self.navigation_history = [
            self.current_directory
        ]

        self.navigation_index = 0

        # Checked files for batch import.
        self.checked_files = set()

        # Current preview selection.
        self.preview_path = None

        self.preview_original_pixmap = None

        # Files displayed in the current folder.
        self.current_entries = []

        # Prevent selection synchronization loops.
        self.updating_file_views = False

        self.icon_provider = QFileIconProvider()
        self._file_icon_cache = {}

        # A single click selects immediately, but ZIP cover extraction waits
        # briefly so an ordinary double-click can open a folder without lag.
        self._queued_preview_path = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(240)
        self._preview_timer.timeout.connect(self._show_queued_preview)

        # Populate only the visible view. Huge directories no longer build
        # the hidden grid and table during each navigation or search.
        self._visible_entries = []
        self._table_needs_refresh = True
        self._grid_needs_refresh = True

        # ====================================================
        # BUILD
        # ====================================================

        self.build_ui()

        self.apply_page_style()

        self._directory_loaded = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._directory_loaded:
            self.load_directory()

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        main_layout = QVBoxLayout(
            self
        )

        main_layout.setContentsMargins(
            22,
            22,
            16,
            16,
        )

        main_layout.setSpacing(
            14
        )

        # ====================================================
        # HEADER
        # ====================================================

        header = QHBoxLayout()

        header_text = QVBoxLayout()

        header_text.setSpacing(
            4
        )

        self.page_title = QLabel(
            "Browse"
        )

        self.page_title.setObjectName(
            "browsePageTitle"
        )

        self.page_description = QLabel(
            "Browse your files and import EPUB, Manga, and Manhwa into your Library"
        )

        self.page_description.setObjectName(
            "browseSecondary"
        )

        header_text.addWidget(
            self.page_title
        )

        header_text.addWidget(
            self.page_description
        )

        header.addLayout(
            header_text,
            1,
        )

        # ====================================================
        # SEARCH
        # ====================================================

        self.search_input = QLineEdit()

        self.search_input.setObjectName(
            "browseSearch"
        )

        self.search_input.setPlaceholderText(
            "Search files..."
        )

        self.search_input.setClearButtonEnabled(
            True
        )

        self.search_input.setFixedHeight(
            42
        )

        self.search_input.setMinimumWidth(
            180
        )

        self.search_input.setMaximumWidth(
            330
        )

        self.search_input.addAction(
            browse_resource_icon("search_input_icon", "search"),
            QLineEdit.LeadingPosition,
        )

        self.search_input.textChanged.connect(
            self.filter_current_directory
        )

        header.addWidget(
            self.search_input
        )

        # ====================================================
        # LIST VIEW BUTTON
        # ====================================================

        self.list_button = QToolButton()

        set_browse_button_icon(
            self.list_button,
            ("list_view", "list_unselected"),
            "☰",
            size=23,
        )

        self.list_button.setObjectName(
            "browseViewButton"
        )

        self.list_button.setFixedSize(
            44,
            42,
        )

        self.list_button.setCheckable(
            True
        )

        self.list_button.setChecked(
            True
        )

        self.list_button.setToolTip(
            "List view"
        )

        self.list_button.clicked.connect(
            self.show_list_view
        )

        # ====================================================
        # GRID VIEW BUTTON
        # ====================================================

        self.grid_button = QToolButton()

        set_browse_button_icon(
            self.grid_button,
            ("grid_view", "grid_selected"),
            "▦",
            size=23,
        )

        self.grid_button.setObjectName(
            "browseViewButton"
        )

        self.grid_button.setFixedSize(
            44,
            42,
        )

        self.grid_button.setCheckable(
            True
        )

        self.grid_button.setToolTip(
            "Grid view"
        )

        self.grid_button.clicked.connect(
            self.show_grid_view
        )

        header.addWidget(
            self.list_button
        )

        header.addWidget(
            self.grid_button
        )

        # ====================================================
        # MAIN SPLITTER
        # ====================================================

        self.main_splitter = QSplitter(
            Qt.Horizontal
        )

        self.main_splitter.setObjectName(
            "browseSplitter"
        )

        # ====================================================
        # LEFT FILE EXPLORER
        # ====================================================

        self.file_panel = QWidget()

        file_panel_layout = QVBoxLayout(
            self.file_panel
        )

        file_panel_layout.setContentsMargins(
            0,
            0,
            10,
            0,
        )

        file_panel_layout.setSpacing(
            12
        )

        # ====================================================
        # NAVIGATION BAR
        # ====================================================

        navigation_layout = QHBoxLayout()

        navigation_layout.setSpacing(
            7
        )

        self.back_button = self.create_navigation_button(
            "←",
            "Back",
            self.go_back,
            icon_names=("back", "navigate_back"),
            direction="back",
        )

        self.forward_button = self.create_navigation_button(
            "→",
            "Forward",
            self.go_forward,
            icon_names=("forward", "navigate_forward"),
            direction="forward",
        )

        self.up_button = self.create_navigation_button(
            "↑",
            "Go to parent folder",
            self.go_up,
            icon_names=("up", "navigate_up"),
            direction="up",
        )

        # There is no dedicated home.png in the current icon pack.
        # The original Home symbol is retained unless one is added.
        self.home_button = self.create_navigation_button(
            "⌂",
            "Go to Home folder",
            self.go_home,
            icon_names=("home",),
        )

        navigation_layout.addWidget(
            self.back_button
        )

        navigation_layout.addWidget(
            self.forward_button
        )

        navigation_layout.addWidget(
            self.up_button
        )

        navigation_layout.addWidget(
            self.home_button
        )

        # ====================================================
        # ADDRESS BAR
        # ====================================================

        self.address_input = QLineEdit()

        self.address_input.setObjectName(
            "browseAddress"
        )

        self.address_input.setPlaceholderText(
            "Enter a folder path..."
        )

        self.address_input.setFixedHeight(
            43
        )

        folder_address_icon = browse_resource_icon("folder", "open_folder")
        if not folder_address_icon.isNull():
            self.address_input.addAction(
                folder_address_icon,
                QLineEdit.LeadingPosition,
            )

        self.address_input.returnPressed.connect(
            self.navigate_to_address
        )

        navigation_layout.addWidget(
            self.address_input,
            1,
        )

        # ====================================================
        # CHOOSE FOLDER
        # ====================================================

        self.choose_folder_button = (
            self.create_navigation_button(
                "📁",
                "Choose a folder",
                self.choose_folder,
                icon_names=("open_folder", "folder"),
            )
        )

        navigation_layout.addWidget(
            self.choose_folder_button
        )

        # ====================================================
        # REFRESH
        # ====================================================

        self.refresh_button = (
            self.create_navigation_button(
                "⟳",
                "Refresh current folder",
                self.load_directory,
                icon_names=("refresh", "reload"),
            )
        )

        navigation_layout.addWidget(
            self.refresh_button
        )

        file_panel_layout.addLayout(
            navigation_layout
        )

        # ====================================================
        # FILE VIEW STACK
        # ====================================================

        self.file_views = QStackedWidget()

        # ====================================================
        # LIST VIEW
        # ====================================================

        self.file_table = QTableWidget()

        self.file_table.setObjectName(
            "browseFileTable"
        )

        self.file_table.setColumnCount(
            5
        )

        self.file_table.setHorizontalHeaderLabels(
            [
                "",
                "Name",
                "Type",
                "Size",
                "Date modified",
            ]
        )

        self.file_table.verticalHeader().hide()

        self.file_table.setShowGrid(
            False
        )

        self.file_table.setAlternatingRowColors(
            False
        )

        self.file_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.file_table.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )

        self.file_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.file_table.setFocusPolicy(
            Qt.StrongFocus
        )

        self.file_table.setIconSize(
            QSize(22, 22)
        )

        self.file_table.setWordWrap(
            False
        )

        self.file_table.setSortingEnabled(
            False
        )

        table_header = (
            self.file_table.horizontalHeader()
        )

        table_header.setSectionResizeMode(
            0,
            QHeaderView.Fixed,
        )

        table_header.resizeSection(
            0,
            44,
        )

        table_header.setSectionResizeMode(
            1,
            QHeaderView.Stretch,
        )

        table_header.setSectionResizeMode(
            2,
            QHeaderView.Fixed,
        )

        table_header.resizeSection(
            2,
            95,
        )

        table_header.setSectionResizeMode(
            3,
            QHeaderView.Fixed,
        )

        table_header.resizeSection(
            3,
            90,
        )

        table_header.setSectionResizeMode(
            4,
            QHeaderView.Fixed,
        )

        table_header.resizeSection(
            4,
            135,
        )

        self.file_table.itemClicked.connect(
            self.on_table_item_clicked
        )

        self.file_table.itemChanged.connect(
            self.on_table_item_changed
        )

        self.file_table.itemDoubleClicked.connect(
            self.on_table_item_double_clicked
        )

        self.file_table.itemSelectionChanged.connect(
            self.on_table_selection_changed
        )

        # ====================================================
        # GRID VIEW
        # ====================================================

        self.file_grid = QListWidget()

        self.file_grid.setObjectName(
            "browseFileGrid"
        )

        self.file_grid.setViewMode(
            QListWidget.IconMode
        )

        self.file_grid.setMovement(
            QListWidget.Static
        )

        self.file_grid.setResizeMode(
            QListWidget.Adjust
        )

        self.file_grid.setFlow(
            QListWidget.LeftToRight
        )

        self.file_grid.setWrapping(
            True
        )

        self.file_grid.setSpacing(
            12
        )

        self.file_grid.setGridSize(
            QSize(145, 140)
        )

        self.file_grid.setIconSize(
            QSize(54, 54)
        )

        self.file_grid.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )

        self.file_grid.itemChanged.connect(
            self.on_grid_item_changed
        )

        self.file_grid.currentItemChanged.connect(
            self.on_grid_current_item_changed
        )

        self.file_grid.itemDoubleClicked.connect(
            self.on_grid_item_double_clicked
        )

        # Shift+click selects a range; Ctrl+A checks all visible imports.
        self.file_grid.itemSelectionChanged.connect(
            self.on_grid_selection_changed
        )
        self.table_select_all_shortcut = QShortcut(
            QKeySequence.SelectAll, self.file_table
        )
        self.table_select_all_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.table_select_all_shortcut.activated.connect(self.select_all_visible)
        self.grid_select_all_shortcut = QShortcut(
            QKeySequence.SelectAll, self.file_grid
        )
        self.grid_select_all_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.grid_select_all_shortcut.activated.connect(self.select_all_visible)

        self.file_views.addWidget(
            self.file_table
        )

        self.file_views.addWidget(
            self.file_grid
        )

        file_panel_layout.addWidget(
            self.file_views,
            1,
        )

        # ====================================================
        # RIGHT PREVIEW PANEL
        # ====================================================

        self.preview_panel = QFrame()

        self.preview_panel.setObjectName(
            "browsePreviewPanel"
        )

        self.preview_panel.setMinimumWidth(
            310
        )

        preview_scroll = QScrollArea(
            self.preview_panel
        )

        preview_scroll.setObjectName(
            "browsePreviewScroll"
        )

        preview_scroll.setWidgetResizable(
            True
        )

        preview_scroll.setFrameShape(
            QFrame.NoFrame
        )

        preview_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        preview_content = QWidget()

        preview_layout = QVBoxLayout(
            preview_content
        )

        preview_layout.setContentsMargins(
            16,
            16,
            16,
            16,
        )

        preview_layout.setSpacing(
            14
        )

        # ====================================================
        # SELECTED FILE INFORMATION
        # ====================================================

        preview_header = QHBoxLayout()

        preview_header.setSpacing(
            14
        )

        self.preview_cover = QLabel()

        self.preview_cover.setObjectName(
            "browsePreviewCover"
        )

        self.preview_cover.setFixedSize(
            120,
            180,
        )

        self.preview_cover.setAlignment(
            Qt.AlignCenter
        )

        self.preview_cover.setText(
            "NO COVER"
        )

        preview_header.addWidget(
            self.preview_cover
        )

        info_layout = QVBoxLayout()

        info_layout.setSpacing(
            7
        )

        self.preview_title = QLabel(
            "Select a file"
        )

        self.preview_title.setObjectName(
            "browsePreviewTitle"
        )

        self.preview_title.setWordWrap(
            True
        )

        self.preview_author = QLabel(
            "Choose an EPUB or CBZ file to preview."
        )

        self.preview_author.setObjectName(
            "browseSecondary"
        )

        self.preview_author.setWordWrap(
            True
        )

        self.preview_size = QLabel()

        self.preview_size.setObjectName(
            "browseSecondary"
        )

        self.preview_modified = QLabel()

        self.preview_modified.setObjectName(
            "browseSecondary"
        )

        self.preview_modified.setWordWrap(
            True
        )

        info_layout.addWidget(
            self.preview_title
        )

        info_layout.addWidget(
            self.preview_author
        )

        info_layout.addWidget(
            self.preview_size
        )

        info_layout.addWidget(
            self.preview_modified
        )

        info_layout.addStretch()

        preview_header.addLayout(
            info_layout,
            1,
        )

        preview_layout.addLayout(
            preview_header
        )

        # ====================================================
        # SEPARATOR
        # ====================================================

        separator = QFrame()

        separator.setObjectName(
            "browseSeparator"
        )

        separator.setFrameShape(
            QFrame.HLine
        )

        preview_layout.addWidget(
            separator
        )

        # ====================================================
        # IMPORT SECTION
        # ====================================================

        import_title = QLabel(
            "Import"
        )

        import_title.setObjectName(
            "browseSectionTitle"
        )

        preview_layout.addWidget(
            import_title
        )

        self.import_description = QLabel(
            "Select one or more EPUB/CBZ files."
        )

        self.import_description.setObjectName(
            "browseSecondary"
        )

        self.import_description.setWordWrap(
            True
        )

        preview_layout.addWidget(
            self.import_description
        )

        # ====================================================
        # IMPORT SELECTED FILES
        # ====================================================

        self.import_button = QPushButton(
            "Import (0)"
        )

        self.import_button.setObjectName(
            "browseImportButton"
        )

        self.import_button.setIcon(
            browse_resource_icon("open_folder", "folder")
        )

        self.import_button.setIconSize(
            QSize(22, 22)
        )

        self.import_button.setFixedHeight(
            52
        )

        self.import_button.setEnabled(
            False
        )

        self.import_button.clicked.connect(
            self.import_selected_files
        )

        preview_layout.addWidget(
            self.import_button
        )

        selection_actions = QHBoxLayout()
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.setObjectName("browseSecondaryButton")
        self.select_all_button.setToolTip(
            "Select all visible EPUB/CBZ files and chapter folders (Ctrl+A)"
        )
        self.select_all_button.clicked.connect(self.select_all_visible)
        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.setObjectName("browseSecondaryButton")
        self.clear_selection_button.clicked.connect(self.clear_file_selection)
        selection_actions.addWidget(self.select_all_button)
        selection_actions.addWidget(self.clear_selection_button)
        preview_layout.addLayout(selection_actions)

        self.group_selected_button = QPushButton(
            "Group Selected Chapters as One Series"
        )
        self.group_selected_button.setObjectName("browseSecondaryButton")
        self.group_selected_button.setFixedHeight(42)
        self.group_selected_button.setEnabled(False)
        self.group_selected_button.setToolTip(
            "Select two or more chapter EPUB/CBZ files, then import them as one Manga/Manhwa book"
        )
        self.group_selected_button.clicked.connect(self.import_selected_as_series)
        preview_layout.addWidget(self.group_selected_button)

        # ====================================================
        # IMPORT COMIC FOLDER
        # ====================================================

        self.import_folder_button = QPushButton(
            "Import Chapter Folder as Manga/Manhwa"
        )

        self.import_folder_button.setObjectName(
            "browseSecondaryButton"
        )

        self.import_folder_button.setFixedHeight(
            44
        )

        comic_folder_icon = browse_resource_icon("add_folder", "open_folder")
        if not comic_folder_icon.isNull():
            self.import_folder_button.setIcon(comic_folder_icon)
            self.import_folder_button.setIconSize(QSize(19, 19))

        self.import_folder_button.setToolTip(
            "Import a folder of CBZ or image-based EPUB chapters as one Manga/Manhwa series."
        )

        self.import_folder_button.clicked.connect(
            self.import_comic_folder
        )

        preview_layout.addWidget(
            self.import_folder_button
        )

        # ====================================================
        # OPTIONS
        # ====================================================

        options_separator = QFrame()

        options_separator.setObjectName(
            "browseSeparator"
        )

        options_separator.setFrameShape(
            QFrame.HLine
        )

        preview_layout.addWidget(
            options_separator
        )

        options_title = QLabel(
            "Options"
        )

        options_title.setObjectName(
            "browseSectionTitle"
        )

        preview_layout.addWidget(
            options_title
        )

        # ====================================================
        # MOVE SOURCE FILES
        # ====================================================

        self.move_files_checkbox = QCheckBox(
            "Move files to Library after import"
        )

        # Keep source files by default.
        self.move_files_checkbox.setChecked(
            False
        )

        self.move_files_checkbox.setToolTip(
            "After a successful import, remove the original file. "
            "The imported copy remains in Litenova's Library."
        )

        preview_layout.addWidget(
            self.move_files_checkbox
        )

        options_description = QLabel(
            "Litenova normally copies imported files into its "
            "Library. Enable this option to remove the original "
            "files after they are successfully imported."
        )

        options_description.setObjectName(
            "browseSecondary"
        )

        options_description.setWordWrap(
            True
        )

        preview_layout.addWidget(
            options_description
        )

        preview_layout.addStretch()

        preview_scroll.setWidget(
            preview_content
        )

        preview_panel_layout = QVBoxLayout(
            self.preview_panel
        )

        preview_panel_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        preview_panel_layout.addWidget(
            preview_scroll
        )

        # ====================================================
        # SPLITTER
        # ====================================================

        self.main_splitter.addWidget(
            self.file_panel
        )

        self.main_splitter.addWidget(
            self.preview_panel
        )

        self.main_splitter.setStretchFactor(
            0,
            3,
        )

        self.main_splitter.setStretchFactor(
            1,
            1,
        )

        self.main_splitter.setSizes(
            [850, 350]
        )

        # ====================================================
        # BOTTOM STATUS
        # ====================================================

        self.status_label = QLabel(
            "Ready"
        )

        self.status_label.setObjectName(
            "browseStatus"
        )

        # ====================================================
        # FINAL LAYOUT
        # ====================================================

        main_layout.addLayout(
            header
        )

        main_layout.addWidget(
            self.main_splitter,
            1,
        )

        main_layout.addWidget(
            self.status_label
        )

    # ========================================================
    # NAVIGATION BUTTON
    # ========================================================

    def create_navigation_button(
        self,
        text,
        tooltip,
        callback,
        icon_names=(),
        direction=None,
    ):

        button = QToolButton()

        button.setObjectName(
            "browseNavigationButton"
        )

        arrow_icon = browse_navigation_arrow(direction) if direction else QIcon()
        if arrow_icon.isNull():
            set_browse_button_icon(button, icon_names, text, size=23)
        else:
            button.setText("")
            button.setIcon(arrow_icon)
            button.setIconSize(QSize(26, 26))

        button.setToolTip(
            tooltip
        )

        button.setFixedSize(
            38,
            42,
        )

        button.setCursor(
            Qt.PointingHandCursor
        )

        button.clicked.connect(
            callback
        )

        return button

    # ========================================================
    # DIRECTORY NAVIGATION
    # ========================================================

    def navigate_to(
        self,
        directory,
        add_history=True,
    ):

        directory = Path(
            str(directory)
        ).expanduser()

        if not directory.is_dir():

            QMessageBox.warning(
                self,
                "Folder Not Found",
                (
                    "Litenova could not open this folder:\n\n"
                    f"{directory}"
                ),
            )

            return False

        directory = directory.resolve()

        # ====================================================
        # NAVIGATION HISTORY
        # ====================================================

        if add_history:

            if (
                directory
                != self.current_directory
            ):

                self.navigation_history = (
                    self.navigation_history[
                        :self.navigation_index + 1
                    ]
                )

                self.navigation_history.append(
                    directory
                )

                self.navigation_index = (
                    len(self.navigation_history)
                    - 1
                )

        self.current_directory = (
            directory
        )

        # ====================================================
        # SAVE LAST FOLDER
        # ====================================================

        self.settings.setValue(
            "last_browser_directory",
            str(directory),
        )

        # ====================================================
        # RESET CURRENT SELECTION
        # ====================================================

        self.checked_files.clear()
        self._preview_timer.stop()
        self._queued_preview_path = None

        self.preview_path = None
        self.clear_preview()

        # Clearing the search used to rebuild the OLD folder first, then
        # rebuild the NEW folder. Block that redundant refresh.
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)

        self.load_directory()

        return True

    # ========================================================
    # BACK
    # ========================================================

    def go_back(self):

        if self.navigation_index <= 0:
            return

        self.navigation_index -= 1

        directory = self.navigation_history[
            self.navigation_index
        ]

        self.navigate_to(
            directory,
            add_history=False,
        )

    # ========================================================
    # FORWARD
    # ========================================================

    def go_forward(self):

        if (
            self.navigation_index
            >= len(self.navigation_history) - 1
        ):
            return

        self.navigation_index += 1

        directory = self.navigation_history[
            self.navigation_index
        ]

        self.navigate_to(
            directory,
            add_history=False,
        )

    # ========================================================
    # UP
    # ========================================================

    def go_up(self):

        parent = self.current_directory.parent

        if parent == self.current_directory:
            return

        self.navigate_to(
            parent
        )

    # ========================================================
    # HOME
    # ========================================================

    def go_home(self):

        self.navigate_to(
            Path.home()
        )

    # ========================================================
    # ADDRESS BAR
    # ========================================================

    def navigate_to_address(self):

        text = (
            self.address_input.text().strip()
        )

        if not text:
            return

        directory = Path(
            os.path.expandvars(text)
        ).expanduser()

        if directory.is_file():

            self.navigate_to(
                directory.parent
            )

            self.show_preview(
                directory
            )

            return

        self.navigate_to(
            directory
        )

    # ========================================================
    # CHOOSE FOLDER
    # ========================================================

    def choose_folder(self):

        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose a Folder",
            str(self.current_directory),
        )

        if not directory:
            return

        self.navigate_to(
            directory
        )

    # ========================================================
    # UPDATE NAVIGATION BUTTONS
    # ========================================================

    def update_navigation_buttons(self):

        self.back_button.setEnabled(
            self.navigation_index > 0
        )

        self.forward_button.setEnabled(
            self.navigation_index
            < len(self.navigation_history) - 1
        )

        self.up_button.setEnabled(
            self.current_directory.parent
            != self.current_directory
        )

    # ========================================================
    # LOAD DIRECTORY
    # ========================================================

    def load_directory(self):

        # Navigation/import may load a folder before the first show.
        self._directory_loaded = True

        self.address_input.setText(
            str(self.current_directory)
        )

        self.update_navigation_buttons()

        entries = []

        try:

            with os.scandir(
                self.current_directory
            ) as iterator:

                for entry in iterator:

                    try:

                        path = Path(
                            entry.path
                        )

                        # Show both folders and files.
                        entries.append(
                            path
                        )

                    except OSError:
                        continue

        except PermissionError:

            QMessageBox.warning(
                self,
                "Access Denied",
                "You do not have permission to open this folder.",
            )

            return

        except OSError as error:

            QMessageBox.warning(
                self,
                "Folder Error",
                str(error),
            )

            return

        # ====================================================
        # FOLDERS FIRST
        # ====================================================

        entries.sort(
            key=lambda path: (
                not path.is_dir(),
                natural_sort_key(
                    path.name
                ),
            )
        )

        self.current_entries = entries

        self.filter_current_directory()

    # ========================================================
    # FILTER FILES
    # ========================================================

    def filter_current_directory(self):

        query = (
            self.search_input
            .text()
            .strip()
            .lower()
        )

        if query:

            visible_entries = [
                path
                for path in self.current_entries
                if query in path.name.lower()
            ]

        else:

            visible_entries = (
                self.current_entries
            )

        self._visible_entries = list(visible_entries)
        self._table_needs_refresh = True
        self._grid_needs_refresh = True

        if self.file_views.currentWidget() is self.file_grid:
            self.populate_grid(self._visible_entries)
            self._grid_needs_refresh = False
        else:
            self.populate_table(self._visible_entries)
            self._table_needs_refresh = False

        self.update_selection_status()

    # ========================================================
    # FILE ICON
    # ========================================================

    def get_file_icon(self, path):
        # Prefer Litenova's folder icon. No EPUB or CBZ icon was
        # supplied, so those retain their normal system file icon.
        if path.is_dir():
            if "<folder>" not in self._file_icon_cache:
                self._file_icon_cache["<folder>"] = browse_resource_icon(
                    "folder", "open_folder"
                )
            folder_icon = self._file_icon_cache["<folder>"]
            if not folder_icon.isNull():
                return folder_icon

        # Windows shell icons can be slow to retrieve on external drives.
        # Files of the same type can share a single cached icon.
        key = path.suffix.lower() or "<no_extension>"
        icon = self._file_icon_cache.get(key)
        if icon is None:
            icon = self.icon_provider.icon(QFileInfo(str(path)))
            self._file_icon_cache[key] = icon
        return icon

    # ========================================================
    # POPULATE TABLE
    # ========================================================

    def populate_table(self, entries):

        self.updating_file_views = True

        self.file_table.blockSignals(
            True
        )

        self.file_table.setRowCount(len(entries))

        for row, path in enumerate(entries):

            self.file_table.setRowHeight(
                row,
                45,
            )

            is_folder = path.is_dir()

            is_supported = supported_target(
                path
            )

            # =================================================
            # CHECKBOX COLUMN
            # =================================================

            checkbox_item = QTableWidgetItem()

            checkbox_item.setTextAlignment(
                Qt.AlignCenter
            )

            checkbox_item.setFlags(
                Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
            )

            if is_supported:

                checkbox_item.setFlags(
                    Qt.ItemIsEnabled
                    | Qt.ItemIsSelectable
                    | Qt.ItemIsUserCheckable
                )

                checkbox_item.setCheckState(
                    Qt.Checked
                    if path in self.checked_files
                    else Qt.Unchecked
                )

            self.file_table.setItem(
                row,
                0,
                checkbox_item,
            )

            # =================================================
            # NAME
            # =================================================

            name_item = QTableWidgetItem(
                path.name
            )

            name_item.setIcon(
                self.get_file_icon(path)
            )

            name_item.setData(
                Qt.UserRole,
                str(path),
            )

            self.file_table.setItem(
                row,
                1,
                name_item,
            )

            # =================================================
            # TYPE
            # =================================================

            type_item = QTableWidgetItem(
                get_file_type(path)
            )

            self.file_table.setItem(
                row,
                2,
                type_item,
            )

            # =================================================
            # SIZE AND DATE
            # =================================================

            try:

                file_stat = path.stat()

                size_text = (
                    ""
                    if is_folder
                    else format_file_size(
                        file_stat.st_size
                    )
                )

                modified_text = format_modified_time(
                    file_stat.st_mtime
                )

            except OSError:

                size_text = ""

                modified_text = ""

            size_item = QTableWidgetItem(
                size_text
            )

            size_item.setTextAlignment(
                Qt.AlignRight
                | Qt.AlignVCenter
            )

            self.file_table.setItem(
                row,
                3,
                size_item,
            )

            modified_item = QTableWidgetItem(
                modified_text
            )

            self.file_table.setItem(
                row,
                4,
                modified_item,
            )

        self.file_table.blockSignals(
            False
        )

        self.updating_file_views = False

    # ========================================================
    # POPULATE GRID
    # ========================================================

    def populate_grid(self, entries):

        self.updating_file_views = True

        self.file_grid.blockSignals(
            True
        )

        self.file_grid.clear()

        for path in entries:

            item = QListWidgetItem(
                self.get_file_icon(path),
                path.name,
            )

            item.setData(
                Qt.UserRole,
                str(path),
            )

            item.setTextAlignment(
                Qt.AlignCenter
            )

            item.setToolTip(
                str(path)
            )

            item.setFlags(
                Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
            )

            if supported_target(path):

                item.setFlags(
                    Qt.ItemIsEnabled
                    | Qt.ItemIsSelectable
                    | Qt.ItemIsUserCheckable
                )

                item.setCheckState(
                    Qt.Checked
                    if path in self.checked_files
                    else Qt.Unchecked
                )

            self.file_grid.addItem(
                item
            )

        self.file_grid.blockSignals(
            False
        )

        self.updating_file_views = False

    # ========================================================
    # GET TABLE ROW PATH
    # ========================================================

    def get_table_row_path(self, row):

        if row < 0:
            return None

        name_item = self.file_table.item(
            row,
            1,
        )

        if name_item is None:
            return None

        value = name_item.data(
            Qt.UserRole
        )

        if not value:
            return None

        return Path(
            str(value)
        )

    # ========================================================
    # TABLE CLICK
    # ========================================================

    def on_table_item_clicked(self, item):
        if self.updating_file_views:
            return
        path = self.get_table_row_path(item.row())
        if path is None:
            return
        self.queue_preview(path)
        # Shift+click uses Qt's range selection; do not flip the final row.
        if QApplication.keyboardModifiers() & (Qt.ShiftModifier | Qt.ControlModifier):
            return
        if item.column() == 0 or not supported_target(path):
            return
        checkbox_item = self.file_table.item(item.row(), 0)
        if checkbox_item is not None:
            checkbox_item.setCheckState(
                Qt.Unchecked if checkbox_item.checkState() == Qt.Checked else Qt.Checked
            )

    # ========================================================
    # TABLE CHECKBOX CHANGED
    # ========================================================

    def on_table_item_changed(self, item):

        if self.updating_file_views:
            return

        if item.column() != 0:
            return

        path = self.get_table_row_path(
            item.row()
        )

        if path is None:
            return

        if not supported_target(path):
            return

        if item.checkState() == Qt.Checked:

            self.checked_files.add(
                path
            )

        else:

            self.checked_files.discard(
                path
            )

        self.sync_grid_checkboxes()

        self.update_selection_status()

    # ========================================================
    # TABLE SELECTION CHANGED
    # ========================================================

    def on_table_selection_changed(self):
        if self.updating_file_views:
            return
        row = self.file_table.currentRow()
        path = self.get_table_row_path(row)
        if path is not None:
            self.queue_preview(path)
        # Qt ExtendedSelection selects the entire range between anchor and
        # clicked row. Convert that range into import checkmarks.
        if QApplication.keyboardModifiers() & Qt.ShiftModifier:
            paths = []
            for index in self.file_table.selectionModel().selectedRows():
                selected_path = self.get_table_row_path(index.row())
                if selected_path is not None:
                    paths.append(selected_path)
            self.check_selected_paths(paths)

    # ========================================================
    # TABLE DOUBLE CLICK
    # ========================================================

    def on_table_item_double_clicked(self, item):
        self._preview_timer.stop()
        self._queued_preview_path = None

        path = self.get_table_row_path(
            item.row()
        )

        if path is None:
            return

        if path.is_dir():

            self.navigate_to(
                path
            )

    # ========================================================
    # GRID ITEM CHANGED
    # ========================================================

    def on_grid_item_changed(self, item):

        if self.updating_file_views:
            return

        value = item.data(
            Qt.UserRole
        )

        if not value:
            return

        path = Path(
            str(value)
        )

        if not supported_target(path):
            return

        if item.checkState() == Qt.Checked:

            self.checked_files.add(
                path
            )

        else:

            self.checked_files.discard(
                path
            )

        self.sync_table_checkboxes()

        self.update_selection_status()

    # ========================================================
    # GRID SELECTION CHANGED
    # ========================================================

    def on_grid_current_item_changed(
        self,
        current,
        previous,
    ):

        if current is None:
            return

        value = current.data(
            Qt.UserRole
        )

        if value:

            self.queue_preview(
                Path(str(value))
            )

    # ========================================================
    # GRID DOUBLE CLICK
    # ========================================================

    def on_grid_item_double_clicked(self, item):
        self._preview_timer.stop()
        self._queued_preview_path = None

        value = item.data(
            Qt.UserRole
        )

        if not value:
            return

        path = Path(
            str(value)
        )

        if path.is_dir():

            self.navigate_to(
                path
            )

    # ========================================================
    # SYNCHRONIZE GRID CHECKBOXES
    # ========================================================

    def sync_grid_checkboxes(self):
        if self._grid_needs_refresh:
            return

        self.file_grid.blockSignals(
            True
        )

        for index in range(
            self.file_grid.count()
        ):

            item = self.file_grid.item(
                index
            )

            path = Path(
                str(
                    item.data(Qt.UserRole)
                )
            )

            if not supported_target(path):
                continue

            item.setCheckState(
                Qt.Checked
                if path in self.checked_files
                else Qt.Unchecked
            )

        self.file_grid.blockSignals(
            False
        )

    # ========================================================
    # SYNCHRONIZE TABLE CHECKBOXES
    # ========================================================

    def sync_table_checkboxes(self):
        if self._table_needs_refresh:
            return

        self.file_table.blockSignals(
            True
        )

        for row in range(
            self.file_table.rowCount()
        ):

            path = self.get_table_row_path(
                row
            )

            if path is None:
                continue

            if not supported_target(path):
                continue

            checkbox_item = self.file_table.item(
                row,
                0,
            )

            checkbox_item.setCheckState(
                Qt.Checked
                if path in self.checked_files
                else Qt.Unchecked
            )

        self.file_table.blockSignals(
            False
        )

    # ========================================================
    # LIST VIEW
    # ========================================================

    def show_list_view(self):

        if self._table_needs_refresh:
            self.populate_table(self._visible_entries)
            self._table_needs_refresh = False

        self.file_views.setCurrentWidget(
            self.file_table
        )

        self.list_button.setChecked(
            True
        )

        self.grid_button.setChecked(
            False
        )

    # ========================================================
    # GRID VIEW
    # ========================================================

    def show_grid_view(self):

        if self._grid_needs_refresh:
            self.populate_grid(self._visible_entries)
            self._grid_needs_refresh = False

        self.file_views.setCurrentWidget(
            self.file_grid
        )

        self.list_button.setChecked(
            False
        )

        self.grid_button.setChecked(
            True
        )

    # ========================================================
    # CLEAR PREVIEW
    # ========================================================

    def clear_preview(self):

        self.preview_path = None

        self.preview_original_pixmap = None

        self.preview_cover.clear()

        self.preview_cover.setText(
            "NO COVER"
        )

        self.preview_title.setText(
            "Select a file"
        )

        self.preview_author.setText(
            "Choose an EPUB or CBZ file to preview."
        )

        self.preview_size.clear()

        self.preview_modified.clear()

    # ========================================================
    # SET PREVIEW COVER
    # ========================================================

    def set_preview_cover(self, pixmap):

        self.preview_original_pixmap = (
            pixmap
        )

        self.preview_cover.clear()

        if (
            pixmap is None
            or pixmap.isNull()
        ):

            self.preview_cover.setText(
                "NO COVER"
            )

            return

        scaled = pixmap.scaled(
            self.preview_cover.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.preview_cover.setPixmap(
            scaled
        )

    # ========================================================
    # NON-BLOCKING CLICK FEEDBACK / COALESCED FILE PREVIEW
    # ========================================================

    def queue_preview(self, path):
        self._queued_preview_path = Path(str(path))
        if self.preview_path == self._queued_preview_path:
            self._preview_timer.stop()
            return
        # Extracting an EPUB/CBZ cover must not block the second click of
        # a double-click. The highlighted row still responds immediately.
        interval = (
            480
            if self._queued_preview_path.suffix.lower() in SUPPORTED_EXTENSIONS
            else 150
        )
        self._preview_timer.start(interval)

    def _show_queued_preview(self):
        path = self._queued_preview_path
        self._queued_preview_path = None
        if path is not None and path.parent == self.current_directory:
            self.show_preview(path)

    # ========================================================
    # SHOW FILE PREVIEW
    # ========================================================

    def show_preview(self, path):

        path = Path(
            str(path)
        )

        if (
            self.preview_path == path
        ):
            return

        self.preview_path = path

        self.preview_title.setText(
            path.name
        )

        self.preview_author.clear()

        self.preview_size.clear()

        self.preview_modified.clear()

        self.set_preview_cover(
            None
        )

        # ====================================================
        # FILE INFORMATION
        # ====================================================

        try:

            file_stat = path.stat()

            if path.is_file():

                self.preview_size.setText(
                    "File size\n"
                    + format_file_size(
                        file_stat.st_size
                    )
                )

            else:

                self.preview_size.setText(
                    "Folder"
                )

            self.preview_modified.setText(
                "Modified\n"
                + format_modified_time(
                    file_stat.st_mtime
                )
            )

        except OSError:
            pass

        # ====================================================
        # FOLDER
        # ====================================================

        if path.is_dir():

            self.preview_title.setText(
                path.name
            )

            chapters = folder_chapters(path)
            if chapters:
                epub_count = sum(ch.suffix.lower() == ".epub" for ch in chapters)
                cbz_count = len(chapters) - epub_count
                self.preview_author.setText(
                    f"Comic series folder • {len(chapters)} chapter(s)\n"
                    f"EPUB: {epub_count}   CBZ: {cbz_count}\n"
                    "Check the folder, then Import as Manga or Manhwa.\n"
                    "Double-click to browse its files."
                )
            else:
                self.preview_author.setText(
                    "Folder • Double-click to open.\n"
                    "Chapter files in subfolders can be browsed normally."
                )

            self.import_folder_button.setEnabled(
                True
            )

            return

        self.import_folder_button.setEnabled(
            False
        )

        # ====================================================
        # EPUB
        # ====================================================

        if path.suffix.lower() == ".epub":

            metadata = read_epub_preview(
                path
            )

            self.preview_title.setText(
                metadata["title"]
            )

            self.preview_author.setText(
                "Author\n"
                + metadata["author"]
            )

            self.set_preview_cover(
                metadata["cover"]
            )

        # ====================================================
        # CBZ
        # ====================================================

        elif path.suffix.lower() == ".cbz":

            metadata = read_cbz_preview(
                path
            )

            self.preview_title.setText(
                metadata["title"]
            )

            self.preview_author.setText(
                "Author\n"
                + metadata["author"]
            )

            self.set_preview_cover(
                metadata["cover"]
            )

        # ====================================================
        # UNSUPPORTED FILE
        # ====================================================

        else:

            self.preview_author.setText(
                "File type\n"
                + get_file_type(path)
            )

    # ========================================================
    # UPDATE SELECTED FILE COUNT
    # ========================================================

    def update_selection_status(self):
        targets = [p for p in self.checked_files if supported_target(p)]
        count = len(targets)
        total_size = 0
        for path in targets:
            if path.is_file():
                try:
                    total_size += path.stat().st_size
                except OSError:
                    pass
        self.import_button.setText(f"Import ({count})")
        self.import_button.setEnabled(count > 0)
        selected_chapters = [p for p in targets if p.is_file()]
        can_group = (
            len(selected_chapters) >= 2
            and len(selected_chapters) == count
            and len({p.parent for p in selected_chapters}) == 1
        )
        self.group_selected_button.setEnabled(can_group)
        self.import_description.setText(
            f"{count} item(s) selected for import. Folders become one comic series."
            if count else "Select EPUB/CBZ files or chapter folders. Shift+click selects a range."
        )
        if count:
            self.status_label.setText(
                f"{count} item(s) selected • Files: {format_file_size(total_size)}"
            )
        else:
            self.status_label.setText(
                f"{len(self.current_entries)} items   •   {self.current_directory}"
            )

    # ========================================================
    # BULK SELECTION (ALL / SHIFT+CLICK)
    # ========================================================

    def visible_import_targets(self):
        query = self.search_input.text().strip().casefold()
        return [
            path for path in self.current_entries
            if (not query or query in path.name.casefold())
            and supported_target(path)
        ]

    def check_selected_paths(self, paths):
        """Check all selected paths once instead of repainting per item."""
        valid = [path for path in paths if supported_target(path)]
        if not valid:
            return
        self.checked_files.update(valid)
        self.sync_table_checkboxes()
        self.sync_grid_checkboxes()
        self.update_selection_status()

    def select_all_visible(self):
        self.check_selected_paths(self.visible_import_targets())

    def clear_file_selection(self):
        self.checked_files.clear()
        self.file_table.clearSelection()
        self.file_grid.clearSelection()
        self.sync_table_checkboxes()
        self.sync_grid_checkboxes()
        self.update_selection_status()

    def on_grid_selection_changed(self):
        if self.updating_file_views:
            return
        if not (QApplication.keyboardModifiers() & Qt.ShiftModifier):
            return
        paths = []
        for item in self.file_grid.selectedItems():
            name = item.data(Qt.UserRole)
            if name:
                paths.append(Path(str(name)))
        self.check_selected_paths(paths)

    # ========================================================
    # DUPLICATE IMPORT CONFIRMATION
    # ========================================================

    def confirm_duplicate_import(
        self,
        item_name,
        item_type="item",
    ):
        """
        Ask whether an already-imported item should be imported
        again as a separate Library entry.
        """

        answer = QMessageBox.question(
            self,
            "Already in Library",
            (
                f"{item_name} is already in your Library.\n\n"
                f"Import another copy of this {item_type} anyway?\n\n"
                "The existing Library item will not be overwritten. "
                "The new copy will have its own reading progress."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        return (
            answer
            == QMessageBox.Yes
        )

    # ========================================================
    # IMPORT SELECTED CHAPTER FILES AS ONE SERIES
    # ========================================================

    def import_selected_as_series(self):
        """Explicitly group checked chapter files, without adding other files."""

        files = sorted(
            (
                p
                for p in self.checked_files
                if supported_file(p)
            ),
            key=lambda p: natural_sort_key(
                p.name
            ),
        )

        if (
            len(files) < 2
            or len(files)
            != len(self.checked_files)
            or len(
                {
                    p.parent
                    for p in files
                }
            )
            != 1
        ):
            QMessageBox.information(
                self,
                "Group chapters",
                (
                    "Select at least two EPUB/CBZ chapter files "
                    "in the same folder.\n"
                    "Alternatively, select their folder and click Import."
                ),
            )
            return

        category = (
            self.choose_comic_category()
        )

        if category is None:
            return

        self.group_selected_button.setEnabled(
            False
        )

        QApplication.setOverrideCursor(
            Qt.WaitCursor
        )

        try:

            with tempfile.TemporaryDirectory(
                prefix="litenova_selected_chapters_"
            ) as temp:

                staged = (
                    Path(temp)
                    / self.current_directory.name
                )

                staged.mkdir()

                for source in files:

                    shutil.copy2(
                        source,
                        staged
                        / source.name,
                    )

                try:

                    import_comic_chapter_folder(
                        staged,
                        category=category,
                    )

                except DuplicateBookError:

                    QApplication.restoreOverrideCursor()

                    import_again = (
                        self.confirm_duplicate_import(
                            self.current_directory.name,
                            "series",
                        )
                    )

                    QApplication.setOverrideCursor(
                        Qt.WaitCursor
                    )

                    if not import_again:
                        return

                    import_comic_chapter_folder(
                        staged,
                        category=category,
                        allow_duplicate=True,
                    )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Group Chapters Failed",
                str(error),
            )

        else:

            self.book_imported.emit()

            self.clear_file_selection()

            QMessageBox.information(
                self,
                "Series Imported",
                (
                    f"Imported {len(files)} chapters as one "
                    f"{category.title()} series.\n"
                    "Original files were kept."
                ),
            )

        finally:

            QApplication.restoreOverrideCursor()

            self.group_selected_button.setEnabled(
                True
            )

            self.update_selection_status()

    # ========================================================
    # CHOOSE COMIC CATEGORY
    # ========================================================

    def choose_comic_category(self):

        category_name, accepted = (
            QInputDialog.getItem(
                self,
                "Comic Category",
                "Import as:",
                [
                    "Manga",
                    "Manhwa",
                ],
                0,
                False,
            )
        )

        if not accepted:
            return None

        if category_name == "Manga":
            return "manga"

        return "manhwa"

    # ========================================================
    # IMPORT SELECTED FILES
    # ========================================================

    def import_selected_files(self):

        targets = sorted(
            (
                p
                for p in self.checked_files
                if supported_target(p)
            ),
            key=lambda p: natural_sort_key(
                p.name
            ),
        )

        if not targets:

            QMessageBox.information(
                self,
                "Import",
                "Select EPUB/CBZ files or chapter folders.",
            )

            return

        need_category = any(
            (
                p.is_dir()
                or p.suffix.lower()
                == ".cbz"
            )
            for p in targets
        )

        category = (
            self.choose_comic_category()
            if need_category
            else None
        )

        if (
            need_category
            and category is None
        ):
            return

        move_originals = (
            self.move_files_checkbox.isChecked()
        )

        if move_originals:

            answer = QMessageBox.question(
                self,
                "Move original files?",
                (
                    "Only successfully imported individual files "
                    "will be moved.\n"
                    "Original chapter folders and their contents "
                    "will be kept.\n\n"
                    "Continue?"
                ),
                QMessageBox.Yes
                | QMessageBox.No,
                QMessageBox.No,
            )

            if answer != QMessageBox.Yes:
                return

        imported = 0
        skipped_duplicates = []
        errors = []
        warnings = []

        self.import_button.setEnabled(
            False
        )

        QApplication.setOverrideCursor(
            Qt.WaitCursor
        )

        try:

            for path in targets:

                result = None

                try:

                    if path.is_dir():

                        result = (
                            import_comic_chapter_folder(
                                path,
                                category=category,
                            )
                        )

                    else:

                        result = import_book(
                            str(path),
                            category=(
                                "light_novel"
                                if path.suffix.lower()
                                == ".epub"
                                else category
                            ),
                        )

                except DuplicateBookError:

                    QApplication.restoreOverrideCursor()

                    import_again = (
                        self.confirm_duplicate_import(
                            path.name,
                            (
                                "series"
                                if path.is_dir()
                                else "book"
                            ),
                        )
                    )

                    QApplication.setOverrideCursor(
                        Qt.WaitCursor
                    )

                    if not import_again:

                        skipped_duplicates.append(
                            path.name
                        )

                        continue

                    try:

                        if path.is_dir():

                            result = (
                                import_comic_chapter_folder(
                                    path,
                                    category=category,
                                    allow_duplicate=True,
                                )
                            )

                        else:

                            result = import_book(
                                str(path),
                                category=(
                                    "light_novel"
                                    if path.suffix.lower()
                                    == ".epub"
                                    else category
                                ),
                                allow_duplicate=True,
                            )

                    except Exception as error:

                        errors.append(
                            f"{path.name}: {error}"
                        )

                        continue

                except Exception as error:

                    errors.append(
                        f"{path.name}: {error}"
                    )

                    continue

                imported += 1

                if (
                    move_originals
                    and path.is_file()
                ):

                    self.remove_original_after_import(
                        path,
                        result,
                        warnings,
                    )

        finally:

            QApplication.restoreOverrideCursor()

            self.import_button.setEnabled(
                True
            )

        if imported:

            self.book_imported.emit()

        self.checked_files.clear()

        self.clear_preview()

        self.load_directory()

        message = (
            f"Imported {imported} item(s). "
            "Each selected folder is one series."
        )

        if skipped_duplicates:

            message += (
                f"\nSkipped existing item(s): "
                f"{len(skipped_duplicates)}"
            )

        if errors:

            message += (
                f"\nFailed: {len(errors)}\n"
                + "\n".join(
                    errors[:8]
                )
            )

        if warnings:

            message += (
                "\nOriginals kept: "
                + ", ".join(
                    warnings[:8]
                )
            )

        if errors:

            QMessageBox.warning(
                self,
                "Import Results",
                message,
            )

        else:

            QMessageBox.information(
                self,
                "Import Results",
                message,
            )

    # ========================================================
    # REMOVE ORIGINAL AFTER IMPORT
    # ========================================================

    def remove_original_after_import(
        self,
        original_path,
        import_result,
        warnings,
    ):
        """
        Delete the source file only after confirming
        that an imported copy exists and matches its size.

        If the imported destination cannot be verified,
        the original file is kept.
        """

        try:

            if not isinstance(
                import_result,
                dict,
            ):

                warnings.append(
                    (
                        f"{original_path.name}: "
                        "Imported location could not be verified."
                    )
                )

                return

            imported_path = import_result.get(
                "file_path"
            )

            if not imported_path:

                imported_path = import_result.get(
                    "epub_path"
                )

            if not imported_path:

                warnings.append(
                    (
                        f"{original_path.name}: "
                        "Imported location could not be verified."
                    )
                )

                return

            destination = Path(
                str(imported_path)
            )

            if not destination.is_file():

                warnings.append(
                    (
                        f"{original_path.name}: "
                        "Imported copy could not be verified."
                    )
                )

                return

            if (
                destination.resolve()
                == original_path.resolve()
            ):

                # Never remove the only copy.
                return

            if (
                destination.stat().st_size
                != original_path.stat().st_size
            ):

                warnings.append(
                    (
                        f"{original_path.name}: "
                        "Imported copy size did not match."
                    )
                )

                return

            original_path.unlink()

        except Exception as error:

            warnings.append(
                (
                    f"{original_path.name}: "
                    f"{error}"
                )
            )

    # ========================================================
    # IMPORT COMIC FOLDER
    # ========================================================

    def import_comic_folder(self):

        folder = (
            self.preview_path
            if (
                self.preview_path
                is not None
                and self.preview_path.is_dir()
            )
            else self.current_directory
        )

        chapters = folder_chapters(
            folder
        )

        if not chapters:

            QMessageBox.information(
                self,
                "Import chapter folder",
                (
                    "The selected folder has no EPUB or CBZ "
                    "chapter files directly inside it.\n"
                    "Double-click a subfolder to browse it, or "
                    "select a folder with chapters."
                ),
            )

            return

        category = (
            self.choose_comic_category()
        )

        if category is None:
            return

        try:

            import_comic_chapter_folder(
                folder,
                category=category,
            )

        except DuplicateBookError:

            import_again = (
                self.confirm_duplicate_import(
                    folder.name,
                    "series",
                )
            )

            if not import_again:
                return

            try:

                import_comic_chapter_folder(
                    folder,
                    category=category,
                    allow_duplicate=True,
                )

            except Exception as error:

                QMessageBox.critical(
                    self,
                    "Import Failed",
                    str(error),
                )

                return

        except Exception as error:

            QMessageBox.critical(
                self,
                "Import Failed",
                str(error),
            )

            return

        self.book_imported.emit()

        QMessageBox.information(
            self,
            "Import Complete",
            (
                f"Imported {folder.name} as "
                f"{category.title()} with "
                f"{len(chapters)} chapters."
            ),
        )

        self.checked_files.discard(
            folder
        )

        self.load_directory()

    # ========================================================
    # STYLING
    # ========================================================

    def apply_page_style(self):

        self.setObjectName(
            "browsePage"
        )

        self.setStyleSheet(
            """
            QWidget#browsePage {
                background: #101217;
                color: #e8e8f5;
            }

            QLabel {
                background: transparent;
                border: none;
            }

            QLabel#browsePageTitle {
                color: #f1f0ff;
                font-size: 32px;
                font-weight: 700;
            }

            QLabel#browseSecondary {
                color: #bfc2d5;
                font-size: 13px;
            }

            QLabel#browsePreviewTitle {
                color: #f1f0ff;
                font-size: 17px;
                font-weight: 600;
            }

            QLabel#browseSectionTitle {
                color: #eeeefe;
                font-size: 19px;
                font-weight: 600;
            }

            QLabel#browseStatus {
                color: #bfc2d5;
                font-size: 13px;
                border-top: 1px solid #363b49;
                padding-top: 10px;
            }

            QLineEdit#browseSearch,
            QLineEdit#browseAddress {
                background: #11141b;
                color: #f0efff;
                border: 1px solid #454b5d;
                border-radius: 9px;
                padding-left: 12px;
                padding-right: 10px;
                font-size: 13px;
            }

            QLineEdit#browseSearch:focus,
            QLineEdit#browseAddress:focus {
                border: 1px solid #9c9de1;
            }

            QToolButton#browseNavigationButton {
                background: transparent;
                color: #cfd1ed;
                border: none;
                border-radius: 8px;
                font-size: 23px;
            }

            QToolButton#browseNavigationButton:hover {
                background: #25293a;
            }

            QToolButton#browseNavigationButton:disabled {
                color: #555a69;
            }

            QToolButton#browseViewButton {
                background: #131720;
                color: #d5d6f5;
                border: 1px solid #353a49;
                border-radius: 8px;
                font-size: 20px;
            }

            QToolButton#browseViewButton:checked {
                background: #333653;
                border: 1px solid #5d6286;
                color: #e7e8ff;
            }

            QTableWidget#browseFileTable {
                background: #101217;
                alternate-background-color: #101217;
                color: #e6e7f5;
                border: 1px solid #363b49;
                border-radius: 10px;
                gridline-color: transparent;
                selection-background-color: #373a59;
                selection-color: #ffffff;
                font-size: 13px;
                outline: none;
            }

            QTableWidget#browseFileTable::item {
                padding-left: 5px;
                border-bottom: 1px solid #1b1e26;
            }

            QTableWidget#browseFileTable::item:selected {
                background: #373a59;
                color: #ffffff;
            }

            QHeaderView::section {
                background: #191c24;
                color: #d9dbf0;
                border: none;
                border-right: 1px solid #292d38;
                border-bottom: 1px solid #363b49;
                padding: 9px;
                font-size: 13px;
                font-weight: 600;
            }

            QListWidget#browseFileGrid {
                background: #101217;
                color: #e8e8f5;
                border: 1px solid #363b49;
                border-radius: 10px;
                outline: none;
                font-size: 12px;
            }

            QListWidget#browseFileGrid::item {
                border: 1px solid transparent;
                border-radius: 10px;
                padding: 7px;
            }

            QListWidget#browseFileGrid::item:selected {
                background: #373a59;
                border: 1px solid #7779ba;
            }

            QListWidget#browseFileGrid::item:hover {
                background: #25283a;
            }

            QFrame#browsePreviewPanel {
                background: #15171d;
                border: 1px solid #303542;
                border-radius: 11px;
            }

            QScrollArea#browsePreviewScroll {
                background: transparent;
                border: none;
            }

            QLabel#browsePreviewCover {
                background: #1b1e27;
                color: #858ba5;
                border-radius: 9px;
                font-size: 12px;
            }

            QFrame#browseSeparator {
                background: #3a4050;
                border: none;
                min-height: 1px;
                max-height: 1px;
            }

            QPushButton#browseImportButton {
                background: #474979;
                border: 1px solid #898bd4;
                color: #f2f1ff;
                border-radius: 22px;
                font-size: 15px;
                font-weight: 600;
            }

            QPushButton#browseImportButton:hover {
                background: #575991;
            }

            QPushButton#browseImportButton:disabled {
                background: #292b3c;
                color: #777a91;
                border: 1px solid #44465b;
            }

            QPushButton#browseSecondaryButton {
                background: #1c2030;
                border: 1px solid #555b79;
                color: #e3e5ff;
                border-radius: 10px;
                font-size: 13px;
            }

            QPushButton#browseSecondaryButton:hover {
                background: #292f45;
            }

            QCheckBox {
                background: transparent;
                color: #e0e1f1;
                spacing: 9px;
                font-size: 13px;
            }

            QCheckBox::indicator {
                width: 17px;
                height: 17px;
            }

            QSplitter#browseSplitter::handle {
                background: transparent;
                width: 6px;
            }

            QScrollBar:vertical {
                background: #11141b;
                width: 9px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #454a60;
                border-radius: 4px;
                min-height: 28px;
            }
            """
        )
