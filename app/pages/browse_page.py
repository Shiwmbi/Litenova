from pathlib import Path

from PySide6.QtCore import (
    Signal,
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from app.services.import_service import (
    import_epub,
    EPUBImportError,
    DuplicateBookError,
    InvalidEPUBError,
)


class BrowsePage(QWidget):

    book_imported = Signal()

    def __init__(self):
        super().__init__()

        self.selected_file = None

        self.build_ui()

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        main_layout = QVBoxLayout(
            self
        )

        main_layout.setContentsMargins(
            30,
            30,
            30,
            30,
        )

        main_layout.setSpacing(
            15
        )

        # ====================================================
        # TITLE
        # ====================================================

        title = QLabel(
            "Browse"
        )

        title.setObjectName(
            "pageTitle"
        )

        # ====================================================
        # DESCRIPTION
        # ====================================================

        description = QLabel(
            (
                "Select an EPUB file from your "
                "computer and import it into Litenova."
            )
        )

        description.setObjectName(
            "secondaryLabel"
        )

        # ====================================================
        # FILE LABEL
        # ====================================================

        self.file_label = QLabel(
            "No EPUB selected."
        )

        self.file_label.setObjectName(
            "secondaryLabel"
        )

        self.file_label.setWordWrap(
            True
        )

        # ====================================================
        # BUTTONS
        # ====================================================

        choose_button = QPushButton(
            "Choose EPUB"
        )

        choose_button.setFixedHeight(
            40
        )

        choose_button.clicked.connect(
            self.choose_epub
        )

        self.import_button = QPushButton(
            "Import EPUB"
        )

        self.import_button.setObjectName(
            "primaryButton"
        )

        self.import_button.setFixedHeight(
            40
        )

        self.import_button.setEnabled(
            False
        )

        self.import_button.clicked.connect(
            self.import_selected_epub
        )

        button_layout = QHBoxLayout()

        button_layout.addWidget(
            choose_button
        )

        button_layout.addWidget(
            self.import_button
        )

        button_layout.addStretch()

        # ====================================================
        # PAGE
        # ====================================================

        main_layout.addWidget(
            title
        )

        main_layout.addWidget(
            description
        )

        main_layout.addSpacing(
            20
        )

        main_layout.addWidget(
            self.file_label
        )

        main_layout.addLayout(
            button_layout
        )

        main_layout.addStretch()

    # ========================================================
    # CHOOSE EPUB
    # ========================================================

    def choose_epub(self):

        file_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                "Choose EPUB",
                "",
                "EPUB Files (*.epub)",
            )
        )

        if not file_path:
            return

        self.selected_file = (
            file_path
        )

        file_name = Path(
            file_path
        ).name

        self.file_label.setText(
            f"Selected: {file_name}"
        )

        self.import_button.setEnabled(
            True
        )

    # ========================================================
    # RESET SELECTION
    # ========================================================

    def reset_selection(self):

        self.selected_file = None

        self.file_label.setText(
            "No EPUB selected."
        )

        self.import_button.setEnabled(
            False
        )

    # ========================================================
    # IMPORT EPUB
    # ========================================================

    def import_selected_epub(self):

        if not self.selected_file:
            return

        # Disable while processing so users
        # cannot double-click Import.
        self.import_button.setEnabled(
            False
        )

        try:

            metadata = import_epub(
                self.selected_file
            )

        # ====================================================
        # DUPLICATE
        # ====================================================

        except DuplicateBookError as error:

            QMessageBox.warning(
                self,
                "Already Imported",
                str(error),
            )

            self.reset_selection()

            return

        # ====================================================
        # INVALID EPUB
        # ====================================================

        except InvalidEPUBError as error:

            QMessageBox.warning(
                self,
                "Invalid EPUB",
                str(error),
            )

            self.reset_selection()

            return

        # ====================================================
        # EXPECTED IMPORT ERROR
        # ====================================================

        except EPUBImportError as error:

            QMessageBox.warning(
                self,
                "Import Failed",
                str(error),
            )

            self.reset_selection()

            return

        # ====================================================
        # UNEXPECTED ERROR
        # ====================================================

        except Exception as error:

            QMessageBox.critical(
                self,
                "Import Failed",
                (
                    "An unexpected error occurred "
                    "while importing this EPUB."
                    f"\n\n{error}"
                ),
            )

            self.reset_selection()

            return

        # ====================================================
        # SUCCESS
        # ====================================================

        self.book_imported.emit()

        QMessageBox.information(
            self,
            "Import Successful",
            (
                "Book imported successfully."
                "\n\n"
                f"Title: {metadata['title']}"
                "\n"
                f"Author: {metadata['author']}"
            ),
        )

        self.reset_selection()