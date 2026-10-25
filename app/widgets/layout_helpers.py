"""Small layout helpers shared by the existing desktop pages."""

from PySide6.QtCore import Qt, QSize, QRect, QEvent, QObject, QSettings, QByteArray, QTimer
from PySide6.QtWidgets import (
    QLabel, QWidget, QSizePolicy, QBoxLayout, QLayout, QComboBox,
    QStyle, QStylePainter, QStyleOptionComboBox,
)


def configure_combo(combo, minimum=120):
    combo.setMinimumWidth(minimum)
    combo.setMinimumContentsLength(12)
    combo.setSizeAdjustPolicy(combo.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    combo.currentTextChanged.connect(combo.setToolTip)
    combo.setToolTip(combo.currentText())


class ElidedComboBox(QComboBox):
    """Retain normal popup/selection behavior, eliding only the closed label."""

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        painter.drawComplexControl(QStyle.CC_ComboBox, option)
        rect = self.style().subControlRect(QStyle.CC_ComboBox, option,
                                          QStyle.SC_ComboBoxEditField, self)
        width = rect.width() - 4
        if not option.currentIcon.isNull():
            width -= option.iconSize.width() + 4
        option.currentText = self.fontMetrics().elidedText(option.currentText,
                                                          Qt.ElideRight, max(0, width))
        painter.drawControl(QStyle.CE_ComboBoxLabel, option)


class ElidedLabel(QLabel):
    """A single line whose full text remains available in a tooltip."""

    def __init__(self, text="", parent=None, mode=Qt.ElideRight):
        self._full_text = str(text)
        self._elide_mode = mode
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.setTextFormat(Qt.PlainText)
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self._refresh()

    def clear(self):
        self.setText("")

    def _refresh(self):
        available = max(0, self.contentsRect().width() - 2 * self.margin())
        super().setText(self.fontMetrics().elidedText(
            self._full_text, self._elide_mode, available,
        ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.StyleChange):
            self._refresh()


class WrappingLabel(QLabel):
    """Wrapped descriptive text that cannot force a panel wider than its layout."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text):
        super().setText(str(text))
        self.setToolTip(str(text))

    def clear(self):
        self.setText("")


class ResponsiveRow(QWidget):
    """Put the control below its label when a horizontal row would clip."""

    def __init__(self, labels, control, parent=None):
        super().__init__(parent)
        self.labels, self.control = labels, control
        self._control_minimum = control.minimumWidth()
        if isinstance(control, QComboBox):
            control.installEventFilter(self)
            control.currentTextChanged.connect(lambda *_: self._update_layout())
        self.row = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.row.setContentsMargins(2, 6, 2, 6)
        self.row.setSpacing(12)
        self.row.addWidget(labels, 1)
        self.row.addWidget(control)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout()

    def eventFilter(self, watched, event):
        if (watched is self.control and hasattr(self, "row")
                and event.type() in (QEvent.FontChange, QEvent.StyleChange)):
            self._update_layout()
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        super().showEvent(event)
        self._update_layout()

    def _update_layout(self):
        margins = self.row.contentsMargins()
        needed = (max(140, self.labels.minimumSizeHint().width())
                  + max(self.control.minimumWidth(), self.control.sizeHint().width())
                  + self.row.spacing() + margins.left() + margins.right())
        if isinstance(self.control, QComboBox):
            option = QStyleOptionComboBox()
            self.control.initStyleOption(option)
            edit = self.control.style().subControlRect(
                QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, self.control)
            chrome = max(50, self.control.width() - edit.width()) + 8
            text_width = min(360, self.control.fontMetrics().horizontalAdvance(
                self.control.currentText()) + chrome)
            needed = max(needed, 140 + text_width + self.row.spacing()
                         + margins.left() + margins.right())
        vertical = self.width() < needed
        if isinstance(self.control, QComboBox):
            self.control.setMinimumWidth(self._control_minimum if vertical else
                                         max(self._control_minimum, text_width))
        self.row.setDirection(QBoxLayout.TopToBottom if vertical else QBoxLayout.LeftToRight)
        self.row.setStretch(0, 0 if vertical else 1)


class WrapLayout(QLayout):
    """Wrap small groups of actions without compressing their size hints."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(6)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), False)

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def sizeHint(self):
        sizes = [item.sizeHint().expandedTo(item.minimumSize()) for item in self._items]
        m = self.contentsMargins()
        return QSize(sum(size.width() for size in sizes)
                     + self.spacing() * max(0, len(sizes) - 1) + m.left() + m.right(),
                     max((size.height() for size in sizes), default=0) + m.top() + m.bottom())

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, True)

    def _arrange(self, rect, apply):
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, height = area.x(), area.y(), 0
        for item in self._items:
            if item.isEmpty():
                continue
            size = item.sizeHint().expandedTo(item.minimumSize())
            if x > area.x() and x + size.width() > area.right() + 1:
                x, y, height = area.x(), y + height + self.spacing(), 0
            if apply:
                item.setGeometry(QRect(x, y, size.width(), size.height()))
            x += size.width() + self.spacing()
            height = max(height, size.height())
        return y + height - rect.y() + m.bottom()


class _SplitterPreferences(QObject):
    """Restore on first display, after Qt has assigned the available width."""

    def __init__(self, splitter, key):
        super().__init__(splitter)
        self.splitter = splitter
        self.key = "layout/" + key
        self.restored = False
        self.settings = QSettings("Litenova", "Litenova")
        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self.restore)
        splitter.installEventFilter(self)
        splitter.splitterMoved.connect(self.save)
        if splitter.isVisible():
            self._schedule_restore()

    def eventFilter(self, watched, event):
        if watched is self.splitter and event.type() == QEvent.Show:
            self._schedule_restore()
        return False

    def _schedule_restore(self):
        # Detach before restoring: restoreState can itself trigger layout events.
        self.splitter.removeEventFilter(self)
        if not self.restored and not self._restore_timer.isActive():
            self._restore_timer.start(0)

    def restore(self):
        if self.restored:
            return
        self.restored = True
        self.splitter.removeEventFilter(self)
        state = self.settings.value(self.key)
        if state is None:
            return
        default_state = self.splitter.saveState()
        orientation = self.splitter.orientation()
        if (not isinstance(state, QByteArray) or state.isEmpty()
                or state.size() != default_state.size()):
            self.settings.remove(self.key)
            return

        try:
            valid = self.splitter.restoreState(state)
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            self.splitter.restoreState(default_state)
            self.settings.remove(self.key)
        # Stored state also contains these flags. Keep current layout limits,
        # including non-collapsible children and each panel's min/max width.
        self.splitter.setOrientation(orientation)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        self.splitter.setOpaqueResize(False)
        sizes = []
        for index, size in enumerate(self.splitter.sizes()):
            widget = self.splitter.widget(index)
            if widget.isHidden():
                sizes.append(0)
            else:
                sizes.append(max(widget.minimumWidth(), min(widget.maximumWidth(), size)))
        self.splitter.setSizes(sizes)

    def save(self, *_):
        if self.restored:
            self.settings.setValue(self.key, self.splitter.saveState())


def persist_splitter(splitter, key):
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(6)
    splitter.setOpaqueResize(False)
    splitter._preferences = _SplitterPreferences(splitter, key)
