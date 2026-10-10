from __future__ import annotations

import os
import re
import shutil
import tempfile
import py_compile

from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent


# ============================================================
# SETTINGS PAGE
# ============================================================

def patch_settings(text):
    # Give the label wrapper a transparent-only object name.
    if 'setObjectName("settingsRowLabel")' not in text:
        text, _ = re.subn(
            r'(\n\s{4}box\s*=\s*QWidget\(\)\n)',
            r'\1\n    box.setObjectName("settingsRowLabel")\n',
            text,
            count=1,
        )

    # Give each SettingsCard row a transparent-only object name.
    if 'setObjectName("settingsRow")' not in text:
        match = re.search(
            r'(\n\s{4}def add_row\(.*?\n)(.*?)(\n\s{4}def |\Z)',
            text,
            re.S,
        )

        if match:
            region = match.group(2)

            region, count = re.subn(
                r'(\n\s{8}widget\s*=\s*QWidget\(\s*self\s*\)\n)',
                r'\1\n        widget.setObjectName("settingsRow")\n',
                region,
                count=1,
            )

            if count:
                text = (
                    text[:match.start(2)]
                    + region
                    + text[match.end(2):]
                )

    # Make the Reader font-size helper widget transparent too.
    if 'setObjectName("settingsInlineControl")' not in text:
        text, _ = re.subn(
            r'(\n\s{8}font_controls\s*=\s*QWidget\(\)\n)',
            r'\1\n        font_controls.setObjectName("settingsInlineControl")\n',
            text,
            count=1,
        )

    # --------------------------------------------------------
    # REMOVE SETTINGS SEARCH BAR
    # --------------------------------------------------------

    text, _ = re.subn(
        (
            r'\n\s{8}self\.search\s*=\s*QLineEdit\(self\)'
            r'.*?'
            r'\n\s{8}title_row\.addWidget\('
            r'\s*self\.search.*?\)\n'
        ),
        '\n',
        text,
        count=1,
        flags=re.S,
    )

    # --------------------------------------------------------
    # HIDE SETTINGS SCROLLBAR
    # --------------------------------------------------------

    # Supports both:
    #
    # scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    #
    # and:
    #
    # scroller.setHorizontalScrollBarPolicy(
    #     Qt.ScrollBarAlwaysOff
    # )
    if not re.search(
        r'scroller\.setVerticalScrollBarPolicy\('
        r'\s*Qt\.ScrollBarAlwaysOff\s*\)',
        text,
        re.S,
    ):
        text, _ = re.subn(
            (
                r'(\n\s{8}scroller\.setHorizontalScrollBarPolicy\('
                r'\s*Qt\.ScrollBarAlwaysOff\s*\)\n)'
            ),
            (
                r'\1'
                '        scroller.setVerticalScrollBarPolicy(\n'
                '            Qt.ScrollBarAlwaysOff\n'
                '        )\n'
            ),
            text,
            count=1,
            flags=re.S,
        )

    # --------------------------------------------------------
    # HIDE ADVANCED CARD IF IT STILL EXISTS
    # --------------------------------------------------------

    text, _ = re.subn(
        (
            r'\n\s{8}(?:left_column|right_column)\.addWidget\('
            r'\s*self\.advanced\s*\)\n'
        ),
        '\n',
        text,
        count=1,
        flags=re.S,
    )

    # --------------------------------------------------------
    # CLEAN SETTINGS VISUALS
    # --------------------------------------------------------

    marker = 'LITENOVA_SETTINGS_CLEAN_ROWS_V3'

    if marker not in text:
        index = text.find('\n    def load_settings')

        if index < 0:
            index = text.find('\n    def filter_settings')

        if index < 0:
            raise RuntimeError(
                'Could not locate the end of the Settings styling section.'
            )

        extra_style = '''
        # LITENOVA_SETTINGS_CLEAN_ROWS_V3
        self.setStyleSheet(
            self.styleSheet()
            + """
            QWidget#settingsRow,
            QWidget#settingsRowLabel,
            QWidget#settingsInlineControl {
                background: transparent;
                background-color: transparent;
                border: none;
            }

            QSlider {
                background: transparent;
                background-color: transparent;
                border: none;
            }

            QSlider::groove:horizontal {
                background: #3b4052;
                height: 5px;
                border: none;
                border-radius: 2px;
            }

            QSlider::sub-page:horizontal {
                background: #7472c6;
                border-radius: 2px;
            }

            QSlider::add-page:horizontal {
                background: #3b4052;
                border-radius: 2px;
            }

            QSlider::handle:horizontal {
                background: #c5c4fa;
                width: 15px;
                margin: -5px 0;
                border-radius: 7px;
            }

            QPushButton#settingsAction {
                background: #20232d;
                color: #e9e8ff;
                border: 1px solid #414658;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 12px;
            }

            QPushButton#settingsAction:hover {
                background: #292d39;
                border-color: #646a82;
            }

            QPushButton#settingsAction:pressed {
                background: #303441;
            }

            QComboBox QAbstractItemView {
                background: #1a1c24;
                color: #e7e8ff;
                selection-background-color: #3d425b;
                selection-color: #ffffff;
                border: 1px solid #464b5e;
                border-radius: 9px;
                outline: none;
                padding: 6px;
            }

            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 5px 9px;
            }
            """
        )
'''

        text = (
            text[:index]
            + extra_style
            + text[index:]
        )

    return text


