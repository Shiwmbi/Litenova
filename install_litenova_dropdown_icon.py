"""
Litenova Custom Dropdown Arrow Installer

Installs the supplied transparent dropdown arrow
and applies it to the Library dropdowns.

Updates:
    app/pages/library_page.py
    resources/icons/dropdown_arrow.png

Does NOT modify:
    main.py
    app/windows/main_window.py
    Database
    Books
    Reading history
"""

import base64
import shutil

from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

LIBRARY = (
    ROOT
    / "app"
    / "pages"
    / "library_page.py"
)

ICON = (
    ROOT
    / "resources"
    / "icons"
    / "dropdown_arrow.png"
)

MARKER = "# LITENOVA_CUSTOM_DROPDOWN_ARROW_V2"


# ============================================================
# CUSTOM DROPDOWN ICON
# ============================================================
#
# This contains the exact transparent PNG
# you uploaded.
#
# The installer creates the PNG automatically.
# You do not need to download the image separately.
# ============================================================

ICON_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAAABmJLR0QA/wD/AP+gvaeTAAAFOUlEQVR4nO3bX25UZQDG4fdrE8IVC2iLTTAxuABWYEAuVIKWbbAYl2GIhOgFhbgCFyDhAiMts4BeIUnn88IKBoVOZ87/8zw33MycnOTw/nrmTJsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA0LfS9wkM0WJRr58mt7LMtSTJVl5sJ092dsqznk+NFbh+qxOAfzk+rp/Vku+TfPmBlxyWmvt7e+V5l+fFaly/ixOAM8fH9Yta8mOSK+e89GSZHOzvlqddnBer+eNVvbmVPMgK16/UfLu3V37p4ryGTgDy9ifHrzn/P88/Xqfk7tWd8rjN82I1R4t6OzUPk1xe8S0npeaGO4Fkq+8TGIKz28ZVx58kl1Pz8GhRb7d1TqxmjfEnyZWzaz57s78DWCzq9dOa39Z8uzuBHq05/re2Sz6f+4PB2d8BnNbc3ODt7gR6sun4k42v/STMPgCp+XTDI1xOzaNXr+rXjZwP53q5qLc2HX+S1Hr2NeGMzT4ANakNHObSMnkgAu17uai3Ss2jbDj+JMlWI9d+1GYfgFLyoqFDXVomP/g40J6jRb3d2PiTlJrfmzjOmM0+ANslTX6f75lAS5r4zP++hq/9KM0+AGdPgQ8bPKQINKyN8Sc5nPs3AIkAJElKzf0kJw0eUgQa0tL4T86u+ewJQJK9vfJ8mRwked3gYUVgQy2N//UyOfBbgH8TgDP7u+VpLbmT5iPgK8I1NPVV33velJp7/o7jndn/JuD7Gv2a6Z03W8nB7m75qcFjTlZb16DUfLe3V35u8JijJwD/QwT6Y/zdEoAPEIHuGX/3BOAjRKA7xt8PATiHCLTP+PsjACsQgfYYf78EYEUi0Dzj758AXIAINMf4h0EALkgENmf8wyEAaxCB9Rn/sAjAmkTg4ox/eARgAyKwOuMfJgHYkAicz/iHSwAaIAIfZvzDJgANEYH/Mv7hE4AGicA7xj8OAtAwETD+MRGAFsw5AsY/LgLQkjlGwPjHRwBaNKcIGP84CUDL5hAB4x8vAejAlCNg/OMmAB2ZYgSMf/wEoENTioDxT4MAdGwKETD+6RCAHow5AsY/LQLQkzFGwPinRwB6NKYIGP80CUDPxhAB458uARiAIUfA+KdNAAZiiBEw/ukTgAEZUgSMfx4EYGCGEAHjnw8BGKA+I2D88yIAA9VHBIx/fgRgwLqMgPHPkwAMXBcRMP75EoARaDMCpyV/Gv98CcBIHC3q7dQ8TLNDfX32b7PHLLl7dac8bvCYtEQARqSlO4Em+ck/MgIwMgOOgPGPkACM0AAjYPwjJQAjNaAIGP+ICcCItfRg8CI88Bu5rb5PgPVd3SmPa8mdvHua36U3peae8Y+bO4AJ6OHjgNv+iRCAiegwAsY/IQIwIR1EwPgnRgAmpsUHgx74TZCHgBPT0oNBD/wmyh3ARDX4ccBt/4QJwIQ1EAHjnzgBmLgNImD8MyAAM7BGBIx/JjwEnIFPdsqTZfJNkpMVXn6yTL4y/nkQgJnY3y1PS82NJIcfedlhqbmxv1uednVe9MtHgBlaLOr10+RWlrmWJNnKi+3kyc5OedbzqQEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADA7PwFaS+a18TjcC4AAAAASUVORK5CYII="
)


# ============================================================
# LIBRARY DROPDOWN STYLING
# ============================================================

