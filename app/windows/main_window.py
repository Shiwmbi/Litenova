from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QStackedWidget,
)

from app.pages.library_page import (
    LibraryPage,
)

from app.pages.browse_page import (
    BrowsePage,
)

from app.pages.reader_page import (
    ReaderPage,
)

from app.pages.settings_page import (
    SettingsPage,
)

from app.services.settings_service import (
    get_reader_theme,
)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Litenova"
        )

        self.resize(
            1200,
            750,
        )

        self.setMinimumSize(
            900,
            600,
        )

        self.build_ui()

    def build_ui(self):

        # ==========================================
        # CENTRAL WIDGET
        # ==========================================

        self.central_widget = QWidget()

        self.main_layout = QHBoxLayout(
            self.central_widget
        )

        self.main_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.main_layout.setSpacing(
            0
        )

        # ==========================================
        # SIDEBAR
        # ==========================================

        self.sidebar = QWidget()

        self.sidebar.setFixedWidth(
            190
        )

        sidebar_layout = QVBoxLayout(
            self.sidebar
        )

        sidebar_layout.setContentsMargins(
            15,
            25,
            15,
            20,
        )

        sidebar_layout.setSpacing(
            10
        )

        self.library_button = QPushButton(
            "Library"
        )

        self.browse_button = QPushButton(
            "Browse"
        )

        self.settings_button = QPushButton(
            "Settings"
        )

        sidebar_layout.addWidget(
            self.library_button
        )

        sidebar_layout.addWidget(
            self.browse_button
        )

        sidebar_layout.addStretch()

        sidebar_layout.addWidget(
            self.settings_button
        )

        # Reader intentionally has no
        # sidebar button.

        # ==========================================
        # PAGE STACK
        # ==========================================

        self.pages = QStackedWidget()

        self.library_page = (
            LibraryPage()
        )

        self.browse_page = (
            BrowsePage()
        )

        self.reader_page = (
            ReaderPage()
        )

        self.settings_page = (
            SettingsPage()
        )

        self.pages.addWidget(
            self.library_page
        )

        self.pages.addWidget(
            self.browse_page
        )

        self.pages.addWidget(
            self.reader_page
        )

        self.pages.addWidget(
            self.settings_page
        )

        # ==========================================
        # NAVIGATION
        # ==========================================

        self.library_button.clicked.connect(
            self.show_library
        )

        self.browse_button.clicked.connect(
            self.show_browse
        )

        self.settings_button.clicked.connect(
            self.show_settings
        )

        # ==========================================
        # IMPORT → LIBRARY
        # ==========================================

        self.browse_page.book_imported.connect(
            self.library_page.load_books
        )

        # ==========================================
        # LIBRARY → READER
        # ==========================================

        self.library_page.book_open_requested.connect(
            self.open_reader
        )

        # ==========================================
        # READER → LIBRARY
        # ==========================================

        self.reader_page.back_requested.connect(
            self.show_library
        )

        # ==========================================
        # SETTINGS CHANGED
        # ==========================================

        self.settings_page.settings_changed.connect(
            self.reader_page.reload_settings
        )

        self.settings_page.settings_changed.connect(
            self.apply_app_theme
        )

        # ==========================================
        # FINAL WINDOW
        # ==========================================

        self.main_layout.addWidget(
            self.sidebar
        )

        self.main_layout.addWidget(
            self.pages,
            1,
        )

        self.setCentralWidget(
            self.central_widget
        )

        # Apply saved theme when Litenova starts.
        self.apply_app_theme()

        self.show_library()

    # ==============================================
    # APP THEME
    # ==============================================

    def apply_app_theme(self):

        theme = get_reader_theme()

        if theme == "light":

            main_background = "#f4f4f6"
            sidebar_background = "#ffffff"

            text_color = "#25262b"
            button_hover = "#e9e9ee"
            button_pressed = "#ddddE5"

            border_color = "#d5d6db"

        else:

            main_background = "#15171e"
            sidebar_background = "#1b1d25"

            text_color = "#eeeeee"
            button_hover = "#292c38"
            button_pressed = "#3b3d50"

            border_color = "#2d303c"

        self.central_widget.setStyleSheet(
            f"""
            QWidget {{
                background-color: {main_background};
                color: {text_color};
            }}
            """
        )

        self.sidebar.setStyleSheet(
            f"""
            QWidget {{
                background-color: {sidebar_background};
            }}

            QPushButton {{
                text-align: left;

                padding: 12px 16px;

                border: none;

                border-radius: 8px;

                color: {text_color};

                font-size: 14px;
            }}

            QPushButton:hover {{
                background-color: {button_hover};
            }}

            QPushButton:pressed {{
                background-color: {button_pressed};
            }}
            """
        )

        # Settings page has some of its own
        # detailed styling, so tell it directly.
        self.settings_page.apply_local_theme(
    theme
)

    # ==============================================
    # LIBRARY
    # ==============================================

    def show_library(self):

        self.library_page.load_books()

        self.pages.setCurrentWidget(
            self.library_page
        )

    # ==============================================
    # BROWSE
    # ==============================================

    def show_browse(self):

        self.pages.setCurrentWidget(
            self.browse_page
        )

    # ==============================================
    # SETTINGS
    # ==============================================

    def show_settings(self):

        self.settings_page.load_settings()

        self.pages.setCurrentWidget(
            self.settings_page
        )

    # ==============================================
    # READER
    # ==============================================

    def open_reader(
        self,
        book,
    ):

        self.reader_page.open_book(
            book
        )

        self.pages.setCurrentWidget(
            self.reader_page
        )