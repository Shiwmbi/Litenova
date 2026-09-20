"""
Litenova Display Panel Alignment Fix

Fixes the alignment of:
- Display heading
- Display mode label
- Grid size label
- Sort heading
- Filters heading
- Other labels in the Display panel

The script preserves:
- Existing Library functionality
- Custom categories
- Reading progress
- Toggle switches
- Dropdown arrow icons
- EPUB and CBZ readers

Only app/pages/library_page.py is modified.
"""

from pathlib import Path
from shutil import copy2


# ============================================================
# PROJECT FILES
# ============================================================

ROOT = Path(__file__).resolve().parent

LIBRARY_FILE = (
    ROOT
    / "app"
    / "pages"
    / "library_page.py"
)

BACKUP_FILE = (
    ROOT
    / "app"
    / "pages"
    / "library_page.before_alignment_fix.bak"
)

MARKER = "LITENOVA_DISPLAY_ALIGNMENT_V1"


# ============================================================
# COMPLETE REPLACEMENT FOR PANEL LABEL METHODS
# ============================================================

NEW_LABEL_METHODS = '''
    # LITENOVA_DISPLAY_ALIGNMENT_V1

    # ========================================================
    # DISPLAY PANEL HEADING
    # ========================================================

    def side_heading(self, text):
        """
        Create a section heading with no additional
        horizontal padding, indentation, or margin.

        Display, Sort, and Filters will use the
        same left alignment as the panel labels.
        """

        label = QLabel(text)

        label.setObjectName(
            "librarySideHeading"
        )

        # Remove QLabel's internal indentation.

        label.setIndent(0)

        label.setMargin(0)

        # Keep the content aligned to the left.

        label.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        # Remove additional widget margins.

        label.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        # Remove internal stylesheet padding that
        # can cause headings to appear farther
        # to the right than the other controls.

        label.setStyleSheet("""
            QLabel#librarySideHeading {
                background: transparent;

                color: #c1c5ff;

                font-size: 19px;
                font-weight: 700;

                border: none;

                margin: 0px;

                padding: 0px;
            }
        """)

        return label

    # ========================================================
    # DISPLAY PANEL LABEL
    # ========================================================

    def side_label(self, text):
        """
        Create a regular panel label using the
        same left alignment as the section headings.
        """

        label = QLabel(text)

        label.setObjectName(
            "librarySideLabel"
        )

        label.setIndent(0)

        label.setMargin(0)

        label.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        label.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        label.setStyleSheet("""
            QLabel#librarySideLabel {
                background: transparent;

                color: #cbd0e5;

                font-size: 14px;

                border: none;

                margin: 0px;

                padding: 0px;
            }
        """)

        return label

'''


# ============================================================
# APPLY ALIGNMENT FIX
# ============================================================

def main():

    # ========================================================
    # CHECK PROJECT FILE
    # ========================================================

    if not LIBRARY_FILE.is_file():

        print(
            "ERROR: Cannot find library_page.py"
        )

        print(
            f"Expected location: {LIBRARY_FILE}"
        )

        return

    # ========================================================
    # READ EXISTING LIBRARY CODE
    # ========================================================

    original = LIBRARY_FILE.read_text(
        encoding="utf-8-sig"
    )

    # ========================================================
    # PREVENT DUPLICATE INSTALLATION
    # ========================================================

    if MARKER in original:

        print(
            "Display panel alignment fix "
            "is already installed."
        )

        print(
            "No files were changed."
        )

        return

    # ========================================================
    # LOCATE EXISTING LABEL METHODS
    # ========================================================

    start_marker = (
        "    def side_heading("
    )

    end_marker = (
        "    def side_rule("
    )

    start = original.find(
        start_marker
    )

    end = original.find(
        end_marker,
        start,
    )

    # ========================================================
    # VERIFY FILE STRUCTURE
    # ========================================================

    if start == -1 or end == -1:

        print(
            "ERROR: Could not locate the Display "
            "panel label methods."
        )

        print(
            "Your Library file may have a "
            "different structure."
        )

        print(
            "No files were changed."
        )

        return

    # ========================================================
    # BUILD UPDATED LIBRARY CODE
    # ========================================================

    updated = (
        original[:start]
        + NEW_LABEL_METHODS
        + original[end:]
    )

    # ========================================================
    # CHECK FOR PYTHON SYNTAX ERRORS
    # ========================================================

    try:

        compile(
            updated,
            str(LIBRARY_FILE),
            "exec",
        )

    except SyntaxError as error:

        print(
            "ERROR: The updated Library code "
            "did not pass the syntax check."
        )

        print(error)

        print(
            "No files were changed."
        )

        return

    # ========================================================
    # BACK UP EXISTING LIBRARY PAGE
    # ========================================================

    if not BACKUP_FILE.exists():

        copy2(
            LIBRARY_FILE,
            BACKUP_FILE,
        )

        print(
            "Backup created:"
        )

        print(
            BACKUP_FILE
        )

    # ========================================================
    # SAVE UPDATED LIBRARY PAGE
    # ========================================================

    LIBRARY_FILE.write_text(
        updated,
        encoding="utf-8",
    )

    print()

    print(
        "Display panel alignment fixed successfully!"
    )

    print()

    print(
        "Updated: app/pages/library_page.py"
    )

    print()

    print(
        "The following files were NOT modified:"
    )

    print(
        "- main.py"
    )

    print(
        "- main_window.py"
    )

    print(
        "- dark.qss"
    )

    print(
        "- light.qss"
    )

    print(
        "- Icon files"
    )

    print(
        "- Database and book files"
    )

    print()

    print(
        "Restart Litenova to see the changes."
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()