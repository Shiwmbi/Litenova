"""Litenova EPUB reader: dark reading canvas and built-in live reader settings.

Replace app/pages/reader_page.py with this file. Other app pages are unchanged.
The settings sidebar controls real QTextBrowser formatting, not CBZ images.
"""

import math
import json
import re
import sys
import posixpath
import zipfile
import time
from urllib.parse import unquote, urlsplit
from html import unescape
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QEvent
from PySide6.QtGui import (
    QFont,
    QPixmap,
    QPainter,
    QTextCursor,
    QKeySequence,
    QShortcut,
    QImage,
    QTextDocument,
    QIcon,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QTextBrowser,
    QListWidget,
    QComboBox,
    QSlider,
    QLineEdit,
    QCheckBox,
    QButtonGroup,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QListWidgetItem,
)

from app.services.epub_service import get_chapters
from app.services.path_service import resource_path
from app.services.icon_service import ui_icon
from app.services.appearance_service import resolved_colors
from app.services.progress_service import get_progress, save_progress
from app.services.settings_service import (
    get_reader_font_size,
    set_reader_font_size,
    get_setting,
    set_setting,
)


DARK = "#12141a"
CARD = "#191b23"
TEXT = "#e8e8f5"
MUTED = "#a9acc1"
ACCENT = "#aba8f0"

FONTS = (
    "Georgia",
    "Noto Serif",
    "Times New Roman",
    "Arial",
    "Verdana",
)


# ============================================================
# DEFAULT READER SETTINGS
# ============================================================

# Restore only EPUB reader appearance/behavior preferences.
#
# Bookmarks, reading positions, panel widths and the app's
# Appearance palette are NOT reset.
READER_DEFAULTS = {
    "reader_font_family": "Georgia",
    "reader_font_size": 17,
    "epub_weight": 2,
    "epub_italic": False,
    "epub_letter_spacing": 0,
    "epub_line_height": 170,
    "epub_paragraph_spacing": 10,
    "epub_paragraph_indent": 0,
    "epub_text_align": "left",
    "epub_side_margin": 65,
    "epub_vertical_margin": 40,
    "epub_show_images": True,
    "epub_show_captions": True,
    "epub_image_size": 100,
    "epub_chapter_align": "center",
    "epub_arrow_chapters": False,
    "epub_progress_mode": "percentage",
    "reader_show_progress_bar": True,
    "epub_keep_screen_on": False,
}


# ============================================================
# ICON HELPERS
# ============================================================

def reader_icon(
    *filenames,
):
    """
    Load a PNG from resources/icons.

    Missing icons safely return an empty QIcon.
    """

    for name in filenames:

        path = resource_path(
            f"resources/icons/{name}"
        )

        if path.is_file():

            icon = QIcon(
                str(path)
            )

            if not icon.isNull():

                return icon

    return QIcon()


def use_button_icon(
    button,
    icon,
    size=20,
):
    """
    Replace a fallback text glyph only when a usable
    PNG icon exists.
    """

    if icon.isNull():

        return

    button.setText(
        ""
    )

    button.setIcon(
        icon
    )

    button.setIconSize(
        QSize(
            size,
            size,
        )
    )


# ============================================================
# SETTING HELPERS
# ============================================================

