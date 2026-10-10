from __future__ import annotations

import py_compile
import shutil
import sys

from datetime import datetime
from pathlib import Path


# ============================================================
# PROJECT
# ============================================================

ROOT = Path(
    __file__
).resolve().parent


FILES = {
    "library": (
        ROOT
        / "app"
        / "pages"
        / "library_page.py"
    ),

    "settings": (
        ROOT
        / "app"
        / "pages"
        / "settings_page.py"
    ),

    "book_card": (
        ROOT
        / "app"
        / "widgets"
        / "book_card.py"
    ),

    "dialogs": (
        ROOT
        / "app"
        / "widgets"
        / "dialogs.py"
    ),

    "qss": (
        ROOT
        / "app"
        / "styles"
        / "dark.qss"
    ),
}


# ============================================================
# SAFE REPLACEMENT HELPERS
# ============================================================

def replace_once(
    text,
    old,
    new,
    label,
):

    # Already applied.
    if new in text:

        return text

    count = text.count(
        old
    )

    if count != 1:

        raise RuntimeError(
            (
                f"{label}: expected exactly "
                f"1 matching block, found {count}."
            )
        )

    return text.replace(
        old,
        new,
        1,
    )


def remove_once(
    text,
    old,
    label,
):

    # Already removed.
    if old not in text:

        return text

    count = text.count(
        old
    )

    if count != 1:

        raise RuntimeError(
            (
                f"{label}: expected exactly "
                f"1 matching block, found {count}."
            )
        )

    return text.replace(
        old,
        "",
        1,
    )


# ============================================================
# LIBRARY PAGE
# ============================================================