# ============================================================
# LIBRARY PAGE
# ============================================================

def patch_library(text):
    # --------------------------------------------------------
    # ADD VISIBLE DELETE CATEGORY BUTTON
    # --------------------------------------------------------

    if 'self.delete_category_button = QPushButton' not in text:
        pattern = (
            r'(\n\s{8}header\.addWidget\('
            r'\s*self\.new_category_button\s*\)\n)'
        )

        block = '''
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

        self.delete_category_button.setToolTip(
            "Delete the selected custom category"
        )

        self.delete_category_button.clicked.connect(
            self.delete_selected_category
        )

        header.addWidget(
            self.delete_category_button
        )
'''

        text, _ = re.subn(
            pattern,
            lambda match: match.group(1) + block,
            text,
            count=1,
            flags=re.S,
        )

    # --------------------------------------------------------
    # REMOVE SHOW «READ» OPTION
    # --------------------------------------------------------

    patterns = (
        (
            r'\n\s{8}self\.show_read_box\s*=\s*\('
            r'\s*self\.toggle_checkbox\('
            r'\s*"Show «Read» button",'
            r'\s*"Show quick action button on covers",'
            r'\s*\)\s*\)\n'
        ),
        (
            r'\n\s{8}self\.show_read_box\.setChecked\('
            r'\s*self\.setting_bool\('
            r'\s*"library_show_read",'
            r'\s*True,?\s*\)\s*\)\n'
        ),
        (
            r'\n\s{8}self\.show_read_box\.toggled\.connect\('
            r'\s*self\.display_options_changed\s*\)\n'
        ),
        (
            r'\n\s{8}side\.addWidget\('
            r'\s*self\.show_read_box\s*\)\n'
        ),
        (
            r'\n\s{8}self\.preferences\.setValue\('
            r'\s*"library_show_read",'
            r'\s*self\.show_read_box\.isChecked\(\),?'
            r'\s*\)\n'
        ),
        (
            r'\n\s{16}show_read_button\s*=\s*\('
            r'\s*self\.show_read_box\.isChecked\(\)'
            r'\s*\),?\n'
        ),
        (
            r'\n\s{16}show_read_button\s*=\s*'
            r'self\.show_read_box\.isChecked\(\),?\n'
        ),
    )

    for pattern in patterns:
        text, _ = re.subn(
            pattern,
            '\n',
            text,
            count=1,
            flags=re.S,
        )

    # Remove remaining cache references.
    text = re.sub(
        (
            r'\n\s*bool\('
            r'\s*self\.show_read_box\.isChecked\(\)'
            r'\s*\),?'
        ),
        '',
        text,
    )

    text = re.sub(
        (
            r'\n\s*self\.show_read_box\.isChecked\(\),?'
        ),
        '',
        text,
    )

    # --------------------------------------------------------
    # REMOVE BOTTOM LIBRARY FOOTER
    # --------------------------------------------------------

    text, _ = re.subn(
        (
            r'\n\s{8}# =+\n'
            r'\s{8}# FOOTER\n'
            r'\s{8}# =+\n'
            r'.*?'
            r'\n\s{8}root\.addLayout\('
            r'\s*footer\s*\)\n'
        ),
        '\n',
        text,
        count=1,
        flags=re.S,
    )

    # Remove later attempts to update the old footer label.
    text, _ = re.subn(
        (
            r'\n\s{8}self\.status_label\.setText\('
            r'.*?\)\n'
        ),
        '\n',
        text,
        count=3,
        flags=re.S,
    )

    # --------------------------------------------------------
    # DELETE CATEGORY BUTTON STYLE
    # --------------------------------------------------------

    if 'QPushButton#libraryDeleteCategory' not in text:
        index = text.find(
            '            QPushButton#libraryAddFolder:hover'
        )

        if index >= 0:
            end = text.find(
                '\n            }',
                index,
            )

            if end >= 0:
                end += len('\n            }')

                block = '''

            QPushButton#libraryDeleteCategory {
                background: #201a1e;
                color: #e9b9bf;
                border: 1px solid #68404a;
                border-radius: 11px;
                padding: 0 15px;
                font-size: 13px;
            }

            QPushButton#libraryDeleteCategory:hover {
                background: #342329;
                border-color: #965563;
                color: #ffd6db;
            }
'''

                text = (
                    text[:end]
                    + block
                    + text[end:]
                )

    return text


