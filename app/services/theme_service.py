"""Apply Litenova's saved dark appearance across Qt pages, including local QSS.

This keeps the original stylesheet of each widget so switching presets or
restoring Mercury never compounds a previously applied color transformation.
It never modifies book covers, imported files, icon PNGs or saved data.
"""

import re
import weakref

from PySide6.QtCore import QObject, QEvent, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from app.services.path_service import resource_path
from app.services.appearance_service import resolved_colors


_HEX = re.compile(r"(?<![0-9a-zA-Z_])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")
_RGBA = re.compile(r"rgba\(\s*116\s*,\s*118\s*,\s*176\s*,", re.IGNORECASE)
_DEFAULT = ("#15171e", "#eeeeee", "#8f88ff")


def _rgb(color):
    value = QColor(color)
    return value.red(), value.green(), value.blue()


def _blend(first, second, fraction):
    a, b = _rgb(first), _rgb(second)
    factor = max(0.0, min(1.0, float(fraction)))
    return QColor(*(round(a[i] * (1.0 - factor) + b[i] * factor) for i in range(3))).name()


def _luma(color):
    r, g, b = _rgb(color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _original_mercury(colors):
    return (colors["background"].lower(), colors["foreground"].lower(),
            colors["accent"].lower()) == _DEFAULT


def _recolor_stylesheet(original, colors):
    """Map Mercury-era dark UI colors to the selected palette.

    Preserve warm warning/danger colors, full book-cover images, alpha values,
    dimensions, fonts, border radii and all other stylesheet declarations.
    """
    if not original or _original_mercury(colors):
        return original

    bg, fg, accent = colors["background"], colors["foreground"], colors["accent"]
    current = {value.lower() for value in colors.values() if isinstance(value, str)}

    # Explicitly handle the original global theme and commonly used action colors.
    exact = {
        "#15171e": bg, "#12141a": colors["reader_background"],
        "#1b1d25": colors["sidebar"], "#1f212b": colors["panel"],
        "#292c38": colors["input"], "#3c3f4d": colors["border"],
        "#eeeeee": fg, "#f1f1f5": fg,
        "#8f88ff": accent, "#aaa4ff": _blend(accent, fg, 0.28),
        "#625ca8": colors["button"], "#756fc0": accent,
        "#514d73": colors["selected"],
        "#363947": colors["hover"],
        "#1c438f": colors["button"], "#315bb1": accent,
    }

    def convert(match):
        token = match.group(0)
        # Retain #RRGGBBAA alpha (e.g. translucent badges), if present.
        if len(token) == 9:
            rgb, alpha = token[:7], token[7:]
        elif len(token) == 4:
            rgb = "#" + "".join(char * 2 for char in token[1:])
            alpha = ""
        else:
            rgb, alpha = token, ""
        source = rgb.lower()

        if source in current:
            # The EPUB reader / Appearance preview already use the NEW palette.
            result = source
        elif source in exact:
            result = exact[source]
        else:
            red, green, blue = _rgb(source)
            brightness = _luma(source)
            span = max(red, green, blue) - min(red, green, blue)
            warm_warning = red > green * 1.35 and red > blue * 1.22 and red > 90

            # Original Litenova brand lavender and purple shades.
            lavender = (blue >= 115 and blue > green + 14 and
                        red >= green - 14 and red <= blue + 14 and
                        not warm_warning)
            dark_violet = (brightness < 108 and blue > red + 17 and
                           blue > green + 17 and red >= green - 15)
            neutral_dark = (brightness < 115 and not warm_warning and
                            red <= green + 18 and blue <= red + 65)
            neutral_text = (brightness >= 118 and not warm_warning and
                            span < 85)

            if dark_violet:
                result = _blend(bg, accent, min(0.52, max(0.13, brightness / 185)))
            elif lavender:
                # Light lavender becomes a lighter version of the chosen accent.
                lightness = max(0.0, min(0.72, (brightness - 140) / 160))
                result = _blend(accent, fg, lightness)
            elif neutral_dark:
                if brightness < 22:
                    result = _blend(bg, "#000000", min(0.27, (22 - brightness) / 75))
                else:
                    result = _blend(bg, fg, min(0.31, (brightness - 22) / 250))
            elif neutral_text:
                result = _blend(bg, fg, max(0.44, min(1.0, (brightness - 30) / 210)))
            else:
                # Keep purposefully colored danger/warning/status indicators.
                result = source
        return result + alpha

    changed = _HEX.sub(convert, original)
    red, green, blue = _rgb(accent)
    return _RGBA.sub(f"rgba({red}, {green}, {blue},", changed)


class _ApplicationAppearance(QObject):
    """Recolor local styles of existing AND later-created Library/Browse/etc widgets."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self._originals = weakref.WeakKeyDictionary()
        self._applying = False
        self._scheduled = False
        self._last_global = None
        self._colors = resolved_colors()
        app.installEventFilter(self)

    def eventFilter(self, watched, event):
        if self._applying or not isinstance(watched, QWidget):
            return False
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.Show):
            try:
                css = watched.styleSheet()
            except RuntimeError:  # A widget is being deleted.
                return False
            if css and self._needs_update(watched, css):
                self._queue_refresh()
        return False

    def _needs_update(self, widget, css):
        previous = self._originals.get(widget)
        return previous is None or css != previous[1]

    def _queue_refresh(self):
        if self._scheduled:
            return
        self._scheduled = True
        QTimer.singleShot(0, self._deferred_refresh)

    def _deferred_refresh(self):
        self._scheduled = False
        self.refresh()

    def _apply_native_palette(self, colors):
        palette = self.app.palette()
        role_colors = (
            (QPalette.ColorRole.Window, colors["background"]),
            (QPalette.ColorRole.WindowText, colors["foreground"]),
            (QPalette.ColorRole.Base, colors["input"]),
            (QPalette.ColorRole.AlternateBase, colors["panel"]),
            (QPalette.ColorRole.Text, colors["foreground"]),
            (QPalette.ColorRole.Button, colors["button"]),
            (QPalette.ColorRole.ButtonText, colors["foreground"]),
            (QPalette.ColorRole.Highlight, colors["selected"]),
            (QPalette.ColorRole.HighlightedText, colors["foreground"]),
            (QPalette.ColorRole.ToolTipBase, colors["panel"]),
            (QPalette.ColorRole.ToolTipText, colors["foreground"]),
            (QPalette.ColorRole.PlaceholderText, _blend(colors["background"], colors["foreground"], 0.60)),
        )
        for role, color in role_colors:
            palette.setColor(role, QColor(color))
        self.app.setPalette(palette)

    def refresh(self):
        if self._applying:
            return
        self._applying = True
        try:
            self._colors = resolved_colors()
            stylesheet_file = resource_path("app/styles/dark.qss")
            global_css = (stylesheet_file.read_text(encoding="utf-8")
                          if stylesheet_file.is_file() else "")
            global_css = _recolor_stylesheet(global_css, self._colors)
            if self._last_global != global_css:
                self._apply_native_palette(self._colors)
                self.app.setStyleSheet(global_css)
                self._last_global = global_css

            # Page-local QSS is stronger than QApplication QSS. Updating only
            # app.setStyleSheet would therefore leave Library, Browse, History,
            # Settings and their buttons stuck in the old lavender palette.
            for widget in self.app.allWidgets():
                try:
                    displayed = widget.styleSheet()
                    previous = self._originals.get(widget)
                    if previous is None:
                        if not displayed:
                            continue
                        base = displayed
                    elif displayed == previous[1]:
                        base = previous[0]
                    else:
                        # A page explicitly set a new style since last refresh.
                        base = displayed
                    updated = _recolor_stylesheet(base, self._colors)
                    self._originals[widget] = (base, updated)
                    if displayed != updated:
                        widget.setStyleSheet(updated)
                except RuntimeError:
                    # The widget disappeared during a page refresh.
                    continue
        finally:
            self._applying = False


_manager = None


def get_theme_stylesheet():
    """Return the current app-level dark stylesheet (public compatibility API)."""
    path = resource_path("app/styles/dark.qss")
    if not path.is_file():
        return ""
    return _recolor_stylesheet(path.read_text(encoding="utf-8"), resolved_colors())


def apply_theme(app):
    """Apply Appearance preferences across existing and future app widgets."""
    global _manager
    if not isinstance(app, QApplication):
        return
    if _manager is None or _manager.app is not app:
        _manager = _ApplicationAppearance(app)
    _manager.refresh()
