"""
Litenova Library Page

Features:
- Cover-focused Grid view
- Compact List view
- Exclusive custom categories
- Adjustable cover size
- Reading progress
- Quick Read buttons
- Search and file-type filtering
- Sorting
- Edit, Move, and Remove books
- Collapsible Display / Sort / Filters panel
"""

import sys
import re

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import (
    Qt,
    Signal,
    QEvent,
    QTimer,
    QSettings,
    QPoint,
    QSize,
)

from PySide6.QtGui import QIcon, QColor, QPainter
from PySide6.QtCore import QRectF

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QScrollArea,
    QGridLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QToolButton,
    QComboBox,
    QSlider,
    QCheckBox,
    QMessageBox,
    QInputDialog,
    QDialog,
    QMenu,
)

from app.database.custom_categories_repository import (
    create_custom_category,
    get_custom_categories,
    get_custom_category,
    get_book_custom_category,
    move_book_to_custom_category,
    remove_book_from_custom_category,
    get_books_in_custom_category,
    get_uncategorized_books,
    delete_custom_category,
)

from app.database.history_repository import (
    get_last_read_entries,
)

from app.services.progress_service import (
    get_progress_by_book_id,
)

from app.services.library_service import (
    remove_book,
    edit_book_details,
)

from app.services.icon_service import ui_icon

from app.widgets.book_card import BookCard

from app.widgets.dialogs import EditBookDialog


# ============================================================
# HELPERS
# ============================================================

def book_value(book, key, default=""):

    try:

        if key in book.keys():

            value = book[key]

            if value is not None:
                return value

    except (
        KeyError,
        TypeError,
        AttributeError,
    ):
        pass

    return default


def date_number(value):

    if value is None:
        return 0.0

    try:

        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        ).timestamp()

    except (
        ValueError,
        TypeError,
        OverflowError,
    ):
        return 0.0


def optional_resource_icon(*names):
    """
    Find an optional PNG icon in resources/icons.

    If a matching file does not exist, return
    an empty QIcon so the original text symbol
    can be used instead.
    """

    if hasattr(sys, "_MEIPASS"):

        project_root = Path(
            sys._MEIPASS
        )

    else:

        project_root = (
            Path(__file__)
            .resolve()
            .parents[2]
        )

    icons_directory = (
        project_root
        / "resources"
        / "icons"
    )

    if not icons_directory.is_dir():
        return QIcon()

    def normalize(value):

        return re.sub(
            r"[^a-z0-9]",
            "",
            str(value).lower(),
        )

    wanted = {
        normalize(name)
        for name in names
    }

    try:

        for path in icons_directory.rglob(
            "*.png"
        ):

            stem = normalize(
                path.stem
            )

            # Supports filenames such as:
            #
            # grid.png
            # grid_view.png
            # grid_view_32.png
            #
            # without accidentally treating
            # unrelated icons as replacements.

            for name in wanted:

                if (
                    stem == name
                    or stem == name + "32"
                    or stem == name + "24"
                    or stem == name + "48"
                    or stem == name + "64"
                ):

                    icon = QIcon(
                        str(path)
                    )

                    if not icon.isNull():
                        return icon

    except OSError:
        pass

    return QIcon()


# ============================================================
# LIBRARY PAGE
# ============================================================



