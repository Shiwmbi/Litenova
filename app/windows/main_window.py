from pathlib import Path

from PySide6.QtCore import QSize, QSettings
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QStackedWidget,
)

from app.pages.library_page import LibraryPage
from app.pages.history_page import HistoryPage
from app.pages.browse_page import BrowsePage
from app.pages.reader_page import ReaderPage
from app.pages.comic_reader_page import ComicReaderPage
from app.pages.settings_page import SettingsPage
from app.services.theme_service import apply_theme
from app.services.icon_service import ui_icon
from app.database.custom_categories_repository import get_book_custom_category


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Litenova")
        self.resize(1400, 850)
        self.setMinimumSize(1000, 650)
        self.reader_return_page = None
        self.build_ui()

    def build_ui(self):
        self.central_widget = QWidget()
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(190)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 25, 15, 20)
        sidebar_layout.setSpacing(10)

        self.library_button = self.make_sidebar_button("Library", "library")
        self.history_button = self.make_sidebar_button("History", "history")
        self.browse_button = self.make_sidebar_button("Browse", "browse")
        self.settings_button = self.make_sidebar_button("Settings", "settings")

        sidebar_layout.addWidget(self.library_button)
        sidebar_layout.addWidget(self.history_button)
        sidebar_layout.addWidget(self.browse_button)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(self.settings_button)

        # Original sidebar styling, before the later replica changes.
        self.sidebar.setStyleSheet("""
            QPushButton#sidebarButton {
                text-align: left;
                padding: 9px 12px;
                min-height: 50px;
                background: transparent;
                color: #dcdff0;
                border: 1px solid transparent;
                border-radius: 12px;
                font-size: 15px;
            }
            QPushButton#sidebarButton:hover {
                background: rgba(116, 118, 176, 0.14);
            }
            QPushButton#sidebarButton:checked {
                background: #32334f;
                border: 1px solid #474966;
                color: #f3f3ff;
            }
        """)

        self.pages = QStackedWidget()
        self.library_page = LibraryPage()
        self.history_page = HistoryPage()
        self.browse_page = BrowsePage()
        self.reader_page = ReaderPage()
        self.comic_reader_page = ComicReaderPage()
        self.settings_page = SettingsPage()

        for page in (
            self.library_page,
            self.history_page,
            self.browse_page,
            self.reader_page,
            self.comic_reader_page,
            self.settings_page,
        ):
            self.pages.addWidget(page)

        self.library_button.clicked.connect(self.show_library)
        self.history_button.clicked.connect(self.show_history)
        self.browse_button.clicked.connect(self.show_browse)
        self.settings_button.clicked.connect(self.show_settings)

        self.browse_page.book_imported.connect(self.library_page.load_books)
        self.library_page.book_open_requested.connect(self.open_reader_from_library)
        self.history_page.continue_reading_requested.connect(self.open_reader_from_history)
        self.history_page.view_in_library_requested.connect(self.view_book_in_library)
        self.reader_page.back_requested.connect(self.return_from_reader)
        self.comic_reader_page.back_requested.connect(self.return_from_reader)
        self.settings_page.settings_changed.connect(self.reader_page.reload_settings)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages, 1)
        self.setCentralWidget(self.central_widget)
        # Respect the General > Open to preference on the next launch.
        start_page = str(QSettings("Litenova", "Litenova").value(
            "general/start_page", "library"))
        start_actions = {
            "library": self.show_library,
            "history": self.show_history,
            "browse": self.show_browse,
            "settings": self.show_settings,
        }
        start_actions.get(start_page, self.show_library)()

    def make_sidebar_button(self, text, icon_name):
        button = QPushButton(text)
        button.setObjectName("sidebarButton")
        button.setCheckable(True)
        button.setIcon(ui_icon(icon_name))
        button.setIconSize(QSize(27, 27))
        button.setMinimumHeight(56)
        return button

    @staticmethod
    def book_value(book, key, default=None):
        try:
            value = book[key] if key in book.keys() else None
            return default if value is None else value
        except (KeyError, TypeError, AttributeError):
            return default

    def update_sidebar_state(self, active_button=None):
        for button in (
            self.library_button,
            self.history_button,
            self.browse_button,
            self.settings_button,
        ):
            button.setChecked(button is active_button)

    def show_library(self):
        self.library_page.load_books()
        self.pages.setCurrentWidget(self.library_page)
        self.update_sidebar_state(self.library_button)

    def show_history(self):
        self.history_page.refresh()
        self.pages.setCurrentWidget(self.history_page)
        self.update_sidebar_state(self.history_button)

    def show_browse(self):
        self.pages.setCurrentWidget(self.browse_page)
        self.update_sidebar_state(self.browse_button)

    def show_settings(self):
        self.settings_page.load_settings()
        self.pages.setCurrentWidget(self.settings_page)
        self.update_sidebar_state(self.settings_button)

    def open_reader_from_library(self, book):
        self.reader_return_page = self.library_page
        self.open_reader(book)

    def open_reader_from_history(self, book):
        self.reader_return_page = self.history_page
        self.open_reader(book)

    def return_from_reader(self):
        if self.reader_return_page is self.history_page:
            self.show_history()
        else:
            self.show_library()

    def view_book_in_library(self, book):
        book_id = self.book_value(book, "id")
        try:
            category = get_book_custom_category(book_id) if book_id is not None else None
        except Exception:
            category = None

        if category is not None:
            category_id = category["id"]
            self.library_page.active_filter_type = "custom"
            self.library_page.active_filter_value = category_id
            self.library_page.refresh_category_filter(select_custom_id=category_id)
        else:
            self.library_page.active_filter_type = "all"
            self.library_page.active_filter_value = None
            self.library_page.refresh_category_filter()
        self.show_library()

    def open_reader(self, book):
        file_format = str(self.book_value(book, "file_format", "")).lower()
        category = str(self.book_value(book, "category", "")).lower()
        file_path = (
            self.book_value(book, "file_path")
            or self.book_value(book, "epub_path", "")
        )
        path = Path(str(file_path))
        is_comic = (
            file_format == "cbz"
            or category in ("manga", "manhwa")
            or path.suffix.lower() == ".cbz"
            or path.is_dir()
        )
        self.update_sidebar_state(None)
        if is_comic:
            self.comic_reader_page.open_book(book)
            self.pages.setCurrentWidget(self.comic_reader_page)
        else:
            self.reader_page.open_book(book)
            self.pages.setCurrentWidget(self.reader_page)

    def refresh_theme(self):
        app = QApplication.instance()
        if app is not None:
            apply_theme(app)