def patch_library(
    text,
):

    # --------------------------------------------------------
    # REMOVE OLD FEATURE DESCRIPTION
    # --------------------------------------------------------

    text = text.replace(
        "- Quick Read buttons\n",
        "",
        1,
    )

    # --------------------------------------------------------
    # ADD VISIBLE DELETE CATEGORY BUTTON
    # --------------------------------------------------------

    old = '''        header.addWidget(
            self.new_category_button
        )

        root.addLayout(
            header
        )
'''

    new = '''        header.addWidget(
            self.new_category_button
        )

        # ====================================================
        # DELETE CATEGORY
        # ====================================================

        self.delete_category_button = QPushButton(
            "Delete Category"
        )

        self.delete_category_button.setObjectName(
            "libraryDeleteCategory"
        )

        self.delete_category_button.setFixedHeight(
            43
        )

        self.delete_category_button.setCursor(
            Qt.PointingHandCursor
        )

        self.delete_category_button.setEnabled(
            False
        )

        self.delete_category_button.setToolTip(
            "Select a custom category to delete it"
        )

        self.delete_category_button.clicked.connect(
            self.delete_selected_category
        )

        header.addWidget(
            self.delete_category_button
        )

        root.addLayout(
            header
        )
'''

    text = replace_once(
        text,
        old,
        new,
        "Library delete-category button",
    )

    # --------------------------------------------------------
    # IMPROVE CATEGORY DROPDOWN
    # --------------------------------------------------------

    old = '''        self.category_filter.setFixedHeight(
            45
        )

        self.category_filter.currentIndexChanged.connect(
'''

    new = '''        self.category_filter.setFixedHeight(
            45
        )

        self.category_filter.setMaxVisibleItems(
            12
        )

        self.category_filter.currentIndexChanged.connect(
'''

    text = replace_once(
        text,
        old,
        new,
        "Library category dropdown",
    )

    # --------------------------------------------------------
    # REMOVE SHOW READ TOGGLE
    # --------------------------------------------------------

    text = remove_once(
        text,
        '''        self.show_read_box = (
            self.toggle_checkbox(
                "Show «Read» button",
                "Show quick action button on covers",
            )
        )

''',
        "Library Read toggle creation",
    )

    text = remove_once(
        text,
        '''        self.show_read_box.setChecked(
            self.setting_bool(
                "library_show_read",
                True,
            )
        )

''',
        "Library Read toggle setting",
    )

    text = remove_once(
        text,
        '''        self.show_read_box.toggled.connect(
            self.display_options_changed
        )

''',
        "Library Read toggle connection",
    )

    text = remove_once(
        text,
        '''        side.addWidget(
            self.show_read_box
        )

''',
        "Library Read toggle widget",
    )

    # --------------------------------------------------------
    # REMOVE LIBRARY FOOTER
    # --------------------------------------------------------

    footer = '''        # ====================================================
        # FOOTER
        # ====================================================

        footer = QHBoxLayout()

        self.status_label = QLabel(
            "0 books"
        )

        self.status_label.setObjectName(
            "libraryFooterLabel"
        )

        footer.addWidget(
            self.status_label
        )

        footer.addStretch()

        self.scan_button = QPushButton(
            "Scan another folder"
        )

        self.scan_button.setObjectName(
            "libraryFooterButton"
        )

        self.scan_button.setCursor(
            Qt.PointingHandCursor
        )

        self.scan_button.clicked.connect(
            self.open_browse
        )

        footer.addWidget(
            self.scan_button
        )

        root.addLayout(
            footer
        )

'''

    text = remove_once(
        text,
        footer,
        "Library footer",
    )

    # --------------------------------------------------------
    # UPDATE CATEGORY BUTTON STATE AFTER REFRESH
    # --------------------------------------------------------

    old = '''        self.category_filter.blockSignals(
            False
        )

    # ========================================================
    # CATEGORY CHANGED
'''

    new = '''        self.category_filter.blockSignals(
            False
        )

        self.update_category_actions()

    # ========================================================
    # CATEGORY CHANGED
'''

    text = replace_once(
        text,
        old,
        new,
        "Library category action refresh",
    )

    # --------------------------------------------------------
    # UPDATE DELETE BUTTON WHEN CATEGORY CHANGES
    # --------------------------------------------------------

    old = '''        (
            self.active_filter_type,
            self.active_filter_value,
        ) = data

        self.load_books()

    # ========================================================
    # CREATE CATEGORY
'''

    new = '''        (
            self.active_filter_type,
            self.active_filter_value,
        ) = data

        self.update_category_actions()
        self.load_books()

    # ========================================================
    # CATEGORY ACTION STATE
    # ========================================================

    def update_category_actions(self):
        """Enable destructive category actions only for custom categories."""

        enabled = (
            self.active_filter_type == "custom"
            and self.active_filter_value is not None
        )

        self.delete_category_button.setEnabled(
            enabled
        )

        if enabled:

            category = get_custom_category(
                self.active_filter_value
            )

            if category is not None:

                self.delete_category_button.setToolTip(
                    f'Delete "{category["name"]}"'
                )

                return

        self.delete_category_button.setToolTip(
            "Select a custom category to delete it"
        )

    # ========================================================
    # CREATE CATEGORY
'''

    text = replace_once(
        text,
        old,
        new,
        "Library category action method",
    )

    # --------------------------------------------------------
    # REMOVE READ BUTTON PREFERENCE
    # --------------------------------------------------------

    text = remove_once(
        text,
        '''        self.preferences.setValue(
            "library_show_read",
            self.show_read_box.isChecked(),
        )

''',
        "Library Read preference",
    )

    # --------------------------------------------------------
    # REMOVE READ SETTING FROM CACHE SIGNATURE
    # --------------------------------------------------------

    text = text.replace(
        '''            bool(
                self.show_read_box.isChecked()
            ),
''',
        "",
        1,
    )

    # Handle current compact formatting too.
    text = text.replace(
        "            bool(self.show_read_box.isChecked()),\n",
        "",
        1,
    )

    # --------------------------------------------------------
    # REMOVE BOTTOM BOOK COUNT UPDATE
    # --------------------------------------------------------

    text = remove_once(
        text,
        '''        self.status_label.setText(
            count_text
        )

''',
        "Library footer count update",
    )

    # --------------------------------------------------------
    # STOP PASSING READ BUTTON OPTION TO CARDS
    # --------------------------------------------------------

    text = remove_once(
        text,
        '''                show_read_button=(
                    self.show_read_box.isChecked()
                ),
''',
        "Library BookCard Read argument",
    )

    # --------------------------------------------------------
    # DELETE CATEGORY BUTTON STYLE
    # --------------------------------------------------------

    old = '''            QPushButton#libraryAddFolder:hover {
                background: #41456b;
            }

            /* Keep the existing search bar appearance. */
'''

    new = '''            QPushButton#libraryAddFolder:hover {
                background: #41456b;
            }

            QPushButton#libraryDeleteCategory {
                background: #251c22;
                color: #f0b9c0;
                border: 1px solid #6f404a;
                border-radius: 11px;
                padding: 0 15px;
                font-size: 13px;
            }

            QPushButton#libraryDeleteCategory:hover {
                background: #3a232a;
                border-color: #a65a68;
                color: #ffd7dc;
            }

            QPushButton#libraryDeleteCategory:disabled {
                background: #18191f;
                color: #686b79;
                border-color: #30323d;
            }

            /* Keep the existing search bar appearance. */
'''

    text = replace_once(
        text,
        old,
        new,
        "Library delete-category style",
    )

    # --------------------------------------------------------
    # DROPDOWN POPUP STYLE
    # --------------------------------------------------------

    old = '''            QComboBox QAbstractItemView {
                background: #1c1e29;
                color: #e8e9ff;
                selection-background-color: #494e7b;
                border: 1px solid #4d526a;
            }
'''

    new = '''            QComboBox QAbstractItemView {
                background: #1b1d26;
                color: #e8e9ff;
                selection-background-color: #444967;
                selection-color: #ffffff;
                border: 1px solid #4d526a;
                border-radius: 9px;
                outline: none;
                padding: 6px;
            }

            QComboBox QAbstractItemView::item {
                min-height: 34px;
                padding: 5px 10px;
                border-radius: 6px;
            }

            QComboBox QAbstractItemView::item:hover {
                background: #33374d;
            }
'''

    text = replace_once(
        text,
        old,
        new,
        "Library dropdown popup style",
    )

    return text


