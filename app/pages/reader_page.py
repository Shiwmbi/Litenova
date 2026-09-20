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
from PySide6.QtGui import QFont, QPixmap, QPainter, QTextCursor, QKeySequence, QShortcut, QImage, QTextDocument, QIcon
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QScrollArea, QTextBrowser, QListWidget,
    QComboBox, QSlider, QLineEdit, QCheckBox, QButtonGroup,
    QMessageBox, QSplitter, QListWidgetItem,
)

from app.services.epub_service import get_chapters
from app.services.path_service import resource_path
from app.services.appearance_service import resolved_colors
from app.services.progress_service import get_progress, save_progress
from app.services.settings_service import (
    get_reader_font_size, set_reader_font_size, get_setting, set_setting,
)


DARK = "#12141a"
CARD = "#191b23"
TEXT = "#e8e8f5"
MUTED = "#a9acc1"
ACCENT = "#aba8f0"
FONTS = ("Georgia", "Noto Serif", "Times New Roman", "Arial", "Verdana")


# Restore only EPUB reader appearance/behavior preferences.  Bookmarks,
# reading positions, panel widths and the app's Appearance palette are NOT reset.
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


def reader_icon(*filenames):
    """Load a PNG from resources/icons; safely fall back when it is missing."""
    for name in filenames:
        path = resource_path(f"resources/icons/{name}")
        if path.is_file():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
    return QIcon()


def use_button_icon(button, icon, size=20):
    """Replace a text glyph only if a usable PNG icon exists."""
    if icon.isNull():
        return
    button.setText("")
    button.setIcon(icon)
    button.setIconSize(QSize(size, size))