# ============================================================
# BOOK CARD
# ============================================================

def patch_book_card(text):
    # Remove constructor parameter.
    text = re.sub(
        (
            r'(progress=0\.0,\s*show_progress=True,\s*)'
            r'show_read_button=True,\s*'
        ),
        r'\1',
        text,
        count=1,
    )

    # Remove stored flag.
    text = re.sub(
        (
            r'\n\s{8}self\.show_read_button\s*='
            r'\s*show_read_button\n'
        ),
        '\n',
        text,
        count=1,
    )

    # Remove blue quick-read button.
    text, _ = re.subn(
        (
            r'\n\s{8}self\.read_button\s*=\s*'
            r'QPushButton\(self\.cover_box\)'
            r'.*?'
            r'\n\s{8}self\.read_button\.clicked\.connect\('
            r'self\.open_book\)\n'
        ),
        '\n',
        text,
        count=1,
        flags=re.S,
    )

    # Remove its style.
    text, _ = re.subn(
        (
            r'\n\s{12}QPushButton#libraryReadButton \{'
            r'.*?'
            r'\n\s{12}\}\n'
            r'\s{12}QPushButton#libraryReadButton:hover '
            r'\{.*?\}\n'
        ),
        '\n',
        text,
        count=1,
        flags=re.S,
    )

    return text


# ============================================================
# GLOBAL DARK QSS
# ============================================================

def patch_dark_qss(text):
    marker = 'LITENOVA_POLISHED_POPUPS_V3'

    if marker in text:
        return text

    return (
        text.rstrip()
        + r'''


/* LITENOVA_POLISHED_POPUPS_V3 */

/* =========================================================
   CLEAN DROPDOWNS
   ========================================================= */

QComboBox QAbstractItemView {
    background-color: #1a1c24;
    color: #eeeeee;
    border: 1px solid #464b5e;
    border-radius: 9px;
    outline: none;
    padding: 6px;
    selection-background-color: #3d425b;
    selection-color: #ffffff;
}

QComboBox QAbstractItemView::item {
    min-height: 32px;
    padding: 5px 9px;
}

/* =========================================================
   CONTEXT MENUS
   ========================================================= */

QMenu {
    background-color: #1a1c24;
    color: #eeeeee;
    border: 1px solid #464b5e;
    border-radius: 9px;
    padding: 6px;
}

QMenu::item {
    min-width: 180px;
    min-height: 28px;
    padding: 6px 26px 6px 10px;
    margin: 1px 0px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: #3d425b;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: #343846;
    margin: 6px 8px;
}

/* =========================================================
   POPUPS / DIALOGS
   ========================================================= */

QMessageBox,
QDialog,
QInputDialog {
    background-color: #1d2029;
    color: #eeeeee;
}

QMessageBox QLabel,
QMessageBox QLabel#qt_msgbox_label,
QMessageBox QLabel#qt_msgbox_informativelabel,
QDialog QLabel,
QInputDialog QLabel {
    background: transparent;
    background-color: transparent;
    border: none;
}

QMessageBox QPushButton,
QDialog QPushButton,
QInputDialog QPushButton {
    min-width: 88px;
    min-height: 30px;
    color: #eeeeee;
    background-color: #252934;
    border: 1px solid #454a5c;
    border-radius: 8px;
    padding: 6px 14px;
}

QMessageBox QPushButton:hover,
QDialog QPushButton:hover,
QInputDialog QPushButton:hover {
    background-color: #303542;
    border-color: #6b718b;
}

QInputDialog QLineEdit,
QInputDialog QComboBox {
    min-height: 34px;
    background-color: #14161c;
    color: #eeeeee;
    border: 1px solid #41465a;
    border-radius: 8px;
    padding: 6px 10px;
}
'''
        + '\n'
    )