# ============================================================
# SETTINGS PAGE
# ============================================================

def patch_settings(
    text,
):

    # --------------------------------------------------------
    # REMOVE SETTINGS SEARCH BAR
    # --------------------------------------------------------

    search_block = '''        self.search = QLineEdit(
            self
        )

        self.search.setPlaceholderText(
            "Search settings..."
        )

        self.search.setObjectName(
            "settingsSearch"
        )

        self.search.setFixedSize(
            300,
            40,
        )

        self.search.addAction(
            ui_icon(
                "search"
            ),
            QLineEdit.LeadingPosition,
        )

        self.search.textChanged.connect(
            self.filter_settings
        )

        title_row.addWidget(
            self.search,
            0,
            Qt.AlignTop,
        )

'''

    text = remove_once(
        text,
        search_block,
        "Settings search bar",
    )

    # --------------------------------------------------------
    # HIDE VISIBLE SCROLLBAR
    # --------------------------------------------------------

    old = '''        scroller.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        content = QWidget()
'''

    new = '''        scroller.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        # Keep mouse-wheel/touchpad scrolling available while
        # removing the visible Settings scrollbar.
        scroller.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        content = QWidget()
'''

    text = replace_once(
        text,
        old,
        new,
        "Settings hidden scrollbar",
    )

    # --------------------------------------------------------
    # REMOVE SEARCH-SPECIFIC STYLE
    # --------------------------------------------------------

    text = text.replace(
        "            QLineEdit#settingsSearch,\n",
        "",
        1,
    )

    text = remove_once(
        text,
        '''            QLineEdit#settingsSearch:focus {
                border-color: #9795d6;
            }

''',
        "Settings search style",
    )

    # --------------------------------------------------------
    # IMPROVE SETTINGS DROPDOWNS
    # --------------------------------------------------------

    old = '''            QComboBox QAbstractItemView {
                background: #191b22;
                color: #e7e8ff;
                selection-background-color: #454969;
                outline: none;
            }
'''

    new = '''            QComboBox QAbstractItemView {
                background: #1b1d26;
                color: #e7e8ff;
                selection-background-color: #454969;
                selection-color: #ffffff;
                border: 1px solid #4e5268;
                border-radius: 9px;
                outline: none;
                padding: 6px;
            }

            QComboBox QAbstractItemView::item {
                min-height: 34px;
                padding: 5px 10px;
                border-radius: 6px;
            }

            QComboBox QAbstractItemView::item:hover {
                background: #33374d;
            }
'''

    text = replace_once(
        text,
        old,
        new,
        "Settings dropdown style",
    )

    # --------------------------------------------------------
    # REMOVE UNUSED SETTINGS SEARCH METHOD
    # --------------------------------------------------------

    filter_method = '''    # ========================================================
    # SEARCH
    # ========================================================

    def filter_settings(
        self,
        text,
    ):

        query = (
            text
            .strip()
            .casefold()
        )

        for card in self.cards:

            card.filter(
                query
            )

'''

    text = remove_once(
        text,
        filter_method,
        "Settings filter method",
    )

    return text


