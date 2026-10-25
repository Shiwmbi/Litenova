"""Litenova Library cards with readable book-type badges on grid covers."""

from app.widgets.layout_helpers import ElidedLabel

from collections import OrderedDict
from math import ceil
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize, QPoint, QRectF, QEvent
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QImageReader
from PySide6.QtWidgets import (
    QFrame, QWidget, QLabel, QPushButton, QToolButton,
    QHBoxLayout, QVBoxLayout, QMenu, QSizePolicy,
)

from app.services.icon_service import ui_icon


class ClickableCover(QWidget):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class BookCard(QFrame):
    clicked = Signal(object)
    edit_requested = Signal(object)
    move_requested = Signal(object)
    remove_requested = Signal(object)

    COVER_RADIUS = 13
    # Only rendered thumbnails are cached. Labels share their pixel storage.
    _cover_cache = OrderedDict()
    _cover_cache_bytes = 0
    COVER_CACHE_BYTES = 16 * 1024 * 1024
    COVER_CACHE_ENTRIES = 256

    def __init__(
        self, book, mode="grid", cover_width=200,
        progress=0.0, show_progress=True,
        parent=None,
    ):
        super().__init__(parent)
        self.book = book
        self.mode = mode
        self.cover_width = cover_width
        self.progress = max(0.0, min(float(progress or 0.0), 1.0))
        self.show_progress = show_progress
        self.setObjectName("libraryBookCard")
        self.setCursor(Qt.PointingHandCursor)
        self.build_ui()

    def book_value(self, key, default=""):
        try:
            if key in self.book.keys():
                value = self.book[key]
                if value is not None:
                    return value
        except (KeyError, TypeError, AttributeError):
            pass
        return default

    @staticmethod
    def cover_file_signature(cover_path):
        if not cover_path:
            return None
        path = Path(str(cover_path))
        try:
            stat = path.stat()
            return (str(path), stat.st_mtime_ns, stat.st_size)
        except (OSError, ValueError):
            return None

    def create_rounded_cover(self, width, height):
        """Decode to physical display size; retain only the rounded thumbnail."""
        signature = self.cover_file_signature(self.book_value("cover_path"))
        if signature is None:
            return QPixmap()
        dpr = max(1.0, self.devicePixelRatioF())
        key = (signature, width, height, dpr)
        cache = BookCard._cover_cache
        cached = cache.get(key)
        if cached is not None:
            cache.move_to_end(key)
            return cached

        # Drop old versions of this file, without evicting other display sizes.
        for old_key in list(cache):
            if old_key[0][0] == signature[0] and old_key[0] != signature:
                old = cache.pop(old_key)
                BookCard._cover_cache_bytes -= old.width() * old.height() * 4

        physical_size = QSize(ceil(width * dpr), ceil(height * dpr))
        reader = QImageReader(signature[0])
        source_size = reader.size()
        if source_size.isValid():
            # Some JPEG decoders sacrifice detail at the exact target size.
            # Decode with modest headroom, then use Qt's smooth final scaling.
            # Small covers keep their native pixels rather than being enlarged.
            decode_size = source_size.scaled(
                physical_size * 2, Qt.KeepAspectRatioByExpanding,
            )
            if decode_size.width() < source_size.width():
                reader.setScaledSize(decode_size)
        image = reader.read()
        if image.isNull():
            return QPixmap()
        scaled = QPixmap.fromImage(image).scaled(
            physical_size, Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        x = max(0, (scaled.width() - physical_size.width()) // 2)
        y = max(0, (scaled.height() - physical_size.height()) // 2)
        result = QPixmap(physical_size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rounded_path = QPainterPath()
        rounded_path.addRoundedRect(
            QRectF(0, 0, physical_size.width(), physical_size.height()),
            self.COVER_RADIUS * dpr, self.COVER_RADIUS * dpr,
        )
        painter.setClipPath(rounded_path)
        painter.drawPixmap(0, 0, scaled, x, y,
                           physical_size.width(), physical_size.height())
        painter.end()
        result.setDevicePixelRatio(dpr)

        cost = result.width() * result.height() * 4
        if cost <= self.COVER_CACHE_BYTES:
            while cache and (
                BookCard._cover_cache_bytes + cost > self.COVER_CACHE_BYTES
                or len(cache) >= self.COVER_CACHE_ENTRIES
            ):
                _, old = cache.popitem(last=False)
                BookCard._cover_cache_bytes -= old.width() * old.height() * 4
            cache[key] = result
            BookCard._cover_cache_bytes += cost
        return result

    def update_cover_pixmap(self):
        self._cover_dpr = self.devicePixelRatioF()
        pixmap = self.create_rounded_cover(self.cover_width, self.cover_box.height())
        self.cover_label.clear()
        if pixmap.isNull():
            self.cover_label.setText("NO COVER")
        else:
            self.cover_label.setPixmap(pixmap)

    def event(self, event):
        result = super().event(event)
        if (event.type() in (QEvent.Type.Show, QEvent.Type.DevicePixelRatioChange)
                and hasattr(self, "cover_label")
                and self.devicePixelRatioF() != getattr(self, "_cover_dpr", None)):
            self.update_cover_pixmap()
        return result

    def build_ui(self):
        if self.mode == "list":
            self.cover_width = 76
            cover_height = 104
            self.setFixedHeight(124)
            self.setMinimumWidth(230)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            root = QHBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(14)
        else:
            cover_height = round(self.cover_width * 1.28)
            self.setFixedSize(self.cover_width, cover_height + 61)
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(5)

        self.cover_box = ClickableCover(self)
        self.cover_box.setObjectName("libraryCoverBox")
        self.cover_box.setFixedSize(self.cover_width, cover_height)
        self.cover_box.clicked.connect(self.open_book)

        self.cover_label = QLabel(self.cover_box)
        self.cover_label.setObjectName("libraryCover")
        self.cover_label.setGeometry(0, 0, self.cover_width, cover_height)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.update_cover_pixmap()

        percentage = self.progress * 100
        self.progress_badge = QLabel(f"{percentage:.1f}%", self.cover_box)
        self.progress_badge.setObjectName("libraryProgressBadge")
        self.progress_badge.setAlignment(Qt.AlignCenter)
        self.progress_badge.setGeometry(8, 8, 68, 29)
        self.progress_badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.progress_badge.setVisible(self.show_progress and self.mode == "grid")


        # Grid cover: a dark, high-contrast badge at the bottom-left.
        # Use the stored format/category, not the user's custom shelf name.
        category = str(self.book_value("category", "")).strip().lower()
        file_format = str(self.book_value("file_format", "")).strip().lower()
        if category == "manga":
            type_text = "MANGA"
        elif category == "manhwa":
            type_text = "MANHWA"
        elif category in ("light_novel", "novel", "epub") or file_format == "epub":
            type_text = "NOVEL"
        elif file_format == "cbz":
            type_text = "MANGA"
        else:
            type_text = "BOOK"

        self.cover_type_badge = QLabel(type_text, self.cover_box)
        self.cover_type_badge.setObjectName("libraryCoverTypeBadge")
        self.cover_type_badge.setAlignment(Qt.AlignCenter)
        self.cover_type_badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.cover_type_badge.setFixedHeight(27)
        self.cover_type_badge.setStyleSheet("""
            QLabel#libraryCoverTypeBadge {
                background-color: rgba(12, 15, 25, 235);
                color: #ffffff;
                border: 1px solid rgba(220, 225, 255, 170);
                border-radius: 12px;
                padding: 0px 5px;
                font-size: 10px;
                font-weight: 800;
            }
        """)
        badge_width = max(54, self.cover_type_badge.fontMetrics().horizontalAdvance(type_text) + 19)
        # Reserve space for the blue Read button, even on the smallest covers.
        badge_width = min(badge_width, max(54, self.cover_width - 61))
        self.cover_type_badge.setFixedWidth(badge_width)
        self.cover_type_badge.move(8, cover_height - 35)
        self.cover_type_badge.setVisible(self.mode == "grid")

        root.addWidget(self.cover_box)

        self.title_label = ElidedLabel(str(self.book_value("title", "Unknown Title")))
        self.title_label.setObjectName("libraryCardTitle")
        self.title_label.setWordWrap(False)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.author_label = ElidedLabel(str(self.book_value("author", "Unknown Author")))
        self.author_label.setObjectName("libraryCardAuthor")
        self.author_label.setWordWrap(False)
        self.author_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        category_names = {
            "light_novel": "Light Novel", "manga": "Manga", "manhwa": "Manhwa",
        }
        self.type_label = QLabel(category_names.get(
            str(self.book_value("category", "")), "Book"
        ))
        self.type_label.setObjectName("libraryCardType")
        self.type_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.options_button = QToolButton()
        self.options_button.setObjectName("libraryCardOptions")
        self.options_button.setIcon(ui_icon("more_options"))
        self.options_button.setIconSize(QSize(19, 19))
        self.options_button.setFixedSize(28, 28)
        self.options_button.setCursor(Qt.PointingHandCursor)
        self.options_button.setToolTip("Book options")
        self.options_menu = QMenu(self.options_button)
        self.options_menu.addAction("Read / Continue Reading").triggered.connect(self.open_book)
        self.options_menu.addSeparator()
        self.options_menu.addAction("Edit title, author or cover").triggered.connect(self.request_edit)
        self.options_menu.addAction("Move to category...").triggered.connect(self.request_move)
        self.options_menu.addSeparator()
        self.options_menu.addAction("Remove from Library").triggered.connect(self.request_remove)
        self.options_button.clicked.connect(self.show_options)

        if self.mode == "list":
            info = QVBoxLayout()
            info.setContentsMargins(0, 0, 0, 0)
            info.setSpacing(5)
            info.addWidget(self.title_label)
            info.addWidget(self.author_label)
            info.addWidget(self.type_label)
            info.addStretch()
            root.addLayout(info, 1)
            self.list_progress = QLabel(f"{percentage:.1f}%", self)
            self.list_progress.setObjectName("libraryCardAuthor")
            root.addWidget(self.list_progress)
            self.list_progress.setVisible(self.show_progress)
            root.addWidget(self.options_button)
        else:
            line = QHBoxLayout()
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(1)
            titles = QVBoxLayout()
            titles.setContentsMargins(0, 0, 0, 0)
            titles.setSpacing(3)
            titles.addWidget(self.title_label)
            titles.addWidget(self.author_label)
            line.addLayout(titles, 1)
            line.addWidget(self.options_button, 0, Qt.AlignTop)
            root.addLayout(line)
        self.apply_card_style()
        self.elide_text()

    def apply_card_style(self):
        self.setStyleSheet("""
            QFrame#libraryBookCard { background: transparent; border: none; }
            QWidget#libraryCoverBox {
                background: #222431; border: none; border-radius: 13px;
            }
            QLabel#libraryCover {
                background: transparent; border: none; border-radius: 13px;
                color: #a6a9c3; font-size: 11px;
            }
            QLabel#libraryProgressBadge {
                background: #babbfa; color: #17192c; border: none;
                border-radius: 14px; font-size: 12px; font-weight: 700;
            }
            QLabel#libraryCardTitle {
                background: transparent; border: none; padding: 0;
                color: #f1f0ff; font-weight: 600; font-size: 13px;
            }
            QLabel#libraryCardAuthor, QLabel#libraryCardType {
                background: transparent; border: none; padding: 0;
                color: #bfc1d4; font-size: 12px;
            }
            QToolButton#libraryCardOptions {
                background: transparent; border: none; border-radius: 7px; padding: 0;
            }
            QToolButton#libraryCardOptions:hover { background: #343751; }
        """)

    def elide_text(self):
        title = str(self.book_value("title", "Unknown Title"))
        author = str(self.book_value("author", "Unknown Author"))
        self.setToolTip(title + "\n" + author)
        self.title_label.setText(title)
        self.author_label.setText(author)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.elide_text()

    def open_book(self, *_args):
        self.clicked.emit(self.book)

    def show_options(self):
        self.options_menu.popup(self.options_button.mapToGlobal(
            QPoint(0, self.options_button.height())
        ))

    def request_edit(self, *_args):
        self.edit_requested.emit(self.book)

    def request_move(self, *_args):
        self.move_requested.emit(self.book)

    def request_remove(self, *_args):
        self.remove_requested.emit(self.book)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.open_book()
            event.accept()
            return
        super().mousePressEvent(event)
