from pathlib import Path

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtGui import QPixmap

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QPushButton,
)


class BookCard(QFrame):

    clicked = Signal(object)

    remove_requested = Signal(object)

    def __init__(
        self,
        book,
    ):
        super().__init__()

        self.book = book

        self.setObjectName(
            "bookCard"
        )

        self.setAttribute(
            Qt.WA_Hover,
            True,
        )

        self.setFixedWidth(
            190
        )

        self.setMinimumHeight(
            360
        )

        self.setCursor(
            Qt.PointingHandCursor
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            10,
            10,
            10,
            10,
        )

        layout.setSpacing(
            8
        )

        # ==========================================
        # COVER
        # ==========================================

        self.cover_label = QLabel()

        self.cover_label.setObjectName(
            "bookCover"
        )

        self.cover_label.setAlignment(
            Qt.AlignCenter
        )

        self.cover_label.setFixedSize(
            168,
            220,
        )

        self.cover_label.setAttribute(
            Qt.WA_TransparentForMouseEvents,
            True,
        )

        self.load_cover(
            book["cover_path"]
        )

        # ==========================================
        # TITLE
        # ==========================================

        title = (
            book["title"]
            or "Unknown Title"
        )

        self.title_label = QLabel(
            title
        )

        self.title_label.setObjectName(
            "bookTitle"
        )

        self.title_label.setWordWrap(
            True
        )

        self.title_label.setMaximumHeight(
            45
        )

        self.title_label.setAttribute(
            Qt.WA_TransparentForMouseEvents,
            True,
        )

        # ==========================================
        # AUTHOR
        # ==========================================

        author = (
            book["author"]
            or "Unknown Author"
        )

        self.author_label = QLabel(
            author
        )

        self.author_label.setObjectName(
            "bookAuthor"
        )

        self.author_label.setAttribute(
            Qt.WA_TransparentForMouseEvents,
            True,
        )

        # ==========================================
        # REMOVE
        # ==========================================

        self.remove_button = QPushButton(
            "Remove"
        )

        self.remove_button.setObjectName(
            "dangerButton"
        )

        self.remove_button.setCursor(
            Qt.PointingHandCursor
        )

        self.remove_button.clicked.connect(
            self.request_remove
        )

        # ==========================================
        # LAYOUT
        # ==========================================

        layout.addWidget(
            self.cover_label
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.author_label
        )

        layout.addStretch()

        layout.addWidget(
            self.remove_button
        )

    # ==============================================
    # COVER
    # ==============================================

    def load_cover(
        self,
        cover_path,
    ):

        if (
            cover_path
            and Path(cover_path).exists()
        ):
            pixmap = QPixmap(
                cover_path
            )

            if not pixmap.isNull():

                scaled_pixmap = pixmap.scaled(
                    168,
                    220,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )

                self.cover_label.setPixmap(
                    scaled_pixmap
                )

                return

        self.cover_label.setText(
            "EPUB"
        )

    # ==============================================
    # CLICK CARD
    # ==============================================

    def mousePressEvent(
        self,
        event,
    ):

        if (
            event.button()
            == Qt.LeftButton
        ):
            self.clicked.emit(
                self.book
            )

        super().mousePressEvent(
            event
        )

    # ==============================================
    # REMOVE
    # ==============================================

    def request_remove(self):

        self.remove_requested.emit(
            self.book
        )