# ============================================================
# BOOK CARD
# ============================================================

def patch_book_card(
    text,
):

    # --------------------------------------------------------
    # REMOVE show_read_button PARAMETER
    # --------------------------------------------------------

    old = '''        self, book, mode="grid", cover_width=200,
        progress=0.0, show_progress=True,
        show_read_button=True, parent=None,
        original_cover=None,
'''

    new = '''        self, book, mode="grid", cover_width=200,
        progress=0.0, show_progress=True,
        parent=None, original_cover=None,
'''

    text = replace_once(
        text,
        old,
        new,
        "BookCard constructor",
    )

    text = text.replace(
        "        self.show_read_button = show_read_button\n",
        "",
        1,
    )

    # --------------------------------------------------------
    # REMOVE BLUE READ BUTTON
    # --------------------------------------------------------

    read_button = '''        self.read_button = QPushButton(self.cover_box)
        self.read_button.setObjectName("libraryReadButton")
        self.read_button.setIcon(ui_icon("continue_reading"))
        self.read_button.setIconSize(QSize(21, 21))
        self.read_button.setFixedSize(39, 39)
        self.read_button.move(self.cover_width - 46, cover_height - 46)
        self.read_button.setToolTip("Read / Continue Reading")
        self.read_button.setCursor(Qt.PointingHandCursor)
        self.read_button.setVisible(self.show_read_button)
        self.read_button.clicked.connect(self.open_book)

'''

    text = remove_once(
        text,
        read_button,
        "BookCard Read button",
    )

    # --------------------------------------------------------
    # USE FULL COVER WIDTH FOR TYPE BADGE
    # --------------------------------------------------------

    old = '''        # Reserve space for the blue Read button, even on the smallest covers.
        badge_width = min(badge_width, max(54, self.cover_width - 61))
'''

    new = '''        # Keep the badge inside the cover with an even right margin.
        badge_width = min(badge_width, max(54, self.cover_width - 16))
'''

    text = replace_once(
        text,
        old,
        new,
        "BookCard cover badge width",
    )

    # --------------------------------------------------------
    # REMOVE READ BUTTON STYLE
    # --------------------------------------------------------

    read_style = '''            QPushButton#libraryReadButton {
                background: #1c438f; border: none; border-radius: 19px; padding: 0;
            }
            QPushButton#libraryReadButton:hover { background: #315bb1; }
'''

    text = remove_once(
        text,
        read_style,
        "BookCard Read button style",
    )

    return text


# ============================================================
# EDIT BOOK DIALOG
# ============================================================

