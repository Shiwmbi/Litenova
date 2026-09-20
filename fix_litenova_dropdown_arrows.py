"""
Litenova Dropdown Arrow Fix

Removes the separate rectangular box around
dropdown arrows while keeping the main dropdown
border and existing functionality.

Updates only:
- app/styles/dark.qss
- app/pages/library_page.py
"""

from pathlib import Path
from shutil import copy2


ROOT = Path(__file__).resolve().parent

DARK = ROOT / "app" / "styles" / "dark.qss"

LIBRARY = ROOT / "app" / "pages" / "library_page.py"

MARKER = "/* LITENOVA_CLEAN_DROPDOWN_ARROWS_V1 */"


# ============================================================
# EXISTING LIBRARY STYLING
# ============================================================

OLD_LIBRARY_STYLE = '''
            QLineEdit#librarySearch,
            QComboBox#libraryCategory,
            QComboBox#librarySideCombo {
                background: #13151b;
                color: #e8e9fb;
                border: 1px solid #404554;
                border-radius: 10px;
                padding: 7px 12px;
                font-size: 13px;
            }

            QLineEdit#librarySearch:focus,
            QComboBox#libraryCategory:focus {
                border: 1px solid #9393cf;
            }
'''


# ============================================================
# UPDATED LIBRARY STYLING
# ============================================================

NEW_LIBRARY_STYLE = '''
            /* Keep the existing search bar appearance. */

            QLineEdit#librarySearch {
                background: #13151b;
                color: #e8e9fb;
                border: 1px solid #404554;
                border-radius: 10px;
                padding: 7px 12px;
                font-size: 13px;
            }

            QLineEdit#librarySearch:focus {
                border: 1px solid #9393cf;
            }

            /* LITENOVA_CLEAN_DROPDOWN_ARROWS_V1 */

            /* Main dropdown: retain one rounded border. */

            QComboBox#libraryCategory,
            QComboBox#librarySideCombo {
                background: #13151b;
                color: #e8e9fb;

                border: 1px solid #404554;
                border-radius: 10px;

                padding: 7px 34px 7px 12px;

                font-size: 13px;
            }

            QComboBox#libraryCategory:focus,
            QComboBox#librarySideCombo:focus {
                border: 1px solid #9393cf;
            }

            /* Remove the separate box around the arrow. */

            QComboBox#libraryCategory::drop-down,
            QComboBox#librarySideCombo::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;

                width: 30px;

                background: transparent;

                border: none;
                border-radius: 0;

                padding: 0;
                margin: 0;
            }

            /* Prevent a box appearing on hover or click. */

            QComboBox#libraryCategory::drop-down:hover,
            QComboBox#libraryCategory::drop-down:on,
            QComboBox#librarySideCombo::drop-down:hover,
            QComboBox#librarySideCombo::drop-down:on {
                background: transparent;
                border: none;
            }

            /* Prevent the arrow from shifting when opened. */

            QComboBox#libraryCategory::down-arrow:on,
            QComboBox#librarySideCombo::down-arrow:on {
                top: 0;
                left: 0;
            }
'''


# ============================================================
# GLOBAL DARK THEME
# ============================================================

GLOBAL_DARK_STYLE = '''

/* LITENOVA_CLEAN_DROPDOWN_ARROWS_V1 */

/* Remove the separate arrow box from dark-theme dropdowns. */

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;

    width: 30px;

    background: transparent;

    border: none;
    border-radius: 0;

    padding: 0;
    margin: 0;
}

/* Remove the arrow box's hover and pressed appearance. */

QComboBox::drop-down:hover,
QComboBox::drop-down:on {
    background: transparent;
    border: none;
}

/* Keep the arrow in its original position. */

QComboBox::down-arrow:on {
    top: 0;
    left: 0;
}
'''


# ============================================================
# APPLY THE FIX
# ============================================================

def main():

    # --------------------------------------------------------
    # CHECK THAT BOTH FILES EXIST
    # --------------------------------------------------------

    for path in (DARK, LIBRARY):

        if not path.is_file():

            raise FileNotFoundError(
                f"Missing project file: {path}"
            )

    # --------------------------------------------------------
    # READ EXISTING FILES
    # --------------------------------------------------------

    dark_text = DARK.read_text(
        encoding="utf-8-sig"
    )

    library_text = LIBRARY.read_text(
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # VERIFY THE LIBRARY CODE BEFORE CHANGING ANYTHING
    # --------------------------------------------------------

    if (
        MARKER not in library_text
        and library_text.count(OLD_LIBRARY_STYLE) != 1
    ):

        raise RuntimeError(
            "The Library stylesheet is different "
            "from the uploaded version. "
            "No files were changed."
        )

    # --------------------------------------------------------
    # PREPARE GLOBAL THEME
    # --------------------------------------------------------

    if MARKER not in dark_text:

        dark_new = (
            dark_text.rstrip()
            + GLOBAL_DARK_STYLE
            + "\n"
        )

    else:

        dark_new = dark_text

    # --------------------------------------------------------
    # PREPARE LIBRARY PAGE
    # --------------------------------------------------------

    if MARKER not in library_text:

        library_new = library_text.replace(
            OLD_LIBRARY_STYLE,
            NEW_LIBRARY_STYLE,
            1,
        )

    else:

        library_new = library_text

    # --------------------------------------------------------
    # SAVE BACKUPS AND APPLY THE CHANGES
    # --------------------------------------------------------

    for path, old, new in (
        (DARK, dark_text, dark_new),
        (LIBRARY, library_text, library_new),
    ):

        if new == old:

            print(
                f"Already updated: {path.relative_to(ROOT)}"
            )

            continue

        # Create a backup before modifying the file.

        backup = path.with_name(
            path.name + ".before_arrow_fix.bak"
        )

        if not backup.exists():

            copy2(
                path,
                backup,
            )

        # Save the updated code.

        path.write_text(
            new,
            encoding="utf-8",
        )

        print(
            f"Updated: {path.relative_to(ROOT)}"
        )

    print(
        "Done. main.py and main_window.py were not changed."
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()