# ============================================================
# MAIN
# ============================================================

def main():
    files = {
        'library': (
            ROOT
            / 'app'
            / 'pages'
            / 'library_page.py'
        ),
        'settings': (
            ROOT
            / 'app'
            / 'pages'
            / 'settings_page.py'
        ),
        'book_card': (
            ROOT
            / 'app'
            / 'widgets'
            / 'book_card.py'
        ),
        'dark_qss': (
            ROOT
            / 'app'
            / 'styles'
            / 'dark.qss'
        ),
    }

    if not (ROOT / 'main.py').is_file():
        print()
        print(
            r'ERROR: Save apply_ui_fix.py inside C:\Projects\Litenova'
        )
        return 1

    missing = [
        str(path)
        for path in files.values()
        if not path.is_file()
    ]

    if missing:
        print()
        print('ERROR: Missing required file(s):')

        for path in missing:
            print(' -', path)

        return 1

    original = {
        name: path.read_text(
            encoding='utf-8-sig'
        )
        for name, path in files.items()
    }

    try:
        changed = {
            'library': patch_library(
                original['library']
            ),
            'settings': patch_settings(
                original['settings']
            ),
            'book_card': patch_book_card(
                original['book_card']
            ),
            'dark_qss': patch_dark_qss(
                original['dark_qss']
            ),
        }

    except Exception as error:
        print()
        print('ERROR: Nothing was changed.')
        print(error)
        return 1

    # --------------------------------------------------------
    # SYNTAX CHECK BEFORE CHANGING YOUR PROJECT
    # --------------------------------------------------------

    temp = Path(
        tempfile.mkdtemp(
            prefix='litenova_ui_check_'
        )
    )

    try:
        for name in (
            'library',
            'settings',
            'book_card',
        ):
            test_file = (
                temp
                / f'{name}.py'
            )

            test_file.write_text(
                changed[name],
                encoding='utf-8',
            )

            py_compile.compile(
                str(test_file),
                doraise=True,
            )

    except Exception as error:
        print()
        print(
            'ERROR: The generated code failed syntax checking.'
        )
        print(
            'Nothing in your Litenova project was changed.'
        )
        print()
        print(error)
        return 1

    finally:
        shutil.rmtree(
            temp,
            ignore_errors=True,
        )

    # --------------------------------------------------------
    # BACKUP CURRENT FILES
    # --------------------------------------------------------

    stamp = datetime.now().strftime(
        '%Y%m%d_%H%M%S'
    )

    backup = (
        ROOT
        / f'Litenova_UI_PreFix_{stamp}'
    )

    try:
        for name, path in files.items():
            destination = (
                backup
                / path.relative_to(ROOT)
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
        # ATOMIC WRITE
        # ----------------------------------------------------

        for name, path in files.items():
            temporary = path.with_name(
                path.name + '.new'
            )

            temporary.write_text(
                changed[name],
                encoding='utf-8',
            )

            os.replace(
                temporary,
                path,
            )

    except Exception as error:
        print()
        print('ERROR while writing the updated files:')
        print(error)
        print()
        print('Your backup is here:')
        print(backup)
        return 1

    print()
    print('=' * 68)
    print('LITENOVA UI FIXES APPLIED SUCCESSFULLY')
    print('=' * 68)
    print()
    print('Applied:')
    print(' - Removed Settings search bar')
    print(' - Hid visible Settings scrollbar')
    print(' - Removed the highlighted Settings-row look')
    print(' - Cleaned Settings sliders')
    print(' - Cleaned Settings action buttons')
    print(' - Hid Advanced card if still present')
    print(' - Removed Show «Read» option')
    print(' - Removed blue Read buttons from covers')
    print(' - Kept Add Category')
    print(' - Added visible Delete Category button')
    print(' - Removed bottom Library book count')
    print(' - Removed Scan another folder')
    print(' - Improved dropdown menus')
    print(' - Improved context menus')
    print(' - Improved popup/dialog styling')
    print()
    print('Backup created at:')
    print(backup)
    print()
    print('Next run:')
    print(
        r'python -m py_compile '
        r'.\app\pages\library_page.py '
        r'.\app\pages\settings_page.py '
        r'.\app\widgets\book_card.py'
    )
    print()
    print('Then:')
    print('python main.py')
    print()

    return 0


if __name__ == '__main__':
    raise SystemExit(
        main()
    )