def patch_dialogs(
    text,
):

    # --------------------------------------------------------
    # DIALOG WINDOW SETTINGS
    # --------------------------------------------------------

    old = '''        self.setMinimumWidth(
            500
        )

        self.build_ui()
'''

    new = '''        self.setObjectName(
            "editBookDialog"
        )

        self.setMinimumWidth(
            540
        )

        self.setModal(
            True
        )

        self.build_ui()
        self.apply_dialog_style()
'''

    text = replace_once(
        text,
        old,
        new,
        "Edit dialog initialization",
    )

    # --------------------------------------------------------
    # COVER BUTTON
    # --------------------------------------------------------

    old = '''        self.choose_cover_button = QPushButton(
            "Choose New Cover"
        )

        self.choose_cover_button.clicked.connect(
'''

    new = '''        self.choose_cover_button = QPushButton(
            "Choose New Cover"
        )

        self.choose_cover_button.setObjectName(
            "dialogSecondaryButton"
        )

        self.choose_cover_button.clicked.connect(
'''

    text = replace_once(
        text,
        old,
        new,
        "Edit dialog cover button",
    )

    # --------------------------------------------------------
    # INPUT FIELDS
    # --------------------------------------------------------

    text = replace_once(
        text,
        '''        self.title_input = QLineEdit()

        self.title_input.setText(
''',
        '''        self.title_input = QLineEdit()
        self.title_input.setObjectName(
            "dialogInput"
        )
        self.title_input.setMinimumHeight(
            40
        )

        self.title_input.setText(
''',
        "Edit dialog title input",
    )

    text = replace_once(
        text,
        '''        self.author_input = QLineEdit()

        self.author_input.setText(
''',
        '''        self.author_input = QLineEdit()
        self.author_input.setObjectName(
            "dialogInput"
        )
        self.author_input.setMinimumHeight(
            40
        )

        self.author_input.setText(
''',
        "Edit dialog author input",
    )

    # --------------------------------------------------------
    # ACTION BUTTONS
    # --------------------------------------------------------

    old = '''        cancel_button = QPushButton(
            "Cancel"
        )

        save_button = QPushButton(
            "Save Changes"
        )

        save_button.setObjectName(
            "primaryButton"
        )
'''

    new = '''        cancel_button = QPushButton(
            "Cancel"
        )

        cancel_button.setObjectName(
            "dialogSecondaryButton"
        )

        save_button = QPushButton(
            "Save Changes"
        )

        save_button.setObjectName(
            "primaryButton"
        )

        cancel_button.setMinimumWidth(
            100
        )

        save_button.setMinimumWidth(
            125
        )
'''

    text = replace_once(
        text,
        old,
        new,
        "Edit dialog action buttons",
    )

    # --------------------------------------------------------
    # ADD DIALOG STYLES
    # --------------------------------------------------------

    anchor = '''        self.load_cover_preview(
            self.book_value(
                "cover_path",
                None,
            )
        )

    # ========================================================
    # COVER PREVIEW
'''

    if (
        "    def apply_dialog_style(self):\n"
        not in text
    ):

        new_anchor = '''        self.load_cover_preview(
            self.book_value(
                "cover_path",
                None,
            )
        )

    # ========================================================
    # DIALOG STYLE
    # ========================================================

    def apply_dialog_style(self):

        self.setStyleSheet(
            """
            QDialog#editBookDialog {
                background: #1b1d26;
                color: #eceeff;
            }

            QDialog#editBookDialog QLabel {
                background: transparent;
                border: none;
            }

            QDialog#editBookDialog QLabel#sectionTitle {
                color: #f3f2ff;
                font-size: 20px;
                font-weight: 700;
            }

            QDialog#editBookDialog QLabel#secondaryLabel {
                color: #aeb3c8;
                font-size: 12px;
            }

            QDialog#editBookDialog QLabel#bookCover {
                background: #13151c;
                color: #8f94aa;
                border: 1px solid #3b4051;
                border-radius: 12px;
            }

            QDialog#editBookDialog QLineEdit#dialogInput {
                background: #12141b;
                color: #f0f1ff;
                border: 1px solid #44495c;
                border-radius: 9px;
                padding: 7px 10px;
                selection-background-color: #555a85;
            }

            QDialog#editBookDialog QLineEdit#dialogInput:focus {
                border-color: #8e8ed0;
            }

            QDialog#editBookDialog QPushButton#dialogSecondaryButton {
                background: #292d3d;
                color: #e8eaff;
                border: 1px solid #4c5269;
                border-radius: 9px;
                padding: 8px 14px;
            }

            QDialog#editBookDialog QPushButton#dialogSecondaryButton:hover {
                background: #373c50;
                border-color: #777da5;
            }

            QDialog#editBookDialog QPushButton#primaryButton {
                background: #4c4f7c;
                color: #ffffff;
                border: 1px solid #7679ad;
                border-radius: 9px;
                padding: 8px 16px;
                font-weight: 600;
            }

            QDialog#editBookDialog QPushButton#primaryButton:hover {
                background: #5a5e91;
                border-color: #9b9ed2;
            }
            """
        )

    # ========================================================
    # COVER PREVIEW
'''

        text = replace_once(
            text,
            anchor,
            new_anchor,
            "Edit dialog style method",
        )

    return text


