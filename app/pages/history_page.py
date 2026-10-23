"""
Litenova History Page

Features:
- Reading history grouped by date
- Search history
- Selected book details
- Continue Reading
- View in Library
- Open Folder
- Remove individual history entries
- Clear all history
- Header three-dot button opens Settings
- Individual history rows have a trash button
- Uses Litenova's custom PNG icons
"""

from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    Signal,
    QUrl,
    QSize,
)

from PySide6.QtGui import (
    QPixmap,
    QDesktopServices,
    QFontMetrics,
)

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QToolButton,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
)

from app.database.history_repository import (
    get_history_entries,
    get_comic_chapter_count,
    delete_history_entry,
    clear_history,
)

from app.database.books_repository import (
    get_book_by_id,
)

from app.services.icon_service import (
    ui_icon,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def entry_value(entry, key, default=None):
    """
    Safely retrieve a value from a dictionary
    or SQLite row.
    """

    if entry is None:
        return default

    try:
        if key in entry.keys():

            value = entry[key]

            if value is not None:
                return value

    except (
        KeyError,
        TypeError,
        AttributeError,
    ):
        pass

    return default


def entry_time(entry):
    """
    Convert a reading-history timestamp
    into a datetime object.
    """

    value = entry_value(
        entry,
        "last_read",
    )

    if not value:
        return None

    try:
        when = datetime.fromisoformat(
            str(value)
        )

        if when.tzinfo is not None:
            return when.astimezone()

        return when

    except (
        ValueError,
        TypeError,
    ):
        return None


def chapter_title(entry):
    """
    Return the chapter title displayed
    in the History page.
    """

    actual_title = entry_value(
        entry,
        "comic_chapter_title",
    )

    if actual_title:
        return str(actual_title)

    try:
        chapter_number = (
            int(
                entry_value(
                    entry,
                    "chapter_index",
                    0,
                )
            )
            + 1
        )

    except (
        TypeError,
        ValueError,
    ):
        chapter_number = 1

    return f"Chapter {chapter_number}"


def set_cover(
    label,
    path,
    width,
    height,
    crop=False,
):
    """
    Display a book cover using its
    original image.

    If the image is missing, show a
    NO COVER placeholder.
    """

    label.clear()

    if not path:
        label.setText("NO COVER")
        return

    cover_path = Path(
        str(path)
    )

    if not cover_path.is_file():
        label.setText("NO COVER")
        return

    original = QPixmap(
        str(cover_path)
    )

    if original.isNull():
        label.setText("NO COVER")
        return

    mode = (
        Qt.KeepAspectRatioByExpanding
        if crop
        else Qt.KeepAspectRatio
    )

    scaled = original.scaled(
        width,
        height,
        mode,
        Qt.SmoothTransformation,
    )

    if crop:

        x = max(
            0,
            (scaled.width() - width) // 2,
        )

        y = max(
            0,
            (scaled.height() - height) // 2,
        )

        scaled = scaled.copy(
            x,
            y,
            width,
            height,
        )

    label.setPixmap(
        scaled
    )


# ============================================================
# HISTORY ROW
# ============================================================

class HistoryRow(QFrame):

    selected = Signal(object)

    remove_requested = Signal(object)

    def __init__(
        self,
        entry,
        parent=None,
    ):
        super().__init__(parent)

        self.entry = entry

        self.setObjectName(
            "historyRow"
        )

        self.setProperty(
            "selected",
            False,
        )

        self.setFixedHeight(
            112
        )

        self.setCursor(
            Qt.PointingHandCursor
        )

        self.build_ui()

    # ========================================================
    # BUILD HISTORY ROW
    # ========================================================

    def build_ui(self):

        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            8,
            7,
            9,
            7,
        )

        layout.setSpacing(
            14
        )

        # ====================================================
        # BOOK COVER
        # ====================================================

        self.cover = QLabel()

        self.cover.setObjectName(
            "historyThumb"
        )

        self.cover.setFixedSize(
            92,
            92,
        )

        self.cover.setAlignment(
            Qt.AlignCenter
        )

        set_cover(
            self.cover,
            entry_value(
                self.entry,
                "cover_path",
            ),
            92,
            92,
            crop=True,
        )

        layout.addWidget(
            self.cover
        )

        # ====================================================
        # BOOK INFORMATION
        # ====================================================

        text_layout = QVBoxLayout()

        text_layout.setContentsMargins(
            0,
            5,
            0,
            5,
        )

        text_layout.setSpacing(
            5
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        self.title_label = QLabel(
            str(
                entry_value(
                    self.entry,
                    "book_title",
                    "Unknown Title",
                )
            )
        )

        self.title_label.setObjectName(
            "historyBookTitle"
        )

        self.title_label.setWordWrap(
            False
        )

        # ----------------------------------------------------
        # CHAPTER
        # ----------------------------------------------------

        self.chapter_label = QLabel(
            chapter_title(
                self.entry
            )
        )

        self.chapter_label.setObjectName(
            "historySecondary"
        )

        # ----------------------------------------------------
        # TIME
        # ----------------------------------------------------

        when = entry_time(
            self.entry
        )

        time_text = (
            when.strftime("%H:%M")
            if when
            else ""
        )

        self.time_label = QLabel(
            time_text
        )

        self.time_label.setObjectName(
            "historySecondary"
        )

        text_layout.addWidget(
            self.title_label
        )

        text_layout.addWidget(
            self.chapter_label
        )

        text_layout.addWidget(
            self.time_label
        )

        text_layout.addStretch()

        layout.addLayout(
            text_layout,
            1,
        )

        # ====================================================
        # DATE
        # ====================================================

        date_text = (
            when.strftime("%d.%m.%y")
            if when
            else ""
        )

        self.date_label = QLabel(
            date_text
        )

        self.date_label.setObjectName(
            "historyDate"
        )

        self.date_label.setMinimumWidth(
            73
        )

        self.date_label.setAlignment(
            Qt.AlignRight
            | Qt.AlignVCenter
        )

        layout.addWidget(
            self.date_label
        )

        # ====================================================
        # REMOVE FROM HISTORY BUTTON
        # ====================================================
        #
        # This replaces the three-dot icon
        # beside the date with a trash icon.
        #
        # Clicking it removes ONLY this
        # specific reading-history entry.
        #
        # It does not open a dropdown menu.
        # ====================================================

        self.remove_button = QToolButton()

        self.remove_button.setObjectName(
            "historyMenuButton"
        )

        self.remove_button.setIcon(
            ui_icon("remove_from_history")
        )

        self.remove_button.setIconSize(
            QSize(21, 21)
        )

        self.remove_button.setFixedSize(
            34,
            42,
        )

        self.remove_button.setToolTip(
            "Remove from History"
        )

        self.remove_button.setCursor(
            Qt.PointingHandCursor
        )

        # Clicking the trash icon sends the
        # specific history entry to HistoryPage.
        self.remove_button.clicked.connect(
            self.request_removal
        )

        layout.addWidget(
            self.remove_button
        )

    # ========================================================
    # REQUEST REMOVAL
    # ========================================================

    def request_removal(self):
        """
        Remove this particular history entry.

        The book itself and its reading
        progress are not deleted.
        """

        self.remove_requested.emit(
            self.entry
        )

    # ========================================================
    # SELECTED STATE
    # ========================================================

    def set_selected(
        self,
        selected,
    ):

        self.setProperty(
            "selected",
            bool(selected),
        )

        self.style().unpolish(
            self
        )

        self.style().polish(
            self
        )

        self.update()

    # ========================================================
    # CLICK HISTORY ROW
    # ========================================================

    def mousePressEvent(
        self,
        event,
    ):

        if (
            event.button()
            == Qt.LeftButton
        ):

            self.selected.emit(
                self.entry
            )

        super().mousePressEvent(
            event
        )


# ============================================================
# HISTORY PAGE
# ============================================================

class HistoryPage(QWidget):

    continue_reading_requested = Signal(
        object
    )

    view_in_library_requested = Signal(
        object
    )

    def __init__(self):
        super().__init__()

        self.entries = []

        self.rows = []

        self.selected_entry = None

        self.selected_history_id = None

        self.build_ui()

        self.apply_page_style()


    # ========================================================
    # CREATE HEADER ICON BUTTON
    # ========================================================

    def make_icon_button(
        self,
        name,
        tooltip,
        size=24,
    ):

        button = QToolButton()

        button.setObjectName(
            "historyHeaderButton"
        )

        button.setIcon(
            ui_icon(name)
        )

        button.setIconSize(
            QSize(
                size,
                size,
            )
        )

        button.setFixedSize(
            42,
            42,
        )

        button.setToolTip(
            tooltip
        )

        button.setCursor(
            Qt.PointingHandCursor
        )

        return button

    # ========================================================
    # CREATE DETAIL ACTION BUTTON
    # ========================================================

    def make_action_button(
        self,
        name,
        label,
        tooltip,
    ):

        button = QToolButton()

        button.setObjectName(
            "historyActionButton"
        )

        button.setText(
            label
        )

        button.setIcon(
            ui_icon(name)
        )

        button.setIconSize(
            QSize(30, 30)
        )

        button.setToolButtonStyle(
            Qt.ToolButtonTextUnderIcon
        )

        button.setToolTip(
            tooltip
        )

        button.setCursor(
            Qt.PointingHandCursor
        )

        button.setMinimumHeight(
            100
        )

        button.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        return button

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        outer = QHBoxLayout(
            self
        )

        outer.setContentsMargins(
            24,
            0,
            0,
            0,
        )

        outer.setSpacing(
            0
        )

        # ====================================================
        # LEFT PANEL
        # ====================================================

        left_panel = QWidget()

        left = QVBoxLayout(
            left_panel
        )

        left.setContentsMargins(
            0,
            23,
            22,
            20,
        )

        left.setSpacing(
            14
        )

        # ====================================================
        # HEADER
        # ====================================================

        header = QHBoxLayout()

        heading = QLabel(
            "History"
        )

        heading.setObjectName(
            "historyPageTitle"
        )

        header.addWidget(
            heading
        )

        header.addStretch()

        # ====================================================
        # CLEAR ALL HISTORY
        # ====================================================

        self.clear_button = (
            self.make_icon_button(
                "clear_history",
                "Clear all History",
            )
        )

        self.clear_button.clicked.connect(
            self.clear_all_history
        )

        # ====================================================
        # HEADER THREE-DOT BUTTON
        # ====================================================
        #
        # Only the three-dot button at the top
        # of the page remains.
        #
        # It opens Settings directly.
        # ====================================================

        self.more_button = (
            self.make_icon_button(
                "more_options",
                "Open Settings",
            )
        )

        self.more_button.clicked.connect(
            self.open_settings
        )

        header.addWidget(
            self.clear_button
        )

        header.addWidget(
            self.more_button
        )

        # ====================================================
        # SEARCH BAR
        # ====================================================

        self.search_input = QLineEdit()

        self.search_input.setObjectName(
            "historySearch"
        )

        self.search_input.setPlaceholderText(
            "Search history..."
        )

        self.search_input.addAction(
            ui_icon("search"),
            QLineEdit.LeadingPosition,
        )

        self.search_input.setClearButtonEnabled(
            True
        )

        self.search_input.setFixedHeight(
            47
        )

        self.search_input.textChanged.connect(
            self.render_history
        )

        # ====================================================
        # HISTORY SCROLL AREA
        # ====================================================

        self.history_scroll = QScrollArea()

        self.history_scroll.setObjectName(
            "historyScroll"
        )

        self.history_scroll.setWidgetResizable(
            True
        )

        self.history_scroll.setFrameShape(
            QFrame.NoFrame
        )

        self.history_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.history_container = QWidget()

        self.history_container.setObjectName(
            "historyContainer"
        )

        self.history_layout = QVBoxLayout(
            self.history_container
        )

        self.history_layout.setContentsMargins(
            0,
            0,
            0,
            18,
        )

        self.history_layout.setSpacing(
            9
        )

        self.history_layout.setAlignment(
            Qt.AlignTop
        )

        self.history_scroll.setWidget(
            self.history_container
        )

        left.addLayout(
            header
        )

        left.addWidget(
            self.search_input
        )

        left.addWidget(
            self.history_scroll,
            1,
        )

        # ====================================================
        # RIGHT DETAILS PANEL
        # ====================================================

        self.details_panel = QFrame()

        self.details_panel.setObjectName(
            "historyDetailsPanel"
        )

        self.details_panel.setMinimumWidth(
            320
        )

        self.details_panel.setMaximumWidth(
            430
        )

        detail = QVBoxLayout(
            self.details_panel
        )

        detail.setContentsMargins(
            21,
            21,
            21,
            21,
        )

        detail.setSpacing(
            11
        )

        # ====================================================
        # LARGE COVER
        # ====================================================

        self.detail_cover = QLabel()

        self.detail_cover.setObjectName(
            "historyLargeCover"
        )

        self.detail_cover.setAlignment(
            Qt.AlignCenter
        )

        self.detail_cover.setMinimumHeight(
            175
        )

        self.detail_cover.setMaximumHeight(
            450
        )

        self.detail_cover.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        # ====================================================
        # TITLE
        # ====================================================

        self.detail_title = QLabel(
            "Select a history entry"
        )

        self.detail_title.setObjectName(
            "historyDetailTitle"
        )

        self.detail_title.setWordWrap(
            True
        )

        # ====================================================
        # CHAPTER
        # ====================================================

        self.detail_chapter = QLabel()

        self.detail_chapter.setObjectName(
            "historyDetailChapter"
        )

        self.detail_chapter.setWordWrap(
            True
        )

        # ====================================================
        # SEPARATOR
        # ====================================================

        separator = QFrame()

        separator.setObjectName(
            "historySeparator"
        )

        separator.setFrameShape(
            QFrame.HLine
        )

        # ====================================================
        # BOOK INFORMATION
        # ====================================================

        self.meta_widget = QWidget()

        self.meta_layout = QVBoxLayout(
            self.meta_widget
        )

        self.meta_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.meta_layout.setSpacing(
            6
        )

        self.last_read_value = (
            self.add_meta_row(
                "Last read"
            )
        )

        self.progress_value = (
            self.add_meta_row(
                "Progress"
            )
        )

        self.total_chapters_value = (
            self.add_meta_row(
                "Total chapters"
            )
        )

        self.source_value = (
            self.add_meta_row(
                "Source"
            )
        )

        self.path_value = (
            self.add_meta_row(
                "Path"
            )
        )

        # ====================================================
        # CONTINUE READING
        # ====================================================

        self.continue_button = QPushButton(
            "Continue Reading"
        )

        self.continue_button.setObjectName(
            "historyContinueButton"
        )

        self.continue_button.setIcon(
            ui_icon("continue_reading")
        )

        self.continue_button.setIconSize(
            QSize(24, 24)
        )

        self.continue_button.setFixedHeight(
            54
        )

        self.continue_button.setCursor(
            Qt.PointingHandCursor
        )

        self.continue_button.clicked.connect(
            self.continue_reading
        )

        # ====================================================
        # DETAIL ACTION BUTTONS
        # ====================================================

        actions = QHBoxLayout()

        actions.setSpacing(
            8
        )

        self.open_folder_button = (
            self.make_action_button(
                "open_folder",
                "Open Folder",
                "Open the book's local folder",
            )
        )

        self.view_library_button = (
            self.make_action_button(
                "view_in_library",
                "View in Library",
                "Find this book in its Library category",
            )
        )

        self.remove_history_button = (
            self.make_action_button(
                "remove_from_history",
                "Remove from\nHistory",
                "Remove the selected reading-history entry",
            )
        )

        self.open_folder_button.clicked.connect(
            self.open_selected_folder
        )

        self.view_library_button.clicked.connect(
            self.view_selected_in_library
        )

        self.remove_history_button.clicked.connect(
            self.remove_selected_history
        )

        actions.addWidget(
            self.open_folder_button
        )

        actions.addWidget(
            self.view_library_button
        )

        actions.addWidget(
            self.remove_history_button
        )

        # ====================================================
        # ADD DETAILS
        # ====================================================

        detail.addWidget(
            self.detail_cover,
            1,
        )

        detail.addWidget(
            self.detail_title
        )

        detail.addWidget(
            self.detail_chapter
        )

        detail.addWidget(
            separator
        )

        detail.addWidget(
            self.meta_widget
        )

        detail.addWidget(
            self.continue_button
        )

        detail.addLayout(
            actions
        )

        # ====================================================
        # COMPLETE LAYOUT
        # ====================================================

        outer.addWidget(
            left_panel,
            1,
        )

        outer.addWidget(
            self.details_panel,
            0,
        )

    # ========================================================
    # OPEN SETTINGS
    # ========================================================

    def open_settings(self):
        """
        Open the Settings page using MainWindow.
        """

        main_window = self.window()

        show_settings = getattr(
            main_window,
            "show_settings",
            None,
        )

        if callable(show_settings):

            show_settings()

        else:

            QMessageBox.warning(
                self,
                "Settings",
                "Could not open the Settings page.",
            )

    # ========================================================
    # METADATA ROW
    # ========================================================

    def add_meta_row(
        self,
        title,
    ):

        row = QWidget()

        layout = QHBoxLayout(
            row
        )

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(
            8
        )

        label = QLabel(
            title
        )

        label.setObjectName(
            "historyMetaLabel"
        )

        label.setFixedWidth(
            105
        )

        value = QLabel(
            "—"
        )

        value.setObjectName(
            "historyMetaValue"
        )

        value.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        layout.addWidget(
            label
        )

        layout.addWidget(
            value,
            1,
        )

        self.meta_layout.addWidget(
            row
        )

        return value

    # ========================================================
    # HISTORY PAGE STYLE
    # ========================================================

    def apply_page_style(self):

        self.setStyleSheet(
            """
            HistoryPage {
                background: #0b0d12;
            }

            QWidget#historyContainer {
                background: transparent;
            }

            QLabel {
                background: transparent;
            }

            QLabel#historyPageTitle {
                color: #f0efff;
                font-size: 32px;
                font-weight: 700;
            }

            QLineEdit#historySearch {
                background: #101218;
                border: 1px solid #454b5d;
                border-radius: 13px;
                color: #e7e8f5;
                font-size: 15px;
                padding-right: 12px;
            }

            QLineEdit#historySearch:focus {
                border: 1px solid #9293d5;
            }

            QScrollArea#historyScroll {
                border: none;
                background: transparent;
            }

            QFrame#historyRow {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 13px;
            }

            QFrame#historyRow:hover {
                background: rgba(87, 88, 126, 0.10);
            }

            QFrame#historyRow[selected="true"] {
                background: rgba(91, 91, 145, 0.22);
                border: 2px solid #b6b5f5;
            }

            QLabel#historyThumb {
                background: #12151e;
                border-radius: 9px;
                color: #777d91;
            }

            QLabel#historyBookTitle {
                color: #f0efff;
                font-size: 15px;
                font-weight: 600;
            }

            QLabel#historySecondary,
            QLabel#historyDate {
                color: #b8bbd2;
                font-size: 13px;
            }

            QLabel#historyGroupTitle {
                color: #b9b8ff;
                font-size: 18px;
                font-weight: 700;
                margin-top: 8px;
            }

            QToolButton#historyMenuButton,
            QToolButton#historyHeaderButton {
                background: transparent;
                border: none;
                border-radius: 10px;
            }

            QToolButton#historyMenuButton:hover,
            QToolButton#historyHeaderButton:hover {
                background: rgba(110, 110, 165, 0.18);
            }

            QFrame#historyDetailsPanel {
                background: #0e1016;
                border-left: 1px solid #252936;
                border-top-left-radius: 14px;
            }

            QLabel#historyLargeCover {
                background: #12151e;
                border-radius: 12px;
                color: #777d91;
            }

            QLabel#historyDetailTitle {
                color: #f1f0ff;
                font-size: 21px;
                font-weight: 700;
            }

            QLabel#historyDetailChapter {
                color: #c2c3d8;
                font-size: 15px;
            }

            QFrame#historySeparator {
                background: #3e4352;
                border: none;
                max-height: 1px;
                min-height: 1px;
            }

            QLabel#historyMetaLabel,
            QLabel#historyMetaValue {
                color: #cdd0e2;
                font-size: 13px;
            }

            QPushButton#historyContinueButton {
                background: #4d4e83;
                border: 1px solid #7778c0;
                border-radius: 14px;
                color: #f0efff;
                font-size: 15px;
                font-weight: 600;
            }

            QPushButton#historyContinueButton:hover {
                background: #5c5d99;
            }

            QToolButton#historyActionButton {
                background: #101218;
                border: 1px solid #454b5d;
                border-radius: 13px;
                color: #e0e0f0;
                font-size: 12px;
                padding: 5px;
            }

            QToolButton#historyActionButton:hover {
                background: #1b1d29;
                border: 1px solid #696f87;
            }

            QPushButton:disabled,
            QToolButton:disabled {
                color: #777b90;
            }
            """
        )

    # ========================================================
    # HISTORY GROUP
    # ========================================================

    def history_group(
        self,
        entry,
    ):

        when = entry_time(
            entry
        )

        if when is None:
            return "Older"

        today = datetime.now().date()

        day = when.date()

        if day == today:
            return "Today"

        if (
            day
            == today - timedelta(days=1)
        ):
            return "Yesterday"

        if (
            day
            >= today - timedelta(days=7)
        ):
            return "Last 7 Days"

        if (
            day
            >= today - timedelta(days=30)
        ):
            return "Last 30 Days"

        return "Older"

    # ========================================================
    # CLEAR HISTORY WIDGETS
    # ========================================================

    def clear_history_widgets(self):

        self.rows = []

        while self.history_layout.count():

            item = (
                self.history_layout.takeAt(
                    0
                )
            )

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    # ========================================================
    # REFRESH HISTORY
    # ========================================================

    def refresh(self):

        self.entries = list(
            get_history_entries()
        )

        self.render_history()

    # ========================================================
    # RENDER HISTORY
    # ========================================================

    def render_history(
        self,
        *_args,
    ):

        self.clear_history_widgets()

        query = (
            self.search_input
            .text()
            .strip()
            .lower()
        )

        # ====================================================
        # SEARCH
        # ====================================================

        shown = []

        for entry in self.entries:

            title = str(
                entry_value(
                    entry,
                    "book_title",
                    "",
                )
            ).lower()

            author = str(
                entry_value(
                    entry,
                    "author",
                    "",
                )
            ).lower()

            chapter = chapter_title(
                entry
            ).lower()

            if (
                not query
                or query in title
                or query in author
                or query in chapter
            ):

                shown.append(
                    entry
                )

        # ====================================================
        # SELECTION
        # ====================================================

        shown_ids = {
            entry_value(
                entry,
                "history_id",
            )
            for entry in shown
        }

        if (
            self.selected_history_id
            not in shown_ids
        ):

            if shown:

                self.selected_entry = shown[0]

                self.selected_history_id = (
                    entry_value(
                        shown[0],
                        "history_id",
                    )
                )

                self.update_details()

            else:

                self.clear_details()

        else:

            self.selected_entry = next(
                (
                    entry
                    for entry in shown
                    if entry_value(
                        entry,
                        "history_id",
                    )
                    == self.selected_history_id
                ),
                None,
            )

            self.update_details()

        # ====================================================
        # EMPTY HISTORY
        # ====================================================

        if not shown:

            empty = QLabel(
                "No reading history found."
            )

            empty.setObjectName(
                "historySecondary"
            )

            empty.setAlignment(
                Qt.AlignCenter
            )

            empty.setMinimumHeight(
                130
            )

            self.history_layout.addWidget(
                empty
            )

            self.history_layout.addStretch()

            return

        # ====================================================
        # GROUP BY DATE
        # ====================================================

        groups = (
            "Today",
            "Yesterday",
            "Last 7 Days",
            "Last 30 Days",
            "Older",
        )

        for group in groups:

            group_entries = [
                entry
                for entry in shown
                if self.history_group(
                    entry
                ) == group
            ]

            if not group_entries:
                continue

            heading = QLabel(
                group
            )

            heading.setObjectName(
                "historyGroupTitle"
            )

            self.history_layout.addWidget(
                heading
            )

            # =================================================
            # HISTORY ROWS
            # =================================================

            for entry in group_entries:

                row = HistoryRow(
                    entry
                )

                row.selected.connect(
                    self.select_entry
                )

                # The row trash icon is connected
                # directly to removal.
                row.remove_requested.connect(
                    self.remove_entry
                )

                row.set_selected(
                    entry_value(
                        entry,
                        "history_id",
                    )
                    == self.selected_history_id
                )

                self.rows.append(
                    row
                )

                self.history_layout.addWidget(
                    row
                )

        self.history_layout.addStretch()

    # ========================================================
    # SELECT HISTORY ENTRY
    # ========================================================

    def select_entry(
        self,
        entry,
    ):

        self.selected_entry = entry

        self.selected_history_id = (
            entry_value(
                entry,
                "history_id",
            )
        )

        for row in self.rows:

            row.set_selected(
                entry_value(
                    row.entry,
                    "history_id",
                )
                == self.selected_history_id
            )

        self.update_details()

    # ========================================================
    # LARGE COVER
    # ========================================================

    def set_detail_cover(
        self,
        path,
    ):

        width = max(
            120,
            self.detail_cover.width() - 10,
        )

        height = max(
            130,
            self.detail_cover.height() - 10,
        )

        set_cover(
            self.detail_cover,
            path,
            width,
            height,
        )

    # ========================================================
    # UPDATE DETAILS
    # ========================================================

    def update_details(self):

        entry = self.selected_entry

        if entry is None:

            self.clear_details()

            return

        # ====================================================
        # COVER
        # ====================================================

        self.set_detail_cover(
            entry_value(
                entry,
                "cover_path",
            )
        )

        # ====================================================
        # TITLE
        # ====================================================

        self.detail_title.setText(
            str(
                entry_value(
                    entry,
                    "book_title",
                    "Unknown Title",
                )
            )
        )

        self.detail_chapter.setText(
            chapter_title(
                entry
            )
        )

        # ====================================================
        # LAST READ
        # ====================================================

        when = entry_time(
            entry
        )

        self.last_read_value.setText(
            when.strftime(
                "%d.%m.%y %H:%M"
            )
            if when
            else "Unknown"
        )

        # ====================================================
        # PROGRESS
        # ====================================================

        try:

            position = float(
                entry_value(
                    entry,
                    "position",
                    0.0,
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            position = 0.0

        position = max(
            0.0,
            min(
                position,
                1.0,
            ),
        )

        self.progress_value.setText(
            f"{position * 100:.1f}%"
        )

        # ====================================================
        # TOTAL CHAPTERS
        # ====================================================

        book_id = entry_value(
            entry,
            "book_id",
        )

        total = get_comic_chapter_count(
            book_id
        )

        self.total_chapters_value.setText(
            str(total)
            if total > 0
            else "Unknown"
        )

        # ====================================================
        # SOURCE
        # ====================================================

        self.source_value.setText(
            "Local file"
        )

        # ====================================================
        # FILE PATH
        # ====================================================

        path = str(
            entry_value(
                entry,
                "file_path",
            )
            or entry_value(
                entry,
                "epub_path",
            )
            or ""
        )

        metrics = QFontMetrics(
            self.path_value.font()
        )

        displayed_path = (
            metrics.elidedText(
                path,
                Qt.ElideMiddle,
                205,
            )
        )

        self.path_value.setText(
            displayed_path
        )

        self.path_value.setToolTip(
            path
        )

        # ====================================================
        # ENABLE BUTTONS
        # ====================================================

        self.continue_button.setEnabled(
            True
        )

        self.open_folder_button.setEnabled(
            bool(path)
        )

        self.view_library_button.setEnabled(
            True
        )

        self.remove_history_button.setEnabled(
            True
        )

    # ========================================================
    # CLEAR DETAILS
    # ========================================================

    def clear_details(self):

        self.selected_entry = None

        self.selected_history_id = None

        self.detail_cover.clear()

        self.detail_cover.setText(
            "NO HISTORY SELECTED"
        )

        self.detail_title.setText(
            "Select a history entry"
        )

        self.detail_chapter.clear()

        labels = (
            self.last_read_value,
            self.progress_value,
            self.total_chapters_value,
            self.source_value,
            self.path_value,
        )

        for label in labels:

            label.setText(
                "—"
            )

        buttons = (
            self.continue_button,
            self.open_folder_button,
            self.view_library_button,
            self.remove_history_button,
        )

        for button in buttons:

            button.setEnabled(
                False
            )

    # ========================================================
    # SELECTED BOOK
    # ========================================================

    def selected_book(self):

        if self.selected_entry is None:
            return None

        book_id = entry_value(
            self.selected_entry,
            "book_id",
        )

        if book_id is None:
            return None

        return get_book_by_id(
            book_id
        )

    # ========================================================
    # CONTINUE READING
    # ========================================================

    def continue_reading(self):

        book = self.selected_book()

        if book is None:

            QMessageBox.warning(
                self,
                "History",
                (
                    "This book is no longer "
                    "in your Library."
                ),
            )

            return

        self.continue_reading_requested.emit(
            book
        )

    # ========================================================
    # VIEW IN LIBRARY
    # ========================================================

    def view_selected_in_library(self):

        book = self.selected_book()

        if book is None:

            QMessageBox.warning(
                self,
                "History",
                (
                    "This book is no longer "
                    "in your Library."
                ),
            )

            return

        self.view_in_library_requested.emit(
            book
        )

    # ========================================================
    # OPEN BOOK FOLDER
    # ========================================================

    def open_selected_folder(self):

        path_text = (
            entry_value(
                self.selected_entry,
                "file_path",
            )
            or entry_value(
                self.selected_entry,
                "epub_path",
            )
        )

        if not path_text:
            return

        path = Path(
            str(path_text)
        )

        folder = (
            path.parent
            if path.is_file()
            else path
        )

        if not folder.is_dir():

            QMessageBox.warning(
                self,
                "Open Folder",
                (
                    "This book's folder "
                    "could not be found."
                ),
            )

            return

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(folder)
            )
        )

    # ========================================================
    # REMOVE ONE HISTORY ENTRY
    # ========================================================

    def remove_entry(
        self,
        entry,
    ):
        """
        Remove only the selected history entry.

        Does not delete the book or its
        saved reading progress.
        """

        history_id = entry_value(
            entry,
            "history_id",
        )

        if history_id is None:
            return

        delete_history_entry(
            history_id
        )

        self.refresh()

    # ========================================================
    # REMOVE SELECTED HISTORY ENTRY
    # ========================================================

    def remove_selected_history(self):

        if self.selected_entry is not None:

            self.remove_entry(
                self.selected_entry
            )

    # ========================================================
    # CLEAR ALL HISTORY
    # ========================================================

    def clear_all_history(self):

        if not self.entries:
            return

        answer = QMessageBox.question(
            self,
            "Clear History",
            (
                "Clear your entire reading history?\n\n"
                "Books and saved reading progress "
                "will not be deleted."
            ),
            (
                QMessageBox.Yes
                | QMessageBox.No
            ),
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        clear_history()

        self.refresh()

    # ========================================================
    # PAGE SHOWN
    # ========================================================

    def showEvent(
        self,
        event,
    ):

        super().showEvent(
            event
        )

        self.refresh()

    # ========================================================
    # WINDOW RESIZED
    # ========================================================

    def resizeEvent(
        self,
        event,
    ):

        super().resizeEvent(
            event
        )

        if self.selected_entry is not None:

            self.set_detail_cover(
                entry_value(
                    self.selected_entry,
                    "cover_path",
                )
            )