def setting_int(key, default, minimum, maximum):
    try:
        value = int(get_setting(key, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def setting_bool(key, default=True):
    return str(get_setting(key, default)).casefold() in ("true", "1", "yes", "on")


def row_label(name, detail=""):
    holder = QWidget()
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    caption = QLabel(name, holder)
    caption.setObjectName("readerRowTitle")
    layout.addWidget(caption)
    if detail:
        desc = QLabel(detail, holder)
        desc.setObjectName("readerRowDetail")
        desc.setWordWrap(True)
        layout.addWidget(desc)
    return holder


class Toggle(QCheckBox):
    """A real checkable widget, painted as a compact lavender switch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(43, 25)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        from PySide6.QtGui import QColor
        painter.setBrush(QColor("#63659c" if self.isChecked() else "#393c4c"))
        painter.drawRoundedRect(0, 1, 43, 23, 12, 12)
        painter.setBrush(QColor("#d8d6ff" if self.isChecked() else "#a4a7ba"))
        painter.drawEllipse(22 if self.isChecked() else 3, 4, 17, 17)
        painter.end()


class EpubTextBrowser(QTextBrowser):
    """Provide EPUB ZIP illustrations to Qt's HTML rendering engine."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_provider = None

    def loadResource(self, kind, url):
        if (
            kind == QTextDocument.ImageResource
            and url.scheme() == "litenova-image"
            and self.image_provider is not None
        ):
            return self.image_provider(url.path().lstrip("/"))
        return super().loadResource(kind, url)


class ReaderPage(QWidget):
    """Compatible with MainWindow: open_book, reload_settings, back_requested."""

    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self.book = None
        self.chapters = []
        self.current_chapter = 0
        self.is_restoring_scroll = False
        self._render_generation = 0
        self._loading_controls = False
        self._toc_open = False
        self._settings_open = True
        self._fullscreen_by_reader = False
        self._prevent_sleep_active = False
        self._changing_slider = False
        self._search_open = False
        # Each book can have one saved reading position per chapter.
        self._bookmarks = {}
        # User-adjustable splitter widths are saved across launches.
        self._toc_width = setting_int("epub_toc_width", 275, 190, 490)
        self._settings_width = setting_int("epub_settings_width", 410, 350, 570)
        self._splitter_ready = False
        self._splitter_store_timer = QTimer(self)
        self._splitter_store_timer.setSingleShot(True)
        self._splitter_store_timer.setInterval(350)
        self._splitter_store_timer.timeout.connect(self.save_panel_widths)
        self._epub_file = None
        self._epub_images = {}
        self._epub_image_index = {}
        self._decoded_images = {}
        self._image_serial = 0
        self._gesture_origin = None
        self._last_horizontal_action = 0.0
        self.read_saved_style()

        self.scroll_save_timer = QTimer(self)
        self.scroll_save_timer.setSingleShot(True)
        self.scroll_save_timer.setInterval(600)
        self.scroll_save_timer.timeout.connect(self.save_current_progress)

        self.style_timer = QTimer(self)
        self.style_timer.setSingleShot(True)
        self.style_timer.setInterval(170)
        self.style_timer.timeout.connect(self.refresh_chapter_style)

        self.build_ui()
        self.setup_shortcuts()
        self.apply_reader_appearance()

    # ------------------------------------------------------------
    # Settings: existing Settings page uses reader_font_size / family.
    # Other keys only affect this EPUB reader and persist in SQLite.
    # ------------------------------------------------------------
    def read_saved_style(self):
        self.font_size = get_reader_font_size()
        font = str(get_setting("reader_font_family", "Georgia"))
        self.font_family = font if font in FONTS else "Georgia"
        self.weight = setting_int("epub_weight", 2, 0, 3)
        self.italic = setting_bool("epub_italic", False)
        self.letter_spacing = setting_int("epub_letter_spacing", 0, 0, 6)
        self.line_height = setting_int("epub_line_height", 170, 120, 240)
        self.paragraph_spacing = setting_int("epub_paragraph_spacing", 10, 0, 30)
        self.paragraph_indent = setting_int("epub_paragraph_indent", 0, 0, 60)
        self.text_align = str(get_setting("epub_text_align", "left"))
        if self.text_align not in ("left", "center", "right", "justify"):
            self.text_align = "left"
        self.side_margin = setting_int("epub_side_margin", 65, 12, 120)
        self.vertical_margin = setting_int("epub_vertical_margin", 40, 8, 110)
        self.show_images = setting_bool("epub_show_images", True)
        self.show_captions = setting_bool("epub_show_captions", True)
        self.image_size = setting_int("epub_image_size", 100, 40, 100)
        self.chapter_align = str(get_setting("epub_chapter_align", "center"))
        if self.chapter_align not in ("left", "center", "right"):
            self.chapter_align = "center"
        self.arrow_chapters = setting_bool("epub_arrow_chapters", False)
        self.progress_mode = str(get_setting("epub_progress_mode", "percentage"))
        if self.progress_mode not in ("percentage", "quantity"):
            self.progress_mode = "percentage"
        self.show_progress = setting_bool("reader_show_progress_bar", True)
        self.keep_screen_on = setting_bool("epub_keep_screen_on", False)

    # ------------------------------------------------------------
    # Interface. All controls are children of the reader page.
    # ------------------------------------------------------------
    def button(self, label, action, width=34, tip=""):
        b = QPushButton(label, self)
        b.setObjectName("readerIconButton")
        b.setFixedHeight(34)
        if width:
            b.setFixedWidth(width)
        b.setCursor(Qt.PointingHandCursor)
        if tip:
            b.setToolTip(tip)
        b.clicked.connect(action)
        return b

    def section(self, layout, heading):
        line = QLabel(heading, self.settings_content)
        line.setObjectName("readerSectionTitle")
        layout.addWidget(line)
        return line

    def option_row(self, layout, title, control, detail=""):
        line = QWidget(self.settings_content)
        row = QHBoxLayout(line)
        row.setContentsMargins(0, 5, 0, 5)
        row.setSpacing(12)
        row.addWidget(row_label(title, detail), 1)
        row.addWidget(control, 0, Qt.AlignVCenter)
        layout.addWidget(line)
        return line

    def slider_control(self, low, high, initial, suffix="", width=130):
        frame = QWidget(self.settings_content)
        line = QHBoxLayout(frame)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(9)
        slider = QSlider(Qt.Horizontal, frame)
        slider.setRange(low, high)
        slider.setValue(initial)
        slider.setFixedWidth(width)
        number = QLabel(f"{initial}{suffix}", frame)
        number.setObjectName("readerSettingValue")
        number.setFixedWidth(42)
        number.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        line.addWidget(slider)
        line.addWidget(number)
        slider.valueChanged.connect(lambda n: number.setText(f"{n}{suffix}"))
        return frame, slider

    def segmented(self, options, selected, changed, setting_key=None):
        holder = QWidget(self.settings_content)
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(0)
        group = QButtonGroup(holder)
        group.setExclusive(True)
        if setting_key is not None:
            self._reader_segment_controls[setting_key] = {}
        for option in options:
            # (caption, value) remains supported for all existing segments.
            # (caption, value, png_filename) adds a resource icon.
            caption, value = option[:2]
            icon_name = option[2] if len(option) > 2 else None
            b = QPushButton(caption, holder)
            if icon_name:
                icon = reader_icon(icon_name)
                if not icon.isNull():
                    b.setText("")
                    b.setIcon(icon)
                    b.setIconSize(QSize(16, 16))
                b.setToolTip(caption)
                b.setAccessibleName(f"Text alignment: {caption}")
            b.setCheckable(True)
            b.setChecked(value == selected)
            b.setObjectName("readerSegment")
            b.setMinimumHeight(27)
            group.addButton(b)
            if setting_key is not None:
                self._reader_segment_controls[setting_key][value] = b
            line.addWidget(b)
            b.clicked.connect(lambda _checked=False, v=value: changed(v))
        return holder

    def build_ui(self):
        self.setObjectName("newReaderPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Full-width book / chapter header.
        header = QFrame(self)
        header.setObjectName("readerHeader")
        bar = QHBoxLayout(header)
        bar.setContentsMargins(15, 8, 13, 8)
        bar.setSpacing(12)
        self.back_button = self.button("‹", self.go_back, 30, "Back to Library or History")
        bar.addWidget(self.back_button)
        self.cover = QLabel(header)
        self.cover.setFixedSize(38, 52)
        self.cover.setObjectName("readerHeaderCover")
        self.cover.setAlignment(Qt.AlignCenter)
        bar.addWidget(self.cover)
        book_titles = QVBoxLayout()
        book_titles.setSpacing(2)
        self.book_title = QLabel("Litenova Reader", header)
        self.book_title.setObjectName("readerHeaderTitle")
        self.book_title.setMaximumWidth(270)
        self.author = QLabel("", header)
        self.author.setObjectName("readerHeaderSub")
        book_titles.addWidget(self.book_title)
        book_titles.addWidget(self.author)
        bar.addLayout(book_titles)
        separator = QFrame(header)
        separator.setObjectName("readerHeaderDivider")
        separator.setFixedSize(1, 36)
        bar.addWidget(separator)
        chapter_titles = QVBoxLayout()
        chapter_titles.setSpacing(2)
        self.chapter_number = QLabel("Chapter 1", header)
        self.chapter_number.setObjectName("readerHeaderTitle")
        self.chapter_title = QLabel("Open a book to begin", header)
        self.chapter_title.setObjectName("readerHeaderSub")
        chapter_titles.addWidget(self.chapter_number)
        chapter_titles.addWidget(self.chapter_title)
        bar.addLayout(chapter_titles, 1)
        self.search_button = self.button("⌕", self.toggle_search, 34, "Find text in this chapter (Ctrl+F)")
        self.toc_button = self.button("☷", self.toggle_toc, 34, "Table of contents")
        self.bookmark_button = self.button("☆", self.toggle_bookmark, 34, "Bookmark this position")
        self.options_button = self.button("⋮", self.toggle_settings, 34, "Show or hide Reader Settings")

        # Existing Litenova icons + the seven new PNGs supplied by the user.
        use_button_icon(self.search_button, reader_icon("search.png", "search_input_icon.png"))
        use_button_icon(self.toc_button, reader_icon("icons8-table-100.png"))
        use_button_icon(self.bookmark_button, reader_icon("icons8-bookmark-50.png"))
        use_button_icon(self.options_button, reader_icon("more_options.png", "item_options.png"))
        for widget in (self.search_button, self.toc_button, self.bookmark_button, self.options_button):
            bar.addWidget(widget)
        root.addWidget(header)

        # Search is embedded, never a floating window.
        self.search_row = QWidget(self)
        search_line = QHBoxLayout(self.search_row)
        search_line.setContentsMargins(20, 5, 20, 5)
        self.search_field = QLineEdit(self.search_row)
        self.search_field.setPlaceholderText("Find in current chapter...")
        self.search_field.returnPressed.connect(self.find_next)
        search_line.addWidget(self.search_field, 1)
        search_line.addWidget(self.button("Find next", self.find_next, 90))
        search_line.addWidget(self.button("✕", self.toggle_search, 30))
        root.addWidget(self.search_row)
        self.search_row.hide()

        # Resize either side panel by dragging its vertical separator.
        # QSplitter retains child widgets (no detached / floating windows).
        body = QSplitter(Qt.Horizontal, self)
        self.body_splitter = body
        body.setObjectName("readerBodySplitter")
        body.setChildrenCollapsible(False)
        body.setHandleWidth(7)

        self.toc_panel = QFrame(body)
        self.toc_panel.setObjectName("readerTocPanel")
        self.toc_panel.setMinimumWidth(190)
        self.toc_panel.setMaximumWidth(490)
        toc_layout = QVBoxLayout(self.toc_panel)
        toc_layout.setContentsMargins(12, 16, 12, 12)
        # Use the new list/justify artwork alongside the chapter list title.
        toc_header = QHBoxLayout()
        toc_icon = reader_icon("icons8-align-justify-50.png")
        if not toc_icon.isNull():
            toc_symbol = QLabel(self.toc_panel)
            toc_symbol.setPixmap(toc_icon.pixmap(QSize(19, 19)))
            toc_symbol.setFixedSize(21, 21)
            toc_header.addWidget(toc_symbol)
        toc_label = QLabel("Table of Contents", self.toc_panel)
        toc_label.setObjectName("readerSectionTitle")
        toc_header.addWidget(toc_label, 1)
        toc_layout.addLayout(toc_header)
        self.toc_list = QListWidget(self.toc_panel)
        self.toc_list.currentRowChanged.connect(self.jump_to_chapter)
        toc_layout.addWidget(self.toc_list, 1)
        body.addWidget(self.toc_panel)
        self.toc_panel.hide()

        self.reader = EpubTextBrowser(body)
        self.reader.image_provider = self.load_epub_image
        self.reader.installEventFilter(self)
        self.reader.viewport().installEventFilter(self)
        self.reader.setObjectName("readerCanvas")
        self.reader.setOpenExternalLinks(False)
        self.reader.setFrameShape(QFrame.NoFrame)
        self.reader.setReadOnly(True)
        self.reader.setMinimumWidth(240)
        self.reader.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)
        body.addWidget(self.reader)

        # Right-side panel, modeled after the reference screenshot.
        self.settings_panel = QScrollArea(body)
        self.settings_panel.setObjectName("readerSettingsPanel")
        self.settings_panel.setWidgetResizable(True)
        self.settings_panel.setFrameShape(QFrame.NoFrame)
        self.settings_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.settings_panel.setMinimumWidth(350)
        self.settings_panel.setMaximumWidth(570)
        self.settings_content = QWidget()
        self.settings_content.setObjectName("readerSettingsContent")
        # Keep references so Reset can update the existing controls in-place.
        # No widgets are rebuilt and the reader's scroll position is retained.
        self._reader_slider_controls = {}
        self._reader_segment_controls = {}
        side = QVBoxLayout(self.settings_content)
        side.setContentsMargins(20, 18, 20, 22)
        side.setSpacing(13)
        self.section(side, "Reader Settings")
        self.section(side, "Font")

        self.font_combo = QComboBox(self.settings_content)
        for name in FONTS:
            self.font_combo.addItem(name)
        self.font_combo.setCurrentText(self.font_family)
        self.font_combo.currentTextChanged.connect(lambda name: self.update_style("reader_font_family", name))
        self.option_row(side, "Font family", self.font_combo)
        self.option_row(side, "Font thickness", self.segmented(
            (("Thin", 0), ("Light", 1), ("Normal", 2), ("Medium", 3)),
            self.weight, lambda n: self.update_style("epub_weight", n), "epub_weight"))
        self.option_row(side, "Font style", self.segmented(
            (("Normal", False), ("Italic", True)),
            self.italic, lambda n: self.update_style("epub_italic", n), "epub_italic"))

        control, self.font_slider = self.slider_control(12, 32, self.font_size, "", 125)
        self._reader_slider_controls["reader_font_size"] = self.font_slider
        self.font_slider.valueChanged.connect(lambda n: self.update_style("reader_font_size", n))
        self.option_row(side, "Font size", control)
        for label, key, low, high, value, suffix in (
            ("Letter spacing", "epub_letter_spacing", 0, 6, self.letter_spacing, ""),
            ("Line height", "epub_line_height", 120, 240, self.line_height, "%"),
            ("Paragraph spacing", "epub_paragraph_spacing", 0, 30, self.paragraph_spacing, ""),
            ("Paragraph indentation", "epub_paragraph_indent", 0, 60, self.paragraph_indent, ""),
        ):
            control, slider = self.slider_control(low, high, value, suffix, 125)
            self._reader_slider_controls[key] = slider
            slider.valueChanged.connect(lambda n, k=key: self.update_style(k, n))
            self.option_row(side, label, control)

        self.section(side, "Reading Layout")
        self.option_row(side, "Text alignment", self.segmented(
            (("Left", "left", "icons8-align-left-50.png"),
             ("Center", "center", "icons8-align-center-50.png"),
             ("Right", "right", "icons8-align-right-50.png"),
             ("Justify", "justify", "icons8-align-justify-50.png")),
            self.text_align, lambda value: self.update_style("epub_text_align", value), "epub_text_align"))
        for label, key, low, high, value in (
            ("Side margins", "epub_side_margin", 12, 120, self.side_margin),
            ("Vertical margins", "epub_vertical_margin", 8, 110, self.vertical_margin),
        ):
            control, slider = self.slider_control(low, high, value, "", 125)
            self._reader_slider_controls[key] = slider
            slider.valueChanged.connect(lambda n, k=key: self.update_style(k, n))
            self.option_row(side, label, control)

        self.section(side, "Images")
        self.images_switch = Toggle(self.settings_content)
        self.images_switch.setChecked(self.show_images)
        self.images_switch.toggled.connect(lambda checked: self.update_style("epub_show_images", checked))
        self.option_row(side, "Display images", self.images_switch)
        self.captions_switch = Toggle(self.settings_content)
        self.captions_switch.setChecked(self.show_captions)
        self.captions_switch.toggled.connect(lambda checked: self.update_style("epub_show_captions", checked))
        self.option_row(side, "Display captions", self.captions_switch)
        control, slider = self.slider_control(40, 100, self.image_size, "%", 125)
        self._reader_slider_controls["epub_image_size"] = slider
        slider.valueChanged.connect(lambda n: self.update_style("epub_image_size", n))
        self.option_row(side, "Image size", control)

        self.section(side, "Chapter Style")
        self.option_row(side, "Chapter title alignment", self.segmented(
            (("Start", "left"), ("Center", "center"), ("End", "right")),
            self.chapter_align, lambda value: self.update_style("epub_chapter_align", value), "epub_chapter_align"))

        self.section(side, "Reading Mode")
        self.arrows_switch = Toggle(self.settings_content)
        self.arrows_switch.setChecked(self.arrow_chapters)
        self.arrows_switch.toggled.connect(lambda checked: self.update_style("epub_arrow_chapters", checked))
        self.option_row(side, "Horizontal gesture", self.arrows_switch,
                        "Swipe sideways or use ← / → to turn reading pages")
        self.option_row(side, "Progress count", self.segmented(
            (("Percentage", "percentage"), ("Quantity", "quantity")),
            self.progress_mode, lambda value: self.update_style("epub_progress_mode", value), "epub_progress_mode"))
        self.progress_switch = Toggle(self.settings_content)
        self.progress_switch.setChecked(self.show_progress)
        self.progress_switch.toggled.connect(lambda checked: self.update_style("reader_show_progress_bar", checked))
        self.option_row(side, "Progress bar", self.progress_switch)
        self.fullscreen_switch = Toggle(self.settings_content)
        self.fullscreen_switch.toggled.connect(self.set_reader_fullscreen)
        self.option_row(side, "Fullscreen", self.fullscreen_switch)
        self.sleep_switch = Toggle(self.settings_content)
        self.sleep_switch.setChecked(self.keep_screen_on)
        if sys.platform != "win32":
            self.sleep_switch.setEnabled(False)
            self.sleep_switch.setToolTip("Keep screen on is implemented for Windows")
        self.sleep_switch.toggled.connect(lambda checked: self.update_style("epub_keep_screen_on", checked))
        self.option_row(side, "Keep screen on", self.sleep_switch)

        # Reset the reader controls without touching the current book or theme.
        self.reset_reader_button = QPushButton("Restore default reader settings", self.settings_content)
        self.reset_reader_button.setObjectName("readerResetButton")
        self.reset_reader_button.setMinimumHeight(39)
        self.reset_reader_button.setCursor(Qt.PointingHandCursor)
        self.reset_reader_button.setToolTip("Restore the original EPUB font, layout, image, and reading controls")
        self.reset_reader_button.clicked.connect(self.restore_default_reader_settings)
        side.addWidget(self.reset_reader_button)
        side.addStretch(1)
        self.settings_panel.setWidget(self.settings_content)
        body.addWidget(self.settings_panel)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setStretchFactor(2, 0)
        body.splitterMoved.connect(self.queue_panel_width_save)
        root.addWidget(body, 1)

        # Bottom reading status and page/chapter navigation.
        footer = QFrame(self)
        footer.setObjectName("readerFooter")
        foot = QVBoxLayout(footer)
        foot.setContentsMargins(15, 5, 15, 7)
        foot.setSpacing(3)
        self.progress_slider = QSlider(Qt.Horizontal, footer)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setTracking(False)
        self.progress_slider.sliderPressed.connect(self.begin_seek)
        self.progress_slider.sliderReleased.connect(self.end_seek)
        foot.addWidget(self.progress_slider)
        line = QHBoxLayout()
        self.percent_label = QLabel("0.0%", footer)
        self.percent_label.setObjectName("readerFooterText")
        self.page_label = QLabel("Position 1 / 1", footer)
        self.page_label.setObjectName("readerFooterText")
        self.chapter_label = QLabel("No chapter", footer)
        self.chapter_label.setObjectName("readerFooterText")
        self.previous_button = self.button("‹", self.previous_page, 32, "Previous reading page (Ctrl+Left for chapter)")
        self.next_button = self.button("›", self.next_page, 32, "Next reading page (Ctrl+Right for chapter)")
        line.addWidget(self.percent_label)
        line.addSpacing(10)
        line.addWidget(self.page_label)
        line.addStretch()
        line.addWidget(self.chapter_label)
        line.addSpacing(10)
        line.addWidget(self.previous_button)
        line.addWidget(self.next_button)
        foot.addLayout(line)
        root.addWidget(footer)

        self.apply_local_style()
        self.update_navigation()

    def apply_local_style(self):
        style = """
        QWidget#newReaderPage { background: #12141a; color: #e8e8f5; }
        QFrame#readerHeader { background: #14171d; border-bottom: 1px solid #303341; }
        QLabel#readerHeaderTitle { font: 600 15px Georgia; color: #e8e8f5; background: transparent; }
        QLabel#readerHeaderSub { font: 11px Georgia; color: #b5b7ca; background: transparent; }
        QLabel#readerHeaderCover { background: #292c3d; border-radius: 5px; }
        QFrame#readerHeaderDivider { background: #606078; border: none; }
        QPushButton#readerIconButton { background: transparent; color: #d2d4ef;
            border: 1px solid transparent; border-radius: 6px; font-size: 18px; padding: 0 5px; }
        QPushButton#readerIconButton:hover { background: #34354d; border-color: #565879; }
        QPushButton#readerIconButton:disabled { color: #66697e; }
        QTextBrowser#readerCanvas { background: #12141a; color: #e8e8f5; border: none;
            selection-background-color: #504c7b; }
        QFrame#readerTocPanel { background: #181a22; border-right: 1px solid #323543; }
        QSplitter#readerBodySplitter::handle { background: #282c3a; }
        QSplitter#readerBodySplitter::handle:hover { background: #6d6b9a; }
        QListWidget { background: #171923; color: #e4e5f3; border: 1px solid #333747;
            border-radius: 7px; outline: none; padding: 4px; }
        QListWidget::item { padding: 10px 6px; }
        QListWidget::item:selected { background: #484968; border-radius: 5px; }
        QScrollArea#readerSettingsPanel { background: #161820; border-left: 1px solid #333645; }
        QWidget#readerSettingsContent { background: #161820; }
        QLabel#readerSectionTitle { background: transparent; color: #d1cfff;
            font: 700 14px Georgia; padding-top: 7px; padding-bottom: 3px; }
        QLabel#readerRowTitle { background: transparent; color: #dadeeb; font-size: 12px; }
        QLabel#readerRowDetail { background: transparent; color: #9298af; font-size: 11px; }
        QLabel#readerSettingValue { background: transparent; color: #dce0f5; font-size: 11px; }
        QComboBox, QLineEdit { background: #12141c; border: 1px solid #383d50; border-radius: 6px;
            color: #dfe0f5; font-size: 12px; padding: 6px; }
        QComboBox::drop-down { background: transparent; border: none; width: 18px; }
        QPushButton#readerSegment { background: #171923; border: 1px solid #484c60;
            color: #cbd0e7; font-size: 11px; border-radius: 5px; padding: 5px 4px; }
        QPushButton#readerSegment:checked { background: #494b72; border-color: #7b7da9;
            color: #eeeefe; }
        QPushButton#readerSegment:hover { border-color: #a19ed7; }
        QPushButton#readerResetButton { background: #30344d; color: #e9e8ff;
            border: 1px solid #6a6f9b; border-radius: 8px;
            padding: 8px 12px; font-size: 12px; font-weight: 600; }
        QPushButton#readerResetButton:hover { background: #41466a; border-color: #b5b0f5; }
        QSlider::groove:horizontal { background: #4b4d6c; border: none; height: 5px; border-radius: 2px; }
        QSlider::handle:horizontal { background: #d4d3ff; border: none; width: 12px;
            margin: -5px 0; border-radius: 6px; }
        QFrame#readerFooter { background: #151720; border-top: 1px solid #323543; }
        QLabel#readerFooterText { background: transparent; color: #c6c8db; font: 11px Georgia; }
        QScrollBar:vertical { background: #161820; width: 8px; border: none; }
        QScrollBar::handle:vertical { background: #55586e; border-radius: 4px; min-height: 30px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal { height: 7px; background: #161820; }
        QScrollBar::handle:horizontal { background: #55586e; border-radius: 3px; }
        """
        palette = resolved_colors()
        if (palette["background"] != "#15171e" or
                palette["foreground"] != "#eeeeee" or
                palette["accent"] != "#8f88ff"):
            # Keep the reader's existing layout and controls, recolor only the
            # known dark-theme tokens. The original theme remains untouched.
            replacements = {
                "#12141a": palette["reader_background"],
                "#14171d": palette["sidebar"],
                "#151720": palette["panel"],
                "#161820": palette["panel"],
                "#181a22": palette["panel"],
                "#191b23": palette["panel"],
                "#e8e8f5": palette["foreground"],
                "#e4e5f3": palette["foreground"],
                "#d2d4ef": palette["foreground"],
                "#dce0f5": palette["foreground"],
                "#aba8f0": palette["accent"],
                "#d4d3ff": palette["accent"],
                "#484968": palette["selected"],
                "#494b72": palette["selected"],
                "#34354d": palette["hover"],
            }
            pattern = re.compile("|".join(re.escape(x) for x in replacements), re.I)
            style = pattern.sub(lambda m: replacements[m.group().lower()], style)
        self.setStyleSheet(style)

    # ------------------------------------------------------------
    # Restore the in-reader controls to their original values.
    # This leaves bookmarks, reading position, TOC/settings widths,
    # the selected book, the app theme and library data untouched.
    # ------------------------------------------------------------
    def restore_default_reader_settings(self):
        answer = QMessageBox.question(
            self,
            "Restore reader settings?",
            "Restore the original EPUB font, spacing, layout, images, and reading controls?"
            "\n\nYour reading progress, bookmarks and app appearance will not be changed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        # Save current location before changing layout-dependent scroll ranges.
        self.scroll_save_timer.stop()
        self.style_timer.stop()
        position = self.get_current_scroll_position()
        self.save_current_progress()

        self._loading_controls = True
        try:
            # Commit the defaults once, without triggering an expensive
            # chapter re-render for every slider or toggle.
            for key, value in READER_DEFAULTS.items():
                if key == "reader_font_size":
                    set_reader_font_size(value)
                else:
                    set_setting(key, value)

            self.read_saved_style()
            self.font_combo.setCurrentText(self.font_family)
            for key, slider in self._reader_slider_controls.items():
                slider.setValue(READER_DEFAULTS[key])
            for key, buttons in self._reader_segment_controls.items():
                buttons[READER_DEFAULTS[key]].setChecked(True)

            self.images_switch.setChecked(self.show_images)
            self.captions_switch.setChecked(self.show_captions)
            self.arrows_switch.setChecked(self.arrow_chapters)
            self.progress_switch.setChecked(self.show_progress)
            self.sleep_switch.setChecked(self.keep_screen_on)
        finally:
            self._loading_controls = False

        # Fullscreen is a temporary reader state, not a saved preference.
        if self._fullscreen_by_reader:
            self.set_reader_fullscreen(False)
        self.apply_keep_screen_on(False)
        self.apply_arrow_shortcuts()
        self.progress_slider.setVisible(self.show_progress)
        self.apply_reader_appearance()
        if self.chapters and self.book is not None:
            self.display_chapter(position=position, save_after=False)
        else:
            self.update_progress_bar()

    # ------------------------------------------------------------
    # Reading/formatting. Original EPUB text is not overwritten.
    # ------------------------------------------------------------
    def update_style(self, key, value):
        if self._loading_controls:
            return
        if key == "reader_font_size":
            set_reader_font_size(int(value))
        else:
            set_setting(key, value)
        self.read_saved_style()
        if key == "epub_arrow_chapters":
            self.apply_arrow_shortcuts()
        elif key == "reader_show_progress_bar" or key == "epub_progress_mode":
            self.progress_slider.setVisible(self.show_progress)
            self.update_progress_bar()
        elif key == "epub_keep_screen_on":
            self.apply_keep_screen_on(self.isVisible() and self.keep_screen_on)
        else:
            self.style_timer.start()

    def refresh_chapter_style(self):
        position = self.get_current_scroll_position()
        self.apply_reader_appearance()
        if self.chapters and self.book is not None:
            self.display_chapter(position=position, save_after=False)

    def apply_reader_appearance(self):
        font = QFont(self.font_family, self.font_size)
        # Many installed fonts do not include a separate Medium face.
        # Bold provides a visible fourth step even with regular/bold-only fonts.
        font.setWeight((QFont.Thin, QFont.Light, QFont.Normal, QFont.Bold)[self.weight])
        font.setItalic(self.italic)
        font.setLetterSpacing(QFont.AbsoluteSpacing, self.letter_spacing)
        self.reader.setFont(font)
        self.reader.document().setDefaultFont(font)
        palette = resolved_colors()
        self.reader.setStyleSheet(f"""
            QTextBrowser#readerCanvas {{ background: {palette['reader_background']};
                color: {palette['foreground']}; border: none;
                padding: {self.vertical_margin}px {self.side_margin}px;
                selection-background-color: {palette['selected']}; }}
        """)

    def prepare_chapter_html(self, chapter_html):
        html = (chapter_html.decode("utf-8", "replace")
                if isinstance(chapter_html, bytes) else str(chapter_html))
        if self.show_images:
            html = self.resolve_epub_images(html)
        else:
            html = re.sub(r"<img\b[^>]*>", "", html, flags=re.IGNORECASE | re.DOTALL)
            html = re.sub(r"<image\b[^>]*>", "", html, flags=re.IGNORECASE | re.DOTALL)
        if not self.show_captions:
            html = re.sub(r"<figcaption\b[^>]*>.*?</figcaption\s*>", "", html,
                          flags=re.IGNORECASE | re.DOTALL)
        font_name = escape(self.font_family, quote=True).replace("'", "")
        weight = ("100", "300", "400", "700")[self.weight]
        italic = "italic" if self.italic else "normal"
        palette = resolved_colors()
        foreground = palette['foreground']
        background = palette['reader_background']
        accent = palette['accent']
        css = f"""<style>
          body {{ background-color: {background} !important; }}
          body, body *, p, div, li, blockquote, span {{ color: {foreground} !important;
            font-family: '{font_name}' !important; font-size: {self.font_size}pt !important;
            font-weight: {weight} !important; font-style: {italic} !important;
            letter-spacing: {self.letter_spacing}px !important;
            line-height: {self.line_height}% !important; }}
          p {{ margin-top: 0px !important; margin-bottom: {self.paragraph_spacing}px !important;
            text-indent: {self.paragraph_indent}px !important;
            text-align: {self.text_align} !important; }}
          blockquote {{ margin-left: 22px; margin-right: 22px; }}
          h1, h2, h3, h4 {{ color: {foreground} !important;
            font-family: '{font_name}' !important; text-align: {self.chapter_align} !important;
            font-weight: 600 !important; font-style: normal !important; }}
          img {{ max-width: {self.image_size}% !important; height: auto !important; }}
          figcaption {{ color: {foreground} !important; text-align: center; font-style: italic; }}
          a {{ color: {accent} !important; }}
        </style>"""
        if re.search(r"</head\s*>", html, re.IGNORECASE):
            return re.sub(r"</head\s*>", lambda m: css + m.group(0), html,
                          count=1, flags=re.IGNORECASE)
        return css + html

    # ------------------------------------------------------------
    # EPUB illustrations: QTextBrowser cannot load relative paths from inside
    # a ZIP. Register the images using internal Qt resource URLs instead.
    # ------------------------------------------------------------
    def index_epub_images(self, book_path):
        self._epub_file = None
        self._epub_images = {}
        self._epub_image_index = {}
        self._decoded_images = {}
        self._image_serial = 0
        if not book_path:
            return
        path = Path(str(book_path))
        if not path.is_file() or path.suffix.lower() != ".epub":
            return
        try:
            with zipfile.ZipFile(path) as archive:
                images = {
                    posixpath.normpath(name.lstrip("/")): name
                    for name in archive.namelist()
                    if name.lower().endswith((
                        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"
                    ))
                }
            self._epub_file = path
            self._epub_images = images
        except (OSError, zipfile.BadZipFile):
            pass

    def resolve_epub_images(self, chapter_html):
        if not self._epub_images:
            return chapter_html

        # EPUB chapter HTML normally uses a path relative to the XHTML file.
        # If that path is unavailable from the chapter extractor, accept a
        # basename match only when it identifies exactly one archive image.
        def convert(match):
            tag = match.group(0)
            attr = re.search(r'''\bsrc\s*=\s*(["'])(.*?)\1''', tag, re.I | re.S)
            if attr is None:
                return tag
            src = unescape(attr.group(2)).strip()
            if not src or src.startswith(("data:", "litenova-image:", "http:", "https:")):
                return tag
            path = posixpath.normpath(unquote(urlsplit(src).path).replace("\\", "/").lstrip("/"))
            member = self._epub_images.get(path)
            if member is None:
                candidates = [value for key, value in self._epub_images.items()
                              if key.endswith("/" + path) or key == path]
                if len(candidates) == 1:
                    member = candidates[0]
            if member is None:
                filename = posixpath.basename(path)
                candidates = [value for key, value in self._epub_images.items()
                              if posixpath.basename(key) == filename]
                if len(candidates) == 1:
                    member = candidates[0]
            if member is None:
                return tag
            self._image_serial += 1
            image_id = str(self._image_serial)
            self._epub_image_index[image_id] = member
            replacement = f"litenova-image:///{image_id}"
            return tag[:attr.start(2)] + replacement + tag[attr.end(2):]

        return re.sub(r"<img\b[^>]*>", convert, chapter_html, flags=re.I | re.S)

    def load_epub_image(self, image_id):
        member = self._epub_image_index.get(str(image_id))
        if member is None or self._epub_file is None:
            return QImage()
        if member in self._decoded_images:
            return self._decoded_images[member]
        try:
            with zipfile.ZipFile(self._epub_file) as archive:
                data = archive.read(member)
            image = QImage.fromData(data)
            if not image.isNull():
                # Bound this auxiliary cache; QTextDocument manages its own.
                if len(self._decoded_images) >= 12:
                    self._decoded_images.clear()
                self._decoded_images[member] = image
            return image
        except (OSError, KeyError, zipfile.BadZipFile):
            return QImage()

    # ------------------------------------------------------------
    # Book/chapter state, progress, and reader compatibility.
    # ------------------------------------------------------------
    @staticmethod
    def row_value(record, key, default=None):
        try:
            value = record[key] if key in record.keys() else default
            return default if value is None else value
        except (KeyError, AttributeError, TypeError):
            return default

    def open_book(self, book):
        if self.book is not None:
            self.save_current_progress()
        self.scroll_save_timer.stop()
        self.style_timer.stop()
        self.book = book
        self.read_saved_style()
        self.apply_reader_appearance()
        self._loading_controls = True
        self.font_combo.setCurrentText(self.font_family)
        self.font_slider.setValue(self.font_size)
        self.images_switch.setChecked(self.show_images)
        self.captions_switch.setChecked(self.show_captions)
        self.progress_switch.setChecked(self.show_progress)
        self.sleep_switch.setChecked(self.keep_screen_on)
        self.arrows_switch.setChecked(self.arrow_chapters)
        self._loading_controls = False
        self.apply_arrow_shortcuts()
        self.progress_slider.setVisible(self.show_progress)
        self.chapters = []
        self.current_chapter = 0
        self.reader.clear()
        self.toc_list.clear()
        self.book_title.setText(str(self.row_value(book, "title", "Untitled")))
        self.author.setText(str(self.row_value(book, "author", "Unknown author")))
        cover_file = self.row_value(book, "cover_path")
        cover = QPixmap(str(cover_file)) if cover_file else QPixmap()
        if not cover.isNull():
            scaled = cover.scaled(self.cover.size(), Qt.KeepAspectRatioByExpanding,
                                  Qt.SmoothTransformation)
            self.cover.setPixmap(scaled)
        else:
            self.cover.setPixmap(QPixmap())
            self.cover.setText("BOOK")
        self._bookmarks = self.load_bookmarks()
        self.update_bookmark_button()
        try:
            file_path = self.row_value(book, "file_path") or self.row_value(book, "epub_path")
            self.index_epub_images(file_path)
            self.chapters = list(get_chapters(file_path))
        except Exception as error:
            QMessageBox.critical(self, "EPUB reader error", f"Could not open this EPUB.\n\n{error}")
            self.update_navigation()
            return
        self.populate_toc()
        if not self.chapters:
            self.reader.setHtml("<h2>No readable chapters found.</h2>")
            self.update_navigation()
            return
        progress = get_progress(book["id"])
        try:
            saved_chapter = int(self.row_value(progress, "chapter_index", 0))
            saved_position = float(self.row_value(progress, "position", 0.0))
        except (TypeError, ValueError):
            saved_chapter, saved_position = 0, 0.0
        self.current_chapter = max(0, min(saved_chapter, len(self.chapters) - 1))
        self.display_chapter(position=max(0.0, min(saved_position, 1.0)), save_after=False)

    def populate_toc(self):
        self.toc_list.blockSignals(True)
        self.toc_list.clear()
        for index, chapter in enumerate(self.chapters):
            title = self.row_value(chapter, "title") or f"Chapter {index + 1}"
            self.toc_list.addItem(QListWidgetItem(str(title)))
        self.toc_list.blockSignals(False)
        self.refresh_toc_bookmarks()

    def display_chapter(self, position=0.0, save_after=True):
        if not self.chapters:
            return
        self._render_generation += 1
        generation = self._render_generation
        self.is_restoring_scroll = True
        chapter = self.chapters[self.current_chapter]
        title = str(self.row_value(chapter, "title") or f"Chapter {self.current_chapter + 1}")
        self.chapter_number.setText(f"Chapter {self.current_chapter + 1}")
        self.chapter_title.setText(title)
        html = self.prepare_chapter_html(self.row_value(chapter, "html", ""))
        self.reader.setHtml(html)
        self.toc_list.blockSignals(True)
        self.toc_list.setCurrentRow(self.current_chapter)
        self.toc_list.blockSignals(False)
        self.chapter_label.setText(f"Chapter {self.current_chapter + 1} of {len(self.chapters)}")
        self.update_navigation()
        self.update_bookmark_button()
        QTimer.singleShot(0, lambda: self.finish_chapter_display(
            generation, position, save_after))

    def finish_chapter_display(self, generation, position, save_after):
        if generation != self._render_generation or not self.chapters:
            return
        bar = self.reader.verticalScrollBar()
        bar.setValue(round(bar.maximum() * max(0.0, min(1.0, position))))
        self.is_restoring_scroll = False
        self.update_progress_bar()
        if save_after:
            self.save_current_progress()

    def get_current_scroll_position(self):
        bar = self.reader.verticalScrollBar()
        return bar.value() / bar.maximum() if bar.maximum() else 0.0

    def update_progress_bar(self):
        if not self.chapters:
            self.percent_label.setText("0.0%")
            self.page_label.setText("Position 1 / 1")
            if not self._changing_slider:
                self.progress_slider.setValue(0)
            return
        fraction = self.get_current_scroll_position()
        overall = (self.current_chapter + fraction) / len(self.chapters)
        bar = self.reader.verticalScrollBar()
        view_height = max(1, self.reader.viewport().height())
        pages = max(1, math.ceil((bar.maximum() + view_height) / view_height))
        current_page = min(pages, 1 + int(bar.value() / view_height))
        if self.progress_mode == "percentage":
            self.percent_label.setText(f"{overall * 100:.1f}%")
        else:
            self.percent_label.setText(f"{self.current_chapter + 1} / {len(self.chapters)}")
        self.page_label.setText(f"Position {current_page} / {pages}")
        if not self._changing_slider:
            self.progress_slider.setValue(round(overall * 1000))

    def on_scroll_changed(self, _value):
        if self.is_restoring_scroll or not self.chapters:
            return
        self.update_navigation()
        self.scroll_save_timer.start()

    def save_current_progress(self):
        if self.book is None or not self.chapters or self.is_restoring_scroll:
            return
        save_progress(book_id=self.book["id"], chapter_index=self.current_chapter,
                      position=self.get_current_scroll_position())

    def begin_seek(self):
        self._changing_slider = True

    def end_seek(self):
        self._changing_slider = False
        if not self.chapters:
            return
        self.save_current_progress()
        point = self.progress_slider.value() / 1000 * len(self.chapters)
        chapter = min(len(self.chapters) - 1, int(point))
        position = 1.0 if self.progress_slider.value() == 1000 else point - chapter
        if chapter != self.current_chapter:
            self.current_chapter = chapter
            self.display_chapter(position=position)
        else:
            self.reader.verticalScrollBar().setValue(
                round(self.reader.verticalScrollBar().maximum() * position))
            self.update_progress_bar()
            self.save_current_progress()

    def jump_to_chapter(self, index):
        if index < 0 or index >= len(self.chapters) or index == self.current_chapter:
            return
        self.save_current_progress()
        self.current_chapter = index
        # Selecting a bookmarked chapter in the TOC opens its saved position.
        self.display_chapter(position=self._bookmarks.get(index, 0.0))

    def previous_chapter(self):
        if self.current_chapter <= 0:
            return
        self.save_current_progress()
        self.current_chapter -= 1
        self.display_chapter()

    def next_chapter(self):
        if self.current_chapter >= len(self.chapters) - 1:
            return
        self.save_current_progress()
        self.current_chapter += 1
        self.display_chapter()

    def previous_page(self):
        """Move up one viewport; at a chapter boundary, open the prior chapter."""
        if not self.chapters:
            return
        scrollbar = self.reader.verticalScrollBar()
        if scrollbar.value() > 0:
            scrollbar.setValue(max(0, scrollbar.value() - max(1, self.reader.viewport().height() - 55)))
        elif self.current_chapter > 0:
            self.save_current_progress()
            self.current_chapter -= 1
            self.display_chapter(position=1.0)
        self.update_navigation()

    def next_page(self):
        """Move down one viewport; at a chapter boundary, open the next chapter."""
        if not self.chapters:
            return
        scrollbar = self.reader.verticalScrollBar()
        if scrollbar.value() < scrollbar.maximum():
            scrollbar.setValue(min(scrollbar.maximum(), scrollbar.value() + max(1, self.reader.viewport().height() - 55)))
        elif self.current_chapter < len(self.chapters) - 1:
            self.save_current_progress()
            self.current_chapter += 1
            self.display_chapter(position=0.0)
        self.update_navigation()

    def update_navigation(self):
        bar = self.reader.verticalScrollBar()
        self.previous_button.setEnabled(bool(self.chapters) and (
            self.current_chapter > 0 or bar.value() > 0))
        self.next_button.setEnabled(bool(self.chapters) and (
            self.current_chapter < len(self.chapters) - 1 or bar.value() < bar.maximum()))
        self.update_progress_bar()

    # ------------------------------------------------------------
    # Top controls: TOC, search, bookmarks and menu.
    # ------------------------------------------------------------
    def queue_panel_width_save(self, _position, _index):
        if self._splitter_ready:
            self._splitter_store_timer.start()

    def save_panel_widths(self):
        if not self._splitter_ready:
            return
        if self._toc_open and self.toc_panel.isVisible() and self.toc_panel.width() >= 190:
            width = self.toc_panel.width()
            if width != self._toc_width:
                self._toc_width = width
                set_setting("epub_toc_width", width)
        if self._settings_open and self.settings_panel.isVisible() and self.settings_panel.width() >= 350:
            width = self.settings_panel.width()
            if width != self._settings_width:
                self._settings_width = width
                set_setting("epub_settings_width", width)

    def restore_panel_widths(self):
        # Called once the splitter has real geometry, and when a panel opens.
        total = self.body_splitter.width()
        if total <= 0:
            return
        left = self._toc_width if self._toc_open else 0
        right = self._settings_width if self._settings_open else 0
        center = max(300, total - left - right - self.body_splitter.handleWidth() * 2)
        self.body_splitter.setSizes([left, center, right])
        self._splitter_ready = True

    def toggle_toc(self):
        self._splitter_store_timer.stop()
        self.save_panel_widths()
        self._toc_open = not self._toc_open
        self.toc_panel.setVisible(self._toc_open)
        self.toc_button.setToolTip("Hide chapters" if self._toc_open else "Show chapters")
        QTimer.singleShot(0, self.restore_panel_widths)

    def toggle_settings(self):
        self._splitter_store_timer.stop()
        self.save_panel_widths()
        self._settings_open = not self._settings_open
        self.settings_panel.setVisible(self._settings_open)
        QTimer.singleShot(0, self.restore_panel_widths)

    def toggle_search(self):
        self._search_open = not self._search_open
        self.search_row.setVisible(self._search_open)
        if self._search_open:
            self.search_field.setFocus()
            self.search_field.selectAll()
        else:
            self.reader.setFocus()

    def find_next(self):
        phrase = self.search_field.text().strip()
        if not phrase:
            return
        if not self.reader.find(phrase):
            cursor = self.reader.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.reader.setTextCursor(cursor)
            self.reader.find(phrase)

    def bookmark_key(self):
        if self.book is None:
            return None
        return f"epub_bookmarks_{self.book['id']}"

    def load_bookmarks(self):
        """Load chapter -> position bookmarks. Older one-bookmark saves still work."""
        key = self.bookmark_key()
        if not key:
            return {}
        result = {}
        raw = get_setting(key, "")
        if raw:
            try:
                data = json.loads(str(raw))
                if isinstance(data, dict):
                    for chapter, fraction in data.items():
                        index = int(chapter)
                        position = float(fraction)
                        if index >= 0 and math.isfinite(position):
                            result[index] = max(0.0, min(1.0, position))
            except (ValueError, TypeError, OverflowError, json.JSONDecodeError):
                result = {}
        if not result:
            legacy = get_setting(f"epub_bookmark_{self.book['id']}", "")
            try:
                chapter, position = str(legacy).split(":", 1)
                index = int(chapter)
                fraction = float(position)
                if index >= 0 and math.isfinite(fraction):
                    result[index] = max(0.0, min(1.0, fraction))
            except (ValueError, TypeError, OverflowError):
                pass
        return result

    def store_bookmarks(self):
        key = self.bookmark_key()
        if key:
            set_setting(key, json.dumps(self._bookmarks, separators=(",", ":")))
            # Remove legacy single-bookmark key so it cannot be restored after
            # the user removes all bookmarks from this book.
            set_setting(f"epub_bookmark_{self.book['id']}", "")

    def toggle_bookmark(self):
        if self.book is None or not self.chapters:
            return
        if self.current_chapter in self._bookmarks:
            del self._bookmarks[self.current_chapter]
        else:
            self._bookmarks[self.current_chapter] = self.get_current_scroll_position()
        self.store_bookmarks()
        self.refresh_toc_bookmarks()
        self.update_bookmark_button()

    def _read_bookmark(self):
        """Compatibility: current chapter first, otherwise first saved chapter."""
        if self.current_chapter in self._bookmarks:
            return self.current_chapter, self._bookmarks[self.current_chapter]
        if self._bookmarks:
            index = min(self._bookmarks)
            return index, self._bookmarks[index]
        return None

    def refresh_toc_bookmarks(self):
        """Show a filled bookmark icon beside each marked chapter title."""
        icon = reader_icon("icons8-bookmark-50 (1).png", "icons8-bookmark-50.png")
        for index in range(self.toc_list.count()):
            item = self.toc_list.item(index)
            chapter = self.chapters[index]
            title = str(self.row_value(chapter, "title") or f"Chapter {index + 1}")
            if index in self._bookmarks:
                item.setText("★  " + title)
                item.setIcon(icon)
                item.setToolTip("Bookmarked — select to jump to your saved position")
            else:
                item.setText(title)
                item.setIcon(QIcon())
                item.setToolTip("")

    def update_bookmark_button(self):
        marked = self.current_chapter in self._bookmarks
        icon = reader_icon(
            "icons8-bookmark-50 (1).png" if marked else "icons8-bookmark-50.png"
        )
        if icon.isNull():
            self.bookmark_button.setText("★" if marked else "☆")
            self.bookmark_button.setIcon(QIcon())
        else:
            use_button_icon(self.bookmark_button, icon)
        self.bookmark_button.setToolTip(
            "Remove bookmark from this chapter" if marked else "Bookmark this chapter at current position"
        )

    def go_to_bookmark(self):
        saved = self._read_bookmark()
        if saved is None or saved[0] >= len(self.chapters):
            QMessageBox.information(self, "Bookmark", "No saved bookmark for this book.")
            return
        self.save_current_progress()
        self.current_chapter = saved[0]
        self.display_chapter(position=saved[1], save_after=False)

    def setup_shortcuts(self):
        self.find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.find_shortcut.activated.connect(self.toggle_search)
        self.toc_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.toc_shortcut.activated.connect(self.toggle_toc)
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(lambda: self.set_reader_fullscreen(not self._fullscreen_by_reader))
        self.next_chapter_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        self.next_chapter_shortcut.activated.connect(self.next_chapter)
        self.prev_chapter_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)
        self.prev_chapter_shortcut.activated.connect(self.previous_chapter)
        # Plain arrows belong to the reading canvas only. A window-wide
        # shortcut would also steal arrows from sliders and dropdowns.
        self.apply_arrow_shortcuts()

    def apply_arrow_shortcuts(self):
        # The canvas event filter handles arrows and horizontal swipes.
        self.reader.setFocusPolicy(Qt.StrongFocus)

    def eventFilter(self, watched, event):
        if hasattr(self, "reader") and watched in (self.reader, self.reader.viewport()):
            if not self.arrow_chapters or not self.chapters:
                return super().eventFilter(watched, event)
            if event.type() == QEvent.KeyPress and event.modifiers() == Qt.NoModifier:
                if event.key() == Qt.Key_Right:
                    self.next_page()
                    return True
                if event.key() == Qt.Key_Left:
                    self.previous_page()
                    return True
            if watched is self.reader.viewport():
                if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                    self._gesture_origin = event.position()
                elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                    start = self._gesture_origin
                    self._gesture_origin = None
                    if start is not None:
                        dx = event.position().x() - start.x()
                        dy = event.position().y() - start.y()
                        if abs(dx) >= 85 and abs(dx) > abs(dy) * 1.6:
                            # Process after Qt finishes dispatching this mouse event.
                            QTimer.singleShot(0, self.next_page if dx < 0 else self.previous_page)
                            return True
                elif event.type() == QEvent.Wheel and not event.modifiers():
                    dx = event.angleDelta().x()
                    if dx == 0:
                        dx = event.pixelDelta().x()
                    if abs(dx) >= 40 and time.monotonic() - self._last_horizontal_action > 0.28:
                        self._last_horizontal_action = time.monotonic()
                        QTimer.singleShot(0, self.next_page if dx < 0 else self.previous_page)
                        return True
        return super().eventFilter(watched, event)

    # ------------------------------------------------------------
    # Fullscreen and Windows display-awake handling.
    # ------------------------------------------------------------
    def set_reader_fullscreen(self, enabled):
        window = self.window()
        if enabled and not window.isFullScreen():
            window.showFullScreen()
            self._fullscreen_by_reader = True
        elif not enabled and self._fullscreen_by_reader:
            window.showNormal()
            self._fullscreen_by_reader = False
        self.fullscreen_switch.blockSignals(True)
        self.fullscreen_switch.setChecked(self._fullscreen_by_reader)
        self.fullscreen_switch.blockSignals(False)

    def apply_keep_screen_on(self, enabled):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            # ES_CONTINUOUS + ES_DISPLAY_REQUIRED on; ES_CONTINUOUS releases it.
            flags = 0x80000003 if enabled else 0x80000000
            result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
            self._prevent_sleep_active = bool(enabled and result)
        except (OSError, AttributeError):
            self._prevent_sleep_active = False

    def reload_settings(self):
        self.style_timer.stop()
        self.read_saved_style()
        self.apply_local_style()
        self.apply_reader_appearance()
        self._loading_controls = True
        self.font_combo.setCurrentText(self.font_family)
        self.font_slider.setValue(self.font_size)
        self.progress_switch.setChecked(self.show_progress)
        self._loading_controls = False
        self.progress_slider.setVisible(self.show_progress)
        self.apply_arrow_shortcuts()
        if self.chapters:
            self.display_chapter(position=self.get_current_scroll_position(), save_after=False)

    def go_back(self):
        self.style_timer.stop()
        self.scroll_save_timer.stop()
        self.save_current_progress()
        if self._fullscreen_by_reader:
            self.set_reader_fullscreen(False)
        self.back_requested.emit()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.restore_panel_widths)
        main = self.window()
        if hasattr(main, "sidebar"):
            main.sidebar.hide()
        self.apply_keep_screen_on(self.keep_screen_on)

    def hideEvent(self, event):
        self._splitter_store_timer.stop()
        self.save_panel_widths()
        self.style_timer.stop()
        self.scroll_save_timer.stop()
        self.save_current_progress()
        self.apply_keep_screen_on(False)
        if self._fullscreen_by_reader:
            self.set_reader_fullscreen(False)
        main = self.window()
        if hasattr(main, "sidebar"):
            main.sidebar.show()
        super().hideEvent(event)
