from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QGridLayout,
    QLineEdit,
    QMessageBox,
)

from app.database.books_repository import (
    get_all_books,
    search_books,
)

from app.services.library_service import (
    remove_book,
)

from app.widgets.book_card import (
    BookCard,
)


class LibraryPage(QWidget):

    book_open_requested = Signal(
        object
    )

    def __init__(self):
        super().__init__()

        self.build_ui()
        self.load_books()

    # ==============================================
    # BUILD UI
    # ==============================================

    def build_ui(self):

        main_layout = QVBoxLayout(
            self
        )

        main_layout.setContentsMargins(
            25,
            25,
            25,
            25,
        )

        main_layout.setSpacing(
            15
        )

        # ==========================================
        # TITLE
        # ==========================================

        self.title = QLabel(
            "Library"
        )

        self.title.setObjectName(
            "pageTitle"
        )

        # ==========================================
        # SEARCH
        # ==========================================

        self.search_input = QLineEdit()

        self.search_input.setPlaceholderText(
            "Search by title or author..."
        )

        self.search_input.setClearButtonEnabled(
            True
        )

        self.search_input.setMaximumWidth(
            500
        )

        self.search_input.setFixedHeight(
            42
        )

        self.search_input.textChanged.connect(
            self.search_changed
        )

        # ==========================================
        # STATUS
        # ==========================================

        self.status_label = QLabel()

        self.status_label.setObjectName(
            "secondaryLabel"
        )

        # ==========================================
        # SCROLL AREA
        # ==========================================

        self.scroll_area = QScrollArea()

        self.scroll_area.setWidgetResizable(
            True
        )

        self.scroll_area.setFrameShape(
            QScrollArea.NoFrame
        )

        # ==========================================
        # GRID
        # ==========================================

        self.books_container = QWidget()

        self.books_layout = QGridLayout(
            self.books_container
        )

        self.books_layout.setSpacing(
            20
        )

        self.books_layout.setAlignment(
            Qt.AlignTop
            | Qt.AlignLeft
        )

        self.scroll_area.setWidget(
            self.books_container
        )

        # ==========================================
        # PAGE
        # ==========================================

        main_layout.addWidget(
            self.title
        )

        main_layout.addWidget(
            self.search_input
        )

        main_layout.addWidget(
            self.status_label
        )

        main_layout.addWidget(
            self.scroll_area,
            1,
        )

    # ==============================================
    # CLEAR CARDS
    # ==============================================

    def clear_books(self):

        while self.books_layout.count():

            item = (
                self.books_layout.takeAt(
                    0
                )
            )

            widget = item.widget()

            if widget:
                widget.deleteLater()

    # ==============================================
    # SEARCH
    # ==============================================

    def search_changed(
        self,
        text,
    ):

        self.load_books(
            text
        )

    # ==============================================
    # LOAD BOOKS
    # ==============================================

    def load_books(
        self,
        query=None,
    ):

        self.clear_books()

        if query is None:

            if hasattr(
                self,
                "search_input",
            ):
                query = (
                    self.search_input.text()
                )

            else:
                query = ""

        query = (
            query.strip()
            if isinstance(
                query,
                str,
            )
            else ""
        )

        if query:

            books = search_books(
                query
            )

        else:

            books = get_all_books()

        # ==========================================
        # EMPTY
        # ==========================================

        if not books:

            if query:

                self.status_label.setText(
                    (
                        "No books found for "
                        f'"{query}".'
                    )
                )

            else:

                self.status_label.setText(
                    (
                        "Your library is empty. "
                        "Import an EPUB from Browse."
                    )
                )

            return

        # ==========================================
        # STATUS
        # ==========================================

        if query:

            self.status_label.setText(
                (
                    f"{len(books)} result(s) "
                    f'for "{query}"'
                )
            )

        else:

            self.status_label.setText(
                (
                    f"{len(books)} book(s) "
                    "in your library"
                )
            )

        # ==========================================
        # CARDS
        # ==========================================

        columns = 4

        for index, book in enumerate(
            books
        ):

            row = (
                index // columns
            )

            column = (
                index % columns
            )

            card = BookCard(
                book
            )

            card.clicked.connect(
                self.book_open_requested.emit
            )

            card.remove_requested.connect(
                self.confirm_remove_book
            )

            self.books_layout.addWidget(
                card,
                row,
                column,
            )

    # ==============================================
    # REMOVE BOOK
    # ==============================================

    def confirm_remove_book(
        self,
        book,
    ):

        title = (
            book["title"]
            or "this book"
        )

        result = QMessageBox.question(
            self,
            "Remove Book",
            (
                f'Remove "{title}" '
                "from your Litenova library?\n\n"
                "This will also delete its saved "
                "reading progress and local EPUB copy."
            ),
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No,
        )

        if result != QMessageBox.Yes:
            return

        try:

            remove_book(
                book
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Remove Failed",
                (
                    "Litenova could not remove "
                    "this book."
                    f"\n\n{error}"
                ),
            )

            return

        QMessageBox.information(
            self,
            "Book Removed",
            (
                f'"{title}" was removed '
                "from your library."
            ),
        )

        self.load_books()