# ============================================================
# GLOBAL DARK STYLESHEET
# ============================================================

def patch_qss(
    text,
):

    marker = (
        "/* =========================================================\n"
        "   POLISHED DROPDOWNS AND POPUP MENUS"
    )

    if marker in text:

        return text

    addition = r'''

/* =========================================================
   POLISHED DROPDOWNS AND POPUP MENUS
   ========================================================= */

QComboBox {
    min-height: 24px;
    padding-left: 10px;
    padding-right: 34px;
}

QComboBox:hover {
    border-color: #676c87;
}

QComboBox:on {
    border-color: #8f88ff;
}

QComboBox QAbstractItemView {
    background-color: #1b1d26;
    color: #eeeeee;
    border: 1px solid #4b5063;
    border-radius: 9px;
    outline: none;
    padding: 6px;
    selection-background-color: #4a4f73;
    selection-color: #ffffff;
}

QComboBox QAbstractItemView::item {
    min-height: 34px;
    padding: 5px 10px;
    border-radius: 6px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #34384a;
}

QMenu {
    background-color: #1b1d26;
    color: #eeeeee;
    border: 1px solid #474c60;
    border-radius: 10px;
    padding: 6px;
}

QMenu::item {
    min-width: 190px;
    min-height: 28px;
    padding: 7px 28px 7px 12px;
    margin: 1px 0px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: #40455f;
    color: #ffffff;
}

QMenu::item:disabled {
    color: #6f7382;
}

QMenu::separator {
    height: 1px;
    background: #373b49;
    margin: 6px 8px;
}

QMenu::indicator {
    width: 14px;
    height: 14px;
}


/* =========================================================
   POLISHED DIALOGS / MESSAGE BOXES
   ========================================================= */

QDialog,
QMessageBox,
QInputDialog {
    background-color: #1b1d26;
    color: #eeeeee;
}

QDialog QLabel,
QMessageBox QLabel,
QInputDialog QLabel {
    background: transparent;
    border: none;
    color: #e9ebf8;
}

QMessageBox QLabel#qt_msgbox_label {
    min-width: 320px;
    padding: 8px 4px 6px 4px;
    font-size: 13px;
}

QMessageBox QLabel#qt_msgbox_informativelabel {
    color: #b9bed0;
    padding-top: 2px;
}

QMessageBox QPushButton,
QDialog QPushButton,
QInputDialog QPushButton {
    min-width: 88px;
    min-height: 32px;
    background-color: #2a2e3d;
    color: #f0f1ff;
    border: 1px solid #4a5065;
    border-radius: 9px;
    padding: 6px 14px;
}

QMessageBox QPushButton:hover,
QDialog QPushButton:hover,
QInputDialog QPushButton:hover {
    background-color: #3a3f53;
    border-color: #8588b7;
}

QMessageBox QPushButton:pressed,
QDialog QPushButton:pressed,
QInputDialog QPushButton:pressed {
    background-color: #454a61;
}

QInputDialog QLineEdit,
QInputDialog QComboBox {
    min-height: 34px;
    background: #12141b;
    color: #f0f1ff;
    border: 1px solid #44495c;
    border-radius: 9px;
    padding: 6px 10px;
}

QInputDialog QLineEdit:focus,
QInputDialog QComboBox:focus {
    border-color: #8f88ff;
}
'''

    return (
        text.rstrip()
        + addition
        + "\n"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # VERIFY FILES
    # --------------------------------------------------------

    missing = [
        str(path)
        for path
        in FILES.values()
        if not path.is_file()
    ]

    if missing:

        print()
        print(
            "ERROR: Required Litenova files were not found:"
        )

        for path in missing:

            print(
                " -",
                path,
            )

        print()
        print(
            "Place apply_ui_cleanup.py inside:"
        )

        print(
            r"C:\Projects\Litenova"
        )

        return 1

    # --------------------------------------------------------
    # READ CURRENT FILES
    # --------------------------------------------------------

    original = {
        key: path.read_text(
            encoding="utf-8-sig"
        )
        for key, path
        in FILES.items()
    }

    # --------------------------------------------------------
    # GENERATE UPDATED CODE IN MEMORY
    # --------------------------------------------------------

    try:

        changed = {
            "library": (
                patch_library(
                    original[
                        "library"
                    ]
                )
            ),

            "settings": (
                patch_settings(
                    original[
                        "settings"
                    ]
                )
            ),

            "book_card": (
                patch_book_card(
                    original[
                        "book_card"
                    ]
                )
            ),

            "dialogs": (
                patch_dialogs(
                    original[
                        "dialogs"
                    ]
                )
            ),

            "qss": (
                patch_qss(
                    original[
                        "qss"
                    ]
                )
            ),
        }

    except Exception as error:

        print()
        print(
            "ERROR: No project files were changed."
        )

        print(
            error
        )

        return 1

    # --------------------------------------------------------
    # SYNTAX CHECK BEFORE TOUCHING REAL FILES
    # --------------------------------------------------------

    temp_root = (
        ROOT
        / ".litenova_ui_cleanup_check"
    )

    if temp_root.exists():

        shutil.rmtree(
            temp_root,
            ignore_errors=True,
        )

    temp_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:

        for key in (
            "library",
            "settings",
            "book_card",
            "dialogs",
        ):

            temp_file = (
                temp_root
                / FILES[
                    key
                ].name
            )

            temp_file.write_text(
                changed[
                    key
                ],
                encoding="utf-8",
            )

            py_compile.compile(
                str(
                    temp_file
                ),
                doraise=True,
            )

    except Exception as error:

        print()
        print(
            "ERROR: Generated code failed syntax checking."
        )

        print(
            "No Litenova files were changed."
        )

        print()
        print(
            error
        )

        return 1

    finally:

        shutil.rmtree(
            temp_root,
            ignore_errors=True,
        )

    # --------------------------------------------------------
    # CREATE BACKUP
    # --------------------------------------------------------

    stamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    backup = (
        ROOT
        / (
            "Litenova_UI_Backup_"
            + stamp
        )
    )

    try:

        for key, path in (
            FILES.items()
        ):

            relative = (
                path.relative_to(
                    ROOT
                )
            )

            destination = (
                backup
                / relative
            )

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                path,
                destination,
            )

        # ----------------------------------------------------
        # WRITE UPDATED FILES
        # ----------------------------------------------------

        for key, path in (
            FILES.items()
        ):

            path.write_text(
                changed[
                    key
                ],
                encoding="utf-8",
            )

    except Exception as error:

        print()
        print(
            "ERROR while applying the update:"
        )

        print(
            error
        )

        print()
        print(
            "Attempting to restore the backup..."
        )

        for key, path in (
            FILES.items()
        ):

            saved = (
                backup
                / path.relative_to(
                    ROOT
                )
            )

            if saved.is_file():

                shutil.copy2(
                    saved,
                    path,
                )

        return 1

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    print()
    print(
        "=" * 62
    )

    print(
        "LITENOVA UI CLEANUP COMPLETE"
    )

    print(
        "=" * 62
    )

    print()

    print(
        "Removed:"
    )

    print(
        " - Show «Read» button setting"
    )

    print(
        " - Blue Read button on covers"
    )

    print(
        " - Bottom Library book count"
    )

    print(
        " - Scan another folder button"
    )

    print(
        " - Settings search bar"
    )

    print(
        " - Visible Settings scrollbar"
    )

    print()

    print(
        "Added / improved:"
    )

    print(
        " - Visible Delete Category button"
    )

    print(
        " - Existing Add Category support retained"
    )

    print(
        " - Cleaner category controls"
    )

    print(
        " - Better dropdown menus"
    )

    print(
        " - Better context menus"
    )

    print(
        " - Better confirmation popups"
    )

    print(
        " - Better input dialogs"
    )

    print(
        " - Improved Edit Book dialog"
    )

    print()

    print(
        "Backup created at:"
    )

    print(
        backup
    )

    print()

    print(
        "Now start Litenova with:"
    )

    print(
        "python main.py"
    )

    print()

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )