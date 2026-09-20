from pathlib import Path

from PySide6.QtCore import (
    Qt,
)

from PySide6.QtGui import (
    QPixmap,
)

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
)


class EditBookDialog(QDialog):

    def __init__(
        self,
        book,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.book = book

        self.selected_cover_path = None

        self.setWindowTitle(
            "Edit Book"
        )

        self.setMinimumWidth(
            500
        )

        self.build_ui()

    # ========================================================
    # SAFE VALUE
    # ========================================================

    def book_value(
        self,
        key,
        default="",
    ):

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
    # BUILD UI
    # ========================================================

    def build_ui(self):

        main_layout = QVBoxLayout(
            self
        )

        main_layout.setContentsMargins(
            22,
            22,
            22,
            22,
        )

        main_layout.setSpacing(
            16
        )

        # ====================================================
        # TITLE
        # ====================================================

        heading = QLabel(
            "Edit Library Entry"
        )

        heading.setObjectName(
            "sectionTitle"
        )

        description = QLabel(
            (
                "Change the title, author, "
                "or cover image."
            )
        )

        description.setObjectName(
            "secondaryLabel"
        )

        main_layout.addWidget(
            heading
        )

        main_layout.addWidget(
            description
        )

        # ====================================================
        # CONTENT
        # ====================================================

        content_layout = QHBoxLayout()

        content_layout.setSpacing(
            20
        )

        # ====================================================
        # COVER
        # ====================================================

        cover_layout = QVBoxLayout()

        self.cover_preview = QLabel()

        self.cover_preview.setFixedSize(
            180,
            240,
        )

        self.cover_preview.setAlignment(
            Qt.AlignCenter
        )

        self.cover_preview.setObjectName(
            "bookCover"
        )

        self.choose_cover_button = QPushButton(
            "Choose New Cover"
        )

        self.choose_cover_button.clicked.connect(
            self.choose_cover
        )

        cover_layout.addWidget(
            self.cover_preview
        )

        cover_layout.addWidget(
            self.choose_cover_button
        )

        cover_layout.addStretch()

        # ====================================================
        # FORM
        # ====================================================

        form_layout = QFormLayout()

        form_layout.setSpacing(
            14
        )

        self.title_input = QLineEdit()

        self.title_input.setText(
            str(
                self.book_value(
                    "title",
                    ""
                )
            )
        )

        self.author_input = QLineEdit()

        self.author_input.setText(
            str(
                self.book_value(
                    "author",
                    "Unknown Author",
                )
            )
        )

        form_layout.addRow(
            "Title",
            self.title_input,
        )

        form_layout.addRow(
            "Author",
            self.author_input,
        )

        form_container = QVBoxLayout()

        form_container.addLayout(
            form_layout
        )

        form_container.addStretch()

        content_layout.addLayout(
            cover_layout
        )

        content_layout.addLayout(
            form_container,
            1,
        )

        main_layout.addLayout(
            content_layout
        )

        # ====================================================
        # BUTTONS
        # ====================================================

        button_layout = QHBoxLayout()

        button_layout.addStretch()

        cancel_button = QPushButton(
            "Cancel"
        )

        save_button = QPushButton(
            "Save Changes"
        )

        save_button.setObjectName(
            "primaryButton"
        )

        cancel_button.clicked.connect(
            self.reject
        )

        save_button.clicked.connect(
            self.validate_and_accept
        )

        button_layout.addWidget(
            cancel_button
        )

        button_layout.addWidget(
            save_button
        )

        main_layout.addLayout(
            button_layout
        )

        # ====================================================
        # INITIAL COVER
        # ====================================================

        self.load_cover_preview(
            self.book_value(
                "cover_path",
                None,
            )
        )

    # ========================================================
    # COVER PREVIEW
    # ========================================================

    def load_cover_preview(
        self,
        cover_path,
    ):

        self.cover_preview.clear()

        if (
            cover_path
            and Path(
                cover_path
            ).exists()
        ):

            pixmap = QPixmap(
                str(
                    cover_path
                )
            )

            if not pixmap.isNull():

                scaled = pixmap.scaled(
                    180,
                    240,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )

                self.cover_preview.setPixmap(
                    scaled
                )

                return

        self.cover_preview.setText(
            "No Cover"
        )

    # ========================================================
    # CHOOSE COVER
    # ========================================================

    def choose_cover(self):

        file_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                "Choose Cover Image",
                "",
                (
                    "Images "
                    "(*.jpg *.jpeg *.png *.webp *.bmp)"
                ),
            )
        )

        if not file_path:
            return

        self.selected_cover_path = (
            file_path
        )

        self.load_cover_preview(
            file_path
        )

    # ========================================================
    # VALIDATE
    # ========================================================

    def validate_and_accept(self):

        title = (
            self.title_input
            .text()
            .strip()
        )

        if not title:

            QMessageBox.warning(
                self,
                "Title Required",
                (
                    "Please enter a title "
                    "for this book."
                ),
            )

            return

        self.accept()

    # ========================================================
    # VALUES
    # ========================================================

    def get_values(self):

        author = (
            self.author_input
            .text()
            .strip()
        )

        if not author:

            author = (
                "Unknown Author"
            )

        return {
            "title": (
                self.title_input
                .text()
                .strip()
            ),

            "author": author,

            "new_cover_path": (
                self.selected_cover_path
            ),
        }