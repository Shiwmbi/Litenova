import sys
import traceback

from pathlib import Path

from PySide6.QtCore import QObject, QEvent, Qt

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QDialog,
    QMenu,
)

from app.windows.main_window import MainWindow

from app.services.theme_service import apply_theme


# ============================================================
# LOG FILE
# ============================================================

ROOT = Path(__file__).resolve().parent

LOG_FILE = ROOT / "floating_windows_log.txt"


# ============================================================
# WINDOW DETECTOR
# ============================================================

class FloatingWindowDetector(QObject):

    def __init__(self):

        super().__init__()

        self.enabled = False

        self.detected_count = 0

    def eventFilter(self, watched, event):

        if not self.enabled:
            return False

        if event.type() != QEvent.Type.Show:
            return False

        if not isinstance(watched, QWidget):
            return False

        # Only inspect widgets that are opening
        # as independent application windows.

        if not watched.isWindow():
            return False

        # Ignore the actual Litenova window and
        # normal application dialogs.

        if isinstance(
            watched,
            (
                QMainWindow,
                QDialog,
                QMenu,
            ),
        ):
            return False

        # Ignore normal popup menus, tooltips,
        # and other temporary Qt popup controls.

        if (
            watched.windowType()
            != Qt.WindowType.Window
        ):
            return False

        # ====================================================
        # UNEXPECTED WINDOW DETECTED
        # ====================================================

        self.detected_count += 1

        parent = watched.parentWidget()

        if parent is None:

            parent_name = "None"

        else:

            parent_name = (
                parent.metaObject().className()
            )

        report = f"""

============================================================
UNEXPECTED WINDOW #{self.detected_count}
============================================================

Widget class:
{watched.metaObject().className()}

Python class:
{type(watched).__name__}

Object name:
{watched.objectName()}

Window title:
{watched.windowTitle()}

Parent:
{parent_name}

Window size:
{watched.width()} x {watched.height()}

Window flags:
{watched.windowFlags()}

============================================================
PYTHON CALL STACK
============================================================

{''.join(traceback.format_stack(limit=15))}

============================================================

"""

        print(
            report,
            flush=True,
        )

        with LOG_FILE.open(
            "a",
            encoding="utf-8",
        ) as log:

            log.write(report)

        return False


# ============================================================
# START LITENOVA
# ============================================================

def main():

    LOG_FILE.write_text(
        "Litenova Floating Window Diagnostic\n\n",
        encoding="utf-8",
    )

    app = QApplication(sys.argv)

    app.setApplicationName("Litenova")

    app.setOrganizationName("Litenova")

    apply_theme(app)

    # Install the detector before creating
    # the main application window.

    detector = FloatingWindowDetector()

    app.installEventFilter(detector)

    window = MainWindow()

    window.show()

    # Start detecting additional windows after
    # the main Litenova window is displayed.

    detector.enabled = True

    print(
        "Litenova is running in diagnostic mode.",
        flush=True,
    )

    print(
        "Open the Library and reproduce the "
        "small floating window.",
        flush=True,
    )

    print(
        f"Diagnostic log: {LOG_FILE}",
        flush=True,
    )

    return app.exec()


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":

    sys.exit(main())