def setting_int(
    key,
    default,
    minimum,
    maximum,
):

    try:

        value = int(
            get_setting(
                key,
                default,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        value = default

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def setting_bool(
    key,
    default=True,
):

    return str(
        get_setting(
            key,
            default,
        )
    ).casefold() in (
        "true",
        "1",
        "yes",
        "on",
    )


# ============================================================
# ROW LABEL
# ============================================================

def row_label(
    name,
    detail="",
):

    holder = QWidget()

    layout = QVBoxLayout(
        holder
    )

    layout.setContentsMargins(
        0,
        0,
        0,
        0,
    )

    layout.setSpacing(
        2
    )

    caption = QLabel(
        name,
        holder,
    )

    caption.setObjectName(
        "readerRowTitle"
    )

    layout.addWidget(
        caption
    )

    if detail:

        desc = QLabel(
            detail,
            holder,
        )

        desc.setObjectName(
            "readerRowDetail"
        )

        desc.setWordWrap(
            True
        )

        layout.addWidget(
            desc
        )

    return holder


# ============================================================
# TOGGLE
# ============================================================

class Toggle(QCheckBox):
    """
    Compact Litenova reader switch.
    """

    def __init__(
        self,
        parent=None,
    ):

        super().__init__(
            parent
        )

        self.setFixedSize(
            43,
            25,
        )

        self.setCursor(
            Qt.PointingHandCursor
        )

    def paintEvent(
        self,
        event,
    ):

        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        painter.setPen(
            Qt.NoPen
        )

        from PySide6.QtGui import QColor

        painter.setBrush(
            QColor(
                "#63659c"
                if self.isChecked()
                else "#393c4c"
            )
        )

        painter.drawRoundedRect(
            0,
            1,
            43,
            23,
            12,
            12,
        )

        painter.setBrush(
            QColor(
                "#d8d6ff"
                if self.isChecked()
                else "#a4a7ba"
            )
        )

        painter.drawEllipse(
            22
            if self.isChecked()
            else 3,
            4,
            17,
            17,
        )

        painter.end()


# ============================================================
# EPUB TEXT BROWSER
# ============================================================

class EpubTextBrowser(QTextBrowser):
    """
    QTextBrowser that can load illustrations from an EPUB ZIP.
    """

    def __init__(
        self,
        parent=None,
    ):

        super().__init__(
            parent
        )

        self.image_provider = None

    def loadResource(
        self,
        kind,
        url,
    ):

        if (
            kind
            == QTextDocument.ImageResource
            and url.scheme()
            == "litenova-image"
            and self.image_provider
            is not None
        ):

            return self.image_provider(
                url.path().lstrip(
                    "/"
                )
            )

        return super().loadResource(
            kind,
            url,
        )


# ============================================================
# READER PAGE
# ============================================================

class ReaderPage(QWidget):
    """
    Litenova EPUB reader.

    MainWindow compatibility:
        open_book()
        reload_settings()
        back_requested
    """

    back_requested = Signal()

    def __init__(
        self,
    ):

        super().__init__()

        self.book = None
        self._last_saved_progress = None

        self.chapters = []

        self.current_chapter = 0

        self.is_restoring_scroll = False
        self._pending_chapter_position = None
        self._pending_chapter_save = False

        self._render_generation = 0

        self._loading_controls = False

        self._toc_open = False

        self._settings_open = True

        self._fullscreen_by_reader = False

        self._prevent_sleep_active = False

        self._changing_slider = False

        self._search_open = False

        self._bookmarks = {}

        # ----------------------------------------------------
        # SAVED PANEL WIDTHS
        # ----------------------------------------------------

        self._toc_width = setting_int(
            "epub_toc_width",
            275,
            190,
            490,
        )

        self._settings_width = setting_int(
            "epub_settings_width",
            450,
            420,
            680,
        )

        self._splitter_ready = False

        self._splitter_store_timer = QTimer(
            self
        )

        self._splitter_store_timer.setSingleShot(
            True
        )

        self._splitter_store_timer.setInterval(
            350
        )

        self._splitter_store_timer.timeout.connect(
            self.save_panel_widths
        )

        # ----------------------------------------------------
        # EPUB IMAGE CACHE
        # ----------------------------------------------------

        self._epub_file = None

        self._epub_images = {}

        self._epub_image_index = {}

        self._decoded_images = {}

        self._image_serial = 0

        # ----------------------------------------------------
        # GESTURES
        # ----------------------------------------------------

        self._gesture_origin = None

        self._last_horizontal_action = 0.0

        self.read_saved_style()

        # ----------------------------------------------------
        # PROGRESS SAVE TIMER
        # ----------------------------------------------------

        self.scroll_save_timer = QTimer(
            self
        )

        self.scroll_save_timer.setSingleShot(
            True
        )

        self.scroll_save_timer.setInterval(
            600
        )

        self.scroll_save_timer.timeout.connect(
            self.save_current_progress
        )

        # ----------------------------------------------------
        # STYLE UPDATE TIMER
        # ----------------------------------------------------

        self.style_timer = QTimer(
            self
        )

        self.style_timer.setSingleShot(
            True
        )

        self.style_timer.setInterval(
            170
        )

        self.style_timer.timeout.connect(
            self.refresh_chapter_style
        )

        self.build_ui()

        self.setup_shortcuts()

        self.apply_reader_appearance()

    # ========================================================
    # READ SAVED STYLE
    # ========================================================

    def read_saved_style(
        self,
    ):

        self.font_size = (
            get_reader_font_size()
        )

        font = str(
            get_setting(
                "reader_font_family",
                "Georgia",
            )
        )

        self.font_family = (
            font
            if font in FONTS
            else "Georgia"
        )

        self.weight = setting_int(
            "epub_weight",
            2,
            0,
            3,
        )

        self.italic = setting_bool(
            "epub_italic",
            False,
        )

        self.letter_spacing = setting_int(
            "epub_letter_spacing",
            0,
            0,
            6,
        )

        self.line_height = setting_int(
            "epub_line_height",
            170,
            120,
            240,
        )

        self.paragraph_spacing = setting_int(
            "epub_paragraph_spacing",
            10,
            0,
            30,
        )

        self.paragraph_indent = setting_int(
            "epub_paragraph_indent",
            0,
            0,
            60,
        )

        self.text_align = str(
            get_setting(
                "epub_text_align",
                "left",
            )
        )

        if self.text_align not in (
            "left",
            "center",
            "right",
            "justify",
        ):

            self.text_align = "left"

        self.side_margin = setting_int(
            "epub_side_margin",
            65,
            12,
            120,
        )

        self.vertical_margin = setting_int(
            "epub_vertical_margin",
            40,
            8,
            110,
        )

        self.show_images = setting_bool(
            "epub_show_images",
            True,
        )

        self.show_captions = setting_bool(
            "epub_show_captions",
            True,
        )

        self.image_size = setting_int(
            "epub_image_size",
            100,
            40,
            100,
        )

        self.chapter_align = str(
            get_setting(
                "epub_chapter_align",
                "center",
            )
        )

        if self.chapter_align not in (
            "left",
            "center",
            "right",
        ):

            self.chapter_align = "center"

        self.arrow_chapters = setting_bool(
            "epub_arrow_chapters",
            False,
        )

        self.progress_mode = str(
            get_setting(
                "epub_progress_mode",
                "percentage",
            )
        )

        if self.progress_mode not in (
            "percentage",
            "quantity",
        ):

            self.progress_mode = (
                "percentage"
            )

        self.show_progress = setting_bool(
            "reader_show_progress_bar",
            True,
        )

        self.keep_screen_on = setting_bool(
            "epub_keep_screen_on",
            False,
        )

    # ========================================================
    # GENERIC READER BUTTON
    # ========================================================

    def button(
        self,
        label,
        action,
        width=34,
        tip="",
    ):

        button = QPushButton(
            label,
            self,
        )

        button.setObjectName(
            "readerIconButton"
        )

        button.setFixedHeight(
            34
        )

        if width:

            button.setFixedWidth(
                width
            )

        button.setCursor(
            Qt.PointingHandCursor
        )

        if tip:

            button.setToolTip(
                tip
            )

        button.clicked.connect(
            action
        )

        return button

    # ========================================================
    # SETTINGS SECTION
    # ========================================================

    def section(
        self,
        layout,
        heading,
    ):

        if heading == "Reader Settings":

            line = QLabel(
                heading,
                self.settings_content,
            )

            line.setObjectName(
                "readerSettingsHeading"
            )

            layout.addWidget(
                line
            )

            return line

        layout.addSpacing(
            8
        )

        line = QLabel(
            heading,
            self.settings_content,
        )

        line.setObjectName(
            "readerSectionTitle"
        )

        layout.addWidget(
            line
        )

        return line

    # ========================================================
    # OPTION ROW
    # ========================================================

    def option_row(
        self,
        layout,
        title,
        control,
        detail="",
    ):

        line = QWidget(
            self.settings_content
        )

        line.setObjectName(
            "readerOptionRow"
        )

        row = QHBoxLayout(
            line
        )

        row.setContentsMargins(
            2,
            6,
            2,
            6,
        )

        row.setSpacing(
            16
        )

        labels = row_label(
            title,
            detail,
        )

        labels.setObjectName(
            "readerOptionLabels"
        )

        row.addWidget(
            labels,
            1,
            Qt.AlignVCenter,
        )

        if isinstance(
            control,
            Toggle,
        ):

            row.addWidget(
                control,
                0,
                Qt.AlignRight
                | Qt.AlignVCenter,
            )

        else:

            control.setMinimumWidth(
                252
            )

            control.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Preferred,
            )

            row.addWidget(
                control,
                0,
                Qt.AlignRight
                | Qt.AlignVCenter,
            )

        line.setMinimumHeight(
            50
            if not detail
            else 64
        )

        layout.addWidget(
            line
        )

        return line

    # ========================================================
    # SLIDER CONTROL
    # ========================================================

    def slider_control(
        self,
        low,
        high,
        initial,
        suffix="",
        width=130,
    ):

        frame = QWidget(
            self.settings_content
        )

        frame.setObjectName(
            "readerSliderControl"
        )

        frame.setMinimumWidth(
            252
        )

        line = QHBoxLayout(
            frame
        )

        line.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        line.setSpacing(
            12
        )

        slider = QSlider(
            Qt.Horizontal,
            frame,
        )

        slider.setObjectName(
            "readerSettingSlider"
        )

        slider.setRange(
            low,
            high,
        )

        slider.setValue(
            initial
        )

        slider.setMinimumWidth(
            max(
                145,
                width,
            )
        )

        slider.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        number = QLabel(
            f"{initial}{suffix}",
            frame,
        )

        number.setObjectName(
            "readerSettingValue"
        )

        number.setFixedWidth(
            54
        )

        number.setMinimumHeight(
            30
        )

        number.setAlignment(
            Qt.AlignCenter
        )

        line.addWidget(
            slider,
            1,
        )

        line.addWidget(
            number
        )

        slider.valueChanged.connect(
            lambda value:
            number.setText(
                f"{value}{suffix}"
            )
        )

        return (
            frame,
            slider,
        )

    # ========================================================
    # SEGMENTED CONTROL
    # ========================================================

    def segmented(
        self,
        options,
        selected,
        changed,
        setting_key=None,
    ):

        holder = QWidget(
            self.settings_content
        )

        holder.setObjectName(
            "readerSegmentHolder"
        )

        holder.setMinimumWidth(
            252
        )

        line = QHBoxLayout(
            holder
        )

        line.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        line.setSpacing(
            6
        )

        group = QButtonGroup(
            holder
        )

        group.setExclusive(
            True
        )

        if setting_key is not None:

            self._reader_segment_controls[
                setting_key
            ] = {}

        for option in options:

            caption, value = (
                option[:2]
            )

            icon_name = (
                option[2]
                if len(option) > 2
                else None
            )

            button = QPushButton(
                caption,
                holder,
            )

            if icon_name:

                icon = reader_icon(
                    icon_name
                )

                if not icon.isNull():

                    button.setText(
                        ""
                    )

                    button.setIcon(
                        icon
                    )

                    button.setIconSize(
                        QSize(
                            17,
                            17,
                        )
                    )

                button.setToolTip(
                    caption
                )

                button.setAccessibleName(
                    (
                        "Text alignment: "
                        + caption
                    )
                )

            button.setCheckable(
                True
            )

            button.setChecked(
                value == selected
            )

            button.setObjectName(
                "readerSegment"
            )

            button.setMinimumHeight(
                34
            )

            button.setMinimumWidth(
                54
            )

            button.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Fixed,
            )

            group.addButton(
                button
            )

            if setting_key is not None:

                self._reader_segment_controls[
                    setting_key
                ][
                    value
                ] = button

            line.addWidget(
                button,
                1,
            )

            button.clicked.connect(
                lambda _checked=False,
                v=value:
                changed(v)
            )

        return holder

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(
        self,
    ):

        self.setObjectName(
            "newReaderPage"
        )

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root.setSpacing(
            0
        )

        # ====================================================
        # HEADER
        # ====================================================

        header = QFrame(
            self
        )

        header.setObjectName(
            "readerHeader"
        )

        bar = QHBoxLayout(
            header
        )

        bar.setContentsMargins(
            15,
            8,
            13,
            8,
        )

        bar.setSpacing(
            12
        )

        self.back_button = self.button(
            "‹",
            self.go_back,
            30,
            "Back to Library or History",
        )

        bar.addWidget(
            self.back_button
        )

        self.cover = QLabel(
            header
        )

        self.cover.setFixedSize(
            38,
            52,
        )

        self.cover.setObjectName(
            "readerHeaderCover"
        )

        self.cover.setAlignment(
            Qt.AlignCenter
        )

        bar.addWidget(
            self.cover
        )

        book_titles = QVBoxLayout()

        book_titles.setSpacing(
            2
        )

        self.book_title = QLabel(
            "Litenova Reader",
            header,
        )

        self.book_title.setObjectName(
            "readerHeaderTitle"
        )

        self.book_title.setMaximumWidth(
            270
        )

        self.author = QLabel(
            "",
            header,
        )

        self.author.setObjectName(
            "readerHeaderSub"
        )

        book_titles.addWidget(
            self.book_title
        )

        book_titles.addWidget(
            self.author
        )

        bar.addLayout(
            book_titles
        )

        separator = QFrame(
            header
        )

        separator.setObjectName(
            "readerHeaderDivider"
        )

        separator.setFixedSize(
            1,
            36,
        )

        bar.addWidget(
            separator
        )

        chapter_titles = QVBoxLayout()

        chapter_titles.setSpacing(
            2
        )

        self.chapter_number = QLabel(
            "Chapter 1",
            header,
        )

        self.chapter_number.setObjectName(
            "readerHeaderTitle"
        )

        self.chapter_title = QLabel(
            "Open a book to begin",
            header,
        )

        self.chapter_title.setObjectName(
            "readerHeaderSub"
        )

        chapter_titles.addWidget(
            self.chapter_number
        )

        chapter_titles.addWidget(
            self.chapter_title
        )

        bar.addLayout(
            chapter_titles,
            1,
        )

        self.search_button = self.button(
            "⌕",
            self.toggle_search,
            34,
            "Find text in this chapter (Ctrl+F)",
        )

        self.toc_button = self.button(
            "☷",
            self.toggle_toc,
            34,
            "Table of contents",
        )

        self.bookmark_button = self.button(
            "☆",
            self.toggle_bookmark,
            34,
            "Bookmark this position",
        )

        self.options_button = self.button(
            "⋮",
            self.toggle_settings,
            34,
            "Show or hide Reader Settings",
        )

        use_button_icon(
            self.search_button,
            reader_icon(
                "search.png",
                "search_input_icon.png",
            ),
        )

        use_button_icon(
            self.toc_button,
            reader_icon(
                "icons8-table-100.png"
            ),
        )

        use_button_icon(
            self.bookmark_button,
            reader_icon(
                "icons8-bookmark-50.png"
            ),
        )

        use_button_icon(
            self.options_button,
            reader_icon(
                "more_options.png",
                "item_options.png",
            ),
        )

        for widget in (
            self.search_button,
            self.toc_button,
            self.bookmark_button,
            self.options_button,
        ):

            bar.addWidget(
                widget
            )

        root.addWidget(
            header
        )

        # ====================================================
        # SEARCH
        # ====================================================

        self.search_row = QWidget(
            self
        )

        search_line = QHBoxLayout(
            self.search_row
        )

        search_line.setContentsMargins(
            20,
            5,
            20,
            5,
        )

        self.search_field = QLineEdit(
            self.search_row
        )

        self.search_field.setPlaceholderText(
            "Find in current chapter..."
        )

        self.search_field.returnPressed.connect(
            self.find_next
        )

        search_line.addWidget(
            self.search_field,
            1,
        )

        search_line.addWidget(
            self.button(
                "Find next",
                self.find_next,
                90,
            )
        )

        search_line.addWidget(
            self.button(
                "✕",
                self.toggle_search,
                30,
            )
        )

        root.addWidget(
            self.search_row
        )

        self.search_row.hide()

        # ====================================================
        # MAIN READER SPLITTER
        # ====================================================

        body = QSplitter(
            Qt.Horizontal,
            self,
        )

        self.body_splitter = (
            body
        )

        body.setObjectName(
            "readerBodySplitter"
        )

        body.setChildrenCollapsible(
            False
        )

        body.setHandleWidth(
            7
        )

        # ====================================================
        # TABLE OF CONTENTS
        # ====================================================

        self.toc_panel = QFrame(
            body
        )

        self.toc_panel.setObjectName(
            "readerTocPanel"
        )

        self.toc_panel.setMinimumWidth(
            190
        )

        self.toc_panel.setMaximumWidth(
            490
        )

        toc_layout = QVBoxLayout(
            self.toc_panel
        )

        toc_layout.setContentsMargins(
            12,
            16,
            12,
            12,
        )

        toc_header = QHBoxLayout()

        toc_icon = reader_icon(
            "icons8-align-justify-50.png"
        )

        if not toc_icon.isNull():

            toc_symbol = QLabel(
                self.toc_panel
            )

            toc_symbol.setPixmap(
                toc_icon.pixmap(
                    QSize(
                        19,
                        19,
                    )
                )
            )

            toc_symbol.setFixedSize(
                21,
                21,
            )

            toc_header.addWidget(
                toc_symbol
            )

        toc_label = QLabel(
            "Table of Contents",
            self.toc_panel,
        )

        toc_label.setObjectName(
            "readerSectionTitle"
        )

        toc_header.addWidget(
            toc_label,
            1,
        )

        toc_layout.addLayout(
            toc_header
        )

        self.toc_list = QListWidget(
            self.toc_panel
        )

        self.toc_list.currentRowChanged.connect(
            self.jump_to_chapter
        )

        toc_layout.addWidget(
            self.toc_list,
            1,
        )

        body.addWidget(
            self.toc_panel
        )

        self.toc_panel.hide()

        # ====================================================
        # READER CANVAS
        # ====================================================

        self.reader = EpubTextBrowser(
            body
        )

        self.reader.image_provider = (
            self.load_epub_image
        )

        self.reader.installEventFilter(
            self
        )

        self.reader.viewport().installEventFilter(
            self
        )

        self.reader.setObjectName(
            "readerCanvas"
        )

        self.reader.setOpenExternalLinks(
            False
        )

        self.reader.setFrameShape(
            QFrame.NoFrame
        )

        self.reader.setReadOnly(
            True
        )

        self.reader.setMinimumWidth(
            240
        )

        self.reader.verticalScrollBar().valueChanged.connect(
            self.on_scroll_changed
        )
        self.reader.verticalScrollBar().rangeChanged.connect(
            self.on_document_range_changed
        )

        body.addWidget(
            self.reader
        )

        # ====================================================
        # READER SETTINGS PANEL
        # ====================================================

        self.settings_panel = QScrollArea(
            body
        )

        self.settings_panel.setObjectName(
            "readerSettingsPanel"
        )

        self.settings_panel.setWidgetResizable(
            True
        )

        self.settings_panel.setFrameShape(
            QFrame.NoFrame
        )

        self.settings_panel.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.settings_panel.setMinimumWidth(
            420
        )

        self.settings_panel.setMaximumWidth(
            680
        )

        self.settings_content = QWidget()

        self.settings_content.setObjectName(
            "readerSettingsContent"
        )

        self._reader_slider_controls = {}

        self._reader_segment_controls = {}

        side = QVBoxLayout(
            self.settings_content
        )

        side.setContentsMargins(
            22,
            20,
            22,
            26,
        )

        side.setSpacing(
            8
        )

        self.section(
            side,
            "Reader Settings",
        )

        self.section(
            side,
            "Font",
        )

        # ====================================================
        # FONT FAMILY
        # ====================================================

        self.font_combo = QComboBox(
            self.settings_content
        )

        self.font_combo.setMinimumHeight(
            36
        )

        self.font_combo.setMinimumWidth(
            252
        )

        for name in FONTS:

            self.font_combo.addItem(
                name
            )

        self.font_combo.setCurrentText(
            self.font_family
        )

        self.font_combo.currentTextChanged.connect(
            lambda name:
            self.update_style(
                "reader_font_family",
                name,
            )
        )

        self.option_row(
            side,
            "Font family",
            self.font_combo,
        )

        # ====================================================
        # FONT THICKNESS
        # ====================================================

        self.option_row(
            side,
            "Font thickness",
            self.segmented(
                (
                    (
                        "Thin",
                        0,
                    ),
                    (
                        "Light",
                        1,
                    ),
                    (
                        "Normal",
                        2,
                    ),
                    (
                        "Medium",
                        3,
                    ),
                ),
                self.weight,
                lambda value:
                self.update_style(
                    "epub_weight",
                    value,
                ),
                "epub_weight",
            ),
        )

        # ====================================================
        # FONT STYLE
        # ====================================================

        self.option_row(
            side,
            "Font style",
            self.segmented(
                (
                    (
                        "Normal",
                        False,
                    ),
                    (
                        "Italic",
                        True,
                    ),
                ),
                self.italic,
                lambda value:
                self.update_style(
                    "epub_italic",
                    value,
                ),
                "epub_italic",
            ),
        )

        # ====================================================
        # FONT SIZE
        # ====================================================

        (
            control,
            self.font_slider,
        ) = self.slider_control(
            12,
            32,
            self.font_size,
            "",
            170,
        )

        self._reader_slider_controls[
            "reader_font_size"
        ] = self.font_slider

        self.font_slider.valueChanged.connect(
            lambda value:
            self.update_style(
                "reader_font_size",
                value,
            )
        )

        self.option_row(
            side,
            "Font size",
            control,
        )

        # ====================================================
        # TEXT SPACING
        # ====================================================

        for (
            label,
            key,
            low,
            high,
            value,
            suffix,
        ) in (
            (
                "Letter spacing",
                "epub_letter_spacing",
                0,
                6,
                self.letter_spacing,
                "",
            ),
            (
                "Line height",
                "epub_line_height",
                120,
                240,
                self.line_height,
                "%",
            ),
            (
                "Paragraph spacing",
                "epub_paragraph_spacing",
                0,
                30,
                self.paragraph_spacing,
                "",
            ),
            (
                "Paragraph indentation",
                "epub_paragraph_indent",
                0,
                60,
                self.paragraph_indent,
                "",
            ),
        ):

            (
                control,
                slider,
            ) = self.slider_control(
                low,
                high,
                value,
                suffix,
                125,
            )

            self._reader_slider_controls[
                key
            ] = slider

            slider.valueChanged.connect(
                lambda value,
                k=key:
                self.update_style(
                    k,
                    value,
                )
            )

            self.option_row(
                side,
                label,
                control,
            )

        # ====================================================
        # READING LAYOUT
        # ====================================================

        self.section(
            side,
            "Reading Layout",
        )

        self.option_row(
            side,
            "Text alignment",
            self.segmented(
                (
                    (
                        "Left",
                        "left",
                        "icons8-align-left-50.png",
                    ),
                    (
                        "Center",
                        "center",
                        "icons8-align-center-50.png",
                    ),
                    (
                        "Right",
                        "right",
                        "icons8-align-right-50.png",
                    ),
                    (
                        "Justify",
                        "justify",
                        "icons8-align-justify-50.png",
                    ),
                ),
                self.text_align,
                lambda value:
                self.update_style(
                    "epub_text_align",
                    value,
                ),
                "epub_text_align",
            ),
        )

        for (
            label,
            key,
            low,
            high,
            value,
        ) in (
            (
                "Side margins",
                "epub_side_margin",
                12,
                120,
                self.side_margin,
            ),
            (
                "Vertical margins",
                "epub_vertical_margin",
                8,
                110,
                self.vertical_margin,
            ),
        ):

            (
                control,
                slider,
            ) = self.slider_control(
                low,
                high,
                value,
                "",
                170,
            )

            self._reader_slider_controls[
                key
            ] = slider

            slider.valueChanged.connect(
                lambda value,
                k=key:
                self.update_style(
                    k,
                    value,
                )
            )

            self.option_row(
                side,
                label,
                control,
            )

        # ====================================================
        # IMAGES
        # ====================================================

        self.section(
            side,
            "Images",
        )

        self.images_switch = Toggle(
            self.settings_content
        )

        self.images_switch.setChecked(
            self.show_images
        )

        self.images_switch.toggled.connect(
            lambda checked:
            self.update_style(
                "epub_show_images",
                checked,
            )
        )

        self.option_row(
            side,
            "Display images",
            self.images_switch,
        )

        self.captions_switch = Toggle(
            self.settings_content
        )

        self.captions_switch.setChecked(
            self.show_captions
        )

        self.captions_switch.toggled.connect(
            lambda checked:
            self.update_style(
                "epub_show_captions",
                checked,
            )
        )

        self.option_row(
            side,
            "Display captions",
            self.captions_switch,
        )

        (
            control,
            slider,
        ) = self.slider_control(
            40,
            100,
            self.image_size,
            "%",
            170,
        )

        self._reader_slider_controls[
            "epub_image_size"
        ] = slider

        slider.valueChanged.connect(
            lambda value:
            self.update_style(
                "epub_image_size",
                value,
            )
        )

        self.option_row(
            side,
            "Image size",
            control,
        )

        # ====================================================
        # CHAPTER STYLE
        # ====================================================

        self.section(
            side,
            "Chapter Style",
        )

        self.option_row(
            side,
            "Chapter title alignment",
            self.segmented(
                (
                    (
                        "Start",
                        "left",
                    ),
                    (
                        "Center",
                        "center",
                    ),
                    (
                        "End",
                        "right",
                    ),
                ),
                self.chapter_align,
                lambda value:
                self.update_style(
                    "epub_chapter_align",
                    value,
                ),
                "epub_chapter_align",
            ),
        )

        # ====================================================
        # READING MODE
        # ====================================================

        self.section(
            side,
            "Reading Mode",
        )

        self.arrows_switch = Toggle(
            self.settings_content
        )

        self.arrows_switch.setChecked(
            self.arrow_chapters
        )

        self.arrows_switch.toggled.connect(
            lambda checked:
            self.update_style(
                "epub_arrow_chapters",
                checked,
            )
        )

        self.option_row(
            side,
            "Horizontal gesture",
            self.arrows_switch,
            (
                "Swipe sideways or use "
                "← / → to turn reading pages"
            ),
        )

        self.option_row(
            side,
            "Progress count",
            self.segmented(
                (
                    (
                        "Percentage",
                        "percentage",
                    ),
                    (
                        "Quantity",
                        "quantity",
                    ),
                ),
                self.progress_mode,
                lambda value:
                self.update_style(
                    "epub_progress_mode",
                    value,
                ),
                "epub_progress_mode",
            ),
        )

        self.progress_switch = Toggle(
            self.settings_content
        )

        self.progress_switch.setChecked(
            self.show_progress
        )

        self.progress_switch.toggled.connect(
            lambda checked:
            self.update_style(
                "reader_show_progress_bar",
                checked,
            )
        )

        self.option_row(
            side,
            "Progress bar",
            self.progress_switch,
        )

        self.fullscreen_switch = Toggle(
            self.settings_content
        )

        self.fullscreen_switch.toggled.connect(
            self.set_reader_fullscreen
        )

        self.option_row(
            side,
            "Fullscreen",
            self.fullscreen_switch,
        )

        self.sleep_switch = Toggle(
            self.settings_content
        )

        self.sleep_switch.setChecked(
            self.keep_screen_on
        )

        if sys.platform != "win32":

            self.sleep_switch.setEnabled(
                False
            )

            self.sleep_switch.setToolTip(
                (
                    "Keep screen on is "
                    "implemented for Windows"
                )
            )

        self.sleep_switch.toggled.connect(
            lambda checked:
            self.update_style(
                "epub_keep_screen_on",
                checked,
            )
        )

        self.option_row(
            side,
            "Keep screen on",
            self.sleep_switch,
        )

        # ====================================================
        # RESTORE DEFAULTS
        # ====================================================

        self.reset_reader_button = QPushButton(
            "Restore default reader settings",
            self.settings_content,
        )

        self.reset_reader_button.setObjectName(
            "readerResetButton"
        )

        self.reset_reader_button.setMinimumHeight(
            39
        )

        self.reset_reader_button.setCursor(
            Qt.PointingHandCursor
        )

        self.reset_reader_button.setToolTip(
            (
                "Restore the original EPUB font, "
                "layout, image, and reading controls"
            )
        )

        self.reset_reader_button.clicked.connect(
            self.restore_default_reader_settings
        )

        side.addWidget(
            self.reset_reader_button
        )

        side.addStretch(
            1
        )

        self.settings_panel.setWidget(
            self.settings_content
        )

        body.addWidget(
            self.settings_panel
        )

        body.setStretchFactor(
            0,
            0,
        )

        body.setStretchFactor(
            1,
            1,
        )

        body.setStretchFactor(
            2,
            0,
        )

        body.splitterMoved.connect(
            self.queue_panel_width_save
        )

        root.addWidget(
            body,
            1,
        )

        # ====================================================
        # FOOTER
        # ====================================================

        footer = QFrame(
            self
        )

        footer.setObjectName(
            "readerFooter"
        )

        foot = QVBoxLayout(
            footer
        )

        foot.setContentsMargins(
            15,
            5,
            15,
            7,
        )

        foot.setSpacing(
            3
        )

        self.progress_slider = QSlider(
            Qt.Horizontal,
            footer,
        )

        self.progress_slider.setRange(
            0,
            1000,
        )

        self.progress_slider.setTracking(
            False
        )

        self.progress_slider.sliderPressed.connect(
            self.begin_seek
        )

        self.progress_slider.sliderReleased.connect(
            self.end_seek
        )

        foot.addWidget(
            self.progress_slider
        )

        line = QHBoxLayout()

        self.percent_label = QLabel(
            "0.0%",
            footer,
        )

        self.percent_label.setObjectName(
            "readerFooterText"
        )

        self.page_label = QLabel(
            "Position 1 / 1",
            footer,
        )

        self.page_label.setObjectName(
            "readerFooterText"
        )

        self.chapter_label = QLabel(
            "No chapter",
            footer,
        )

        self.chapter_label.setObjectName(
            "readerFooterText"
        )

        self.previous_button = self.button(
            "‹",
            self.previous_page,
            32,
            (
                "Previous reading page "
                "(Ctrl+Left for chapter)"
            ),
        )

        self.next_button = self.button(
            "›",
            self.next_page,
            32,
            (
                "Next reading page "
                "(Ctrl+Right for chapter)"
            ),
        )

        line.addWidget(
            self.percent_label
        )

        line.addSpacing(
            10
        )

        line.addWidget(
            self.page_label
        )

        line.addStretch()

        line.addWidget(
            self.chapter_label
        )

        line.addSpacing(
            10
        )

        line.addWidget(
            self.previous_button
        )

        line.addWidget(
            self.next_button
        )

        foot.addLayout(
            line
        )

        root.addWidget(
            footer
        )

        self.apply_local_style()

        self.update_navigation()

    # ========================================================
    # LOCAL STYLE
    # ========================================================

    def apply_local_style(
        self,
    ):

        style = """
        QWidget#newReaderPage {
            background: #12141a;
            color: #e8e8f5;
        }

        QFrame#readerHeader {
            background: #14171d;
            border-bottom: 1px solid #303341;
        }

        QLabel#readerHeaderTitle {
            font: 600 15px Georgia;
            color: #e8e8f5;
            background: transparent;
        }

        QLabel#readerHeaderSub {
            font: 11px Georgia;
            color: #b5b7ca;
            background: transparent;
        }

        QLabel#readerHeaderCover {
            background: #292c3d;
            border-radius: 5px;
        }

        QFrame#readerHeaderDivider {
            background: #606078;
            border: none;
        }

        QPushButton#readerIconButton {
            background: transparent;
            color: #d2d4ef;
            border: 1px solid transparent;
            border-radius: 6px;
            font-size: 18px;
            padding: 0 5px;
        }

        QPushButton#readerIconButton:hover {
            background: #34354d;
            border-color: #565879;
        }

        QPushButton#readerIconButton:disabled {
            color: #66697e;
        }

        QTextBrowser#readerCanvas {
            background: #12141a;
            color: #e8e8f5;
            border: none;
            selection-background-color: #504c7b;
        }

        QFrame#readerTocPanel {
            background: #181a22;
            border-right: 1px solid #323543;
        }

        QSplitter#readerBodySplitter::handle {
            background: #282c3a;
        }

        QSplitter#readerBodySplitter::handle:hover {
            background: #6d6b9a;
        }

        QListWidget {
            background: #171923;
            color: #e4e5f3;
            border: 1px solid #333747;
            border-radius: 7px;
            outline: none;
            padding: 4px;
        }

        QListWidget::item {
            padding: 10px 6px;
        }

        QListWidget::item:selected {
            background: #484968;
            border-radius: 5px;
        }

        QScrollArea#readerSettingsPanel {
            background: #161820;
            border-left: 1px solid #303441;
        }

        QWidget#readerSettingsContent {
            background: #161820;
        }

        QWidget#readerOptionRow,
        QWidget#readerOptionLabels,
        QWidget#readerSliderControl,
        QWidget#readerSegmentHolder {
            background: transparent;
            border: none;
        }

        QLabel#readerSettingsHeading {
            background: transparent;
            color: #f0efff;
            font-size: 20px;
            font-weight: 700;
            padding: 0 0 6px 0;
        }

        QLabel#readerSectionTitle {
            background: transparent;
            color: #d5d3ff;
            font-size: 15px;
            font-weight: 700;
            padding: 10px 0 5px 0;
        }

        QLabel#readerRowTitle {
            background: transparent;
            color: #e5e7f3;
            font-size: 12px;
            font-weight: 500;
        }

        QLabel#readerRowDetail {
            background: transparent;
            color: #9298af;
            font-size: 10px;
            padding-top: 2px;
        }

        QLabel#readerSettingValue {
            background: #20232d;
            color: #e9eaff;
            border: 1px solid #383d4d;
            border-radius: 8px;
            font-size: 11px;
            font-weight: 600;
            padding: 0 4px;
        }

        QComboBox,
        QLineEdit {
            background: #12141c;
            border: 1px solid #3b4051;
            border-radius: 8px;
            color: #e7e8f5;
            font-size: 12px;
            padding: 6px 10px;
        }

        QComboBox:hover,
        QComboBox:focus,
        QLineEdit:focus {
            border-color: #6f7398;
        }

        QComboBox::drop-down {
            background: transparent;
            border: none;
            width: 24px;
        }

        QComboBox QAbstractItemView {
            background: #1a1d26;
            color: #e7e8f5;
            border: 1px solid #44495b;
            border-radius: 8px;
            outline: none;
            padding: 5px;
            selection-background-color: #3b405b;
            selection-color: #ffffff;
        }

        QPushButton#readerSegment {
            background: #20232d;
            border: 1px solid #3c4152;
            color: #cbd0df;
            font-size: 11px;
            border-radius: 8px;
            padding: 5px 6px;
        }

        QPushButton#readerSegment:hover {
            background: #292d3a;
            border-color: #626783;
            color: #f0f1ff;
        }

        QPushButton#readerSegment:checked {
            background: #343851;
            border-color: #7f82b4;
            color: #ffffff;
            font-weight: 600;
        }

        QPushButton#readerResetButton {
            background: #292d3e;
            color: #e9e8ff;
            border: 1px solid #51576f;
            border-radius: 9px;
            padding: 9px 14px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 10px;
        }

        QPushButton#readerResetButton:hover {
            background: #363b50;
            border-color: #777da4;
        }

        /*
        Reader setting sliders are explicitly transparent.

        This prevents Qt/global QSS from painting the entire
        slider widget as a dark/black rectangle.
        */

        QSlider#readerSettingSlider {
            background: transparent;
            border: none;
            min-height: 26px;
            padding: 0px;
        }

        QSlider#readerSettingSlider::groove:horizontal {
            background: #343847;
            border: none;
            height: 5px;
            border-radius: 2px;
        }

        QSlider#readerSettingSlider::sub-page:horizontal {
            background: #7775c7;
            border-radius: 2px;
        }

        QSlider#readerSettingSlider::add-page:horizontal {
            background: #343847;
            border-radius: 2px;
        }

        QSlider#readerSettingSlider::handle:horizontal {
            background: #d1d0ff;
            border: 2px solid #676bb0;
            width: 14px;
            height: 14px;
            margin: -6px 0;
            border-radius: 8px;
        }

        QSlider#readerSettingSlider::handle:horizontal:hover {
            background: #ffffff;
            border-color: #8d8fd1;
        }

        QFrame#readerFooter {
            background: #151720;
            border-top: 1px solid #323543;
        }

        QLabel#readerFooterText {
            background: transparent;
            color: #c6c8db;
            font: 11px Georgia;
        }

        QScrollBar:vertical {
            background: #161820;
            width: 8px;
            border: none;
        }

        QScrollBar::handle:vertical {
            background: #55586e;
            border-radius: 4px;
            min-height: 30px;
        }

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0;
        }

        QScrollBar:horizontal {
            height: 7px;
            background: #161820;
        }

        QScrollBar::handle:horizontal {
            background: #55586e;
            border-radius: 3px;
        }
        """

        palette = (
            resolved_colors()
        )

        if (
            palette["background"]
            != "#15171e"
            or palette["foreground"]
            != "#eeeeee"
            or palette["accent"]
            != "#8f88ff"
        ):

            replacements = {
                "#12141a": (
                    palette[
                        "reader_background"
                    ]
                ),
                "#14171d": (
                    palette[
                        "sidebar"
                    ]
                ),
                "#151720": (
                    palette[
                        "panel"
                    ]
                ),
                "#161820": (
                    palette[
                        "panel"
                    ]
                ),
                "#181a22": (
                    palette[
                        "panel"
                    ]
                ),
                "#191b23": (
                    palette[
                        "panel"
                    ]
                ),
                "#e8e8f5": (
                    palette[
                        "foreground"
                    ]
                ),
                "#e4e5f3": (
                    palette[
                        "foreground"
                    ]
                ),
                "#d2d4ef": (
                    palette[
                        "foreground"
                    ]
                ),
                "#dce0f5": (
                    palette[
                        "foreground"
                    ]
                ),
                "#aba8f0": (
                    palette[
                        "accent"
                    ]
                ),
                "#d4d3ff": (
                    palette[
                        "accent"
                    ]
                ),
                "#484968": (
                    palette[
                        "selected"
                    ]
                ),
                "#494b72": (
                    palette[
                        "selected"
                    ]
                ),
                "#34354d": (
                    palette[
                        "hover"
                    ]
                ),
            }

            pattern = re.compile(
                "|".join(
                    re.escape(
                        value
                    )
                    for value
                    in replacements
                ),
                re.I,
            )

            style = pattern.sub(
                lambda match:
                replacements[
                    match.group().lower()
                ],
                style,
            )

        self.setStyleSheet(
            style
        )

    # ========================================================
    # RESTORE DEFAULT READER SETTINGS
    # ========================================================

    def restore_default_reader_settings(
        self,
    ):

        answer = QMessageBox.question(
            self,
            "Restore reader settings?",
            (
                "Restore the original EPUB font, spacing, "
                "layout, images, and reading controls?"
                "\n\n"
                "Your reading progress, bookmarks and app "
                "appearance will not be changed."
            ),
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:

            return

        self.scroll_save_timer.stop()

        self.style_timer.stop()

        position = (
            self.get_current_scroll_position()
        )

        self.save_current_progress()

        self._loading_controls = True

        try:

            for (
                key,
                value,
            ) in READER_DEFAULTS.items():

                if key == "reader_font_size":

                    set_reader_font_size(
                        value
                    )

                else:

                    set_setting(
                        key,
                        value,
                    )

            self.read_saved_style()

            self.font_combo.setCurrentText(
                self.font_family
            )

            for (
                key,
                slider,
            ) in self._reader_slider_controls.items():

                slider.setValue(
                    READER_DEFAULTS[
                        key
                    ]
                )

            for (
                key,
                buttons,
            ) in self._reader_segment_controls.items():

                buttons[
                    READER_DEFAULTS[
                        key
                    ]
                ].setChecked(
                    True
                )

            self.images_switch.setChecked(
                self.show_images
            )

            self.captions_switch.setChecked(
                self.show_captions
            )

            self.arrows_switch.setChecked(
                self.arrow_chapters
            )

            self.progress_switch.setChecked(
                self.show_progress
            )

            self.sleep_switch.setChecked(
                self.keep_screen_on
            )

        finally:

            self._loading_controls = False

        if self._fullscreen_by_reader:

            self.set_reader_fullscreen(
                False
            )

        self.apply_keep_screen_on(
            False
        )

        self.apply_arrow_shortcuts()

        self.progress_slider.setVisible(
            self.show_progress
        )

        self.apply_reader_appearance()

        if (
            self.chapters
            and self.book is not None
        ):

            self.display_chapter(
                position=position,
                save_after=False,
            )

        else:

            self.update_progress_bar()

    # ========================================================
    # UPDATE STYLE SETTING
    # ========================================================

    def update_style(
        self,
        key,
        value,
    ):

        if self._loading_controls:

            return

        if key == "reader_font_size":

            set_reader_font_size(
                int(value)
            )

        else:

            set_setting(
                key,
                value,
            )

        self.read_saved_style()

        if key == "epub_arrow_chapters":

            self.apply_arrow_shortcuts()

        elif key in (
            "reader_show_progress_bar",
            "epub_progress_mode",
        ):

            self.progress_slider.setVisible(
                self.show_progress
            )

            self.update_progress_bar()

        elif key == "epub_keep_screen_on":

            self.apply_keep_screen_on(
                (
                    self.isVisible()
                    and self.keep_screen_on
                )
            )

        else:

            self.style_timer.start()

    # ========================================================
    # REFRESH CHAPTER STYLE
    # ========================================================

    def refresh_chapter_style(
        self,
    ):

        position = (
            self.get_current_scroll_position()
        )

        self.apply_reader_appearance()

        if (
            self.chapters
            and self.book is not None
        ):

            self.display_chapter(
                position=position,
                save_after=False,
            )

    # ========================================================
    # APPLY READER APPEARANCE
    # ========================================================

    def apply_reader_appearance(
        self,
    ):

        font = QFont(
            self.font_family,
            self.font_size,
        )

        font.setWeight(
            (
                QFont.Thin,
                QFont.Light,
                QFont.Normal,
                QFont.Bold,
            )[
                self.weight
            ]
        )

        font.setItalic(
            self.italic
        )

        font.setLetterSpacing(
            QFont.AbsoluteSpacing,
            self.letter_spacing,
        )

        self.reader.setFont(
            font
        )

        self.reader.document().setDefaultFont(
            font
        )

        palette = (
            resolved_colors()
        )

        self.reader.setStyleSheet(
            f"""
            QTextBrowser#readerCanvas {{
                background:
                    {palette['reader_background']};

                color:
                    {palette['foreground']};

                border:
                    none;

                padding:
                    {self.vertical_margin}px
                    {self.side_margin}px;

                selection-background-color:
                    {palette['selected']};
            }}
            """
        )

    # ========================================================
    # PREPARE CHAPTER HTML
    # ========================================================

    def prepare_chapter_html(
        self,
        chapter_html,
    ):

        if isinstance(
            chapter_html,
            bytes,
        ):

            html = chapter_html.decode(
                "utf-8",
                "replace",
            )

        else:

            html = str(
                chapter_html
            )

        if self.show_images:

            html = self.resolve_epub_images(
                html
            )

        else:

            html = re.sub(
                r"<img\b[^>]*>",
                "",
                html,
                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                ),
            )

            html = re.sub(
                r"<image\b[^>]*>",
                "",
                html,
                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                ),
            )

        if not self.show_captions:

            html = re.sub(
                (
                    r"<figcaption\b[^>]*>"
                    r".*?"
                    r"</figcaption\s*>"
                ),
                "",
                html,
                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                ),
            )

        font_name = escape(
            self.font_family,
            quote=True,
        ).replace(
            "'",
            "",
        )

        weight = (
            "100",
            "300",
            "400",
            "700",
        )[
            self.weight
        ]

        italic = (
            "italic"
            if self.italic
            else "normal"
        )

        palette = (
            resolved_colors()
        )

        foreground = (
            palette[
                "foreground"
            ]
        )

        background = (
            palette[
                "reader_background"
            ]
        )

        accent = (
            palette[
                "accent"
            ]
        )

        css = f"""
        <style>
            body {{
                background-color:
                    {background} !important;
            }}

            body,
            body *,
            p,
            div,
            li,
            blockquote,
            span {{
                color:
                    {foreground} !important;

                font-family:
                    '{font_name}' !important;

                font-size:
                    {self.font_size}pt !important;

                font-weight:
                    {weight} !important;

                font-style:
                    {italic} !important;

                letter-spacing:
                    {self.letter_spacing}px !important;

                line-height:
                    {self.line_height}% !important;
            }}

            p {{
                margin-top:
                    0px !important;

                margin-bottom:
                    {self.paragraph_spacing}px !important;

                text-indent:
                    {self.paragraph_indent}px !important;

                text-align:
                    {self.text_align} !important;
            }}

            blockquote {{
                margin-left:
                    22px;

                margin-right:
                    22px;
            }}

            h1,
            h2,
            h3,
            h4 {{
                color:
                    {foreground} !important;

                font-family:
                    '{font_name}' !important;

                text-align:
                    {self.chapter_align} !important;

                font-weight:
                    600 !important;

                font-style:
                    normal !important;
            }}

            img {{
                max-width:
                    {self.image_size}% !important;

                height:
                    auto !important;
            }}

            figcaption {{
                color:
                    {foreground} !important;

                text-align:
                    center;

                font-style:
                    italic;
            }}

            a {{
                color:
                    {accent} !important;
            }}
        </style>
        """

        if re.search(
            r"</head\s*>",
            html,
            re.IGNORECASE,
        ):

            return re.sub(
                r"</head\s*>",
                lambda match:
                css
                + match.group(
                    0
                ),
                html,
                count=1,
                flags=re.IGNORECASE,
            )

        return (
            css
            + html
        )

    # ========================================================
    # INDEX EPUB IMAGES
    # ========================================================

    def index_epub_images(
        self,
        book_path,
    ):

        self._epub_file = None

        self._epub_images = {}

        self._epub_image_index = {}

        self._decoded_images = {}

        self._image_serial = 0

        if not book_path:

            return

        path = Path(
            str(
                book_path
            )
        )

        if (
            not path.is_file()
            or path.suffix.lower()
            != ".epub"
        ):

            return

        try:

            with zipfile.ZipFile(
                path
            ) as archive:

                images = {
                    posixpath.normpath(
                        name.lstrip(
                            "/"
                        )
                    ): name
                    for name
                    in archive.namelist()
                    if name.lower().endswith(
                        (
                            ".jpg",
                            ".jpeg",
                            ".png",
                            ".gif",
                            ".webp",
                            ".bmp",
                        )
                    )
                }

            self._epub_file = (
                path
            )

            self._epub_images = (
                images
            )

        except (
            OSError,
            zipfile.BadZipFile,
        ):

            pass

    # ========================================================
    # RESOLVE EPUB IMAGES
    # ========================================================

    def resolve_epub_images(
        self,
        chapter_html,
    ):

        if not self._epub_images:

            return chapter_html

        def convert(
            match,
        ):

            tag = (
                match.group(
                    0
                )
            )

            attr = re.search(
                r'''\bsrc\s*=\s*(["'])(.*?)\1''',
                tag,
                re.I
                | re.S,
            )

            if attr is None:

                return tag

            src = unescape(
                attr.group(
                    2
                )
            ).strip()

            if (
                not src
                or src.startswith(
                    (
                        "data:",
                        "litenova-image:",
                        "http:",
                        "https:",
                    )
                )
            ):

                return tag

            path = posixpath.normpath(
                unquote(
                    urlsplit(
                        src
                    ).path
                )
                .replace(
                    "\\",
                    "/",
                )
                .lstrip(
                    "/"
                )
            )

            member = (
                self._epub_images.get(
                    path
                )
            )

            if member is None:

                candidates = [
                    value
                    for (
                        key,
                        value,
                    )
                    in self._epub_images.items()
                    if (
                        key.endswith(
                            "/"
                            + path
                        )
                        or key == path
                    )
                ]

                if len(
                    candidates
                ) == 1:

                    member = (
                        candidates[
                            0
                        ]
                    )

            if member is None:

                filename = (
                    posixpath.basename(
                        path
                    )
                )

                candidates = [
                    value
                    for (
                        key,
                        value,
                    )
                    in self._epub_images.items()
                    if (
                        posixpath.basename(
                            key
                        )
                        == filename
                    )
                ]

                if len(
                    candidates
                ) == 1:

                    member = (
                        candidates[
                            0
                        ]
                    )

            if member is None:

                return tag

            self._image_serial += 1

            image_id = str(
                self._image_serial
            )

            self._epub_image_index[
                image_id
            ] = member

            replacement = (
                "litenova-image:///"
                + image_id
            )

            return (
                tag[
                    :attr.start(
                        2
                    )
                ]
                + replacement
                + tag[
                    attr.end(
                        2
                    ):
                ]
            )

        return re.sub(
            r"<img\b[^>]*>",
            convert,
            chapter_html,
            flags=(
                re.I
                | re.S
            ),
        )

    # ========================================================
    # LOAD EPUB IMAGE
    # ========================================================

    def load_epub_image(
        self,
        image_id,
    ):

        member = (
            self._epub_image_index.get(
                str(
                    image_id
                )
            )
        )

        if (
            member is None
            or self._epub_file
            is None
        ):

            return QImage()

        if member in self._decoded_images:

            return (
                self._decoded_images[
                    member
                ]
            )

        try:

            with zipfile.ZipFile(
                self._epub_file
            ) as archive:

                data = archive.read(
                    member
                )

            image = QImage.fromData(
                data
            )

            if not image.isNull():

                if len(
                    self._decoded_images
                ) >= 12:

                    self._decoded_images.clear()

                self._decoded_images[
                    member
                ] = image

            return image

        except (
            OSError,
            KeyError,
            zipfile.BadZipFile,
        ):

            return QImage()

    # ========================================================
    # SAFE ROW VALUE
    # ========================================================

    @staticmethod
    def row_value(
        record,
        key,
        default=None,
    ):

        try:

            value = (
                record[
                    key
                ]
                if key in record.keys()
                else default
            )

            return (
                default
                if value is None
                else value
            )

        except (
            KeyError,
            AttributeError,
            TypeError,
        ):

            return default

    # ========================================================
    # OPEN BOOK
    # ========================================================

    def open_book(
        self,
        book,
    ):

        if self.book is not None:

            self.save_current_progress()
            self.release_book_content()

        self.scroll_save_timer.stop()

        self.style_timer.stop()

        self.book = (
            book
        )
        self._last_saved_progress = None

        self.read_saved_style()

        self.apply_reader_appearance()

        self._loading_controls = True

        self.font_combo.setCurrentText(
            self.font_family
        )

        self.font_slider.setValue(
            self.font_size
        )

        self.images_switch.setChecked(
            self.show_images
        )

        self.captions_switch.setChecked(
            self.show_captions
        )

        self.progress_switch.setChecked(
            self.show_progress
        )

        self.sleep_switch.setChecked(
            self.keep_screen_on
        )

        self.arrows_switch.setChecked(
            self.arrow_chapters
        )

        self._loading_controls = False

        self.apply_arrow_shortcuts()

        self.progress_slider.setVisible(
            self.show_progress
        )

        self.chapters = []

        self.current_chapter = 0

        self.reader.clear()

        self.toc_list.clear()

        self.book_title.setText(
            str(
                self.row_value(
                    book,
                    "title",
                    "Untitled",
                )
            )
        )

        self.author.setText(
            str(
                self.row_value(
                    book,
                    "author",
                    "Unknown author",
                )
            )
        )

        cover_file = (
            self.row_value(
                book,
                "cover_path",
            )
        )

        cover = (
            QPixmap(
                str(
                    cover_file
                )
            )
            if cover_file
            else QPixmap()
        )

        if not cover.isNull():

            scaled = cover.scaled(
                self.cover.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )

            self.cover.setPixmap(
                scaled
            )

        else:

            self.cover.setPixmap(
                QPixmap()
            )

            self.cover.setText(
                "BOOK"
            )

        self._bookmarks = (
            self.load_bookmarks()
        )

        self.update_bookmark_button()

        try:

            file_path = (
                self.row_value(
                    book,
                    "file_path",
                )
                or self.row_value(
                    book,
                    "epub_path",
                )
            )

            self.index_epub_images(
                file_path
            )

            self.chapters = list(
                get_chapters(
                    file_path
                )
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "EPUB reader error",
                (
                    "Could not open this EPUB."
                    "\n\n"
                    f"{error}"
                ),
            )

            self.update_navigation()

            return

        self.populate_toc()

        if not self.chapters:

            self.reader.setHtml(
                (
                    "<h2>"
                    "No readable chapters found."
                    "</h2>"
                )
            )

            self.update_navigation()

            return

        progress = get_progress(
            book[
                "id"
            ]
        )

        try:

            saved_chapter = int(
                self.row_value(
                    progress,
                    "chapter_index",
                    0,
                )
            )

            saved_position = float(
                self.row_value(
                    progress,
                    "position",
                    0.0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            saved_chapter = 0

            saved_position = 0.0

        self.current_chapter = max(
            0,
            min(
                saved_chapter,
                len(
                    self.chapters
                )
                - 1,
            ),
        )

        self.display_chapter(
            position=max(
                0.0,
                min(
                    saved_position,
                    1.0,
                ),
            ),
            save_after=False,
        )

    # ========================================================
    # POPULATE TABLE OF CONTENTS
    # ========================================================

    def populate_toc(
        self,
    ):

        self.toc_list.blockSignals(
            True
        )

        self.toc_list.clear()

        for (
            index,
            chapter,
        ) in enumerate(
            self.chapters
        ):

            title = (
                self.row_value(
                    chapter,
                    "title",
                )
                or (
                    f"Chapter "
                    f"{index + 1}"
                )
            )

            self.toc_list.addItem(
                QListWidgetItem(
                    str(
                        title
                    )
                )
            )

        self.toc_list.blockSignals(
            False
        )

        self.refresh_toc_bookmarks()

    # ========================================================
    # DISPLAY CHAPTER
    # ========================================================

    def display_chapter(
        self,
        position=0.0,
        save_after=True,
    ):

        if not self.chapters:

            return

        self._render_generation += 1

        generation = (
            self._render_generation
        )

        self.is_restoring_scroll = True
        self._pending_chapter_position = position
        self._pending_chapter_save = save_after

        chapter = (
            self.chapters[
                self.current_chapter
            ]
        )

        title = str(
            self.row_value(
                chapter,
                "title",
            )
            or (
                f"Chapter "
                f"{self.current_chapter + 1}"
            )
        )

        self.chapter_number.setText(
            (
                f"Chapter "
                f"{self.current_chapter + 1}"
            )
        )

        self.chapter_title.setText(
            title
        )

        html = (
            self.prepare_chapter_html(
                self.row_value(
                    chapter,
                    "html",
                    "",
                )
            )
        )

        self.reader.setHtml(
            html
        )

        self.toc_list.blockSignals(
            True
        )

        self.toc_list.setCurrentRow(
            self.current_chapter
        )

        self.toc_list.blockSignals(
            False
        )

        self.chapter_label.setText(
            (
                f"Chapter "
                f"{self.current_chapter + 1} "
                f"of {len(self.chapters)}"
            )
        )

        self.update_navigation()

        self.update_bookmark_button()

        QTimer.singleShot(
            0,
            lambda: self.finish_chapter_display(
                generation,
                position,
                save_after,
            ),
        )

    # ========================================================
    # FINISH CHAPTER DISPLAY
    # ========================================================

    def finish_chapter_display(
        self,
        generation,
        position,
        save_after,
    ):

        if (
            generation
            != self._render_generation
            or not self.chapters
        ):

            return

        bar = (
            self.reader.verticalScrollBar()
        )

        # The document can already have its final height while QTextEdit's
        # scrollbar still has the pre-scrollbar-width layout. Wait for its
        # rangeChanged notification instead of saving an incorrect fraction.
        height = self.reader.document().size().height()
        maximum = max(0, math.ceil(height) - self.reader.viewport().height())
        if abs(bar.maximum() - maximum) > 1:
            return

        bar.setValue(
            round(
                bar.maximum()
                * max(
                    0.0,
                    min(
                        1.0,
                        position,
                    ),
                )
            )
        )

        self.is_restoring_scroll = False
        self._pending_chapter_position = None
        self._pending_chapter_save = False

        self.update_progress_bar()

        if save_after:

            self.save_current_progress()

    # ========================================================
    # CURRENT SCROLL POSITION
    # ========================================================

    def on_document_range_changed(self, _minimum, _maximum):
        if self.is_restoring_scroll and self._pending_chapter_position is not None:
            generation = self._render_generation
            position = self._pending_chapter_position
            save_after = self._pending_chapter_save
            QTimer.singleShot(
                0,
                lambda: self.finish_chapter_display(generation, position, save_after),
            )

    def get_current_scroll_position(
        self,
    ):

        bar = (
            self.reader.verticalScrollBar()
        )

        if bar.maximum():

            return (
                bar.value()
                / bar.maximum()
            )

        return 0.0

    # ========================================================
    # UPDATE PROGRESS BAR
    # ========================================================

    def update_progress_bar(
        self,
    ):

        if not self.chapters:

            self.percent_label.setText(
                "0.0%"
            )

            self.page_label.setText(
                "Position 1 / 1"
            )

            if not self._changing_slider:

                self.progress_slider.setValue(
                    0
                )

            return

        fraction = (
            self.get_current_scroll_position()
        )

        overall = (
            (
                self.current_chapter
                + fraction
            )
            / len(
                self.chapters
            )
        )

        bar = (
            self.reader.verticalScrollBar()
        )

        view_height = max(
            1,
            self.reader.viewport().height(),
        )

        pages = max(
            1,
            math.ceil(
                (
                    bar.maximum()
                    + view_height
                )
                / view_height
            ),
        )

        current_page = min(
            pages,
            (
                1
                + int(
                    bar.value()
                    / view_height
                )
            ),
        )

        if (
            self.progress_mode
            == "percentage"
        ):

            self.percent_label.setText(
                f"{overall * 100:.1f}%"
            )

        else:

            self.percent_label.setText(
                (
                    f"{self.current_chapter + 1} "
                    f"/ {len(self.chapters)}"
                )
            )

        self.page_label.setText(
            (
                f"Position "
                f"{current_page} "
                f"/ {pages}"
            )
        )

        if not self._changing_slider:

            self.progress_slider.setValue(
                round(
                    overall
                    * 1000
                )
            )

    # ========================================================
    # SCROLL CHANGED
    # ========================================================

    def on_scroll_changed(
        self,
        _value,
    ):

        if (
            self.is_restoring_scroll
            or not self.chapters
        ):

            return

        self.update_navigation()

        self.scroll_save_timer.start()

    # ========================================================
    # SAVE CURRENT PROGRESS
    # ========================================================

    def save_current_progress(
        self,
    ):

        if (
            self.book is None
            or not self.chapters
        ):

            return

        state = (
            self.book["id"], self.current_chapter,
            self._pending_chapter_position
            if self.is_restoring_scroll
            else self.get_current_scroll_position(),
        )
        if state == self._last_saved_progress:
            return
        save_progress(book_id=state[0], chapter_index=state[1], position=state[2])
        # Only remember successful saves; failures must remain retryable.
        self._last_saved_progress = state

    # ========================================================
    # RELEASE INACTIVE BOOK
    # ========================================================

    def release_book_content(self):
        """Discard only this book's content, after its final progress save."""
        if self.book is None:
            return
        self._render_generation += 1
        self.book = None
        self.chapters = []
        self.current_chapter = 0
        self._bookmarks = {}
        self._epub_file = None
        self._epub_images.clear()
        self._epub_image_index.clear()
        self._decoded_images.clear()
        self._image_serial = 0
        self._last_saved_progress = None
        self._pending_chapter_position = None
        self._pending_chapter_save = False
        self.is_restoring_scroll = False
        blocked = self.toc_list.blockSignals(True)
        self.toc_list.clear()
        self.toc_list.blockSignals(blocked)
        self.cover.clear()

        # QTextDocument also caches image resources; clearing HTML alone
        # does not reliably release those resources between books.
        old_document = self.reader.document()
        document = QTextDocument(self.reader)
        document.setDefaultFont(old_document.defaultFont())
        document.setDefaultStyleSheet(old_document.defaultStyleSheet())
        document.setDocumentMargin(old_document.documentMargin())
        old_document.setParent(None)
        self.reader.setDocument(document)
        old_document.deleteLater()
        self.scroll_save_timer.stop()
        self.style_timer.stop()

    # ========================================================
    # BEGIN SEEK
    # ========================================================

    def begin_seek(
        self,
    ):

        self._changing_slider = True

    # ========================================================
    # END SEEK
    # ========================================================

    def end_seek(
        self,
    ):

        self._changing_slider = False

        if not self.chapters:

            return

        self.save_current_progress()

        point = (
            self.progress_slider.value()
            / 1000
            * len(
                self.chapters
            )
        )

        chapter = min(
            len(
                self.chapters
            )
            - 1,
            int(
                point
            ),
        )

        position = (
            1.0
            if (
                self.progress_slider.value()
                == 1000
            )
            else (
                point
                - chapter
            )
        )

        if chapter != self.current_chapter:

            self.current_chapter = (
                chapter
            )

            self.display_chapter(
                position=position
            )

        else:

            self.reader.verticalScrollBar().setValue(
                round(
                    self.reader
                    .verticalScrollBar()
                    .maximum()
                    * position
                )
            )

            self.update_progress_bar()

            self.save_current_progress()

    # ========================================================
    # JUMP TO CHAPTER
    # ========================================================

    def jump_to_chapter(
        self,
        index,
    ):

        if (
            index < 0
            or index >= len(
                self.chapters
            )
            or index
            == self.current_chapter
        ):

            return

        self.save_current_progress()

        self.current_chapter = (
            index
        )

        self.display_chapter(
            position=(
                self._bookmarks.get(
                    index,
                    0.0,
                )
            )
        )

    # ========================================================
    # PREVIOUS CHAPTER
    # ========================================================

    def previous_chapter(
        self,
    ):

        if self.current_chapter <= 0:

            return

        self.save_current_progress()

        self.current_chapter -= 1

        self.display_chapter()

    # ========================================================
    # NEXT CHAPTER
    # ========================================================

    def next_chapter(
        self,
    ):

        if (
            self.current_chapter
            >= len(
                self.chapters
            )
            - 1
        ):

            return

        self.save_current_progress()

        self.current_chapter += 1

        self.display_chapter()

    # ========================================================
    # PREVIOUS PAGE
    # ========================================================

    def previous_page(
        self,
    ):

        if not self.chapters:

            return

        scrollbar = (
            self.reader.verticalScrollBar()
        )

        if scrollbar.value() > 0:

            scrollbar.setValue(
                max(
                    0,
                    (
                        scrollbar.value()
                        - max(
                            1,
                            (
                                self.reader
                                .viewport()
                                .height()
                                - 55
                            ),
                        )
                    ),
                )
            )

        elif self.current_chapter > 0:

            self.save_current_progress()

            self.current_chapter -= 1

            self.display_chapter(
                position=1.0
            )

        self.update_navigation()

    # ========================================================
    # NEXT PAGE
    # ========================================================

    def next_page(
        self,
    ):

        if not self.chapters:

            return

        scrollbar = (
            self.reader.verticalScrollBar()
        )

        if (
            scrollbar.value()
            < scrollbar.maximum()
        ):

            scrollbar.setValue(
                min(
                    scrollbar.maximum(),
                    (
                        scrollbar.value()
                        + max(
                            1,
                            (
                                self.reader
                                .viewport()
                                .height()
                                - 55
                            ),
                        )
                    ),
                )
            )

        elif (
            self.current_chapter
            < len(
                self.chapters
            )
            - 1
        ):

            self.save_current_progress()

            self.current_chapter += 1

            self.display_chapter(
                position=0.0
            )

        self.update_navigation()

    # ========================================================
    # UPDATE NAVIGATION
    # ========================================================

    def update_navigation(
        self,
    ):

        bar = (
            self.reader.verticalScrollBar()
        )

        self.previous_button.setEnabled(
            bool(
                self.chapters
            )
            and (
                self.current_chapter > 0
                or bar.value() > 0
            )
        )

        self.next_button.setEnabled(
            bool(
                self.chapters
            )
            and (
                self.current_chapter
                < len(
                    self.chapters
                )
                - 1
                or bar.value()
                < bar.maximum()
            )
        )

        self.update_progress_bar()

    # ========================================================
    # QUEUE PANEL WIDTH SAVE
    # ========================================================

    def queue_panel_width_save(
        self,
        _position,
        _index,
    ):

        if self._splitter_ready:

            self._splitter_store_timer.start()

    # ========================================================
    # SAVE PANEL WIDTHS
    # ========================================================

    def save_panel_widths(
        self,
    ):

        if not self._splitter_ready:

            return

        if (
            self._toc_open
            and self.toc_panel.isVisible()
            and self.toc_panel.width()
            >= 190
        ):

            width = (
                self.toc_panel.width()
            )

            if width != self._toc_width:

                self._toc_width = (
                    width
                )

                set_setting(
                    "epub_toc_width",
                    width,
                )

        if (
            self._settings_open
            and self.settings_panel.isVisible()
            and self.settings_panel.width()
            >= 420
        ):

            width = (
                self.settings_panel.width()
            )

            if (
                width
                != self._settings_width
            ):

                self._settings_width = (
                    width
                )

                set_setting(
                    "epub_settings_width",
                    width,
                )

    # ========================================================
    # RESTORE PANEL WIDTHS
    # ========================================================

    def restore_panel_widths(
        self,
    ):

        total = (
            self.body_splitter.width()
        )

        if total <= 0:

            return

        left = (
            self._toc_width
            if self._toc_open
            else 0
        )

        right = (
            self._settings_width
            if self._settings_open
            else 0
        )

        center = max(
            300,
            (
                total
                - left
                - right
                - (
                    self.body_splitter.handleWidth()
                    * 2
                )
            ),
        )

        self.body_splitter.setSizes(
            [
                left,
                center,
                right,
            ]
        )

        self._splitter_ready = True

    # ========================================================
    # TOGGLE TABLE OF CONTENTS
    # ========================================================

    def toggle_toc(
        self,
    ):

        self._splitter_store_timer.stop()

        self.save_panel_widths()

        self._toc_open = (
            not self._toc_open
        )

        self.toc_panel.setVisible(
            self._toc_open
        )

        self.toc_button.setToolTip(
            (
                "Hide chapters"
                if self._toc_open
                else "Show chapters"
            )
        )

        QTimer.singleShot(
            0,
            self.restore_panel_widths,
        )

    # ========================================================
    # TOGGLE SETTINGS
    # ========================================================

    def toggle_settings(
        self,
    ):

        self._splitter_store_timer.stop()

        self.save_panel_widths()

        self._settings_open = (
            not self._settings_open
        )

        self.settings_panel.setVisible(
            self._settings_open
        )

        QTimer.singleShot(
            0,
            self.restore_panel_widths,
        )

    # ========================================================
    # TOGGLE SEARCH
    # ========================================================

    def toggle_search(
        self,
    ):

        self._search_open = (
            not self._search_open
        )

        self.search_row.setVisible(
            self._search_open
        )

        if self._search_open:

            self.search_field.setFocus()

            self.search_field.selectAll()

        else:

            self.reader.setFocus()

    # ========================================================
    # FIND NEXT
    # ========================================================

    def find_next(
        self,
    ):

        phrase = (
            self.search_field
            .text()
            .strip()
        )

        if not phrase:

            return

        if not self.reader.find(
            phrase
        ):

            cursor = (
                self.reader.textCursor()
            )

            cursor.movePosition(
                QTextCursor.Start
            )

            self.reader.setTextCursor(
                cursor
            )

            self.reader.find(
                phrase
            )

    # ========================================================
    # BOOKMARK KEY
    # ========================================================

    def bookmark_key(
        self,
    ):

        if self.book is None:

            return None

        return (
            f"epub_bookmarks_"
            f"{self.book['id']}"
        )

    # ========================================================
    # LOAD BOOKMARKS
    # ========================================================

    def load_bookmarks(
        self,
    ):

        key = (
            self.bookmark_key()
        )

        if not key:

            return {}

        result = {}

        raw = get_setting(
            key,
            "",
        )

        if raw:

            try:

                data = json.loads(
                    str(
                        raw
                    )
                )

                if isinstance(
                    data,
                    dict,
                ):

                    for (
                        chapter,
                        fraction,
                    ) in data.items():

                        index = int(
                            chapter
                        )

                        position = float(
                            fraction
                        )

                        if (
                            index >= 0
                            and math.isfinite(
                                position
                            )
                        ):

                            result[
                                index
                            ] = max(
                                0.0,
                                min(
                                    1.0,
                                    position,
                                ),
                            )

            except (
                ValueError,
                TypeError,
                OverflowError,
                json.JSONDecodeError,
            ):

                result = {}

        if not result:

            legacy = get_setting(
                (
                    f"epub_bookmark_"
                    f"{self.book['id']}"
                ),
                "",
            )

            try:

                (
                    chapter,
                    position,
                ) = str(
                    legacy
                ).split(
                    ":",
                    1,
                )

                index = int(
                    chapter
                )

                fraction = float(
                    position
                )

                if (
                    index >= 0
                    and math.isfinite(
                        fraction
                    )
                ):

                    result[
                        index
                    ] = max(
                        0.0,
                        min(
                            1.0,
                            fraction,
                        ),
                    )

            except (
                ValueError,
                TypeError,
                OverflowError,
            ):

                pass

        return result

    # ========================================================
    # STORE BOOKMARKS
    # ========================================================

    def store_bookmarks(
        self,
    ):

        key = (
            self.bookmark_key()
        )

        if key:

            set_setting(
                key,
                json.dumps(
                    self._bookmarks,
                    separators=(
                        ",",
                        ":",
                    ),
                ),
            )

            set_setting(
                (
                    f"epub_bookmark_"
                    f"{self.book['id']}"
                ),
                "",
            )

    # ========================================================
    # TOGGLE BOOKMARK
    # ========================================================

    def toggle_bookmark(
        self,
    ):

        if (
            self.book is None
            or not self.chapters
        ):

            return

        if (
            self.current_chapter
            in self._bookmarks
        ):

            del self._bookmarks[
                self.current_chapter
            ]

        else:

            self._bookmarks[
                self.current_chapter
            ] = (
                self.get_current_scroll_position()
            )

        self.store_bookmarks()

        self.refresh_toc_bookmarks()

        self.update_bookmark_button()

    # ========================================================
    # READ BOOKMARK
    # ========================================================

    def _read_bookmark(
        self,
    ):

        if (
            self.current_chapter
            in self._bookmarks
        ):

            return (
                self.current_chapter,
                self._bookmarks[
                    self.current_chapter
                ],
            )

        if self._bookmarks:

            index = min(
                self._bookmarks
            )

            return (
                index,
                self._bookmarks[
                    index
                ],
            )

        return None

    # ========================================================
    # REFRESH TOC BOOKMARKS
    # ========================================================

    def refresh_toc_bookmarks(
        self,
    ):

        icon = reader_icon(
            "icons8-bookmark-50 (1).png",
            "icons8-bookmark-50.png",
        )

        for index in range(
            self.toc_list.count()
        ):

            item = (
                self.toc_list.item(
                    index
                )
            )

            chapter = (
                self.chapters[
                    index
                ]
            )

            title = str(
                self.row_value(
                    chapter,
                    "title",
                )
                or (
                    f"Chapter "
                    f"{index + 1}"
                )
            )

            if index in self._bookmarks:

                item.setText(
                    "★  "
                    + title
                )

                item.setIcon(
                    icon
                )

                item.setToolTip(
                    (
                        "Bookmarked — select to "
                        "jump to your saved position"
                    )
                )

            else:

                item.setText(
                    title
                )

                item.setIcon(
                    QIcon()
                )

                item.setToolTip(
                    ""
                )

    # ========================================================
    # UPDATE BOOKMARK BUTTON
    # ========================================================

    def update_bookmark_button(
        self,
    ):

        marked = (
            self.current_chapter
            in self._bookmarks
        )

        icon = reader_icon(
            (
                "icons8-bookmark-50 (1).png"
                if marked
                else "icons8-bookmark-50.png"
            )
        )

        if icon.isNull():

            self.bookmark_button.setText(
                "★"
                if marked
                else "☆"
            )

            self.bookmark_button.setIcon(
                QIcon()
            )

        else:

            use_button_icon(
                self.bookmark_button,
                icon,
            )

        self.bookmark_button.setToolTip(
            (
                "Remove bookmark from this chapter"
                if marked
                else (
                    "Bookmark this chapter "
                    "at current position"
                )
            )
        )

    # ========================================================
    # GO TO BOOKMARK
    # ========================================================

    def go_to_bookmark(
        self,
    ):

        saved = (
            self._read_bookmark()
        )

        if (
            saved is None
            or saved[
                0
            ]
            >= len(
                self.chapters
            )
        ):

            QMessageBox.information(
                self,
                "Bookmark",
                (
                    "No saved bookmark "
                    "for this book."
                ),
            )

            return

        self.save_current_progress()

        self.current_chapter = (
            saved[
                0
            ]
        )

        self.display_chapter(
            position=saved[
                1
            ],
            save_after=False,
        )

    # ========================================================
    # SETUP SHORTCUTS
    # ========================================================

    def setup_shortcuts(
        self,
    ):

        self.find_shortcut = QShortcut(
            QKeySequence(
                "Ctrl+F"
            ),
            self,
        )

        self.find_shortcut.activated.connect(
            self.toggle_search
        )

        self.toc_shortcut = QShortcut(
            QKeySequence(
                "Ctrl+T"
            ),
            self,
        )

        self.toc_shortcut.activated.connect(
            self.toggle_toc
        )

        self.fullscreen_shortcut = QShortcut(
            QKeySequence(
                "F11"
            ),
            self,
        )

        self.fullscreen_shortcut.activated.connect(
            lambda:
            self.set_reader_fullscreen(
                not self._fullscreen_by_reader
            )
        )

        self.next_chapter_shortcut = QShortcut(
            QKeySequence(
                "Ctrl+Right"
            ),
            self,
        )

        self.next_chapter_shortcut.activated.connect(
            self.next_chapter
        )

        self.prev_chapter_shortcut = QShortcut(
            QKeySequence(
                "Ctrl+Left"
            ),
            self,
        )

        self.prev_chapter_shortcut.activated.connect(
            self.previous_chapter
        )

        self.apply_arrow_shortcuts()

    # ========================================================
    # ARROW SHORTCUTS
    # ========================================================

    def apply_arrow_shortcuts(
        self,
    ):

        self.reader.setFocusPolicy(
            Qt.StrongFocus
        )

    # ========================================================
    # EVENT FILTER
    # ========================================================

    def eventFilter(
        self,
        watched,
        event,
    ):

        if (
            hasattr(
                self,
                "reader",
            )
            and watched in (
                self.reader,
                self.reader.viewport(),
            )
        ):

            if (
                not self.arrow_chapters
                or not self.chapters
            ):

                return super().eventFilter(
                    watched,
                    event,
                )

            if (
                event.type()
                == QEvent.KeyPress
                and event.modifiers()
                == Qt.NoModifier
            ):

                if (
                    event.key()
                    == Qt.Key_Right
                ):

                    self.next_page()

                    return True

                if (
                    event.key()
                    == Qt.Key_Left
                ):

                    self.previous_page()

                    return True

            if (
                watched
                is self.reader.viewport()
            ):

                if (
                    event.type()
                    == QEvent.MouseButtonPress
                    and event.button()
                    == Qt.LeftButton
                ):

                    self._gesture_origin = (
                        event.position()
                    )

                elif (
                    event.type()
                    == QEvent.MouseButtonRelease
                    and event.button()
                    == Qt.LeftButton
                ):

                    start = (
                        self._gesture_origin
                    )

                    self._gesture_origin = None

                    if start is not None:

                        dx = (
                            event.position().x()
                            - start.x()
                        )

                        dy = (
                            event.position().y()
                            - start.y()
                        )

                        if (
                            abs(
                                dx
                            )
                            >= 85
                            and abs(
                                dx
                            )
                            > abs(
                                dy
                            )
                            * 1.6
                        ):

                            QTimer.singleShot(
                                0,
                                (
                                    self.next_page
                                    if dx < 0
                                    else self.previous_page
                                ),
                            )

                            return True

                elif (
                    event.type()
                    == QEvent.Wheel
                    and not event.modifiers()
                ):

                    dx = (
                        event
                        .angleDelta()
                        .x()
                    )

                    if dx == 0:

                        dx = (
                            event
                            .pixelDelta()
                            .x()
                        )

                    if (
                        abs(
                            dx
                        )
                        >= 40
                        and (
                            time.monotonic()
                            - self._last_horizontal_action
                        )
                        > 0.28
                    ):

                        self._last_horizontal_action = (
                            time.monotonic()
                        )

                        QTimer.singleShot(
                            0,
                            (
                                self.next_page
                                if dx < 0
                                else self.previous_page
                            ),
                        )

                        return True

        return super().eventFilter(
            watched,
            event,
        )

    # ========================================================
    # FULLSCREEN
    # ========================================================

    def set_reader_fullscreen(
        self,
        enabled,
    ):

        window = (
            self.window()
        )

        if (
            enabled
            and not window.isFullScreen()
        ):

            window.showFullScreen()

            self._fullscreen_by_reader = True

        elif (
            not enabled
            and self._fullscreen_by_reader
        ):

            window.showNormal()

            self._fullscreen_by_reader = False

        self.fullscreen_switch.blockSignals(
            True
        )

        self.fullscreen_switch.setChecked(
            self._fullscreen_by_reader
        )

        self.fullscreen_switch.blockSignals(
            False
        )

    # ========================================================
    # KEEP SCREEN ON
    # ========================================================

    def apply_keep_screen_on(
        self,
        enabled,
    ):

        if sys.platform != "win32":

            return

        try:

            import ctypes

            flags = (
                0x80000003
                if enabled
                else 0x80000000
            )

            result = (
                ctypes.windll
                .kernel32
                .SetThreadExecutionState(
                    flags
                )
            )

            self._prevent_sleep_active = bool(
                enabled
                and result
            )

        except (
            OSError,
            AttributeError,
        ):

            self._prevent_sleep_active = False

    # ========================================================
    # RELOAD SETTINGS
    # ========================================================

    def reload_settings(
        self,
    ):

        self.style_timer.stop()

        self.read_saved_style()

        self.apply_local_style()

        self.apply_reader_appearance()

        self._loading_controls = True

        self.font_combo.setCurrentText(
            self.font_family
        )

        self.font_slider.setValue(
            self.font_size
        )

        self.progress_switch.setChecked(
            self.show_progress
        )

        self._loading_controls = False

        self.progress_slider.setVisible(
            self.show_progress
        )

        self.apply_arrow_shortcuts()

        if self.chapters:

            self.display_chapter(
                position=(
                    self.get_current_scroll_position()
                ),
                save_after=False,
            )

    # ========================================================
    # GO BACK
    # ========================================================

    def go_back(
        self,
    ):

        self.style_timer.stop()

        self.scroll_save_timer.stop()

        self.save_current_progress()

        if self._fullscreen_by_reader:

            self.set_reader_fullscreen(
                False
            )

        self.back_requested.emit()

    # ========================================================
    # SHOW EVENT
    # ========================================================

    def showEvent(
        self,
        event,
    ):

        super().showEvent(
            event
        )

        QTimer.singleShot(
            0,
            self.restore_panel_widths,
        )

        main = (
            self.window()
        )

        if hasattr(
            main,
            "sidebar",
        ):

            main.sidebar.hide()

        self.apply_keep_screen_on(
            self.keep_screen_on
        )

    # ========================================================
    # HIDE EVENT
    # ========================================================

    def hideEvent(
        self,
        event,
    ):

        self._splitter_store_timer.stop()

        self.save_panel_widths()

        self.style_timer.stop()

        self.scroll_save_timer.stop()

        self.save_current_progress()

        self.apply_keep_screen_on(
            False
        )

        self.release_book_content()

        if self._fullscreen_by_reader:

            self.set_reader_fullscreen(
                False
            )

        main = (
            self.window()
        )

        if hasattr(
            main,
            "sidebar",
        ):

            main.sidebar.show()

        super().hideEvent(
            event
        )