STYLE_METHOD = '''

    # LITENOVA_CUSTOM_DROPDOWN_ARROW_V2

    def install_custom_dropdown_arrow(self):
        """
        Apply the custom PNG arrow to the Library dropdowns.

        The main dropdown keeps its rounded border.

        The arrow itself has no separate box,
        border, or background.
        """

        from pathlib import Path

        import sys

        # ====================================================
        # LOCATE ICON
        # ====================================================

        base = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(__file__).resolve().parents[2],
            )
        )

        arrow_path = (
            base
            / "resources"
            / "icons"
            / "dropdown_arrow.png"
        )

        if not arrow_path.is_file():
            return

        # Use an absolute path so the icon loads
        # correctly on Windows.

        arrow_url = (
            arrow_path.resolve().as_posix()
        )

        # ====================================================
        # DROPDOWN STYLESHEET
        # ====================================================

        combo_style = f"""

            /* =============================================
               MAIN DROPDOWN
               ============================================= */

            QComboBox#libraryCategory,
            QComboBox#librarySideCombo {{

                background: #13151b;

                color: #e8e9fb;

                border: 1px solid #404554;

                border-radius: 10px;

                padding: 0px 34px 0px 12px;

                font-size: 13px;
            }}

            /* =============================================
               HOVER AND FOCUS
               ============================================= */

            QComboBox#libraryCategory:hover,
            QComboBox#librarySideCombo:hover,
            QComboBox#libraryCategory:focus,
            QComboBox#librarySideCombo:focus {{

                border: 1px solid #9393cf;
            }}

            /* =============================================
               REMOVE THE SEPARATE ARROW BOX
               ============================================= */

            QComboBox::drop-down,
            QComboBox::drop-down:hover,
            QComboBox::drop-down:on {{

                subcontrol-origin: padding;

                subcontrol-position: top right;

                width: 30px;

                background: transparent;

                border: none;

                border-radius: 0px;

                margin: 0px;

                padding: 0px;
            }}

            /* =============================================
               CUSTOM TRANSPARENT ARROW ICON
               ============================================= */

            QComboBox::down-arrow {{

                image: url("{arrow_url}");

                width: 24px;

                height: 24px;

                background: transparent;

                border: none;
            }}

            /* =============================================
               KEEP ARROW CENTERED WHEN OPEN
               ============================================= */

            QComboBox::down-arrow:on {{

                top: 0px;

                left: 0px;
            }}

        """

        # ====================================================
        # APPLY TO ALL LIBRARY DROPDOWNS
        # ====================================================

        for combo in (

            self.category_filter,

            self.sort_combo,

            self.type_combo,

        ):

            combo.setStyleSheet(
                combo_style
            )

'''


# ============================================================
# INSTALL THE FIX
# ============================================================

def main():

    # ========================================================
    # VERIFY THE PROJECT FILE
    # ========================================================

    if not LIBRARY.is_file():

        raise SystemExit(
            f"Cannot find Library file: {LIBRARY}"
        )

    # ========================================================
    # READ THE CURRENT LIBRARY CODE
    # ========================================================

    original = LIBRARY.read_text(
        encoding="utf-8-sig"
    )

    call = "        self.apply_page_style()"

    anchor = "    def apply_page_style(self):"

    # ========================================================
    # CHECK WHETHER THE FIX IS ALREADY INSTALLED
    # ========================================================

    if MARKER in original:

        print(
            "The Library dropdown fix is already installed."
        )

        print(
            "No additional Python changes were made."
        )

    else:

        # ====================================================
        # CHECK THE EXISTING FILE STRUCTURE
        # ====================================================

        if (
            original.count(call) != 1
            or original.count(anchor) != 1
        ):

            raise SystemExit(
                "Your library_page.py has a different structure. "
                "No files were changed."
            )

        # ====================================================
        # INSTALL THE DROPDOWN METHOD
        # ====================================================

        updated = original.replace(

            call,

            call
            + "\n"
            + "        self.install_custom_dropdown_arrow()",

            1,

        )

        updated = updated.replace(

            anchor,

            STYLE_METHOD + anchor,

            1,

        )

        # ====================================================
        # VERIFY THE UPDATED PYTHON CODE
        # ====================================================

        compile(
            updated,
            str(LIBRARY),
            "exec",
        )

        # ====================================================
        # CREATE BACKUP
        # ====================================================

        backup = LIBRARY.with_name(
            "library_page.before_arrow_icon.bak"
        )

        if not backup.exists():

            shutil.copy2(
                LIBRARY,
                backup,
            )

        # ====================================================
        # SAVE UPDATED LIBRARY
        # ====================================================

        LIBRARY.write_text(
            updated,
            encoding="utf-8",
        )

        print(
            "Updated: app/pages/library_page.py"
        )

        print(
            f"Backup created: {backup.name}"
        )

    # ========================================================
    # INSTALL THE PNG ICON
    # ========================================================

    ICON.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    image_bytes = base64.b64decode(
        ICON_BASE64
    )

    # ========================================================
    # BACK UP A DIFFERENT EXISTING ICON
    # ========================================================

    if (
        ICON.exists()
        and ICON.read_bytes() != image_bytes
    ):

        previous_icon = ICON.with_name(
            "dropdown_arrow.before_fix.png"
        )

        if not previous_icon.exists():

            shutil.copy2(
                ICON,
                previous_icon,
            )

    # ========================================================
    # SAVE THE CUSTOM ICON
    # ========================================================

    ICON.write_bytes(
        image_bytes
    )

    print(
        "Installed: resources/icons/dropdown_arrow.png"
    )

    print(
        "main.py and main_window.py were not modified."
    )

    print(
        "Restart Litenova with: python main.py"
    )


# ============================================================
# RUN INSTALLER
# ============================================================

if __name__ == "__main__":

    main()