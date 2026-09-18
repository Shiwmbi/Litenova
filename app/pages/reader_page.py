import re

from PySide6.QtCore import (
    Qt,
    Signal,
    QTimer,
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QMessageBox,
    QListWidget,
    QFrame,
)

from app.services.epub_service import (
    get_chapters,
)

from app.services.progress_service import (
    get_progress,
    save_progress,
)

from app.services.settings_service import (
    get_reader_font_size,
    get_reader_theme,
)


class ReaderPage(QWidget):

    back_requested = Signal()

    def __init__(self):
        super().__init__()

        self.book = None
        self.chapters = []
        self.current_chapter = 0

        self.reader_font_size = (
            get_reader_font_size()
        )

        self.reader_theme = (
            get_reader_theme()
        )

        self.is_restoring_scroll = False

        # ==========================================
        # AUTO SAVE TIMER
        # ==========================================

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

        self.build_ui()

    # ==============================================
    # BUILD UI
    # ==============================================

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

        # ==========================================
        # TOP BAR
        # ==========================================

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

        self.toc_button = QPushButton(
            "☰ Contents"
        )

        self.toc_button.setCursor(
            Qt.PointingHandCursor
        )

        self.toc_button.clicked.connect(
            self.toggle_toc
        )

        self.book_title = QLabel(
            "Reader"
        )

        self.book_title.setObjectName(
            "readerBookTitle"
        )

        top_layout.addWidget(
            self.back_button
        )

        top_layout.addWidget(
            self.toc_button
        )

        top_layout.addSpacing(
            15
        )

        top_layout.addWidget(
            self.book_title
        )

        top_layout.addStretch()

        # ==========================================
        # READING SECTION
        # ==========================================

        reading_layout = QHBoxLayout()

        reading_layout.setSpacing(
            10
        )

        # ==========================================
        # TABLE OF CONTENTS
        # ==========================================

        self.toc_panel = QFrame()

        self.toc_panel.setObjectName(
            "tocPanel"
        )

        self.toc_panel.setFixedWidth(
            280
        )

        toc_layout = QVBoxLayout(
            self.toc_panel
        )

        toc_layout.setContentsMargins(
            10,
            12,
            10,
            10,
        )

        toc_title = QLabel(
            "Table of Contents"
        )

        toc_title.setObjectName(
            "sectionTitle"
        )

        self.toc_list = QListWidget()

        self.toc_list.currentRowChanged.connect(
            self.jump_to_chapter
        )

        toc_layout.addWidget(
            toc_title
        )

        toc_layout.addWidget(
            self.toc_list,
            1,
        )

        self.toc_panel.hide()

        # ==========================================
        # READER
        # ==========================================

        self.reader = QTextBrowser()

        self.reader.setObjectName(
            "readerBrowser"
        )

        self.reader.setOpenExternalLinks(
            False
        )

        self.reader.verticalScrollBar().valueChanged.connect(
            self.on_scroll_changed
        )

        self.apply_reader_appearance()

        reading_layout.addWidget(
            self.toc_panel
        )

        reading_layout.addWidget(
            self.reader,
            1,
        )

        # ==========================================
        # BOTTOM NAVIGATION
        # ==========================================

        navigation_layout = QHBoxLayout()

        self.previous_button = QPushButton(
            "← Previous"
        )

        self.previous_button.setCursor(
            Qt.PointingHandCursor
        )

        self.previous_button.clicked.connect(
            self.previous_chapter
        )

        self.chapter_label = QLabel(
            "No chapter"
        )

        self.chapter_label.setObjectName(
            "secondaryLabel"
        )

        self.chapter_label.setAlignment(
            Qt.AlignCenter
        )

        self.next_button = QPushButton(
            "Next →"
        )

        self.next_button.setCursor(
            Qt.PointingHandCursor
        )

        self.next_button.clicked.connect(
            self.next_chapter
        )

        navigation_layout.addWidget(
            self.previous_button
        )

        navigation_layout.addStretch()

        navigation_layout.addWidget(
            self.chapter_label
        )

        navigation_layout.addStretch()

        navigation_layout.addWidget(
            self.next_button
        )

        # ==========================================
        # FINAL PAGE
        # ==========================================

        main_layout.addLayout(
            top_layout
        )

        main_layout.addLayout(
            reading_layout,
            1,
        )

        main_layout.addLayout(
            navigation_layout
        )

        self.update_navigation()

    # ==============================================
    # READER APPEARANCE
    # ==============================================

    def apply_reader_appearance(self):

        if self.reader_theme == "light":

            background = "#f7f5f0"
            foreground = "#242424"

            scrollbar_background = (
                "#e4e1da"
            )

            scrollbar_handle = (
                "#aaa7a0"
            )

        else:

            background = "#181a22"
            foreground = "#eeeeee"

            scrollbar_background = (
                "#15171e"
            )

            scrollbar_handle = (
                "#55586a"
            )

        self.reader.setStyleSheet(
            f"""
            QTextBrowser {{
                background-color: {background};

                color: {foreground};

                font-size: {self.reader_font_size}px;

                padding-top: 30px;
                padding-bottom: 30px;

                padding-left: 70px;
                padding-right: 70px;

                border: none;
            }}

            QScrollBar:vertical {{
                background-color: {scrollbar_background};

                width: 10px;
            }}

            QScrollBar::handle:vertical {{
                background-color: {scrollbar_handle};

                border-radius: 5px;
            }}
            """
        )

    # ==============================================
    # EPUB HTML APPEARANCE
    # ==============================================

    def prepare_chapter_html(
        self,
        chapter_html,
    ):

        if self.reader_theme == "light":

            background = "#f7f5f0"
            foreground = "#242424"
            secondary = "#555555"
            link_color = "#5146a8"

        else:

            background = "#181a22"
            foreground = "#eeeeee"
            secondary = "#c6c7d0"
            link_color = "#aaa4ff"

        h1_size = int(
            self.reader_font_size * 1.8
        )

        h2_size = int(
            self.reader_font_size * 1.5
        )

        h3_size = int(
            self.reader_font_size * 1.3
        )

        h4_size = int(
            self.reader_font_size * 1.15
        )

        smaller_size = max(
            10,
            self.reader_font_size - 2,
        )

        reader_css = f"""
        <style>
            html,
            body {{
                background-color: {background} !important;

                color: {foreground} !important;

                font-size: {self.reader_font_size}px !important;

                line-height: 1.7 !important;
            }}

            p,
            div,
            span,
            li,
            td,
            th,
            blockquote,
            section,
            article {{
                color: {foreground} !important;

                font-size: {self.reader_font_size}px !important;

                line-height: 1.7 !important;
            }}

            h1 {{
                color: {foreground} !important;
                font-size: {h1_size}px !important;
            }}

            h2 {{
                color: {foreground} !important;
                font-size: {h2_size}px !important;
            }}

            h3 {{
                color: {foreground} !important;
                font-size: {h3_size}px !important;
            }}

            h4,
            h5,
            h6 {{
                color: {foreground} !important;
                font-size: {h4_size}px !important;
            }}

            a {{
                color: {link_color} !important;
            }}

            small,
            figcaption {{
                color: {secondary} !important;
                font-size: {smaller_size}px !important;
            }}

            img {{
                max-width: 100% !important;
                height: auto !important;
            }}
        </style>
        """

        if re.search(
            r"</head>",
            chapter_html,
            flags=re.IGNORECASE,
        ):

            return re.sub(
                r"</head>",
                reader_css + "</head>",
                chapter_html,
                count=1,
                flags=re.IGNORECASE,
            )

        return (
            reader_css
            + chapter_html
        )

    # ==============================================
    # RELOAD SETTINGS
    # ==============================================

    def reload_settings(self):

        current_position = (
            self.get_current_scroll_position()
        )

        self.reader_font_size = (
            get_reader_font_size()
        )

        self.reader_theme = (
            get_reader_theme()
        )

        self.apply_reader_appearance()

        if self.chapters:

            self.display_chapter(
                position=current_position,
                save_after=False,
            )

    # ==============================================
    # OPEN BOOK
    # ==============================================

    def open_book(
        self,
        book,
    ):

        if self.book is not None:
            self.save_current_progress()

        self.scroll_save_timer.stop()

        self.reader_font_size = (
            get_reader_font_size()
        )

        self.reader_theme = (
            get_reader_theme()
        )

        self.apply_reader_appearance()

        self.book = book

        self.chapters = []

        self.current_chapter = 0

        self.reader.clear()

        self.toc_list.clear()

        try:

            self.chapters = get_chapters(
                book["epub_path"]
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Reader Error",
                (
                    "Could not open this EPUB."
                    f"\n\n{error}"
                ),
            )

            self.chapters = []

            self.chapter_label.setText(
                "No chapters"
            )

            self.update_navigation()

            return

        self.book_title.setText(
            book["title"]
        )

        self.populate_toc()

        if not self.chapters:

            self.reader.setHtml(
                "<h2>No readable chapters found.</h2>"
            )

            self.chapter_label.setText(
                "No chapters"
            )

            self.update_navigation()

            return

        progress = get_progress(
            book["id"]
        )

        try:

            saved_chapter = int(
                progress.get(
                    "chapter_index",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            saved_chapter = 0

        try:

            saved_position = float(
                progress.get(
                    "position",
                    0.0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            saved_position = 0.0

        saved_chapter = max(
            0,
            min(
                saved_chapter,
                len(self.chapters) - 1,
            ),
        )

        saved_position = max(
            0.0,
            min(
                saved_position,
                1.0,
            ),
        )

        self.current_chapter = (
            saved_chapter
        )

        self.display_chapter(
            position=saved_position,
            save_after=False,
        )

    # ==============================================
    # TOC
    # ==============================================

    def populate_toc(self):

        self.toc_list.blockSignals(
            True
        )

        self.toc_list.clear()

        for index, chapter in enumerate(
            self.chapters
        ):

            title = chapter.get(
                "title"
            )

            if not title:

                title = (
                    f"Chapter {index + 1}"
                )

            self.toc_list.addItem(
                title
            )

        if self.chapters:

            self.toc_list.setCurrentRow(
                self.current_chapter
            )

        self.toc_list.blockSignals(
            False
        )

    # ==============================================
    # DISPLAY CHAPTER
    # ==============================================

    def display_chapter(
        self,
        position=0.0,
        save_after=True,
    ):

        if not self.chapters:
            return

        chapter = self.chapters[
            self.current_chapter
        ]

        self.is_restoring_scroll = True

        formatted_html = (
            self.prepare_chapter_html(
                chapter["html"]
            )
        )

        self.reader.setHtml(
            formatted_html
        )

        chapter_title = chapter.get(
            "title",
            "",
        )

        if not chapter_title:

            chapter_title = (
                f"Chapter "
                f"{self.current_chapter + 1}"
            )

        self.chapter_label.setText(
            (
                f"{chapter_title}"
                f"   •   "
                f"{self.current_chapter + 1}"
                f" / "
                f"{len(self.chapters)}"
            )
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

        self.update_navigation()

        QTimer.singleShot(
            0,
            lambda: self.finish_chapter_display(
                position,
                save_after,
            ),
        )

    # ==============================================
    # RESTORE SCROLL
    # ==============================================

    def finish_chapter_display(
        self,
        position,
        save_after,
    ):

        scroll_bar = (
            self.reader.verticalScrollBar()
        )

        maximum = (
            scroll_bar.maximum()
        )

        value = int(
            maximum * position
        )

        scroll_bar.setValue(
            value
        )

        self.is_restoring_scroll = False

        if save_after:
            self.save_current_progress()

    # ==============================================
    # SCROLL POSITION
    # ==============================================

    def get_current_scroll_position(
        self,
    ):

        scroll_bar = (
            self.reader.verticalScrollBar()
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

    # ==============================================
    # JUMP TO CHAPTER
    # ==============================================

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

        if index == self.current_chapter:
            return

        self.save_current_progress()

        self.current_chapter = (
            index
        )

        self.display_chapter(
            position=0.0,
            save_after=True,
        )

    # ==============================================
    # PREVIOUS
    # ==============================================

    def previous_chapter(self):

        if self.current_chapter <= 0:
            return

        self.save_current_progress()

        self.current_chapter -= 1

        self.display_chapter(
            position=0.0,
            save_after=True,
        )

    # ==============================================
    # NEXT
    # ==============================================

    def next_chapter(self):

        if not self.chapters:
            return

        if (
            self.current_chapter
            >= len(self.chapters) - 1
        ):
            return

        self.save_current_progress()

        self.current_chapter += 1

        self.display_chapter(
            position=0.0,
            save_after=True,
        )

    # ==============================================
    # TOGGLE TOC
    # ==============================================

    def toggle_toc(self):

        is_visible = (
            self.toc_panel.isVisible()
        )

        self.toc_panel.setVisible(
            not is_visible
        )

        if is_visible:

            self.toc_button.setText(
                "☰ Contents"
            )

        else:

            self.toc_button.setText(
                "✕ Contents"
            )

    # ==============================================
    # SCROLL AUTO SAVE
    # ==============================================

    def on_scroll_changed(
        self,
        value,
    ):

        if self.is_restoring_scroll:
            return

        if self.book is None:
            return

        if not self.chapters:
            return

        self.scroll_save_timer.start()

    # ==============================================
    # SAVE PROGRESS
    # ==============================================

    def save_current_progress(self):

        if self.book is None:
            return

        if not self.chapters:
            return

        position = (
            self.get_current_scroll_position()
        )

        save_progress(
            book_id=self.book["id"],
            chapter_index=self.current_chapter,
            position=position,
        )

    # ==============================================
    # BACK
    # ==============================================

    def go_back(self):

        self.scroll_save_timer.stop()

        self.save_current_progress()

        self.back_requested.emit()

    # ==============================================
    # NAVIGATION STATES
    # ==============================================

    def update_navigation(self):

        has_chapters = bool(
            self.chapters
        )

        self.previous_button.setEnabled(
            has_chapters
            and self.current_chapter > 0
        )

        self.next_button.setEnabled(
            has_chapters
            and self.current_chapter
            < len(self.chapters) - 1
        )

    # ==============================================
    # PAGE HIDDEN
    # ==============================================

    def hideEvent(
        self,
        event,
    ):

        self.scroll_save_timer.stop()

        self.save_current_progress()

        super().hideEvent(
            event
        )