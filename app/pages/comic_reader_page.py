from pathlib import Path
import time

from PySide6.QtCore import (
    Qt,
    Signal,
    QTimer,
    QEvent,
)

from PySide6.QtGui import (
    QPixmap,
    QShortcut,
    QKeySequence,
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QListWidget,
    QFrame,
    QStackedWidget,
    QMessageBox,
)

from app.database.books_repository import (
    get_comic_chapters,
)

from app.services.cbz_service import (
    get_cbz_pages,
    read_cbz_page,
    natural_sort_key,
)

from app.services.progress_service import (
    get_progress,
    save_progress,
)

from app.services.settings_service import (
    get_setting,
    set_setting,
)


class ComicReaderPage(QWidget):

    back_requested = Signal()

    # ========================================================
    # ZOOM
    # ========================================================

    MIN_ZOOM = 10
    MAX_ZOOM = 250
    ZOOM_STEP = 10
    DEFAULT_ZOOM = 50

    # "auto" preserves the previous Manga / Manhwa defaults.
    PAGED_MODES = frozenset(("paged_ltr", "paged_rtl", "paged_vertical"))
    READING_MODE_NAMES = {
        "paged_ltr": "Paged (left to right)",
        "paged_rtl": "Paged (right to left)",
        "paged_vertical": "Paged (vertical)",
        "long_strip": "Long strip",
        "long_strip_gaps": "Long strip with gaps",
    }

    def __init__(self):
        super().__init__()

        # ====================================================
        # BOOK STATE
        # ====================================================

        self.book = None
        self.category = "manga"
        self.reading_mode = "paged_ltr"
        self._last_vertical_wheel_time = 0.0

        self.chapters = []

        self.current_chapter = 0
        self.current_page = 0

        self.current_page_names = []

        # ====================================================
        # MANGA CACHE
        # ====================================================

        self.original_manga_pixmap = None

        # ====================================================
        # MANHWA CACHE
        # ====================================================

        self.manhwa_original_pixmaps = []
        self.manhwa_page_labels = []

        self.cached_manhwa_chapter_path = None

        self.current_manhwa_render_width = None

        # Used to cancel an old high-quality render
        # when another zoom operation begins.
        self.render_generation = 0

        self.quality_refine_index = 0

        # ====================================================
        # SCROLL STATE
        # ====================================================

        self.is_restoring_scroll = False

        # ====================================================
        # SAVED ZOOM
        # ====================================================

        try:
            self.zoom_percent = int(
                get_setting(
                    "comic_zoom",
                    self.DEFAULT_ZOOM,
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            self.zoom_percent = (
                self.DEFAULT_ZOOM
            )

        self.zoom_percent = max(
            self.MIN_ZOOM,
            min(
                self.zoom_percent,
                self.MAX_ZOOM,
            ),
        )

        self.pending_zoom_percent = (
            self.zoom_percent
        )

        # ====================================================
        # ZOOM DEBOUNCE
        # ====================================================
        #
        # Rapid mouse-wheel events are combined.
        # We do not resize every image for every wheel tick.
        # ====================================================

        self.zoom_timer = QTimer(
            self
        )

        self.zoom_timer.setSingleShot(
            True
        )

        self.zoom_timer.setInterval(
            100
        )

        self.zoom_timer.timeout.connect(
            self.apply_pending_zoom
        )

        # ====================================================
        # HIGH QUALITY TIMER
        # ====================================================
        #
        # While zooming:
        #     fast rendering
        #
        # After zooming stops:
        #     smooth high-quality rendering
        # ====================================================

        self.quality_render_timer = QTimer(
            self
        )

        self.quality_render_timer.setSingleShot(
            True
        )

        self.quality_render_timer.setInterval(
            220
        )

        self.quality_render_timer.timeout.connect(
            self.apply_high_quality_zoom
        )

        # ====================================================
        # PROGRESS TIMER
        # ====================================================

        self.scroll_save_timer = QTimer(
            self
        )

        self.scroll_save_timer.setSingleShot(
            True
        )

        self.scroll_save_timer.setInterval(
            500
        )

        self.scroll_save_timer.timeout.connect(
            self.save_current_progress
        )

        # ====================================================
        # WINDOW RESIZE TIMER
        # ====================================================

        self.resize_render_timer = QTimer(
            self
        )

        self.resize_render_timer.setSingleShot(
            True
        )

        self.resize_render_timer.setInterval(
            160
        )

        self.resize_render_timer.timeout.connect(
            self.apply_resize_render
        )

        # ====================================================
        # BUILD
        # ====================================================

        self.build_ui()
        self.setup_shortcuts()

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        main_layout = QVBoxLayout(
            self
        )

        main_layout.setContentsMargins(
            20,
            15,
            20,
            15,
        )

        main_layout.setSpacing(
            10
        )

        # ====================================================
        # TOP BAR
        # ====================================================

        top_layout = QHBoxLayout()

        self.back_button = QPushButton(
            "← Back to Library"
        )

        self.back_button.setCursor(
            Qt.PointingHandCursor
        )

        self.back_button.clicked.connect(
            self.go_back
        )

        self.contents_button = QPushButton(
            "☰ Contents"
        )

        self.contents_button.setCursor(
            Qt.PointingHandCursor
        )

        self.contents_button.clicked.connect(
            self.toggle_contents
        )

        self.book_title = QLabel(
            "Comic Reader"
        )

        self.book_title.setObjectName(
            "readerBookTitle"
        )

        self.mode_label = QLabel()

        self.mode_label.setObjectName(
            "secondaryLabel"
        )

        top_layout.addWidget(
            self.back_button
        )

        top_layout.addWidget(
            self.contents_button
        )

        top_layout.addSpacing(
            15
        )

        top_layout.addWidget(
            self.book_title
        )

        top_layout.addStretch()

        top_layout.addWidget(
            self.mode_label
        )

        # ====================================================
        # ZOOM BAR
        # ====================================================

        zoom_layout = QHBoxLayout()

        zoom_layout.addStretch()

        zoom_text = QLabel(
            "Zoom"
        )

        zoom_text.setObjectName(
            "secondaryLabel"
        )

        zoom_layout.addWidget(
            zoom_text
        )

        # ====================================================
        # ZOOM OUT
        # ====================================================

        self.zoom_out_button = QPushButton(
            "−"
        )

        self.zoom_out_button.setFixedSize(
            38,
            34,
        )

        self.zoom_out_button.setCursor(
            Qt.PointingHandCursor
        )

        self.zoom_out_button.setToolTip(
            "Zoom out (Ctrl + Mouse Wheel Down)"
        )

        self.zoom_out_button.clicked.connect(
            self.zoom_out
        )

        # ====================================================
        # ZOOM PERCENTAGE
        # ====================================================

        self.zoom_label = QLabel()

        self.zoom_label.setObjectName(
            "secondaryLabel"
        )

        self.zoom_label.setAlignment(
            Qt.AlignCenter
        )

        self.zoom_label.setMinimumWidth(
            60
        )

        # ====================================================
        # ZOOM IN
        # ====================================================

        self.zoom_in_button = QPushButton(
            "+"
        )

        self.zoom_in_button.setFixedSize(
            38,
            34,
        )

        self.zoom_in_button.setCursor(
            Qt.PointingHandCursor
        )

        self.zoom_in_button.setToolTip(
            "Zoom in (Ctrl + Mouse Wheel Up)"
        )

        self.zoom_in_button.clicked.connect(
            self.zoom_in
        )

        # ====================================================
        # RESET
        # ====================================================

        self.zoom_reset_button = QPushButton(
            "Reset"
        )

        self.zoom_reset_button.setFixedHeight(
            34
        )

        self.zoom_reset_button.setCursor(
            Qt.PointingHandCursor
        )

        self.zoom_reset_button.setToolTip(
            "Reset zoom to 100% (Ctrl+0)"
        )

        self.zoom_reset_button.clicked.connect(
            self.reset_zoom
        )

        zoom_layout.addWidget(
            self.zoom_out_button
        )

        zoom_layout.addWidget(
            self.zoom_label
        )

        zoom_layout.addWidget(
            self.zoom_in_button
        )

        zoom_layout.addWidget(
            self.zoom_reset_button
        )

        self.update_zoom_controls()

        # ====================================================
        # READER AREA
        # ====================================================

        reading_layout = QHBoxLayout()

        reading_layout.setSpacing(
            10
        )

        # ====================================================
        # CONTENTS PANEL
        # ====================================================

        self.contents_panel = QFrame()

        self.contents_panel.setObjectName(
            "tocPanel"
        )

        self.contents_panel.setFixedWidth(
            280
        )

        contents_layout = QVBoxLayout(
            self.contents_panel
        )

        contents_layout.setContentsMargins(
            10,
            12,
            10,
            10,
        )

        contents_title = QLabel(
            "Chapters"
        )

        contents_title.setObjectName(
            "sectionTitle"
        )

        self.chapter_list = QListWidget()

        self.chapter_list.currentRowChanged.connect(
            self.jump_to_chapter
        )

        contents_layout.addWidget(
            contents_title
        )

        contents_layout.addWidget(
            self.chapter_list,
            1,
        )

        self.contents_panel.hide()

        # ====================================================
        # READER STACK
        # ====================================================

        self.reader_stack = QStackedWidget()

        # ====================================================
        # MANGA MODE
        # ====================================================

        self.manga_scroll = QScrollArea()

        self.manga_scroll.setWidgetResizable(
            False
        )

        self.manga_scroll.setAlignment(
            Qt.AlignCenter
        )

        self.manga_scroll.setFrameShape(
            QFrame.NoFrame
        )

        self.manga_image = QLabel()

        self.manga_image.setAlignment(
            Qt.AlignCenter
        )

        self.manga_scroll.setWidget(
            self.manga_image
        )

        # Forward clicks on the displayed image to its scroll-area viewport.
        # This makes the whole left/right half of the reading area clickable,
        # including the visible image when it is larger than the viewport.
        self.manga_image.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.manga_scroll.viewport().installEventFilter(self)

        # ====================================================
        # MANHWA MODE
        # ====================================================

        self.manhwa_scroll = QScrollArea()

        self.manhwa_scroll.setWidgetResizable(
            True
        )

        self.manhwa_scroll.setFrameShape(
            QFrame.NoFrame
        )

        self.manhwa_container = QWidget()

        self.manhwa_layout = QVBoxLayout(
            self.manhwa_container
        )

        self.manhwa_layout.setContentsMargins(
            20,
            10,
            20,
            10,
        )

        self.manhwa_layout.setSpacing(
            4
        )

        self.manhwa_layout.setAlignment(
            Qt.AlignTop
            | Qt.AlignHCenter
        )

        self.manhwa_scroll.setWidget(
            self.manhwa_container
        )

        self.manhwa_scroll.viewport().installEventFilter(
            self
        )

        self.manhwa_scroll.verticalScrollBar().valueChanged.connect(
            self.on_manhwa_scroll
        )

        # ====================================================
        # ADD READERS
        # ====================================================

        self.reader_stack.addWidget(
            self.manga_scroll
        )

        self.reader_stack.addWidget(
            self.manhwa_scroll
        )

        reading_layout.addWidget(
            self.contents_panel
        )

        reading_layout.addWidget(
            self.reader_stack,
            1,
        )

        # ====================================================
        # BOTTOM NAVIGATION
        # ====================================================

        navigation_layout = QHBoxLayout()

        self.previous_button = QPushButton(
            "← Previous"
        )

        self.previous_button.setCursor(
            Qt.PointingHandCursor
        )

        self.previous_button.clicked.connect(
            self.previous_item
        )

        self.position_label = QLabel(
            "No chapter"
        )

        self.position_label.setObjectName(
            "secondaryLabel"
        )

        self.position_label.setAlignment(
            Qt.AlignCenter
        )

        self.next_button = QPushButton(
            "Next →"
        )

        self.next_button.setCursor(
            Qt.PointingHandCursor
        )

        self.next_button.clicked.connect(
            self.next_item
        )

        navigation_layout.addWidget(
            self.previous_button
        )

        navigation_layout.addStretch()

        navigation_layout.addWidget(
            self.position_label
        )

        navigation_layout.addStretch()

        navigation_layout.addWidget(
            self.next_button
        )

        # ====================================================
        # FINAL
        # ====================================================

        main_layout.addLayout(
            top_layout
        )

        main_layout.addLayout(
            zoom_layout
        )

        main_layout.addLayout(
            reading_layout,
            1,
        )

        main_layout.addLayout(
            navigation_layout
        )
        self.navigation_layout = navigation_layout

    # ========================================================
    # CTRL + MOUSE WHEEL
    # ========================================================

    def eventFilter(self, watched, event):
        # Click the left/right half of a paged Manga to turn its page.
        # The selected reading direction controls which side advances:
        # LTR = right next / left previous; RTL = left next / right previous.
        # Do not intercept clicks in vertical or long-strip reading modes.
        if (
            watched is self.manga_scroll.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and self.book is not None
            and self.reading_mode in ("paged_ltr", "paged_rtl")
            and self.current_page_names
        ):
            midpoint = self.manga_scroll.viewport().width() / 2
            side = "left" if event.position().x() < midpoint else "right"
            self.navigate_by_arrow(side)
            event.accept()
            return True

        viewports = (self.manga_scroll.viewport(), self.manhwa_scroll.viewport())
        if watched in viewports and event.type() == QEvent.Type.Wheel:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if delta:
                    self.queue_zoom(self.ZOOM_STEP if delta > 0 else -self.ZOOM_STEP)
                event.accept()
                return True

            # Paged vertical: scroll within a zoomed page normally. At a page
            # boundary, use the wheel to move to the preceding/next page.
            if (watched is self.manga_scroll.viewport()
                    and self.is_paged()
                    and self.reading_mode == "paged_vertical"
                    and delta):
                bar = self.manga_scroll.verticalScrollBar()
                at_edge = ((delta < 0 and bar.value() >= bar.maximum())
                           or (delta > 0 and bar.value() <= bar.minimum()))
                if at_edge:
                    now = time.monotonic()
                    if now - self._last_vertical_wheel_time >= 0.38:
                        self._last_vertical_wheel_time = now
                        if delta < 0:
                            self.next_item()
                        else:
                            self.previous_item()
                    event.accept()
                    return True

        return super().eventFilter(watched, event)

    # ========================================================
    # SHORTCUTS
    # ========================================================

    def setup_shortcuts(self):

        self.zoom_in_shortcut = QShortcut(
            QKeySequence(
                "Ctrl++"
            ),
            self,
        )

        self.zoom_in_shortcut.activated.connect(
            self.zoom_in
        )

        self.zoom_in_alt_shortcut = QShortcut(
            QKeySequence(
                "Ctrl+="
            ),
            self,
        )

        self.zoom_in_alt_shortcut.activated.connect(
            self.zoom_in
        )

        self.zoom_out_shortcut = QShortcut(
            QKeySequence(
                "Ctrl+-"
            ),
            self,
        )

        self.zoom_out_shortcut.activated.connect(
            self.zoom_out
        )

        self.zoom_reset_shortcut = QShortcut(
            QKeySequence(
                "Ctrl+0"
            ),
            self,
        )

        self.zoom_reset_shortcut.activated.connect(
            self.reset_zoom
        )

        # Arrow shortcuts are scoped to the single-page reader. They do not
        # interfere with the Contents chapter list or long-strip scrolling.
        for key, direction in (("Left", "left"), ("Right", "right"),
                               ("Up", "up"), ("Down", "down")):
            shortcut = QShortcut(QKeySequence(key), self.manga_scroll)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(
                lambda d=direction: self.navigate_by_arrow(d)
            )

    # ========================================================
    # ZOOM IN
    # ========================================================

    def zoom_in(self):

        self.queue_zoom(
            self.ZOOM_STEP
        )

    # ========================================================
    # ZOOM OUT
    # ========================================================

    def zoom_out(self):

        self.queue_zoom(
            -self.ZOOM_STEP
        )

    # ========================================================
    # RESET ZOOM
    # ========================================================

    def reset_zoom(self):

        self.zoom_timer.stop()

        self.cancel_quality_render()

        self.pending_zoom_percent = (
            self.DEFAULT_ZOOM
        )

        self.apply_pending_zoom()

    # ========================================================
    # CANCEL OLD QUALITY RENDER
    # ========================================================

    def cancel_quality_render(self):

        self.quality_render_timer.stop()

        # Invalidate any page-by-page Manhwa
        # refinement that is still running.
        self.render_generation += 1

    # ========================================================
    # QUEUE ZOOM
    # ========================================================

    def queue_zoom(
        self,
        amount,
    ):

        self.cancel_quality_render()

        self.pending_zoom_percent = max(
            self.MIN_ZOOM,
            min(
                self.pending_zoom_percent
                + amount,
                self.MAX_ZOOM,
            ),
        )

        # Show the requested percentage immediately.
        self.zoom_label.setText(
            f"{self.pending_zoom_percent}%"
        )

        self.zoom_out_button.setEnabled(
            self.pending_zoom_percent
            > self.MIN_ZOOM
        )

        self.zoom_in_button.setEnabled(
            self.pending_zoom_percent
            < self.MAX_ZOOM
        )

        self.zoom_reset_button.setEnabled(
            self.pending_zoom_percent
            != self.DEFAULT_ZOOM
        )

        # Every new wheel event restarts this timer.
        # The expensive image resize happens only
        # once the wheel pauses.
        self.zoom_timer.start()

    # ========================================================
    # APPLY ZOOM
    # ========================================================

    def apply_pending_zoom(self):

        new_zoom = max(
            self.MIN_ZOOM,
            min(
                int(
                    self.pending_zoom_percent
                ),
                self.MAX_ZOOM,
            ),
        )

        if (
            new_zoom
            == self.zoom_percent
        ):

            self.update_zoom_controls()

            return

        # ====================================================
        # PRESERVE MANHWA POSITION
        # ====================================================

        if not self.is_paged():

            position = (
                self.get_manhwa_scroll_position()
            )

        else:

            position = None

        self.zoom_percent = (
            new_zoom
        )

        # ====================================================
        # SAVE ZOOM SETTING
        # ====================================================

        set_setting(
            "comic_zoom",
            self.zoom_percent,
        )

        self.update_zoom_controls()

        # ====================================================
        # FAST PREVIEW
        # ====================================================

        if self.is_paged():

            if (
                self.original_manga_pixmap
                is not None
            ):

                self.apply_manga_zoom(
                    smooth=False
                )

        elif not self.is_paged():

            if self.manhwa_original_pixmaps:

                self.apply_manhwa_zoom(
                    position=position,
                    smooth=False,
                )

        self.update_position_label()

        # ====================================================
        # HIGH QUALITY PASS
        # ====================================================

        self.quality_render_timer.start()

    # ========================================================
    # HIGH QUALITY FINAL RENDER
    # ========================================================

    def apply_high_quality_zoom(self):

        if self.book is None:

            return

        # ====================================================
        # MANGA
        # ====================================================

        if self.is_paged():

            if (
                self.original_manga_pixmap
                is not None
            ):

                self.apply_manga_zoom(
                    smooth=True
                )

        # ====================================================
        # MANHWA
        # ====================================================

        elif not self.is_paged():

            if self.manhwa_original_pixmaps:

                self.start_manhwa_quality_refinement()

    # ========================================================
    # UPDATE ZOOM UI
    # ========================================================

    def update_zoom_controls(self):

        self.pending_zoom_percent = (
            self.zoom_percent
        )

        self.zoom_label.setText(
            f"{self.zoom_percent}%"
        )

        self.zoom_out_button.setEnabled(
            self.zoom_percent
            > self.MIN_ZOOM
        )

        self.zoom_in_button.setEnabled(
            self.zoom_percent
            < self.MAX_ZOOM
        )

        self.zoom_reset_button.setEnabled(
            self.zoom_percent
            != self.DEFAULT_ZOOM
        )

    # ========================================================
    # SAFE BOOK VALUE
    # ========================================================

    # ========================================================
    # SAVED COMIC READING MODE
    # ========================================================

    def is_paged(self):
        return self.reading_mode in self.PAGED_MODES

    def resolve_reading_mode(self):
        choice = str(get_setting("comic_reading_mode", "auto") or "auto")
        if choice not in self.READING_MODE_NAMES and choice != "auto":
            choice = "auto"
        if choice == "auto":
            return "long_strip" if self.category == "manhwa" else "paged_ltr"
        return choice

    def configure_reading_mode(self):
        """Select the reader and navigation direction for this book."""
        paged = self.is_paged()
        self.reader_stack.setCurrentWidget(
            self.manga_scroll if paged else self.manhwa_scroll
        )
        label = self.READING_MODE_NAMES.get(self.reading_mode, "Paged")
        self.mode_label.setText(f"{self.category.title()} • {label}")

        # No seams in Long strip; intentional spacing in the gaps mode.
        gaps = self.reading_mode == "long_strip_gaps"
        self.manhwa_layout.setSpacing(14 if gaps else 0)
        self.manhwa_layout.setContentsMargins(20, 10 if gaps else 0,
                                             20, 10 if gaps else 0)

        # Right-to-left manga: the Next control lives on the left; Previous
        # on the right. Buttons are hidden before moving them within the same
        # parent layout so they cannot momentarily become floating windows.
        self.previous_button.hide()
        self.next_button.hide()
        self.navigation_layout.removeWidget(self.previous_button)
        self.navigation_layout.removeWidget(self.next_button)
        if self.reading_mode == "paged_rtl":
            self.next_button.setText("← Next")
            self.previous_button.setText("Previous →")
            self.navigation_layout.insertWidget(0, self.next_button)
            self.navigation_layout.addWidget(self.previous_button)
        else:
            vertical = self.reading_mode == "paged_vertical"
            self.previous_button.setText("↑ Previous" if vertical else "← Previous")
            self.next_button.setText("↓ Next" if vertical else "Next →")
            self.navigation_layout.insertWidget(0, self.previous_button)
            self.navigation_layout.addWidget(self.next_button)
        self.previous_button.show()
        self.next_button.show()

    def navigate_by_arrow(self, direction):
        if not self.is_paged() or self.book is None:
            return
        if self.reading_mode == "paged_ltr":
            operation = ("previous" if direction == "left" else "next"
                         if direction == "right" else None)
        elif self.reading_mode == "paged_rtl":
            operation = ("next" if direction == "left" else "previous"
                         if direction == "right" else None)
        else:
            operation = ("previous" if direction == "up" else "next"
                         if direction == "down" else None)
        if operation == "previous":
            self.previous_item()
        elif operation == "next":
            self.next_item()

    def book_value(
        self,
        key,
        default=None,
    ):

        if self.book is None:

            return default

        try:

            if key in self.book.keys():

                value = self.book[
                    key
                ]

                if value is not None:

                    return value

        except Exception:

            pass

        return default

    # ========================================================
    # SAFE PROGRESS VALUE
    # ========================================================

    def progress_value(
        self,
        progress,
        key,
        default=None,
    ):

        if progress is None:

            return default

        try:

            if isinstance(
                progress,
                dict,
            ):

                return progress.get(
                    key,
                    default,
                )

            if (
                hasattr(
                    progress,
                    "keys",
                )
                and key in progress.keys()
            ):

                value = progress[
                    key
                ]

                if value is not None:

                    return value

        except Exception:

            pass

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

        self.zoom_timer.stop()
        self.scroll_save_timer.stop()
        self.resize_render_timer.stop()

        self.cancel_quality_render()

        self.book = book

        # ====================================================
        # CLEAR OLD CACHE
        # ====================================================

        self.original_manga_pixmap = None

        self.clear_manhwa_cache()

        # ====================================================
        # CATEGORY
        # ====================================================

        self.category = str(
            self.book_value(
                "category",
                "manga",
            )
        ).lower()

        if self.category not in [
            "manga",
            "manhwa",
        ]:

            self.category = "manga"

        # ====================================================
        # TITLE
        # ====================================================

        self.book_title.setText(
            str(
                self.book_value(
                    "title",
                    "Comic",
                )
            )
        )

        # ====================================================
        # MODE
        # ====================================================

        self.reading_mode = self.resolve_reading_mode()
        self.configure_reading_mode()

        # ====================================================
        # LOAD CHAPTERS
        # ====================================================

        self.chapters = list(
            get_comic_chapters(
                self.book[
                    "id"
                ]
            )
        )

        # Older imported comic.
        if not self.chapters:

            self.chapters = (
                self.scan_comic_files()
            )

        if not self.chapters:

            QMessageBox.critical(
                self,
                "Comic Reader Error",
                (
                    "No CBZ chapters were found "
                    "for this Manga/Manhwa."
                ),
            )

            return

        # ====================================================
        # RESTORE PROGRESS
        # ====================================================

        progress = get_progress(
            self.book[
                "id"
            ]
        )

        try:

            chapter_index = int(
                self.progress_value(
                    progress,
                    "chapter_index",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            chapter_index = 0

        try:

            position = float(
                self.progress_value(
                    progress,
                    "position",
                    0.0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            position = 0.0

        self.current_chapter = max(
            0,
            min(
                chapter_index,
                len(
                    self.chapters
                ) - 1,
            ),
        )

        position = max(
            0.0,
            min(
                position,
                1.0,
            ),
        )

        self.populate_contents()

        self.load_current_chapter(
            position=position
        )

    # ========================================================
    # SCAN OLD COMIC IMPORTS
    # ========================================================

    def scan_comic_files(self):

        file_path = (
            self.book_value(
                "file_path"
            )
            or self.book_value(
                "epub_path"
            )
        )

        if not file_path:

            return []

        path = Path(
            file_path
        )

        # ====================================================
        # SINGLE CBZ
        # ====================================================

        if (
            path.is_file()
            and path.suffix.lower()
            == ".cbz"
        ):

            try:

                pages = get_cbz_pages(
                    path
                )

                page_count = len(
                    pages
                )

            except Exception:

                page_count = 0

            return [
                {
                    "chapter_index": 0,
                    "title": path.stem,
                    "file_path": str(
                        path
                    ),
                    "page_count": page_count,
                }
            ]

        # ====================================================
        # CBZ FOLDER
        # ====================================================

        if path.is_dir():

            files = [
                item
                for item in path.iterdir()
                if (
                    item.is_file()
                    and item.suffix.lower()
                    == ".cbz"
                )
            ]

            files.sort(
                key=lambda item: (
                    natural_sort_key(
                        item.name
                    )
                )
            )

            chapters = []

            for index, item in enumerate(
                files
            ):

                try:

                    pages = get_cbz_pages(
                        item
                    )

                    page_count = len(
                        pages
                    )

                except Exception:

                    page_count = 0

                chapters.append(
                    {
                        "chapter_index": index,
                        "title": item.stem,
                        "file_path": str(
                            item
                        ),
                        "page_count": page_count,
                    }
                )

            return chapters

        return []

    # ========================================================
    # CHAPTER LIST
    # ========================================================

    def populate_contents(self):

        self.chapter_list.blockSignals(
            True
        )

        self.chapter_list.clear()

        for index, chapter in enumerate(
            self.chapters
        ):

            try:

                title = chapter[
                    "title"
                ]

            except Exception:

                title = None

            if not title:

                title = (
                    f"Chapter {index + 1}"
                )

            self.chapter_list.addItem(
                str(title)
            )

        self.chapter_list.setCurrentRow(
            self.current_chapter
        )

        self.chapter_list.blockSignals(
            False
        )

    # ========================================================
    # CURRENT CHAPTER
    # ========================================================

    def current_chapter_path(self):

        if not self.chapters:

            return None

        chapter = self.chapters[
            self.current_chapter
        ]

        return Path(
            chapter[
                "file_path"
            ]
        )

    # ========================================================
    # LOAD CHAPTER
    # ========================================================

    def load_current_chapter(
        self,
        position=0.0,
    ):

        self.cancel_quality_render()

        chapter_path = (
            self.current_chapter_path()
        )

        if chapter_path is None:

            return

        try:

            self.current_page_names = (
                get_cbz_pages(
                    chapter_path
                )
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Comic Reader Error",
                (
                    "Could not open this CBZ chapter."
                    f"\n\n{error}"
                ),
            )

            return

        # ====================================================
        # MANHWA
        # ====================================================

        if not self.is_paged():

            self.load_manhwa_chapter(
                position
            )

        # ====================================================
        # MANGA
        # ====================================================

        else:

            if self.current_page_names:

                self.current_page = int(
                    round(
                        position
                        * (
                            len(
                                self.current_page_names
                            )
                            - 1
                        )
                    )
                )

            else:

                self.current_page = 0

            self.show_manga_page()

        self.sync_contents()

        self.update_navigation()

    # ========================================================
    # SHOW MANGA PAGE
    # ========================================================

    def show_manga_page(self):

        self.cancel_quality_render()

        if not self.current_page_names:

            return

        self.current_page = max(
            0,
            min(
                self.current_page,
                len(
                    self.current_page_names
                ) - 1,
            ),
        )

        chapter_path = (
            self.current_chapter_path()
        )

        page_name = (
            self.current_page_names[
                self.current_page
            ]
        )

        try:

            image_data = read_cbz_page(
                chapter_path,
                page_name,
            )

            pixmap = QPixmap()

            pixmap.loadFromData(
                image_data
            )

        except Exception as error:

            QMessageBox.warning(
                self,
                "Page Error",
                (
                    "Could not display "
                    "this comic page."
                    f"\n\n{error}"
                ),
            )

            return

        if pixmap.isNull():

            return

        # Keep full original quality in memory.
        self.original_manga_pixmap = (
            pixmap
        )

        # One Manga image is cheap enough to
        # display with high quality immediately.
        self.apply_manga_zoom(
            smooth=True
        )

        self.update_position_label()

    # ========================================================
    # MANGA ZOOM
    # ========================================================

    def apply_manga_zoom(
        self,
        smooth=True,
    ):

        if (
            self.original_manga_pixmap
            is None
        ):

            return

        pixmap = (
            self.original_manga_pixmap
        )

        viewport = (
            self.manga_scroll
            .viewport()
            .size()
        )

        available_width = max(
            100,
            viewport.width() - 40,
        )

        available_height = max(
            100,
            viewport.height() - 40,
        )

        original_width = (
            pixmap.width()
        )

        original_height = (
            pixmap.height()
        )

        if (
            original_width <= 0
            or original_height <= 0
        ):

            return

        # ====================================================
        # CALCULATE 100% FIT SIZE
        # ====================================================

        fit_scale = min(
            available_width
            / original_width,
            available_height
            / original_height,
        )

        base_width = max(
            1,
            int(
                original_width
                * fit_scale
            ),
        )

        base_height = max(
            1,
            int(
                original_height
                * fit_scale
            ),
        )

        # ====================================================
        # USER ZOOM
        # ====================================================

        zoom_factor = (
            self.zoom_percent
            / 100.0
        )

        target_width = max(
            1,
            int(
                base_width
                * zoom_factor
            ),
        )

        target_height = max(
            1,
            int(
                base_height
                * zoom_factor
            ),
        )

        transformation = (
            Qt.SmoothTransformation
            if smooth
            else Qt.FastTransformation
        )

        scaled_pixmap = pixmap.scaled(
            target_width,
            target_height,
            Qt.KeepAspectRatio,
            transformation,
        )

        self.manga_image.setPixmap(
            scaled_pixmap
        )

        self.manga_image.setFixedSize(
            scaled_pixmap.size()
        )

    # ========================================================
    # CLEAR MANHWA WIDGETS
    # ========================================================

    def clear_manhwa_widgets(self):

        while self.manhwa_layout.count():

            item = (
                self.manhwa_layout.takeAt(
                    0
                )
            )

            widget = item.widget()

            if widget:

                widget.deleteLater()

    # ========================================================
    # CLEAR MANHWA CACHE
    # ========================================================

    def clear_manhwa_cache(self):

        self.cancel_quality_render()

        self.clear_manhwa_widgets()

        self.manhwa_original_pixmaps = []

        self.manhwa_page_labels = []

        self.cached_manhwa_chapter_path = (
            None
        )

        self.current_manhwa_render_width = (
            None
        )

        self.quality_refine_index = 0

    # ========================================================
    # MANHWA POSITION
    # ========================================================

    def get_manhwa_scroll_position(self):

        scroll_bar = (
            self.manhwa_scroll
            .verticalScrollBar()
        )

        maximum = (
            scroll_bar.maximum()
        )

        if maximum <= 0:

            return 0.0

        return (
            scroll_bar.value()
            / maximum
        )

    # ========================================================
    # MANHWA TARGET WIDTH
    # ========================================================

    def get_manhwa_target_width(self):

        viewport_width = max(
            100,
            (
                self.manhwa_scroll
                .viewport()
                .width()
                - 60
            ),
        )

        # At 100%, Manhwa will not exceed 900px.
        base_width = min(
            900,
            viewport_width,
        )

        zoom_factor = (
            self.zoom_percent
            / 100.0
        )

        # 10% must actually be allowed to become
        # very small, unlike the older 250px minimum.
        target_width = max(
            60,
            int(
                base_width
                * zoom_factor
            ),
        )

        return target_width

    # ========================================================
    # LOAD MANHWA CHAPTER
    # ========================================================

    def load_manhwa_chapter(
        self,
        position=0.0,
    ):

        position = max(
            0.0,
            min(
                float(position),
                1.0,
            ),
        )

        self.is_restoring_scroll = True

        chapter_path = (
            self.current_chapter_path()
        )

        chapter_path_string = str(
            chapter_path
        )

        # ====================================================
        # CHAPTER CHANGED
        # ====================================================

        if (
            self.cached_manhwa_chapter_path
            != chapter_path_string
        ):

            self.clear_manhwa_cache()

            self.cached_manhwa_chapter_path = (
                chapter_path_string
            )

            # =================================================
            # DECODE EACH CBZ IMAGE ONCE
            # =================================================

            for page_name in (
                self.current_page_names
            ):

                try:

                    image_data = read_cbz_page(
                        chapter_path,
                        page_name,
                    )

                    pixmap = QPixmap()

                    pixmap.loadFromData(
                        image_data
                    )

                    if pixmap.isNull():

                        continue

                    label = QLabel()

                    label.setAlignment(
                        Qt.AlignCenter
                    )

                    self.manhwa_original_pixmaps.append(
                        pixmap
                    )

                    self.manhwa_page_labels.append(
                        label
                    )

                    self.manhwa_layout.addWidget(
                        label,
                        0,
                        Qt.AlignHCenter,
                    )

                except Exception:

                    continue

            self.manhwa_layout.addStretch()

        # ====================================================
        # QUICK INITIAL DISPLAY
        # ====================================================

        self.apply_manhwa_zoom(
            position=position,
            smooth=False,
        )

        # Then refine to smooth quality once the
        # initial layout has settled.
        self.quality_render_timer.start()

    # ========================================================
    # MANHWA ZOOM
    # ========================================================

    def apply_manhwa_zoom(
        self,
        position=None,
        smooth=False,
    ):

        if not self.manhwa_original_pixmaps:

            self.is_restoring_scroll = False

            return

        if position is None:

            position = (
                self.get_manhwa_scroll_position()
            )

        position = max(
            0.0,
            min(
                float(position),
                1.0,
            ),
        )

        self.is_restoring_scroll = True

        target_width = (
            self.get_manhwa_target_width()
        )

        transformation = (
            Qt.SmoothTransformation
            if smooth
            else Qt.FastTransformation
        )

        # ====================================================
        # SCALE ORIGINAL CACHED IMAGES
        # ====================================================

        for (
            original_pixmap,
            label,
        ) in zip(
            self.manhwa_original_pixmaps,
            self.manhwa_page_labels,
        ):

            scaled = (
                original_pixmap.scaledToWidth(
                    target_width,
                    transformation,
                )
            )

            label.setPixmap(
                scaled
            )

            label.setFixedSize(
                scaled.size()
            )

        self.current_manhwa_render_width = (
            target_width
        )

        self.manhwa_container.adjustSize()

        QTimer.singleShot(
            0,
            lambda: (
                self.restore_manhwa_position(
                    position
                )
            ),
        )

        self.update_position_label()

    # ========================================================
    # START MANHWA HIGH QUALITY PASS
    # ========================================================

    def start_manhwa_quality_refinement(self):
        """
        Upgrade the fast Manhwa preview to
        SmoothTransformation one page at a time.

        This avoids one large UI freeze.
        """

        if not self.manhwa_original_pixmaps:

            return

        # Cancel any older refinement.
        self.render_generation += 1

        generation = (
            self.render_generation
        )

        self.quality_refine_index = 0

        target_width = (
            self.get_manhwa_target_width()
        )

        self.current_manhwa_render_width = (
            target_width
        )

        self.refine_next_manhwa_page(
            generation,
            target_width,
        )

    # ========================================================
    # REFINE ONE MANHWA PAGE
    # ========================================================

    def refine_next_manhwa_page(
        self,
        generation,
        target_width,
    ):
        """
        Render one page at high quality, then
        return control to Qt before doing the next.

        This keeps scrolling and controls responsive.
        """

        # A new zoom operation started.
        if (
            generation
            != self.render_generation
        ):

            return

        # Zoom changed again.
        if (
            target_width
            != self.get_manhwa_target_width()
        ):

            return

        if (
            self.quality_refine_index
            >= len(
                self.manhwa_original_pixmaps
            )
        ):

            return

        index = (
            self.quality_refine_index
        )

        original_pixmap = (
            self.manhwa_original_pixmaps[
                index
            ]
        )

        label = (
            self.manhwa_page_labels[
                index
            ]
        )

        # ====================================================
        # HIGH QUALITY SCALE FROM ORIGINAL
        # ====================================================

        scaled = (
            original_pixmap.scaledToWidth(
                target_width,
                Qt.SmoothTransformation,
            )
        )

        label.setPixmap(
            scaled
        )

        label.setFixedSize(
            scaled.size()
        )

        self.quality_refine_index += 1

        # Let Qt process scrolling, painting and input
        # before processing the next page.
        QTimer.singleShot(
            1,
            lambda: (
                self.refine_next_manhwa_page(
                    generation,
                    target_width,
                )
            ),
        )

    # ========================================================
    # RESTORE MANHWA POSITION
    # ========================================================

    def restore_manhwa_position(
        self,
        position,
    ):

        scroll_bar = (
            self.manhwa_scroll
            .verticalScrollBar()
        )

        value = int(
            scroll_bar.maximum()
            * position
        )

        scroll_bar.setValue(
            value
        )

        self.is_restoring_scroll = False

    # ========================================================
    # MANHWA SCROLL
    # ========================================================

    def on_manhwa_scroll(
        self,
        _value,
    ):

        if self.is_paged():

            return

        if self.is_restoring_scroll:

            return

        if self.book is None:

            return

        self.scroll_save_timer.start()

    # ========================================================
    # POSITION LABEL
    # ========================================================

    def update_position_label(self):

        if not self.chapters:

            return

        chapter = self.chapters[
            self.current_chapter
        ]

        try:

            chapter_title = (
                chapter[
                    "title"
                ]
            )

        except Exception:

            chapter_title = (
                f"Chapter "
                f"{self.current_chapter + 1}"
            )

        # ====================================================
        # MANHWA
        # ====================================================

        if not self.is_paged():

            self.position_label.setText(
                (
                    f"{chapter_title}"
                    f"   •   "
                    f"Chapter "
                    f"{self.current_chapter + 1}"
                    f" / "
                    f"{len(self.chapters)}"
                    f"   •   "
                    f"{self.zoom_percent}%"
                )
            )

        # ====================================================
        # MANGA
        # ====================================================

        else:

            self.position_label.setText(
                (
                    f"{chapter_title}"
                    f"   •   "
                    f"Chapter "
                    f"{self.current_chapter + 1}"
                    f" / "
                    f"{len(self.chapters)}"
                    f"   •   "
                    f"Page "
                    f"{self.current_page + 1}"
                    f" / "
                    f"{len(self.current_page_names)}"
                    f"   •   "
                    f"{self.zoom_percent}%"
                )
            )

    # ========================================================
    # PREVIOUS
    # ========================================================

    def previous_item(self):

        if not self.chapters:

            return

        # ====================================================
        # MANGA
        # ====================================================

        if self.is_paged():

            if self.current_page > 0:

                self.current_page -= 1

                self.show_manga_page()

                self.save_current_progress()

                self.update_navigation()

                return

            if self.current_chapter > 0:

                self.current_chapter -= 1

                self.load_current_chapter(
                    position=1.0
                )

                self.save_current_progress()

            return

        # ====================================================
        # MANHWA
        # ====================================================

        if self.current_chapter > 0:

            self.save_current_progress()

            self.current_chapter -= 1

            self.load_current_chapter(
                position=0.0
            )

    # ========================================================
    # NEXT
    # ========================================================

    def next_item(self):

        if not self.chapters:

            return

        # ====================================================
        # MANGA
        # ====================================================

        if self.is_paged():

            if (
                self.current_page
                < len(
                    self.current_page_names
                ) - 1
            ):

                self.current_page += 1

                self.show_manga_page()

                self.save_current_progress()

                self.update_navigation()

                return

            if (
                self.current_chapter
                < len(
                    self.chapters
                ) - 1
            ):

                self.current_chapter += 1

                self.load_current_chapter(
                    position=0.0
                )

                self.save_current_progress()

            return

        # ====================================================
        # MANHWA
        # ====================================================

        if (
            self.current_chapter
            < len(
                self.chapters
            ) - 1
        ):

            self.save_current_progress()

            self.current_chapter += 1

            self.load_current_chapter(
                position=0.0
            )

    # ========================================================
    # JUMP TO CHAPTER
    # ========================================================

    def jump_to_chapter(
        self,
        index,
    ):

        if index < 0:

            return

        if index >= len(
            self.chapters
        ):

            return

        if (
            index
            == self.current_chapter
        ):

            return

        self.save_current_progress()

        self.current_chapter = (
            index
        )

        self.current_page = 0

        self.load_current_chapter(
            position=0.0
        )

    # ========================================================
    # CONTENTS
    # ========================================================

    def toggle_contents(self):

        visible = (
            self.contents_panel.isVisible()
        )

        self.contents_panel.setVisible(
            not visible
        )

        if visible:

            self.contents_button.setText(
                "☰ Contents"
            )

        else:

            self.contents_button.setText(
                "✕ Contents"
            )

    # ========================================================
    # SYNC CONTENTS
    # ========================================================

    def sync_contents(self):

        self.chapter_list.blockSignals(
            True
        )

        self.chapter_list.setCurrentRow(
            self.current_chapter
        )

        self.chapter_list.blockSignals(
            False
        )

    # ========================================================
    # NAVIGATION
    # ========================================================

    def update_navigation(self):

        if not self.chapters:

            self.previous_button.setEnabled(
                False
            )

            self.next_button.setEnabled(
                False
            )

            return

        # ====================================================
        # MANGA
        # ====================================================

        if self.is_paged():

            can_previous = (
                self.current_page > 0
                or self.current_chapter > 0
            )

            can_next = (
                self.current_page
                < len(
                    self.current_page_names
                ) - 1
                or
                self.current_chapter
                < len(
                    self.chapters
                ) - 1
            )

        # ====================================================
        # MANHWA
        # ====================================================

        else:

            can_previous = (
                self.current_chapter > 0
            )

            can_next = (
                self.current_chapter
                < len(
                    self.chapters
                ) - 1
            )

        self.previous_button.setEnabled(
            can_previous
        )

        self.next_button.setEnabled(
            can_next
        )

        self.update_position_label()

    # ========================================================
    # SAVE PROGRESS
    # ========================================================

    def save_current_progress(self):

        if self.book is None:

            return

        if not self.chapters:

            return

        # ====================================================
        # MANGA
        # ====================================================

        if self.is_paged():

            if (
                len(
                    self.current_page_names
                )
                > 1
            ):

                position = (
                    self.current_page
                    / (
                        len(
                            self.current_page_names
                        )
                        - 1
                    )
                )

            else:

                position = 0.0

        # ====================================================
        # MANHWA
        # ====================================================

        else:

            position = (
                self.get_manhwa_scroll_position()
            )

        save_progress(
            book_id=self.book[
                "id"
            ],
            chapter_index=self.current_chapter,
            position=position,
        )

    # ========================================================
    # WINDOW RESIZE
    # ========================================================

    def resizeEvent(
        self,
        event,
    ):

        super().resizeEvent(
            event
        )

        if self.book is None:

            return

        self.resize_render_timer.start()

    # ========================================================
    # APPLY RESIZE
    # ========================================================

    def apply_resize_render(self):

        if self.book is None:

            return

        self.cancel_quality_render()

        # ====================================================
        # MANGA
        # ====================================================

        if self.is_paged():

            if (
                self.original_manga_pixmap
                is not None
            ):

                self.apply_manga_zoom(
                    smooth=True
                )

        # ====================================================
        # MANHWA
        # ====================================================

        elif not self.is_paged():

            if self.manhwa_original_pixmaps:

                position = (
                    self.get_manhwa_scroll_position()
                )

                self.apply_manhwa_zoom(
                    position=position,
                    smooth=False,
                )

                self.quality_render_timer.start()

    # ========================================================
    # BACK
    # ========================================================

    def go_back(self):

        self.zoom_timer.stop()
        self.quality_render_timer.stop()
        self.scroll_save_timer.stop()
        self.resize_render_timer.stop()

        self.render_generation += 1

        self.save_current_progress()

        self.back_requested.emit()

    # ========================================================
    # HIDDEN
    # ========================================================

    def hideEvent(
        self,
        event,
    ):

        self.zoom_timer.stop()
        self.quality_render_timer.stop()
        self.scroll_save_timer.stop()
        self.resize_render_timer.stop()

        self.render_generation += 1

        self.save_current_progress()

        super().hideEvent(
            event
        )