# LITENOVA_DISPLAY_PANEL_V1
class DisplayToggle(QCheckBox):
    """A clickable, accessible checkbox drawn as a lavender pill switch."""

    def __init__(self, title, description, parent=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        self.setAccessibleName(title)
        self.setToolTip(description)
        self.setFixedHeight(65)
        self.setCursor(Qt.PointingHandCursor)
        self.toggled.connect(lambda _checked: self.update())

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        x = self.width() - 57
        y = (self.height() - 30) / 2
        painter.setBrush(QColor("#51527f" if self.isChecked() else "#303344"))
        painter.drawRoundedRect(QRectF(x, y, 53, 30), 15, 15)
        painter.setBrush(QColor("#c5c4fa" if self.isChecked() else "#858aa6"))
        painter.drawEllipse(QRectF(x + (27 if self.isChecked() else 3), y + 3, 24, 24))

        font = painter.font()
        font.setPixelSize(14)
        painter.setFont(font)
        painter.setPen(QColor("#e7e8f6"))
        painter.drawText(0, 25, self.title)

        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(QColor("#aeb3c9"))
        painter.drawText(0, 46, self.description)
        painter.end()

class LibraryPage(QWidget):

    book_open_requested = Signal(object)

    def __init__(self):

        super().__init__()

        # ====================================================
        # CUSTOM CATEGORIES
        # ====================================================

        self.active_filter_type = "all"

        self.active_filter_value = None

        # ====================================================
        # DISPLAY SETTINGS
        # ====================================================

        self.preferences = QSettings(
            "Litenova",
            "Litenova",
        )

        self.display_mode = str(
            self.preferences.value(
                "library_display_mode",
                "grid",
            )
        )

        if self.display_mode not in (
            "grid",
            "list",
        ):

            self.display_mode = "grid"

        # Display panel is visible when the
        # Library opens for the first time.
        self.display_panel_visible = True

        # ====================================================
        # CARDS
        # ====================================================


        self.cards = []

        # LITENOVA_FAST_VIEW_SWITCH_V3

        self._view_cards = {
            "grid": None,
            "list": None,
        }

        self._visible_books = []

        self._visible_progress = {}

        self._layout_signature = None

        self._content_signature = None

        self._reflowing = False

        self._switching_view = False

        self._last_layout_width = 0

        self._cards_cover_width = 0

        # ====================================================
        # RESIZE TIMER
        # ====================================================

        self._resize_timer = QTimer(
            self
        )

        self._resize_timer.setSingleShot(
            True
        )

        self._resize_timer.setInterval(
            100
        )

        self._resize_timer.timeout.connect(
            self.reflow_cards
        )

        # ====================================================
        # BUILD UI
        # ====================================================

        self.build_ui()

        self.refresh_category_filter()

        self.load_books()

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        self.setObjectName(
            "libraryPage"
        )

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            21,
            20,
            14,
            14,
        )

        root.setSpacing(
            13
        )

        # ====================================================
        # HEADER
        # ====================================================

        header = QHBoxLayout()

        heading = QLabel(
            "Library"
        )

        heading.setObjectName(
            "libraryPageHeading"
        )

        header.addWidget(
            heading
        )

        header.addStretch()

        # ====================================================
        # GRID BUTTON
        # ====================================================

        self.grid_button = (
            self.header_button(
                "▦",
                "Grid view",
                self.show_grid_view,
                icon=optional_resource_icon(
                    "grid",
                    "grid_view",
                    "view_grid",
                ),
            )
        )

        # ====================================================
        # LIST BUTTON
        # ====================================================

        self.list_button = (
            self.header_button(
                "☰",
                "List view",
                self.show_list_view,
                icon=optional_resource_icon(
                    "list",
                    "list_view",
                    "view_list",
                ),
            )
        )

        # ====================================================
        # SORT BUTTON
        # ====================================================

        self.sort_button = (
            self.header_button(
                "↕",
                "Sort books",
                self.show_sort_menu,
                icon=optional_resource_icon(
                    "sort",
                    "sort_books",
                    "sort_order",
                ),
            )
        )

        # ====================================================
        # THREE-DOT DISPLAY BUTTON
        # ====================================================
        #
        # Clicking this button shows or hides
        # the entire panel on the right.
        #
        # It does not open a dropdown menu.
        # ====================================================

        self.more_button = QToolButton()

        self.more_button.setObjectName(
            "libraryHeaderButton"
        )

        self.more_button.setIcon(
            ui_icon("more_options")
        )

        self.more_button.setIconSize(
            QSize(22, 22)
        )

        self.more_button.setToolTip(
            "Show / Hide Display Options"
        )

        self.more_button.setFixedSize(
            42,
            42,
        )

        self.more_button.setCursor(
            Qt.PointingHandCursor
        )

        self.more_button.clicked.connect(
            self.toggle_display_panel
        )

        header.addWidget(
            self.grid_button
        )

        header.addWidget(
            self.list_button
        )

        header.addSpacing(
            6
        )

        header.addWidget(
            self.sort_button
        )

        header.addWidget(
            self.more_button
        )

        header.addSpacing(
            16
        )

        # ====================================================
        # ADD CATEGORY
        # ====================================================

        self.new_category_button = QPushButton(
            "＋  Add Category"
        )

        self.new_category_button.setObjectName(
            "libraryAddFolder"
        )

        self.new_category_button.setFixedHeight(
            43
        )

        self.new_category_button.setCursor(
            Qt.PointingHandCursor
        )

        self.new_category_button.clicked.connect(
            self.create_category
        )

        header.addWidget(
            self.new_category_button
        )

        self.delete_category_button = QPushButton(
            "Delete Category"
        )

        self.delete_category_button.setObjectName(
            "libraryDeleteCategory"
        )

        self.delete_category_button.setFixedHeight(
            43
        )

        self.delete_category_button.setCursor(
            Qt.PointingHandCursor
        )

        self.delete_category_button.setToolTip(
            "Delete the selected custom category"
        )

        self.delete_category_button.clicked.connect(
            self.delete_selected_category
        )

        header.addWidget(
            self.delete_category_button
        )

        root.addLayout(
            header
        )

        # ====================================================
        # MAIN AREA
        # ====================================================

        body = QHBoxLayout()

        body.setSpacing(
            13
        )

        # ====================================================
        # LEFT SIDE
        # ====================================================

        left = QVBoxLayout()

        left.setSpacing(
            12
        )

        # ====================================================
        # CATEGORY AND SEARCH
        # ====================================================

        bar = QHBoxLayout()

        # ====================================================
        # CATEGORY SELECTOR
        # ====================================================

        self.category_filter = QComboBox()

        self.category_filter.setObjectName(
            "libraryCategory"
        )

        self.category_filter.setMinimumWidth(
            180
        )

        self.category_filter.setFixedHeight(
            45
        )

        self.category_filter.currentIndexChanged.connect(
            self.category_filter_changed
        )

        bar.addWidget(
            self.category_filter,
            1,
        )

        # ====================================================
        # SEARCH
        # ====================================================

        self.search_input = QLineEdit()

        self.search_input.setObjectName(
            "librarySearch"
        )

        self.search_input.setPlaceholderText(
            "Search books or authors..."
        )

        self.search_input.addAction(
            ui_icon("search"),
            QLineEdit.LeadingPosition,
        )

        self.search_input.setClearButtonEnabled(
            True
        )

        self.search_input.setFixedHeight(
            45
        )

        self.search_input.textChanged.connect(
            self.search_changed
        )

        bar.addWidget(
            self.search_input,
            1,
        )

        left.addLayout(
            bar
        )

        # ====================================================
        # BOOK GRID SCROLL AREA
        # ====================================================

        self.scroll_area = QScrollArea()

        self.scroll_area.setObjectName(
            "libraryBooksScroll"
        )

        self.scroll_area.setWidgetResizable(
            True
        )

        self.scroll_area.setFrameShape(
            QFrame.NoFrame
        )

        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.books_container = QWidget()

        self.books_container.setObjectName(
            "libraryBooksContainer"
        )

        self.books_layout = QGridLayout(
            self.books_container
        )

        self.books_layout.setContentsMargins(
            0,
            2,
            0,
            8,
        )

        self.books_layout.setHorizontalSpacing(
            22
        )

        self.books_layout.setVerticalSpacing(
            18
        )

        self.books_layout.setAlignment(
            Qt.AlignTop
            | Qt.AlignLeft
        )

        self.scroll_area.setWidget(
            self.books_container
        )

        self.scroll_area.viewport().installEventFilter(
            self
        )

        left.addWidget(
            self.scroll_area,
            1,
        )

        body.addLayout(
            left,
            1,
        )

        # ====================================================
        # RIGHT DISPLAY PANEL
        # ====================================================

        self.settings_panel = QFrame()

        self.settings_panel.setObjectName(
            "libraryDisplayPanel"
        )

        self.settings_panel.setFixedWidth(
            340
        )

        side = QVBoxLayout(
            self.settings_panel
        )

        side.setContentsMargins(
            16,
            17,
            16,
            16,
        )

        side.setSpacing(
            11
        )

        side.addWidget(
            self.side_heading(
                "Display"
            )
        )

        # ====================================================
        # DISPLAY MODE
        # ====================================================

        side.addWidget(
            self.side_label(
                "Display mode"
            )
        )

        mode_row = QHBoxLayout()

        mode_row.setSpacing(
            0
        )

        self.grid_mode_button = QPushButton(
            "Grid"
        )

        self.list_mode_button = QPushButton(
            "List"
        )

        for button in (
            self.grid_mode_button,
            self.list_mode_button,
        ):

            button.setObjectName(
                "libraryModeButton"
            )

            button.setCheckable(
                True
            )

            button.setFixedHeight(
                43
            )

            button.setCursor(
                Qt.PointingHandCursor
            )

        self.grid_mode_button.clicked.connect(
            self.show_grid_view
        )

        self.list_mode_button.clicked.connect(
            self.show_list_view
        )

        mode_row.addWidget(
            self.grid_mode_button
        )

        mode_row.addWidget(
            self.list_mode_button
        )

        side.addLayout(
            mode_row
        )

        # ====================================================
        # GRID SIZE
        # ====================================================

        side.addWidget(
            self.side_label(
                "Grid size"
            )
        )

        size_row = QHBoxLayout()

        self.grid_size_label = (
            self.side_label(
                "Auto"
            )
        )

        self.grid_size_label.setFixedWidth(
            49
        )

        self.grid_slider = QSlider(
            Qt.Horizontal
        )
        self.grid_slider.setObjectName("libraryGridSize")

        self.grid_slider.setRange(
            0,
            5,
        )

        self.grid_slider.setSingleStep(
            1
        )

        try:

            saved_size = int(
                self.preferences.value(
                    "library_grid_size",
                    0,
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            saved_size = 0

        self.grid_slider.setValue(
            max(
                0,
                min(
                    saved_size,
                    5,
                ),
            )
        )

        self.grid_slider.valueChanged.connect(
            self.grid_size_changed
        )

        size_row.addWidget(
            self.grid_size_label
        )

        size_row.addWidget(
            self.grid_slider,
            1,
        )

        side.addLayout(
            size_row
        )

        # ====================================================
        # DISPLAY OPTIONS
        # ====================================================

        self.show_progress_box = (
            self.toggle_checkbox(
                "Show progress",
                "Display reading progress on covers",
            )
        )


        self.show_progress_box.setChecked(
            self.setting_bool(
                "library_show_progress",
                True,
            )
        )


        self.show_progress_box.toggled.connect(
            self.display_options_changed
        )


        side.addWidget(
            self.show_progress_box
        )


        # ====================================================
        # SORT
        # ====================================================

        side.addWidget(
            self.side_rule()
        )

        side.addWidget(
            self.side_heading(
                "Sort"
            )
        )

        self.sort_combo = QComboBox()

        self.sort_combo.setObjectName(
            "librarySideCombo"
        )

        self.sort_combo.setFixedHeight(
            42
        )

        sort_options = (
            ("Last read", "last_read"),
            ("Title A–Z", "title"),
            ("Author A–Z", "author"),
            ("Recently added", "date_added"),
            ("Reading progress", "progress"),
        )

        for title, key in sort_options:

            self.sort_combo.addItem(
                title,
                key,
            )

        saved_sort = str(
            self.preferences.value(
                "library_sort",
                "last_read",
            )
        )

        for index in range(
            self.sort_combo.count()
        ):

            if (
                self.sort_combo.itemData(index)
                == saved_sort
            ):

                self.sort_combo.setCurrentIndex(
                    index
                )

                break

        self.sort_combo.currentIndexChanged.connect(
            self.sort_changed
        )

        side.addWidget(
            self.sort_combo
        )

        # ====================================================
        # FILTERS
        # ====================================================

        side.addWidget(
            self.side_rule()
        )

        side.addWidget(
            self.side_heading(
                "Filters"
            )
        )

        # A second search field in the side panel, synchronized with
        # the main Library search instead of applying a second filter.
        self.side_search_input = QLineEdit()
        self.side_search_input.setObjectName("librarySideSearch")
        self.side_search_input.setPlaceholderText("Search files...")
        self.side_search_input.setClearButtonEnabled(True)
        self.side_search_input.setFixedHeight(42)
        self.side_search_input.addAction(
            ui_icon("search"), QLineEdit.LeadingPosition
        )
        self.side_search_input.textChanged.connect(self.search_input.setText)
        self.search_input.textChanged.connect(self.side_search_input.setText)
        side.addWidget(self.side_search_input)

        side.addWidget(
            self.side_label(
                "File type"
            )
        )

        self.type_combo = QComboBox()

        self.type_combo.setObjectName(
            "librarySideCombo"
        )

        self.type_combo.setFixedHeight(
            42
        )

        self.type_combo.addItem(
            "All supported files",
            "all",
        )

        self.type_combo.addItem(
            "Light Novels (EPUB)",
            "light_novel",
        )

        self.type_combo.addItem(
            "Manga (CBZ)",
            "manga",
        )

        self.type_combo.addItem(
            "Manhwa (CBZ)",
            "manhwa",
        )

        self.type_combo.currentIndexChanged.connect(
            self.load_books
        )

        side.addWidget(
            self.type_combo
        )

        side.addStretch()

        # ====================================================
        # BOOK COUNT
        # ====================================================

        self.side_count = self.side_label(
            "0 books"
        )

        side.addWidget(
            self.side_count
        )

        body.addWidget(
            self.settings_panel
        )

        root.addLayout(
            body,
            1,
        )


        # ====================================================
        # INITIAL DISPLAY STATE
        # ====================================================

        self.settings_panel.setVisible(
            self.display_panel_visible
        )

        self.update_mode_buttons()

        self.grid_size_changed(
            self.grid_slider.value(),
            reload=False,
        )

        self.update_display_button()

        self.apply_page_style()
        self.install_custom_dropdown_arrow()

    # ========================================================
    # HEADER BUTTON
    # ========================================================

    def header_button(
        self,
        text,
        tooltip,
        callback,
        icon=None,
    ):

        button = QToolButton()

        button.setObjectName(
            "libraryHeaderButton"
        )

        button.setToolTip(
            tooltip
        )

        button.setFixedSize(
            42,
            42,
        )

        button.setCursor(
            Qt.PointingHandCursor
        )

        if (
            icon is not None
            and not icon.isNull()
        ):

            button.setIcon(
                icon
            )

            button.setIconSize(
                QSize(22, 22)
            )

        else:

            button.setText(
                text
            )

        button.clicked.connect(
            callback
        )

        return button

    # ========================================================
    # TOGGLE DISPLAY PANEL
    # ========================================================

    def toggle_display_panel(self):
        """Toggle the panel without rebuilding book cards."""
        self.display_panel_visible = not self.display_panel_visible
        self.settings_panel.setVisible(self.display_panel_visible)
        self.update_display_button()
        # Resizing the viewport already schedules a debounced reflow.
        # There is no need to reload every book or display a second window.
        self._resize_timer.start()

    # ========================================================
    # UPDATE THREE-DOT BUTTON
    # ========================================================

    def update_display_button(self):

        self.more_button.setProperty(
            "active",
            self.display_panel_visible,
        )

        if self.display_panel_visible:

            self.more_button.setToolTip(
                "Hide Display Options"
            )

        else:

            self.more_button.setToolTip(
                "Show Display Options"
            )

        self.more_button.style().unpolish(
            self.more_button
        )

        self.more_button.style().polish(
            self.more_button
        )

        self.more_button.update()

    # ========================================================
    # SIDE PANEL HELPERS
    # ========================================================


    # LITENOVA_DISPLAY_ALIGNMENT_V1

    # ========================================================
    # DISPLAY PANEL HEADING
    # ========================================================

    def side_heading(self, text):
        """
        Create a section heading with no additional
        horizontal padding, indentation, or margin.

        Display, Sort, and Filters will use the
        same left alignment as the panel labels.
        """

        label = QLabel(text)

        label.setObjectName(
            "librarySideHeading"
        )

        # Remove QLabel's internal indentation.

        label.setIndent(0)

        label.setMargin(0)

        # Keep the content aligned to the left.

        label.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        # Remove additional widget margins.

        label.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        # Remove internal stylesheet padding that
        # can cause headings to appear farther
        # to the right than the other controls.

        label.setStyleSheet("""
            QLabel#librarySideHeading {
                background: transparent;

                color: #c1c5ff;

                font-size: 19px;
                font-weight: 700;

                border: none;

                margin: 0px;

                padding: 0px;
            }
        """)

        return label

    # ========================================================
    # DISPLAY PANEL LABEL
    # ========================================================

    def side_label(self, text):
        """
        Create a regular panel label using the
        same left alignment as the section headings.
        """

        label = QLabel(text)

        label.setObjectName(
            "librarySideLabel"
        )

        label.setIndent(0)

        label.setMargin(0)

        label.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        label.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        label.setStyleSheet("""
            QLabel#librarySideLabel {
                background: transparent;

                color: #cbd0e5;

                font-size: 14px;

                border: none;

                margin: 0px;

                padding: 0px;
            }
        """)

        return label

    def side_rule(self):

        rule = QFrame()

        rule.setObjectName(
            "librarySideRule"
        )

        rule.setFixedHeight(
            1
        )

        return rule

    def toggle_checkbox(self, text, description):
        return DisplayToggle(text, description, self)

    # ========================================================
    # SAVED BOOLEAN SETTING
    # ========================================================

    def setting_bool(
        self,
        key,
        default,
    ):

        value = self.preferences.value(
            key,
            default,
        )

        if isinstance(value, bool):
            return value

        return (
            str(value).strip().lower()
            in (
                "true",
                "1",
                "yes",
                "on",
            )
        )

    # ========================================================
    # REFRESH CATEGORY FILTER
    # ========================================================

    def refresh_category_filter(
        self,
        select_custom_id=None,
    ):

        self.category_filter.blockSignals(
            True
        )

        self.category_filter.clear()

        # ====================================================
        # ALL BOOKS
        # ====================================================

        folder_icon = ui_icon(
            "open_folder"
        )

        self.category_filter.addItem(
            folder_icon,
            "All Books",
            (
                "all",
                None,
            ),
        )

        # ====================================================
        # CUSTOM CATEGORIES
        # ====================================================

        for category in get_custom_categories():

            self.category_filter.addItem(
                folder_icon,
                (
                    f"{category['name']} "
                    f"({category['book_count']})"
                ),
                (
                    "custom",
                    category["id"],
                ),
            )

        # ====================================================
        # KEEP SELECTION
        # ====================================================

        if select_custom_id is not None:

            desired = (
                "custom",
                select_custom_id,
            )

        else:

            desired = (
                self.active_filter_type,
                self.active_filter_value,
            )

        target = 0

        for index in range(
            self.category_filter.count()
        ):

            if (
                self.category_filter.itemData(index)
                == desired
            ):

                target = index

                break

        self.category_filter.setCurrentIndex(
            target
        )

        data = (
            self.category_filter.itemData(
                target
            )
        )

        if data is not None:

            (
                self.active_filter_type,
                self.active_filter_value,
            ) = data

        self.category_filter.blockSignals(
            False
        )

    # ========================================================
    # CATEGORY CHANGED
    # ========================================================

    def category_filter_changed(
        self,
        _index,
    ):

        data = (
            self.category_filter.currentData()
        )

        if data is None:
            return

        (
            self.active_filter_type,
            self.active_filter_value,
        ) = data

        self.load_books()

    # ========================================================
    # CREATE CATEGORY
    # ========================================================

    def create_category(self):

        name, accepted = (
            QInputDialog.getText(
                self,
                "Add Category",
                "New category name:",
            )
        )

        if (
            not accepted
            or not name.strip()
        ):
            return

        try:

            category_id = (
                create_custom_category(
                    name.strip()
                )
            )

        except Exception as error:

            QMessageBox.warning(
                self,
                "Add Category",
                str(error),
            )

            return

        self.active_filter_type = (
            "custom"
        )

        self.active_filter_value = (
            category_id
        )

        self.refresh_category_filter(
            select_custom_id=category_id
        )

        self.load_books()

    # ========================================================
    # CATEGORY OPTIONS
    # ========================================================

    def show_category_menu(self):
        """
        Category management is available
        from the category dropdown's context menu.

        The header three-dot button is reserved
        exclusively for the Display panel.
        """

        menu = QMenu(
            self.category_filter
        )

        menu.addAction(
            "Refresh Library"
        ).triggered.connect(
            self.refresh_library
        )

        if self.active_filter_type == "custom":

            menu.addSeparator()

            menu.addAction(
                "Rename Category"
            ).triggered.connect(
                self.rename_category
            )

            menu.addAction(
                "Delete Category"
            ).triggered.connect(
                self.delete_selected_category
            )

        menu.exec(
            self.category_filter.mapToGlobal(
                QPoint(
                    0,
                    self.category_filter.height(),
                )
            )
        )

    # ========================================================
    # RENAME CATEGORY
    # ========================================================

    def rename_category(self):

        if self.active_filter_type != "custom":
            return

        category = get_custom_category(
            self.active_filter_value
        )

        if category is None:
            return

        new_name, accepted = (
            QInputDialog.getText(
                self,
                "Rename Category",
                "Category name:",
                text=str(
                    category["name"]
                ),
            )
        )

        if (
            not accepted
            or not new_name.strip()
            or new_name.strip()
            == category["name"]
        ):
            return

        try:

            from app.database.database import (
                get_connection,
            )

            connection = get_connection()

            try:

                connection.execute(
                    """
                    UPDATE custom_categories
                    SET name = ?
                    WHERE id = ?
                    """,
                    (
                        new_name.strip(),
                        self.active_filter_value,
                    ),
                )

                connection.commit()

            finally:

                connection.close()

        except Exception as error:

            QMessageBox.warning(
                self,
                "Rename Category",
                (
                    "Could not rename category."
                    f"\n\n{error}"
                ),
            )

            return

        self.refresh_library()

    # ========================================================
    # DELETE CATEGORY
    # ========================================================

    def delete_selected_category(self):

        if self.active_filter_type != "custom":
            return

        category = get_custom_category(
            self.active_filter_value
        )

        if category is None:
            return

        answer = QMessageBox.question(
            self,
            "Delete Category",
            (
                f'Delete "{category["name"]}"?\n\n'
                "Its books will return to All Books. "
                "The actual EPUB/CBZ files will not "
                "be deleted."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:

            delete_custom_category(
                self.active_filter_value
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Delete Category",
                str(error),
            )

            return

        self.active_filter_type = "all"

        self.active_filter_value = None

        self.refresh_library()

    # ========================================================
    # MOVE BOOK
    # ========================================================

    def move_book(
        self,
        book,
    ):

        categories = list(
            get_custom_categories()
        )

        current = (
            get_book_custom_category(
                book["id"]
            )
        )

        options = [
            "All Books"
        ]

        options += [
            str(category["name"])
            for category in categories
        ]

        ids = [
            None
        ]

        ids += [
            category["id"]
            for category in categories
        ]

        current_id = (
            current["id"]
            if current is not None
            else None
        )

        selected = (
            ids.index(current_id)
            if current_id in ids
            else 0
        )

        chosen, accepted = (
            QInputDialog.getItem(
                self,
                "Move Book",
                (
                    f'Move "{book_value(book, "title", "Book")}" '
                    "to:"
                ),
                options,
                selected,
                False,
            )
        )

        if not accepted:
            return

        destination = ids[
            options.index(chosen)
        ]

        if destination == current_id:
            return

        try:

            if destination is None:

                remove_book_from_custom_category(
                    book["id"]
                )

            else:

                move_book_to_custom_category(
                    book["id"],
                    destination,
                )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Move Failed",
                str(error),
            )

            return

        self.refresh_library()

    # ========================================================
    # EDIT BOOK
    # ========================================================

    def edit_book(
        self,
        book,
    ):

        dialog = EditBookDialog(
            book,
            self,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        values = dialog.get_values()

        try:

            edit_book_details(
                book=book,
                title=values["title"],
                author=values["author"],
                new_cover_path=values["new_cover_path"],
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Edit Failed",
                str(error),
            )

            return

        self.load_books()

    # ========================================================
    # REMOVE BOOK
    # ========================================================

    def confirm_remove_book(
        self,
        book,
    ):

        title = book_value(
            book,
            "title",
            "this book",
        )

        answer = QMessageBox.question(
            self,
            "Remove Book",
            (
                f'Remove "{title}" from your Library?\n\n'
                "Its local files and reading progress "
                "will also be removed."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:

            remove_book(
                book
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Remove Failed",
                str(error),
            )

            return

        self.refresh_library()

    # ========================================================
    # SEARCH
    # ========================================================

    def search_changed(
        self,
        *_args,
    ):

        self.load_books()

    # ========================================================
    # SORT CHANGED
    # ========================================================

    def sort_changed(
        self,
        *_args,
    ):

        self.preferences.setValue(
            "library_sort",
            self.sort_combo.currentData(),
        )

        self.load_books()

    # ========================================================
    # HEADER SORT MENU
    # ========================================================

    def show_sort_menu(self):

        menu = QMenu(
            self.sort_button
        )

        for index in range(
            self.sort_combo.count()
        ):

            action = menu.addAction(
                self.sort_combo.itemText(
                    index
                )
            )

            action.setCheckable(
                True
            )

            action.setChecked(
                index
                == self.sort_combo.currentIndex()
            )

            action.triggered.connect(
                lambda _checked=False, i=index:
                self.sort_combo.setCurrentIndex(i)
            )

        menu.popup(
            self.sort_button.mapToGlobal(
                QPoint(
                    0,
                    self.sort_button.height(),
                )
            )
        )

    # ========================================================
    # UPDATE DISPLAY MODE BUTTONS
    # ========================================================

    def update_mode_buttons(self):

        grid = (
            self.display_mode == "grid"
        )

        self.grid_mode_button.setChecked(
            grid
        )

        self.list_mode_button.setChecked(
            not grid
        )

        self.grid_mode_button.setText(
            "✓  Grid"
            if grid
            else "Grid"
        )

        self.list_mode_button.setText(
            "List"
            if grid
            else "✓  List"
        )

        self.grid_button.setProperty(
            "active",
            grid,
        )

        self.list_button.setProperty(
            "active",
            not grid,
        )

        for button in (
            self.grid_button,
            self.list_button,
        ):

            button.style().unpolish(
                button
            )

            button.style().polish(
                button
            )

        self.grid_slider.setEnabled(
            grid
        )

    # ========================================================
    # GRID VIEW
    # ========================================================


    def show_grid_view(self):

        if self.display_mode == "grid":
            return

        self.display_mode = "grid"

        self.preferences.setValue(
            "library_display_mode",
            "grid",
        )

        self.update_mode_buttons()

        self._activate_cached_view()

    # ========================================================
    # LIST VIEW
    # ========================================================


    def show_list_view(self):

        if self.display_mode == "list":
            return

        self.display_mode = "list"

        self.preferences.setValue(
            "library_display_mode",
            "list",
        )

        self.update_mode_buttons()

        self._activate_cached_view()

    # ========================================================
    # GRID SIZE
    # ========================================================

    def grid_size_changed(
        self,
        value,
        reload=True,
    ):

        self.grid_size_label.setText(
            "Auto"
            if value == 0
            else str(value)
        )

        self.preferences.setValue(
            "library_grid_size",
            int(value),
        )

        if (
            reload
            and self.display_mode == "grid"
        ):

            self.load_books()

    # ========================================================
    # DISPLAY OPTIONS
    # ========================================================

    def display_options_changed(
        self,
        *_args,
    ):

        self.preferences.setValue(
            "library_show_progress",
            self.show_progress_box.isChecked(),
        )


        self.load_books()

    # ========================================================
    # REFRESH LIBRARY
    # ========================================================

    def refresh_library(self):

        self.refresh_category_filter()

        self.load_books()

    # ========================================================
    # LOAD BOOKS
    # ========================================================

    def load_books(
        self,
        *_args,
    ):

        # ====================================================
        # CURRENT CATEGORY
        # ====================================================
        #
        # All Books remains the default category.
        #
        # Moving a book into a custom category
        # removes it from All Books.
        # ====================================================

        if self.active_filter_type == "custom":

            books = list(
                get_books_in_custom_category(
                    self.active_filter_value
                )
            )

        else:

            books = list(
                get_uncategorized_books()
            )

        # ====================================================
        # SEARCH
        # ====================================================

        query = (
            self.search_input
            .text()
            .strip()
            .casefold()
        )

        if query:

            books = [
                book
                for book in books
                if (
                    query
                    in str(
                        book_value(
                            book,
                            "title",
                        )
                    ).casefold()
                    or query
                    in str(
                        book_value(
                            book,
                            "author",
                        )
                    ).casefold()
                )
            ]

        # ====================================================
        # FILE TYPE FILTER
        # ====================================================

        selected_type = (
            self.type_combo.currentData()
        )

        if (
            selected_type
            and selected_type != "all"
        ):

            books = [
                book
                for book in books
                if book_value(
                    book,
                    "category",
                ) == selected_type
            ]

        # ====================================================
        # LAST READ TIMES
        # ====================================================

        history_times = {}

        try:

            for entry in get_last_read_entries():

                book_id = book_value(
                    entry,
                    "book_id",
                    None,
                )

                when = date_number(
                    book_value(
                        entry,
                        "last_read",
                        None,
                    )
                )

                history_times[book_id] = max(
                    when,
                    history_times.get(
                        book_id,
                        0.0,
                    ),
                )

        except Exception:
            pass

        # ====================================================
        # READING PROGRESS
        # ====================================================

        progress_by_id = {}
        stored_progress = get_progress_by_book_id()

        for book in books:

            try:

                progress = stored_progress.get(book["id"])

                position = float(
                    book_value(
                        progress,
                        "position",
                        0.0,
                    )
                )

                progress_by_id[
                    book["id"]
                ] = max(
                    0.0,
                    min(
                        position,
                        1.0,
                    ),
                )

            except (
                TypeError,
                ValueError,
                KeyError,
                OSError,
            ):

                progress_by_id[
                    book["id"]
                ] = 0.0

        # ====================================================
        # SORT BOOKS
        # ====================================================

        sort_key = (
            self.sort_combo.currentData()
        )

        if sort_key == "title":

            books.sort(
                key=lambda book: str(
                    book_value(
                        book,
                        "title",
                    )
                ).casefold()
            )

        elif sort_key == "author":

            books.sort(
                key=lambda book: (
                    str(
                        book_value(
                            book,
                            "author",
                        )
                    ).casefold(),
                    str(
                        book_value(
                            book,
                            "title",
                        )
                    ).casefold(),
                )
            )

        elif sort_key == "date_added":

            books.sort(
                key=lambda book: date_number(
                    book_value(
                        book,
                        "date_added",
                    )
                ),
                reverse=True,
            )

        elif sort_key == "progress":

            books.sort(
                key=lambda book: progress_by_id.get(
                    book["id"],
                    0.0,
                ),
                reverse=True,
            )

        else:

            books.sort(
                key=lambda book: (
                    history_times.get(
                        book["id"],
                        0.0,
                    ),
                    date_number(
                        book_value(
                            book,
                            "date_added",
                        )
                    ),
                ),
                reverse=True,
            )

        # ====================================================
        # CLEAR OLD CARDS
        # ====================================================


        # Reuse widgets when returning from Browse/History or reopening
        # the Display panel. Only rebuild when visible book data changes.
        content_signature = (
            self.active_filter_type,
            self.active_filter_value,
            tuple(
                (
                    book_value(book, "id"),
                    book_value(book, "title"),
                    book_value(book, "author"),
                    BookCard.cover_file_signature(book_value(book, "cover_path")),
                    book_value(book, "category"),
                    book_value(book, "file_path"),
                    progress_by_id.get(book["id"], 0.0))
                for book in books
            ),
            bool(self.show_progress_box.isChecked()),
            self.grid_slider.value(),
        )
        if (
            content_signature == self._content_signature
            and self._view_cards.get(self.display_mode) is not None
        ):
            self._resize_timer.start()
            return

        self._visible_books = books
        self._visible_progress = progress_by_id
        self.clear_books()
        self._content_signature = content_signature

        cover_width = (
            self.current_cover_width()
        )

        self._cards_cover_width = (
            cover_width
        )

        # ====================================================
        # CREATE NEW CARDS
        # ====================================================


        self.cards = self._create_view_cards(
            self.display_mode,
            cover_width,
        )

        self._view_cards[self.display_mode] = self.cards

        self._layout_signature = None

        # ====================================================
        # BOOK COUNT
        # ====================================================

        count = len(
            books
        )

        count_text = (
            f"{count} "
            f"{'book' if count == 1 else 'books'}"
        )


        self.side_count.setText(
            count_text
        )

        # ====================================================
        # DISPLAY CARDS
        # ====================================================

        self.reflow_cards()

        # ====================================================
        # EMPTY CATEGORY
        # ====================================================

        if not books:

            if (
                query
                or selected_type != "all"
            ):

                message = (
                    "No matching books."
                )

            else:

                message = (
                    "This category is empty. "
                    "Import a book in Browse "
                    "or move one here."
                )

            self.empty_label = QLabel(
                message, self.books_container
            )

            self.empty_label.setObjectName(
                "libraryEmpty"
            )

            self.books_layout.addWidget(
                self.empty_label,
                0,
                0,
                Qt.AlignTop,
            )

    # ========================================================
    # COVER WIDTH
    # ========================================================

    def current_cover_width(self):

        setting = (
            self.grid_slider.value()
        )

        if setting == 0:

            available = max(
                200,
                self.scroll_area
                .viewport()
                .width() - 6,
            )

            columns = max(
                1,
                min(
                    5,
                    (
                        (available + 22)
                        // (198 + 22)
                    ),
                ),
            )

            return max(
                145,
                min(
                    220,
                    (
                        available
                        - 22 * (columns - 1)
                    ) // columns,
                ),
            )

        return (
            145,
            160,
            185,
            205,
            230,
            260,
        )[setting]

    # ========================================================
    # CLEAR CARDS
    # ========================================================


    def clear_books(self):
        """Discard old cards without making them independent windows."""
        self._resize_timer.stop()
        self._layout_signature = None
        self._content_signature = None
        self.books_container.setUpdatesEnabled(False)
        try:
            old_widgets = {}
            for mode_cards in self._view_cards.values():
                for card in mode_cards or ():
                    old_widgets[id(card)] = card
                    card.hide()

            while self.books_layout.count():
                item = self.books_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.hide()
                    old_widgets[id(widget)] = widget

            for widget in old_widgets.values():
                widget.hide()
                # In particular, never show a detached old card while
                # it is waiting for Qt's deferred deletion.
                widget.deleteLater()

            self._view_cards = {"grid": None, "list": None}
            self.cards = []
        finally:
            self.books_container.setUpdatesEnabled(True)

    # ========================================================
    # CREATE AND CACHE BOOK CARDS
    # ========================================================

    def _create_view_cards(self, mode, cover_width):
        """
        Create book cards for one display mode.

        BookCard reuses byte-bounded, display-sized cover thumbnails.

        Every card has an explicit Library parent,
        preventing it from becoming a separate window.
        """

        cards = []

        for book in self._visible_books:

            card = BookCard(
                book,
                mode=mode,
                cover_width=cover_width,
                progress=self._visible_progress.get(
                    book["id"],
                    0.0,
                ),
                show_progress=(
                    self.show_progress_box.isChecked()
                ),
                parent=self.books_container,
            )

            # Do not display the card until it has
            # been added to the correct layout.

            card.hide()

            card.clicked.connect(
                self.book_open_requested.emit
            )

            card.edit_requested.connect(
                self.edit_book
            )

            card.move_requested.connect(
                self.move_book
            )

            card.remove_requested.connect(
                self.confirm_remove_book
            )

            cards.append(card)

        return cards

    # ========================================================
    # SWITCH BETWEEN CACHED VIEWS
    # ========================================================

    def _activate_cached_view(self):
        """Switch views while the entire book area is not painting."""
        if self._switching_view:
            return
        if not self._visible_books:
            self.load_books()
            return

        self._switching_view = True
        self._resize_timer.stop()
        self.scroll_area.setUpdatesEnabled(False)
        scroll_value = self.scroll_area.verticalScrollBar().value()
        try:
            for card in self.cards:
                card.hide()
            # Preserve ownership: takeAt removes layout items, not widgets.
            while self.books_layout.count():
                item = self.books_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.hide()

            desired = self._view_cards.get(self.display_mode)
            if desired is None:
                cover_width = self.current_cover_width()
                desired = self._create_view_cards(
                    self.display_mode, cover_width
                )
                self._view_cards[self.display_mode] = desired
                if self.display_mode == "grid":
                    self._cards_cover_width = cover_width
            self.cards = desired
            self._layout_signature = None
            self.reflow_cards()
        finally:
            self.scroll_area.setUpdatesEnabled(True)
            self._switching_view = False
        self.scroll_area.verticalScrollBar().setValue(scroll_value)

    # ========================================================
    # REFLOW CARDS
    # ========================================================


    def reflow_cards(self):
        """Layout only the active cards; never show an orphan QWidget."""
        if self._reflowing or not self.cards:
            return
        self._reflowing = True
        self.books_container.setUpdatesEnabled(False)
        try:
            available = max(200, self.scroll_area.viewport().width() - 6)
            if self.display_mode == "list":
                columns = 1
            else:
                if self.grid_slider.value() == 0:
                    desired_width = self.current_cover_width()
                    if desired_width != self._cards_cover_width:
                        # Rebuild the GRID cache only. The LIST cache stays
                        # available for an instant switch back to List mode.
                        old_grid = self._view_cards.get("grid") or []
                        for card in old_grid:
                            card.hide()
                        while self.books_layout.count():
                            item = self.books_layout.takeAt(0)
                            widget = item.widget()
                            if widget is not None:
                                widget.hide()
                        self._cards_cover_width = desired_width
                        new_grid = self._create_view_cards(
                            "grid", desired_width
                        )
                        self.cards = new_grid
                        self._view_cards["grid"] = new_grid
                        for card in old_grid:
                            card.hide()
                            card.deleteLater()
                        self._layout_signature = None
                card_width = self.cards[0].width()
                columns = max(1, (available + 22) // (card_width + 22))

            signature = (
                self.display_mode,
                columns,
                available if self.display_mode == "list" else 0,
                id(self.cards),
            )
            if signature == self._layout_signature:
                return

            # Remove only layout items, never the parent widget itself.
            for card in self.cards:
                card.hide()
            while self.books_layout.count():
                item = self.books_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.hide()

            for index, card in enumerate(self.cards):
                # This also recovers cards orphaned by an earlier version of
                # the Grid/List switching code. A card MUST NOT be a window.
                if card.parentWidget() is not self.books_container or card.isWindow():
                    card.setParent(self.books_container, Qt.Widget)
                if self.display_mode == "list":
                    card.setFixedWidth(max(200, available - 8))
                self.books_layout.addWidget(
                    card, index // columns, index % columns, Qt.AlignTop
                )

            for card in self.cards:
                # Check again after addWidget to avoid ever showing a
                # top-level book card with its own Windows title bar.
                if card.parentWidget() is not self.books_container or card.isWindow():
                    card.setParent(self.books_container, Qt.Widget)
                card.setVisible(True)
            self._layout_signature = signature
        finally:
            self.books_container.setUpdatesEnabled(True)
            self._reflowing = False

    # ========================================================
    # RESIZE
    # ========================================================

    def eventFilter(
        self,
        watched,
        event,
    ):

        if (
            watched
            is self.scroll_area.viewport()
            and event.type()
            == QEvent.Type.Resize
        ):

            width = (
                self.scroll_area
                .viewport()
                .width()
            )

            if (
                width
                != self._last_layout_width
            ):

                self._last_layout_width = (
                    width
                )

                self._resize_timer.start()

        return super().eventFilter(
            watched,
            event,
        )

    # ========================================================
    # OPEN BROWSE
    # ========================================================

    def open_browse(self):

        main_window = (
            self.window()
        )

        navigate = getattr(
            main_window,
            "show_browse",
            None,
        )

        if callable(navigate):
            navigate()

    # ========================================================
    # PAGE STYLING
    # ========================================================



    # LITENOVA_CUSTOM_DROPDOWN_ARROW_V2

    def install_custom_dropdown_arrow(self):
        """
        Apply the custom PNG arrow to the Library dropdowns.

        The main dropdown keeps its rounded border.

        The arrow itself has no separate box,
        border, or background.
        """

        from pathlib import Path

        import sys

        # ====================================================
        # LOCATE ICON
        # ====================================================

        base = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(__file__).resolve().parents[2],
            )
        )

        arrow_path = (
            base
            / "resources"
            / "icons"
            / "dropdown_arrow.png"
        )

        if not arrow_path.is_file():
            return

        # Use an absolute path so the icon loads
        # correctly on Windows.

        arrow_url = (
            arrow_path.resolve().as_posix()
        )

        # ====================================================
        # DROPDOWN STYLESHEET
        # ====================================================

        combo_style = f"""

            /* =============================================
               MAIN DROPDOWN
               ============================================= */

            QComboBox#libraryCategory,
            QComboBox#librarySideCombo {{

                background: #13151b;

                color: #e8e9fb;

                border: 1px solid #404554;

                border-radius: 10px;

                padding: 0px 34px 0px 12px;

                font-size: 13px;
            }}

            /* =============================================
               HOVER AND FOCUS
               ============================================= */

            QComboBox#libraryCategory:hover,
            QComboBox#librarySideCombo:hover,
            QComboBox#libraryCategory:focus,
            QComboBox#librarySideCombo:focus {{

                border: 1px solid #9393cf;
            }}

            /* =============================================
               REMOVE THE SEPARATE ARROW BOX
               ============================================= */

            QComboBox::drop-down,
            QComboBox::drop-down:hover,
            QComboBox::drop-down:on {{

                subcontrol-origin: padding;

                subcontrol-position: top right;

                width: 30px;

                background: transparent;

                border: none;

                border-radius: 0px;

                margin: 0px;

                padding: 0px;
            }}

            /* =============================================
               CUSTOM TRANSPARENT ARROW ICON
               ============================================= */

            QComboBox::down-arrow {{

                image: url("{arrow_url}");

                width: 24px;

                height: 24px;

                background: transparent;

                border: none;
            }}

            /* =============================================
               KEEP ARROW CENTERED WHEN OPEN
               ============================================= */

            QComboBox::down-arrow:on {{

                top: 0px;

                left: 0px;
            }}

        """

        # ====================================================
        # APPLY TO ALL LIBRARY DROPDOWNS
        # ====================================================

        for combo in (

            self.category_filter,

            self.sort_combo,

            self.type_combo,

        ):

            combo.setStyleSheet(
                combo_style
            )

    def apply_page_style(self):

        self.setStyleSheet(
            """
            QWidget#libraryPage {
                background: #111217;
                color: #e8e9f8;
            }

            QLabel {
                background: transparent;
                border: none;
            }

            QLabel#libraryPageHeading {
                color: #f1f0ff;
                font-size: 31px;
                font-weight: 700;
            }

            QToolButton#libraryHeaderButton {
                background: transparent;
                border: none;
                border-radius: 11px;
                color: #d9dcff;
                font-size: 24px;
            }

            QToolButton#libraryHeaderButton:hover,
            QToolButton#libraryHeaderButton[active="true"] {
                background: #30334e;
            }

            QPushButton#libraryAddFolder {
                background: #303351;
                color: #e9e9ff;
                border: none;
                border-radius: 11px;
                padding: 0 17px;
                font-size: 14px;
            }

            QPushButton#libraryAddFolder:hover {
                background: #41456b;
            }

            QPushButton#libraryDeleteCategory {
                background: #201a1e;
                color: #e9b9bf;
                border: 1px solid #68404a;
                border-radius: 11px;
                padding: 0 15px;
                font-size: 13px;
            }

            QPushButton#libraryDeleteCategory:hover {
                background: #342329;
                border-color: #965563;
                color: #ffd6db;
            }


            /* Keep the existing search bar appearance. */

            QLineEdit#librarySearch {
                background: #13151b;
                color: #e8e9fb;
                border: 1px solid #404554;
                border-radius: 10px;
                padding: 7px 12px;
                font-size: 13px;
            }

            QLineEdit#librarySearch:focus {
                border: 1px solid #9393cf;
            }

            /* LITENOVA_CLEAN_DROPDOWN_ARROWS_V1 */

            /* Main dropdown: retain one rounded border. */

            QComboBox#libraryCategory,
            QComboBox#librarySideCombo {
                background: #13151b;
                color: #e8e9fb;

                border: 1px solid #404554;
                border-radius: 10px;

                padding: 7px 34px 7px 12px;

                font-size: 13px;
            }

            QComboBox#libraryCategory:focus,
            QComboBox#librarySideCombo:focus {
                border: 1px solid #9393cf;
            }

            /* Remove the separate box around the arrow. */

            QComboBox#libraryCategory::drop-down,
            QComboBox#librarySideCombo::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;

                width: 30px;

                background: transparent;

                border: none;
                border-radius: 0;

                padding: 0;
                margin: 0;
            }

            /* Prevent a box appearing on hover or click. */

            QComboBox#libraryCategory::drop-down:hover,
            QComboBox#libraryCategory::drop-down:on,
            QComboBox#librarySideCombo::drop-down:hover,
            QComboBox#librarySideCombo::drop-down:on {
                background: transparent;
                border: none;
            }

            /* Prevent the arrow from shifting when opened. */

            QComboBox#libraryCategory::down-arrow:on,
            QComboBox#librarySideCombo::down-arrow:on {
                top: 0;
                left: 0;
            }

            QComboBox QAbstractItemView {
                background: #1c1e29;
                color: #e8e9ff;
                selection-background-color: #494e7b;
                border: 1px solid #4d526a;
            }

            QScrollArea#libraryBooksScroll {
                background: transparent;
                border: none;
            }

            QWidget#libraryBooksContainer {
                background: transparent;
            }

            QFrame#libraryDisplayPanel {
                background: #15171d;
                border: 1px solid #292e39;
                border-radius: 12px;
            }

            QLabel#librarySideHeading {
                color: #c7caff;
                font-size: 18px;
                font-weight: 700;
                padding-top: 3px;
            }

            QLabel#librarySideLabel {
                color: #cbd0e5;
                font-size: 13px;
            }

            QFrame#librarySideRule {
                background: #363b49;
                border: none;
            }

            QPushButton#libraryModeButton {
                background: #14161d;
                color: #e0e2f5;
                border: 1px solid #474b61;
                border-radius: 12px;
                font-size: 13px;
            }

            QPushButton#libraryModeButton:checked {
                background: #3e4267;
                border: 1px solid #777bad;
            }

            QSlider::groove:horizontal {
                background: #4e527d;
                height: 7px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #c3c4ff;
                width: 13px;
                margin: -5px 0;
                border-radius: 6px;
            }

            QCheckBox#librarySideCheck {
                color: #e3e4f1;
                font-size: 13px;
                spacing: 8px;
            }

            QCheckBox#librarySideCheck::indicator {
                width: 17px;
                height: 17px;
            }

            QLabel#libraryFooterLabel,
            QLabel#libraryEmpty {
                color: #c0c3d7;
                font-size: 13px;
            }

            QPushButton#libraryFooterButton {
                background: transparent;
                border: none;
                color: #c6c9ec;
                font-size: 13px;
            }

            QPushButton#libraryFooterButton:hover {
                color: #ffffff;
            }

            /* LITENOVA_DISPLAY_PANEL_V1 - panel-only styling */
            QLabel#librarySideHeading {
                color: #c1c5ff;
                font-size: 19px;
                font-weight: 700;
                padding-top: 4px;
            }
            QLabel#librarySideLabel {
                color: #cbd0e5;
                font-size: 14px;
            }
            QPushButton#libraryModeButton {
                background: #13151b;
                color: #e3e4f1;
                border: 1px solid #4a4d60;
                border-radius: 17px;
                font-size: 14px;
            }
            QPushButton#libraryModeButton:checked {
                background: #3e4163;
                border: 1px solid #777bad;
                color: #f0efff;
            }
            QFrame#librarySideRule {
                background: #3b3e50;
                border: none;
                max-height: 1px;
            }
            QLineEdit#librarySideSearch {
                background: #12151b;
                color: #e8e9fb;
                border: 1px solid #404554;
                border-radius: 11px;
                padding-left: 9px;
                padding-right: 8px;
                font-size: 13px;
            }
            QLineEdit#librarySideSearch:focus {
                border: 1px solid #9393cf;
            }
            QSlider#libraryGridSize::groove:horizontal {
                background: #50527d;
                height: 8px;
                border-radius: 4px;
            }
            QSlider#libraryGridSize::handle:horizontal {
                background: #c5c4ff;
                width: 8px;
                margin: -9px 0px;
                border-radius: 4px;
            }
            """
        )