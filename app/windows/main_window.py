import filecmp
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from packaging.version import Version, InvalidVersion

from PySide6.QtCore import (
    QSize,
    QSettings,
    QTimer,
    QUrl,
    Qt,
)

from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QStackedWidget,
    QMessageBox,
)

from app.pages.library_page import LibraryPage
from app.pages.history_page import HistoryPage
from app.pages.browse_page import BrowsePage
from app.pages.reader_page import ReaderPage
from app.pages.comic_reader_page import ComicReaderPage
from app.pages.settings_page import SettingsPage

from app.widgets.welcome_dialog import WelcomeDialog

from app.services.theme_service import apply_theme
from app.services.icon_service import ui_icon
from app.services.import_service import import_book, DuplicateBookError
from app.database.books_repository import get_all_books, get_book_by_id

from app.database.custom_categories_repository import (
    get_book_custom_category,
)


WELCOME_VERSION = 1
LATEST_RELEASE_API = "https://api.github.com/repos/Shiwmbi/Litenova/releases/latest"


class MainWindow(QMainWindow):

    def __init__(
        self,
        startup_files=None,
    ):
        super().__init__()

        self.setWindowTitle(
            "Litenova"
        )

        self.resize(
            1400,
            850,
        )

        self.setMinimumSize(
            1000,
            650,
        )

        self.reader_return_page = None
        self.startup_files = list(startup_files or [])
        self._update_manager = None
        self._update_reply = None
        self._notified_update_versions = set()

        self.build_ui()

        # Show onboarding only after the main window has appeared.
        QTimer.singleShot(
            250,
            self.finish_startup,
        )

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(
        self,
    ):
        self.central_widget = QWidget()

        main_layout = QHBoxLayout(
            self.central_widget
        )

        main_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        main_layout.setSpacing(
            0
        )

        # ====================================================
        # SIDEBAR
        # ====================================================

        self.sidebar = QWidget()

        self.sidebar.setObjectName(
            "sidebar"
        )

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

        self.library_button = (
            self.make_sidebar_button(
                "Library",
                "library",
            )
        )

        self.history_button = (
            self.make_sidebar_button(
                "History",
                "history",
            )
        )

        self.browse_button = (
            self.make_sidebar_button(
                "Browse",
                "browse",
            )
        )

        self.settings_button = (
            self.make_sidebar_button(
                "Settings",
                "settings",
            )
        )

        sidebar_layout.addWidget(
            self.library_button
        )

        sidebar_layout.addWidget(
            self.history_button
        )

        sidebar_layout.addWidget(
            self.browse_button
        )

        sidebar_layout.addStretch()

        sidebar_layout.addWidget(
            self.settings_button
        )

        self.sidebar.setStyleSheet(
            """
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
            """
        )

        # ====================================================
        # PAGES
        # ====================================================

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

            self.pages.addWidget(
                page
            )

        # ====================================================
        # SIDEBAR CONNECTIONS
        # ====================================================

        self.library_button.clicked.connect(
            self.show_library
        )

        self.history_button.clicked.connect(
            self.show_history
        )

        self.browse_button.clicked.connect(
            self.show_browse
        )

        self.settings_button.clicked.connect(
            self.show_settings
        )

        # ====================================================
        # PAGE CONNECTIONS
        # ====================================================

        self.browse_page.book_imported.connect(
            self.library_page.load_books
        )

        self.library_page.book_open_requested.connect(
            self.open_reader_from_library
        )

        self.history_page.continue_reading_requested.connect(
            self.open_reader_from_history
        )

        self.history_page.view_in_library_requested.connect(
            self.view_book_in_library
        )

        self.reader_page.back_requested.connect(
            self.return_from_reader
        )

        self.comic_reader_page.back_requested.connect(
            self.return_from_reader
        )

        self.settings_page.settings_changed.connect(
            self.reader_page.reload_settings
        )
        self.settings_page.check_updates_requested.connect(
            lambda: self.check_for_updates(manual=True)
        )

        # ====================================================
        # MAIN WINDOW
        # ====================================================

        main_layout.addWidget(
            self.sidebar
        )

        main_layout.addWidget(
            self.pages,
            1,
        )

        self.setCentralWidget(
            self.central_widget
        )

        # ====================================================
        # START PAGE
        # ====================================================

        settings = QSettings(
            "Litenova",
            "Litenova",
        )

        start_page = str(
            settings.value(
                "general/start_page",
                "library",
            )
        )

        start_actions = {
            "library": self.show_library,
            "history": self.show_history,
            "browse": self.show_browse,
            "settings": self.show_settings,
        }

        start_actions.get(
            start_page,
            self.show_library,
        )()

    # ========================================================
    # FIRST RUN
    # ========================================================

    def finish_startup(self):
        self.show_first_run_welcome()
        paths, self.startup_files = self.startup_files, []
        for argument in paths:
            self.open_external_file(argument)
        QTimer.singleShot(3000, self.check_for_updates)

    def check_for_updates(self, manual=False):
        """Make one bounded asynchronous request; manual checks bypass the cache."""
        settings = QSettings("Litenova", "Litenova")
        now = int(time.time())
        if not manual:
            try:
                last_check = int(settings.value("updates/last_check_utc", 0))
            except (TypeError, ValueError, OverflowError):
                last_check = 0
            if 0 <= now - last_check < 86400 or self._update_reply is not None:
                return

        if self._update_reply is not None:
            previous, self._update_reply = self._update_reply, None
            previous.abort()

        if self._update_manager is None:
            self._update_manager = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(LATEST_RELEASE_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        current = QApplication.applicationVersion()
        request.setRawHeader(b"User-Agent", f"Litenova/{current}".encode("ascii"))
        request.setTransferTimeout(10000)
        # Cache attempts as well as successes so offline launches do not retry
        # repeatedly. Manual checks always remain available.
        settings.setValue("updates/last_check_utc", now)
        reply = self._update_manager.get(request)
        self._update_reply = reply
        self.settings_page.check_updates_button.setEnabled(False)
        timeout = QTimer(reply)
        timeout.setSingleShot(True)
        timeout.timeout.connect(reply.abort)
        reply.finished.connect(timeout.stop)
        reply.finished.connect(lambda: self._finish_update_check(reply, manual))
        timeout.start(10000)

    def _finish_update_check(self, reply, manual):
        if reply is not self._update_reply:
            reply.deleteLater()
            return
        self._update_reply = None
        self.settings_page.check_updates_button.setEnabled(True)
        failure_message = (
            "Unable to check for updates right now.\n"
            "Please check your internet connection and try again."
        )
        try:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status is not None and status != 200:
                if status == 404:
                    failure_message = (
                        "The GitHub update information is not publicly available.\n"
                        "The repository may be unavailable or private, or it may "
                        "not have a published stable release yet. Please try again later."
                    )
                raise ValueError(f"HTTP {status}")
            if reply.error() != QNetworkReply.NetworkError.NoError:
                # Only the enum name is logged, never proxy URLs or credentials.
                raise ValueError(f"network error: {reply.error().name}")
            if status != 200:
                raise ValueError("missing HTTP status")
            raw = bytes(reply.readAll())
            if len(raw) > 1024 * 1024:
                raise ValueError("Unexpected release response size")
            try:
                release = json.loads(raw)
            except (ValueError, UnicodeError) as error:
                raise ValueError("invalid JSON") from error
            self._show_update_result(release, manual)
        except (ValueError, TypeError, KeyError, UnicodeError, InvalidVersion) as error:
            if manual:
                if not getattr(sys, "frozen", False):
                    # Validation errors below contain fixed labels, not API data.
                    print(f"Update check failed: {error}")
                QMessageBox.information(
                    self, "Updates",
                    failure_message,
                )
        finally:
            reply.deleteLater()

    def _show_update_result(self, release, manual):
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            raise ValueError("Expected a stable release")
        if "tag_name" not in release:
            raise ValueError("missing tag_name")
        if "html_url" not in release:
            raise ValueError("missing html_url")
        tag = release["tag_name"]
        page = release["html_url"]
        name = release.get("name", "")
        if not isinstance(tag, str) or not isinstance(page, str) or not isinstance(name, (str, type(None))):
            raise ValueError("Malformed release metadata")
        current_text = QApplication.applicationVersion()
        try:
            latest = Version(tag.removeprefix("v"))
            current = Version(current_text)
        except InvalidVersion as error:
            raise ValueError("malformed version") from error
        if latest.is_prerelease or latest.is_devrelease:
            raise ValueError("Expected a stable version")
        url = urlsplit(page)
        if (url.scheme != "https" or url.netloc != "github.com"
                or not url.path.startswith("/Shiwmbi/Litenova/releases/tag/")
                or url.query or url.fragment or "/../" in url.path):
            raise ValueError("Unexpected release page")
        if latest <= current:
            if manual:
                QMessageBox.information(
                    self, "Updates",
                    f"You're up to date.\n\nLitenova {current_text} is the latest version."
                    if latest == current else
                    f"You're up to date.\n\nLitenova {current_text} is newer than the latest release.",
                )
            return
        if latest in self._notified_update_versions:
            if manual:
                QMessageBox.information(
                    self, "Updates", f"Litenova {latest} is available. "
                    "You have already been notified during this session.",
                )
            return
        self._notified_update_versions.add(latest)
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Litenova Update")
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(
            "A new version of Litenova is available.\n\n"
            f"Current version: {current_text}\nLatest version: {latest}"
        )
        download = dialog.addButton("Download Update", QMessageBox.ButtonRole.AcceptRole)
        later = dialog.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(later)
        dialog.exec()
        if dialog.clickedButton() is download:
            QDesktopServices.openUrl(QUrl(page))

    def open_external_file(self, argument):
        """Import an Explorer request using the normal import service."""
        try:
            path = Path(argument)
            if path.suffix.lower() not in (".epub", ".cbz") or not path.is_file():
                return
            path = path.resolve()
            # Check the actual stored copy, including books whose metadata
            # was edited after import. Never copy the same content again.
            book = None
            for candidate in get_all_books():
                stored = self.book_value(candidate, "file_path") or self.book_value(
                    candidate, "epub_path"
                )
                if not stored:
                    continue
                try:
                    if filecmp.cmp(str(path), str(stored), shallow=False):
                        book = candidate
                        break
                except OSError:
                    continue

            if book is None:
                category = "light_novel"
                if path.suffix.lower() == ".cbz":
                    category = self.browse_page.choose_comic_category()
                    if category is None:
                        return
                try:
                    result = import_book(str(path), category=category)
                    book = get_book_by_id(result["book_id"])
                except DuplicateBookError as error:
                    book = error.existing_book
                    if book is None:
                        raise

            self.show_library()
            if book is not None:
                self.open_reader_from_library(book)
        except Exception as error:
            QMessageBox.warning(self, "Open Book", str(error))

    def show_first_run_welcome(
        self,
    ):
        settings = QSettings(
            "Litenova",
            "Litenova",
        )

        saved_value = settings.value(
            "onboarding/welcome_version",
            0,
        )

        try:

            completed_version = int(
                saved_value
            )

        except (
            TypeError,
            ValueError,
        ):

            completed_version = 0

        if (
            completed_version
            >= WELCOME_VERSION
        ):

            return

        dialog = WelcomeDialog(
            self
        )

        dialog.exec()

        # The first-run screen is intentionally shown only once.
        #
        # If a later version requires new onboarding,
        # increase WELCOME_VERSION.

        settings.setValue(
            "onboarding/welcome_version",
            WELCOME_VERSION,
        )

        settings.sync()

        if dialog.action == "import":

            self.show_browse()

        elif dialog.action == "library":

            self.show_library()

    # ========================================================
    # SIDEBAR BUTTON
    # ========================================================

    def make_sidebar_button(
        self,
        text,
        icon_name,
    ):
        button = QPushButton(
            text
        )

        button.setObjectName(
            "sidebarButton"
        )

        button.setCheckable(
            True
        )

        button.setIcon(
            ui_icon(
                icon_name
            )
        )

        button.setIconSize(
            QSize(
                27,
                27,
            )
        )

        button.setMinimumHeight(
            56
        )

        return button

    # ========================================================
    # SAFE BOOK VALUE
    # ========================================================

    @staticmethod
    def book_value(
        book,
        key,
        default=None,
    ):
        try:

            value = (
                book[key]
                if key in book.keys()
                else None
            )

            return (
                default
                if value is None
                else value
            )

        except (
            KeyError,
            TypeError,
            AttributeError,
        ):

            return default

    # ========================================================
    # SIDEBAR STATE
    # ========================================================

    def update_sidebar_state(
        self,
        active_button=None,
    ):
        for button in (
            self.library_button,
            self.history_button,
            self.browse_button,
            self.settings_button,
        ):

            button.setChecked(
                button is active_button
            )

    # ========================================================
    # LIBRARY
    # ========================================================

    def show_library(
        self,
    ):
        self.library_page.load_books()

        self.pages.setCurrentWidget(
            self.library_page
        )

        self.update_sidebar_state(
            self.library_button
        )

    # ========================================================
    # HISTORY
    # ========================================================

    def show_history(
        self,
    ):
        self.history_page.refresh()

        self.pages.setCurrentWidget(
            self.history_page
        )

        self.update_sidebar_state(
            self.history_button
        )

    # ========================================================
    # BROWSE
    # ========================================================

    def show_browse(
        self,
    ):
        self.pages.setCurrentWidget(
            self.browse_page
        )

        self.update_sidebar_state(
            self.browse_button
        )

    # ========================================================
    # SETTINGS
    # ========================================================

    def show_settings(
        self,
    ):
        self.settings_page.load_settings()

        self.pages.setCurrentWidget(
            self.settings_page
        )

        self.update_sidebar_state(
            self.settings_button
        )

    # ========================================================
    # OPEN FROM LIBRARY
    # ========================================================

    def open_reader_from_library(
        self,
        book,
    ):
        self.reader_return_page = (
            self.library_page
        )

        self.open_reader(
            book
        )

    # ========================================================
    # OPEN FROM HISTORY
    # ========================================================

    def open_reader_from_history(
        self,
        book,
    ):
        self.reader_return_page = (
            self.history_page
        )

        self.open_reader(
            book
        )

    # ========================================================
    # RETURN FROM READER
    # ========================================================

    def return_from_reader(
        self,
    ):
        if (
            self.reader_return_page
            is self.history_page
        ):

            self.show_history()

        else:

            self.show_library()

    # ========================================================
    # VIEW BOOK IN LIBRARY
    # ========================================================

    def view_book_in_library(
        self,
        book,
    ):
        book_id = self.book_value(
            book,
            "id",
        )

        try:

            category = (
                get_book_custom_category(
                    book_id
                )
                if book_id is not None
                else None
            )

        except Exception:

            category = None

        if category is not None:

            category_id = category[
                "id"
            ]

            self.library_page.active_filter_type = (
                "custom"
            )

            self.library_page.active_filter_value = (
                category_id
            )

            self.library_page.refresh_category_filter(
                select_custom_id=category_id
            )

        else:

            self.library_page.active_filter_type = (
                "all"
            )

            self.library_page.active_filter_value = (
                None
            )

            self.library_page.refresh_category_filter()

        self.show_library()

    # ========================================================
    # OPEN READER
    # ========================================================

    def open_reader(
        self,
        book,
    ):
        file_format = str(
            self.book_value(
                book,
                "file_format",
                "",
            )
        ).lower()

        category = str(
            self.book_value(
                book,
                "category",
                "",
            )
        ).lower()

        file_path = (
            self.book_value(
                book,
                "file_path",
            )
            or self.book_value(
                book,
                "epub_path",
                "",
            )
        )

        path = Path(
            str(
                file_path
            )
        )

        is_comic = (
            file_format == "cbz"
            or category in (
                "manga",
                "manhwa",
            )
            or path.suffix.lower()
            == ".cbz"
            or path.is_dir()
        )

        self.update_sidebar_state(
            None
        )

        if is_comic:

            self.comic_reader_page.open_book(
                book
            )

            self.pages.setCurrentWidget(
                self.comic_reader_page
            )

        else:

            self.reader_page.open_book(
                book
            )

            self.pages.setCurrentWidget(
                self.reader_page
            )

    # ========================================================
    # THEME REFRESH
    # ========================================================

    def refresh_theme(
        self,
    ):
        app = QApplication.instance()

        if app is not None:

            apply_theme(
                app
            )
