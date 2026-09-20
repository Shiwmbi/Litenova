"""Update only the Litenova Library display panel; preserve the rest of the app.

Run from C:\\Projects\\Litenova with:
    python fix_litenova_display_panel.py
"""

from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parent
LIBRARY = ROOT / "app" / "pages" / "library_page.py"
MARKER = "LITENOVA_DISPLAY_PANEL_V1"

TOGGLE_CLASS = '''

# LITENOVA_DISPLAY_PANEL_V1
class DisplayToggle(QCheckBox):
    """A clickable, accessible checkbox drawn as a lavender pill switch."""

    def __init__(self, title, description, parent=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        self.setAccessibleName(title)
        self.setToolTip(description)
        self.setFixedHeight(65)
        self.setCursor(Qt.PointingHandCursor)
        self.toggled.connect(lambda _checked: self.update())

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        x = self.width() - 57
        y = (self.height() - 30) / 2
        painter.setBrush(QColor("#51527f" if self.isChecked() else "#303344"))
        painter.drawRoundedRect(QRectF(x, y, 53, 30), 15, 15)
        painter.setBrush(QColor("#c5c4fa" if self.isChecked() else "#858aa6"))
        painter.drawEllipse(QRectF(x + (27 if self.isChecked() else 3), y + 3, 24, 24))

        font = painter.font()
        font.setPixelSize(14)
        painter.setFont(font)
        painter.setPen(QColor("#e7e8f6"))
        painter.drawText(0, 25, self.title)

        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(QColor("#aeb3c9"))
        painter.drawText(0, 46, self.description)
        painter.end()

'''

TOGGLE_METHOD = '''    def toggle_checkbox(self, text, description):
        return DisplayToggle(text, description, self)

'''

FILTER_SEARCH = '''        # A second search field in the side panel, synchronized with
        # the main Library search instead of applying a second filter.
        self.side_search_input = QLineEdit()
        self.side_search_input.setObjectName("librarySideSearch")
        self.side_search_input.setPlaceholderText("Search files...")
        self.side_search_input.setClearButtonEnabled(True)
        self.side_search_input.setFixedHeight(42)
        self.side_search_input.addAction(
            ui_icon("search"), QLineEdit.LeadingPosition
        )
        self.side_search_input.textChanged.connect(self.search_input.setText)
        self.search_input.textChanged.connect(self.side_search_input.setText)
        side.addWidget(self.side_search_input)

'''

PANEL_CSS = '''
            /* LITENOVA_DISPLAY_PANEL_V1 - panel-only styling */
            QLabel#librarySideHeading {
                color: #c1c5ff;
                font-size: 19px;
                font-weight: 700;
                padding-top: 4px;
            }
            QLabel#librarySideLabel {
                color: #cbd0e5;
                font-size: 14px;
            }
            QPushButton#libraryModeButton {
                background: #13151b;
                color: #e3e4f1;
                border: 1px solid #4a4d60;
                border-radius: 17px;
                font-size: 14px;
            }
            QPushButton#libraryModeButton:checked {
                background: #3e4163;
                border: 1px solid #777bad;
                color: #f0efff;
            }
            QFrame#librarySideRule {
                background: #3b3e50;
                border: none;
                max-height: 1px;
            }
            QLineEdit#librarySideSearch {
                background: #12151b;
                color: #e8e9fb;
                border: 1px solid #404554;
                border-radius: 11px;
                padding-left: 9px;
                padding-right: 8px;
                font-size: 13px;
            }
            QLineEdit#librarySideSearch:focus {
                border: 1px solid #9393cf;
            }
            QSlider#libraryGridSize::groove:horizontal {
                background: #50527d;
                height: 8px;
                border-radius: 4px;
            }
            QSlider#libraryGridSize::handle:horizontal {
                background: #c5c4ff;
                width: 8px;
                margin: -9px 0px;
                border-radius: 4px;
            }
'''


def replace_once(source, original, updated, label):
    count = source.count(original)
    if count != 1:
        raise RuntimeError(
            f"Cannot locate {label} uniquely (found {count}). "
            "No files were changed."
        )
    return source.replace(original, updated, 1)


def main():
    if not LIBRARY.is_file():
        raise SystemExit(f"Library page not found: {LIBRARY}")

    source = LIBRARY.read_text(encoding="utf-8-sig")
    if MARKER in source:
        print("Display panel fix is already installed; no changes made.")
        return

    updated = source
    updated = replace_once(
        updated,
        "from PySide6.QtGui import QIcon",
        "from PySide6.QtGui import QIcon, QColor, QPainter\nfrom PySide6.QtCore import QRectF",
        "Qt drawing imports",
    )
    updated = replace_once(
        updated,
        "class LibraryPage(QWidget):",
        TOGGLE_CLASS + "class LibraryPage(QWidget):",
        "LibraryPage class",
    )
    start = updated.find("    def toggle_checkbox(")
    stop = updated.find("    # SAVED BOOLEAN SETTING", start)
    if start < 0 or stop < 0:
        raise RuntimeError("Cannot locate the old toggle widget method. No changes made.")
    # Remove the old method and its preceding section-divider comments without
    # modifying the next section or any book/library logic.
    next_divider = updated.rfind("    # ========================================================", start, stop)
    if next_divider < 0:
        raise RuntimeError("Cannot find toggle method boundary. No changes made.")
    updated = updated[:start] + TOGGLE_METHOD + updated[next_divider:]

    updated = replace_once(
        updated,
        "self.settings_panel.setFixedWidth(\n            310\n        )",
        "self.settings_panel.setFixedWidth(\n            340\n        )",
        "Display panel width",
    )
    updated = replace_once(
        updated,
        "self.grid_slider = QSlider(\n            Qt.Horizontal\n        )",
        "self.grid_slider = QSlider(\n            Qt.Horizontal\n        )\n        self.grid_slider.setObjectName(\"libraryGridSize\")",
        "grid-size slider",
    )
    updated = replace_once(
        updated,
        "        side.addWidget(\n            self.side_label(\n                \"File type\"\n            )\n        )",
        FILTER_SEARCH
        + "        side.addWidget(\n            self.side_label(\n                \"File type\"\n            )\n        )",
        "File type filter label",
    )
    # Apply the new panel rules last within the Library's existing stylesheet.
    style_start = updated.find("    def apply_page_style(self):")
    style_end = updated.find('            """\n        )', style_start)
    if style_start < 0 or style_end < 0:
        raise RuntimeError("Cannot find Library stylesheet. No files were changed.")
    updated = updated[:style_end] + PANEL_CSS + updated[style_end:]

    compile(updated, str(LIBRARY), "exec")
    backup = LIBRARY.with_name("library_page.before_display_panel_fix.bak")
    if not backup.exists():
        copy2(LIBRARY, backup)
    LIBRARY.write_text(updated, encoding="utf-8")
    print("Updated: app/pages/library_page.py")
    print("Backup: app/pages/library_page.before_display_panel_fix.bak")
    print("main.py, main_window.py, book files, and dropdown icons were not changed.")


if __name__ == "__main__":
    main()
