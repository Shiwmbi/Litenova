"""Litenova's fixed-dark, two-column Settings page.

Only implemented controls are interactive.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import (
    Qt,
    Signal,
    QSize,
    QTimer,
    QThread,
)

from PySide6.QtGui import (
    QColor,
    QPainter,
)

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
    QStackedWidget,
    QDialog,
    QProgressBar,
)

from app.pages.appearance_page import AppearancePage

from app.services.icon_service import ui_icon

from app.services.path_service import (
    get_data_dir,
    resource_path,
)

from app.services.settings_service import (
    DEFAULT_FONT_SIZE,
    get_reader_font_size,
    set_reader_font_size,
    get_setting,
    set_setting,
)

from app.services.settings_data_service import (
    application_settings,
    configure_logging,
    create_backup,
    log_directory,
    reset_data,
    restore_backup,
    set_startup_enabled,
    startup_enabled,
)


FONT_OPTIONS = (
    "Georgia",
    "Noto Serif",
    "Times New Roman",
    "Arial",
    "Verdana",
)


COMIC_READING_MODES = (
    (
        "Automatic (Manga / Manhwa)",
        "auto",
    ),
    (
        "Paged (left to right)",
        "paged_ltr",
    ),
    (
        "Paged (right to left)",
        "paged_rtl",
    ),
    (
        "Paged (vertical)",
        "paged_vertical",
    ),
    (
        "Long strip",
        "long_strip",
    ),
    (
        "Long strip with gaps",
        "long_strip_gaps",
    ),
)


# ============================================================
# SETTING LABEL
# ============================================================

def row_label(
    title,
    description="",
):

    box = QWidget()

    layout = QVBoxLayout(
        box
    )

    layout.setContentsMargins(
        0,
        0,
        0,
        0,
    )

    layout.setSpacing(
        4
    )

    name = QLabel(
        title
    )

    name.setObjectName(
        "settingName"
    )

    layout.addWidget(
        name
    )

    if description:

        detail = QLabel(
            description
        )

        detail.setObjectName(
            "settingDetail"
        )

        detail.setWordWrap(
            True
        )

        layout.addWidget(
            detail
        )

    return box


# ============================================================
# TOGGLE SWITCH
# ============================================================

class PillSwitch(QCheckBox):

    def __init__(
        self,
        parent=None,
    ):

        super().__init__(
            parent
        )

        self.setFixedSize(
            52,
            31,
        )

        self.setCursor(
            Qt.PointingHandCursor
        )

    def paintEvent(
        self,
        _event,
    ):

        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        painter.setPen(
            Qt.NoPen
        )

        painter.setBrush(
            QColor(
                "#595b91"
                if self.isChecked()
                else "#363a4a"
            )
        )

        painter.drawRoundedRect(
            0,
            2,
            52,
            27,
            14,
            14,
        )

        painter.setBrush(
            QColor(
                "#cecdff"
                if self.isChecked()
                else "#a9aec3"
            )
        )

        painter.drawEllipse(
            28
            if self.isChecked()
            else 4,
            5,
            21,
            21,
        )


# ============================================================
# SETTINGS CARD
# ============================================================

class SettingsCard(QFrame):

    def __init__(
        self,
        icon_name,
        title,
        subtitle,
        parent=None,
    ):

        super().__init__(
            parent
        )

        self.setObjectName(
            "settingsCard"
        )

        self.items = []

        self.layout_ = QVBoxLayout(
            self
        )

        self.layout_.setContentsMargins(
            20,
            18,
            20,
            19,
        )

        self.layout_.setSpacing(
            13
        )

        header = QHBoxLayout()

        symbol = QLabel()

        symbol.setPixmap(
            ui_icon(
                icon_name
            ).pixmap(
                QSize(
                    27,
                    27,
                )
            )
        )

        symbol.setFixedSize(
            30,
            30,
        )

        header.addWidget(
            symbol,
            0,
            Qt.AlignTop,
        )

        captions = QVBoxLayout()

        captions.setSpacing(
            2
        )

        heading = QLabel(
            title
        )

        heading.setObjectName(
            "settingsCardTitle"
        )

        captions.addWidget(
            heading
        )

        note = QLabel(
            subtitle
        )

        note.setWordWrap(
            True
        )

        note.setObjectName(
            "settingDetail"
        )

        captions.addWidget(
            note
        )

        header.addLayout(
            captions,
            1,
        )

        self.layout_.addLayout(
            header
        )

        self.layout_.addSpacing(
            5
        )

    def add_row(
        self,
        title,
        description,
        control,
    ):

        widget = QWidget(
            self
        )

        row = QHBoxLayout(
            widget
        )

        row.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        row.setSpacing(
            15
        )

        row.addWidget(
            row_label(
                title,
                description,
            ),
            1,
        )

        row.addWidget(
            control,
            0,
            Qt.AlignVCenter,
        )

        self.layout_.addWidget(
            widget
        )

        self.items.append(
            (
                title.casefold()
                + " "
                + description.casefold(),
                widget,
            )
        )

        return widget

    def add_full(
        self,
        text,
        control,
    ):

        self.layout_.addWidget(
            control
        )

        self.items.append(
            (
                text.casefold(),
                control,
            )
        )

        return control

    def filter(
        self,
        query,
    ):

        count = 0

        for words, widget in self.items:

            match = (
                not query
                or query in words
            )

            widget.setVisible(
                match
            )

            count += int(
                match
            )

        self.setVisible(
            count > 0
        )

        return count


# ============================================================
# DATA OPERATION LOADING DIALOG
# ============================================================

class DataOperationDialog(QDialog):

    def __init__(
        self,
        title,
        detail,
        parent=None,
    ):

        super().__init__(
            parent
        )

        self.setObjectName(
            "dataOperationDialog"
        )

        self.setWindowTitle(
            "Litenova · "
            + title
        )

        self.setWindowModality(
            Qt.ApplicationModal
        )

        self.setWindowFlags(
            Qt.Dialog
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
        )

        self.setMinimumWidth(
            410
        )

        self._allow_close = False

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            26,
            24,
            26,
            26,
        )

        layout.setSpacing(
            13
        )

        heading = QLabel(
            title,
            self,
        )

        heading.setObjectName(
            "dataOperationHeading"
        )

        note = QLabel(
            detail,
            self,
        )

        note.setObjectName(
            "dataOperationDetail"
        )

        note.setWordWrap(
            True
        )

        progress = QProgressBar(
            self
        )

        progress.setObjectName(
            "dataOperationProgress"
        )

        progress.setRange(
            0,
            0,
        )

        progress.setTextVisible(
            False
        )

        progress.setFixedHeight(
            8
        )

        layout.addWidget(
            heading
        )

        layout.addWidget(
            note
        )

        layout.addSpacing(
            5
        )

        layout.addWidget(
            progress
        )

        self.setStyleSheet(
            """
            QDialog#dataOperationDialog {
                background: #1b1e28;
                border: 1px solid #515577;
                border-radius: 12px;
                color: #f1f0ff;
            }

            QLabel {
                background: transparent;
                border: none;
            }

            QLabel#dataOperationHeading {
                color: #f2f1ff;
                font-size: 18px;
                font-weight: 700;
            }

            QLabel#dataOperationDetail {
                color: #c2c5d9;
                font-size: 13px;
            }

            QProgressBar#dataOperationProgress {
                background: #303548;
                border: none;
                border-radius: 4px;
            }

            QProgressBar#dataOperationProgress::chunk {
                background: #aba9ff;
                border-radius: 4px;
            }
            """
        )

    def reject(
        self,
    ):

        if self._allow_close:

            super().reject()

    def closeEvent(
        self,
        event,
    ):

        if self._allow_close:

            event.accept()

        else:

            event.ignore()

    def finish(
        self,
    ):

        self._allow_close = True

        self.accept()


# ============================================================
# BACKGROUND DATA OPERATION
# ============================================================

class DataOperationThread(QThread):

    def __init__(
        self,
        operation,
        path=None,
        parent=None,
    ):

        super().__init__(
            parent
        )

        self.operation = (
            operation
        )

        self.path = (
            path
        )

        self.result = None

        self.failure = None

    def run(
        self,
    ):

        try:

            if self.operation == "export":

                self.result = create_backup(
                    self.path
                )

            elif self.operation == "import":

                self.result = restore_backup(
                    self.path
                )

            elif self.operation == "reset":

                self.result = reset_data()

            else:

                raise ValueError(
                    "Unknown data operation"
                )

        except Exception as error:

            self.failure = str(
                error
            )


# ============================================================
# SETTINGS PAGE
# ============================================================

class SettingsPage(QWidget):

    settings_changed = Signal()

    def __init__(
        self,
    ):

        super().__init__()

        self.ui_settings = (
            application_settings()
        )

        self._loading = False

        self._data_job = None

        self._data_dialog = None

        # Keep internal logging available even though the
        # Advanced card is no longer shown in Settings.
        configure_logging()

        self._reader_update_timer = QTimer(
            self
        )

        self._reader_update_timer.setSingleShot(
            True
        )

        self._reader_update_timer.setInterval(
            180
        )

        self._reader_update_timer.timeout.connect(
            self.settings_changed.emit
        )

        self.build_ui()

        self.load_settings()

    # ========================================================
    # COMBO BOX
    # ========================================================

    def combo(
        self,
        choices,
        width=210,
    ):

        widget = QComboBox(
            self
        )

        widget.setFixedWidth(
            width
        )

        widget.setFixedHeight(
            37
        )

        for text, value in choices:

            widget.addItem(
                text,
                value,
            )

        return widget

    # ========================================================
    # ACTION BUTTON
    # ========================================================

    def action(
        self,
        text,
        callback,
        danger=False,
    ):

        button = QPushButton(
            text,
            self,
        )

        button.setObjectName(
            "settingsDanger"
            if danger
            else "settingsAction"
        )

        button.setCursor(
            Qt.PointingHandCursor
        )

        button.clicked.connect(
            callback
        )

        return button

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(
        self,
    ):

        self.setObjectName(
            "settingsPage"
        )

        self.page_stack = QStackedWidget(
            self
        )

        self.main_panel = QWidget(
            self.page_stack
        )

        self.main_panel.setObjectName(
            "settingsMainPanel"
        )

        host = QVBoxLayout(
            self
        )

        host.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        host.setSpacing(
            0
        )

        host.addWidget(
            self.page_stack
        )

        outer = QVBoxLayout(
            self.main_panel
        )

        outer.setContentsMargins(
            24,
            19,
            22,
            16,
        )

        outer.setSpacing(
            14
        )

        # ====================================================
        # HEADER
        # ====================================================

        title_row = QHBoxLayout()

        heading = QVBoxLayout()

        title = QLabel(
            "Settings"
        )

        title.setObjectName(
            "settingsHeading"
        )

        heading.addWidget(
            title
        )

        description = QLabel(
            "Customize Litenova to your liking"
        )

        description.setObjectName(
            "settingsDescription"
        )

        heading.addWidget(
            description
        )

        title_row.addLayout(
            heading
        )

        title_row.addStretch()

        self.search = QLineEdit(
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

        outer.addLayout(
            title_row
        )

        # ====================================================
        # SCROLL AREA
        # ====================================================

        scroller = QScrollArea(
            self
        )

        scroller.setObjectName(
            "settingsScroller"
        )

        scroller.setWidgetResizable(
            True
        )

        scroller.setFrameShape(
            QFrame.NoFrame
        )

        scroller.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        content = QWidget()

        columns = QHBoxLayout(
            content
        )

        columns.setContentsMargins(
            0,
            0,
            0,
            6,
        )

        columns.setSpacing(
            13
        )

        left_column = QVBoxLayout()

        left_column.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        left_column.setSpacing(
            13
        )

        right_column = QVBoxLayout()

        right_column.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        right_column.setSpacing(
            13
        )

        # ====================================================
        # CARDS
        # ====================================================

        self.general = SettingsCard(
            "settings",
            "General",
            "Application behavior and system preferences",
        )

        self.reader_card = SettingsCard(
            "library",
            "Reader",
            "Font, text, and reading behavior",
        )

        self.data_card = SettingsCard(
            "folder",
            "Data",
            "Manage your library data and storage",
        )

        self.appearance = SettingsCard(
            "settings",
            "Appearance",
            "Litenova's original dark interface",
        )

        left_column.addWidget(
            self.general
        )

        left_column.addWidget(
            self.data_card
        )

        left_column.addStretch(
            1
        )

        right_column.addWidget(
            self.reader_card
        )

        right_column.addWidget(
            self.appearance
        )

        right_column.addStretch(
            1
        )

        columns.addLayout(
            left_column,
            1,
        )

        columns.addLayout(
            right_column,
            1,
        )

        scroller.setWidget(
            content
        )

        outer.addWidget(
            scroller,
            1,
        )

        # ====================================================
        # GENERAL
        # ====================================================

        language = QLabel(
            "English"
        )

        language.setObjectName(
            "settingsStatic"
        )

        self.general.add_row(
            "App language",
            "Currently supported language",
            language,
        )

        self.launch_toggle = PillSwitch(
            self
        )

        if sys.platform != "win32":

            self.launch_toggle.setEnabled(
                False
            )

            self.launch_toggle.setToolTip(
                "Windows only"
            )

        self.general.add_row(
            "Launch at system startup",
            "Open Litenova when signing into Windows",
            self.launch_toggle,
        )

        self.launch_toggle.toggled.connect(
            self.change_startup
        )

        self.open_to = self.combo(
            [
                (
                    "Library",
                    "library",
                ),
                (
                    "History",
                    "history",
                ),
                (
                    "Browse",
                    "browse",
                ),
                (
                    "Settings",
                    "settings",
                ),
            ],
            170,
        )

        self.general.add_row(
            "Open to",
            "Page displayed when Litenova starts",
            self.open_to,
        )

        self.open_to.currentIndexChanged.connect(
            self.change_start_page
        )

        # ====================================================
        # READER
        # ====================================================

        self.font_combo = self.combo(
            [
                (
                    name,
                    name,
                )
                for name
                in FONT_OPTIONS
            ],
            180,
        )

        self.reader_card.add_row(
            "Default font",
            "EPUB reader font family",
            self.font_combo,
        )

        self.font_combo.currentIndexChanged.connect(
            self.change_font
        )

        font_controls = QWidget()

        frow = QHBoxLayout(
            font_controls
        )

        frow.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        frow.setSpacing(
            8
        )

        self.font_slider = QSlider(
            Qt.Horizontal
        )

        self.font_slider.setRange(
            12,
            32,
        )

        self.font_slider.setFixedWidth(
            145
        )

        self.font_size_label = QLabel(
            "17 pt"
        )

        self.font_size_label.setFixedWidth(
            38
        )

        frow.addWidget(
            self.font_slider
        )

        frow.addWidget(
            self.font_size_label
        )

        self.reader_card.add_row(
            "Font size",
            "Default size for EPUB text",
            font_controls,
        )

        self.font_slider.valueChanged.connect(
            self.change_font_size
        )

        self.reading_mode_combo = self.combo(
            COMIC_READING_MODES,
            250,
        )

        self.reader_card.add_row(
            "Default comic reading mode",
            "Manga / Manhwa (CBZ). EPUB remains vertical scroll.",
            self.reading_mode_combo,
        )

        self.reading_mode_combo.currentIndexChanged.connect(
            self.change_reading_mode
        )

        self.progress_toggle = PillSwitch(
            self
        )

        self.reader_card.add_row(
            "Show progress bar",
            "Show EPUB reading progress below the text",
            self.progress_toggle,
        )

        self.progress_toggle.toggled.connect(
            self.change_progress
        )

        self.reader_card.add_full(
            "reader defaults",
            self.action(
                "Restore reader defaults",
                self.reset_reader,
            ),
        )

        # ====================================================
        # APPEARANCE
        # ====================================================

        theme = QLabel(
            "Litenova Dark · Customizable"
        )

        theme.setObjectName(
            "settingsStatic"
        )

        self.appearance.add_row(
            "Interface theme",
            "Choose Mercury, Neptune or Aurora (all dark)",
            theme,
        )

        self.appearance.add_full(
            "appearance theme color presets live preview",
            self.action(
                "Customize appearance  →",
                self.show_appearance,
            ),
        )

        # ====================================================
        # DATA
        # ====================================================

        self.data_path = QLineEdit(
            self
        )

        self.data_path.setReadOnly(
            True
        )

        self.data_path.setObjectName(
            "settingsPath"
        )

        self.data_path.setMinimumWidth(
            170
        )

        self.data_path.setMaximumWidth(
            290
        )

        self.data_card.add_row(
            "App data location",
            (
                "Live books, covers, database and history "
                "(not backup storage)"
            ),
            self.data_path,
        )

        self.data_card.add_full(
            "open data folder",
            self.action(
                "Open data folder",
                self.open_data_folder,
            ),
        )

        # ----------------------------------------------------
        # SHARED IMPORT / EXPORT FOLDER
        # ----------------------------------------------------

        self.backup_path = QLineEdit(
            self
        )

        self.backup_path.setReadOnly(
            True
        )

        self.backup_path.setObjectName(
            "settingsPath"
        )

        self.backup_path.setMinimumWidth(
            170
        )

        self.backup_path.setMaximumWidth(
            290
        )

        self.data_card.add_row(
            "Import / export folder",
            "Choose where backup ZIPs are saved and opened",
            self.backup_path,
        )

        self.data_card.add_full(
            "choose import export backup folder location",
            self.action(
                "Choose import / export folder...",
                self.choose_backup_folder,
            ),
        )

        self.data_card.add_row(
            "Export data",
            "Back up books and reading records as a ZIP",
            self.action(
                "Export...",
                self.export_data,
            ),
        )

        self.data_card.add_row(
            "Import data",
            "Replace data from a Litenova ZIP backup",
            self.action(
                "Import...",
                self.import_data,
            ),
        )

        self.data_card.add_row(
            "Reset app data",
            "Erase books, categories, history and preferences",
            self.action(
                "Reset...",
                self.reset_app,
                danger=True,
            ),
        )

        # ====================================================
        # SEARCHABLE CARDS
        # ====================================================

        self.cards = (
            self.general,
            self.reader_card,
            self.appearance,
            self.data_card,
        )

        self.apply_local_style()

        # ====================================================
        # APPEARANCE PAGE
        # ====================================================

        self.page_stack.addWidget(
            self.main_panel
        )

        self.appearance_editor = AppearancePage(
            self.page_stack
        )

        self.page_stack.addWidget(
            self.appearance_editor
        )

        self.appearance_editor.back_requested.connect(
            self.show_main_settings
        )

        self.appearance_editor.changed.connect(
            self.settings_changed.emit
        )

        self.page_stack.setCurrentWidget(
            self.main_panel
        )

    # ========================================================
    # APPEARANCE NAVIGATION
    # ========================================================

    def show_appearance(
        self,
    ):

        self.appearance_editor.load_settings()

        self.page_stack.setCurrentWidget(
            self.appearance_editor
        )

    def show_main_settings(
        self,
    ):

        self.page_stack.setCurrentWidget(
            self.main_panel
        )

    # ========================================================
    # LOCAL STYLING
    # ========================================================

    def apply_local_style(
        self,
    ):

        arrow = resource_path(
            "resources/icons/dropdown_arrow.png"
        )

        image = (
            f'image: url("{arrow.resolve().as_posix()}");'
            if arrow.is_file()
            else ""
        )

        self.setStyleSheet(
            """
            QWidget#settingsPage {
                background: #15171e;
                color: #e9ebfb;
            }

            QScrollArea#settingsScroller {
                background: transparent;
                border: none;
            }

            QScrollArea#settingsScroller > QWidget > QWidget {
                background: transparent;
            }

            QLabel {
                background: transparent;
                border: none;
            }

            QLabel#settingsHeading {
                color: #f2f0ff;
                font-size: 29px;
                font-weight: 700;
            }

            QLabel#settingsDescription {
                color: #c4c7dd;
                font-size: 13px;
            }

            QFrame#settingsCard {
                background: #191b22;
                border: 1px solid #323744;
                border-radius: 11px;
            }

            QLabel#settingsCardTitle {
                font-weight: 700;
                color: #e7e8ff;
                font-size: 17px;
            }

            QLabel#settingName {
                color: #e6e7f4;
                font-size: 13px;
            }

            QLabel#settingDetail {
                color: #adb2c8;
                font-size: 11px;
            }

            QLabel#settingsStatic {
                color: #c7c8ed;
                font-size: 12px;
            }

            QLineEdit#settingsSearch,
            QLineEdit#settingsPath,
            QComboBox {
                background: #14161c;
                border: 1px solid #41465a;
                border-radius: 8px;
                color: #eff0ff;
                font-size: 12px;
                padding: 5px 10px;
            }

            QLineEdit#settingsSearch:focus {
                border-color: #9795d6;
            }

            QComboBox {
                padding-right: 29px;
            }

            QComboBox::drop-down,
            QComboBox::drop-down:hover,
            QComboBox::drop-down:on {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                background: transparent;
                border: none;
            }

            QComboBox::down-arrow:on {
                top: 0;
                left: 0;
            }

            QComboBox QAbstractItemView {
                background: #191b22;
                color: #e7e8ff;
                selection-background-color: #454969;
                outline: none;
            }

            QSlider::groove:horizontal {
                background: #4b506e;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #c5c4fa;
                width: 15px;
                margin: -5px 0;
                border-radius: 7px;
            }

            QPushButton#settingsAction,
            QPushButton#settingsDanger {
                background: #30344d;
                color: #e9e8ff;
                border: 1px solid #6a6f9b;
                padding: 8px 14px;
                border-radius: 7px;
                font-size: 12px;
            }

            QPushButton#settingsAction:hover {
                background: #404567;
            }

            QPushButton#settingsDanger {
                border-color: #b04a53;
                color: #ffbbbb;
                background: #292025;
            }

            QPushButton#settingsDanger:hover {
                background: #4a282e;
            }
            """
            + (
                "QComboBox::down-arrow { "
                + image
                + " width: 13px; height: 13px; }"
                if image
                else ""
            )
        )

    # ========================================================
    # LOAD SETTINGS
    # ========================================================

    def load_settings(
        self,
    ):

        self._loading = True

        try:

            start = str(
                self.ui_settings.value(
                    "general/start_page",
                    "library",
                )
            )

            index = self.open_to.findData(
                start
            )

            self.open_to.setCurrentIndex(
                index
                if index >= 0
                else 0
            )

            self.launch_toggle.setChecked(
                startup_enabled()
            )

            font = str(
                get_setting(
                    "reader_font_family",
                    FONT_OPTIONS[0],
                )
            )

            index = self.font_combo.findData(
                font
            )

            self.font_combo.setCurrentIndex(
                index
                if index >= 0
                else 0
            )

            self.font_slider.setValue(
                get_reader_font_size()
            )

            mode = str(
                get_setting(
                    "comic_reading_mode",
                    "auto",
                )
                or "auto"
            )

            mode_index = (
                self.reading_mode_combo.findData(
                    mode
                )
            )

            self.reading_mode_combo.setCurrentIndex(
                mode_index
                if mode_index >= 0
                else 0
            )

            self.font_size_label.setText(
                f"{self.font_slider.value()} pt"
            )

            self.progress_toggle.setChecked(
                str(
                    get_setting(
                        "reader_show_progress_bar",
                        "True",
                    )
                ).lower()
                in (
                    "true",
                    "1",
                    "yes",
                )
            )

            live_path = str(
                get_data_dir()
            )

            self.data_path.setText(
                live_path
            )

            self.data_path.setToolTip(
                live_path
            )

            self.data_path.setCursorPosition(
                0
            )

            self._display_backup_directory()

        finally:

            self._loading = False

    # ========================================================
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

    # ========================================================
    # STARTUP
    # ========================================================

    def change_startup(
        self,
        state,
    ):

        if self._loading:
            return

        try:

            set_startup_enabled(
                state
            )

        except Exception as error:

            QMessageBox.warning(
                self,
                "Startup setting",
                str(error),
            )

            self._loading = True

            self.launch_toggle.setChecked(
                startup_enabled()
            )

            self._loading = False

    # ========================================================
    # START PAGE
    # ========================================================

    def change_start_page(
        self,
        _index,
    ):

        if not self._loading:

            self.ui_settings.setValue(
                "general/start_page",
                self.open_to.currentData(),
            )

    # ========================================================
    # READER FONT
    # ========================================================

    def change_font(
        self,
        _index,
    ):

        if not self._loading:

            set_setting(
                "reader_font_family",
                self.font_combo.currentData(),
            )

            self.settings_changed.emit()

    def change_font_size(
        self,
        size,
    ):

        self.font_size_label.setText(
            f"{size} pt"
        )

        if not self._loading:

            set_reader_font_size(
                size
            )

            self._reader_update_timer.start()

    # ========================================================
    # COMIC READING MODE
    # ========================================================

    def change_reading_mode(
        self,
        _index,
    ):

        if not self._loading:

            selected = (
                self.reading_mode_combo.currentData()
            )

            if selected is not None:

                set_setting(
                    "comic_reading_mode",
                    selected,
                )

                self.settings_changed.emit()

    # ========================================================
    # PROGRESS BAR
    # ========================================================

    def change_progress(
        self,
        enabled,
    ):

        if not self._loading:

            set_setting(
                "reader_show_progress_bar",
                bool(enabled),
            )

            self.settings_changed.emit()

    # ========================================================
    # RESTORE READER DEFAULTS
    # ========================================================

    def reset_reader(
        self,
    ):

        self._loading = True

        self.font_combo.setCurrentIndex(
            0
        )

        self.font_slider.setValue(
            DEFAULT_FONT_SIZE
        )

        self.font_size_label.setText(
            f"{DEFAULT_FONT_SIZE} pt"
        )

        self.progress_toggle.setChecked(
            True
        )

        self.reading_mode_combo.setCurrentIndex(
            0
        )

        self._loading = False

        set_setting(
            "reader_font_family",
            FONT_OPTIONS[0],
        )

        set_reader_font_size(
            DEFAULT_FONT_SIZE
        )

        set_setting(
            "reader_show_progress_bar",
            True,
        )

        set_setting(
            "comic_reading_mode",
            "auto",
        )

        self._reader_update_timer.stop()

        self.settings_changed.emit()

    # ========================================================
    # INTERNAL LOGGING SUPPORT
    # ========================================================

    def change_verbose(
        self,
        enabled,
    ):

        if not self._loading:

            self.ui_settings.setValue(
                "advanced/verbose",
                enabled,
            )

            configure_logging()

    # ========================================================
    # OPEN PATH
    # ========================================================

    @staticmethod
    def _open_path(
        path,
    ):

        if sys.platform == "win32":

            os.startfile(
                str(path)
            )

        else:

            from PySide6.QtGui import (
                QDesktopServices,
            )

            from PySide6.QtCore import (
                QUrl,
            )

            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(path)
                )
            )

    # ========================================================
    # DATA FOLDER
    # ========================================================

    def open_data_folder(
        self,
    ):

        self._open_path(
            get_data_dir()
        )

    # ========================================================
    # SHARED IMPORT / EXPORT FOLDER
    # ========================================================

    @staticmethod
    def _default_backup_directory(
    ):

        documents = (
            Path.home()
            / "Documents"
        )

        if documents.is_dir():

            return documents

        downloads = (
            Path.home()
            / "Downloads"
        )

        if downloads.is_dir():

            return downloads

        return Path.home()

    def _backup_directory(
        self,
    ):

        value = (
            self.ui_settings.value(
                "data/backup_directory",
                "",
            )
        )

        if value:

            return Path(
                str(value)
            ).expanduser()

        return (
            self._default_backup_directory()
        )

    def _display_backup_directory(
        self,
    ):

        directory = str(
            self._backup_directory()
        )

        self.backup_path.setText(
            directory
        )

        self.backup_path.setToolTip(
            directory
        )

        self.backup_path.setCursorPosition(
            0
        )

    @staticmethod
    def _is_inside_live_data(
        directory,
    ):

        data = (
            get_data_dir()
            .resolve()
        )

        folder = (
            Path(
                directory
            )
            .expanduser()
            .resolve()
        )

        return (
            folder == data
            or data in folder.parents
        )

    def _remember_backup_directory(
        self,
        directory,
    ):

        directory = (
            Path(
                directory
            )
            .expanduser()
            .resolve()
        )

        self.ui_settings.setValue(
            "data/backup_directory",
            str(directory),
        )

        self.ui_settings.sync()

        self._display_backup_directory()

    def choose_backup_folder(
        self,
    ):

        if self._data_job is not None:
            return

        initial = (
            self._backup_directory()
        )

        if not initial.is_dir():

            initial = (
                self._default_backup_directory()
            )

        chosen = QFileDialog.getExistingDirectory(
            self,
            "Choose an Import / Export Folder",
            str(initial),
        )

        if not chosen:
            return

        destination = Path(
            chosen
        )

        if self._is_inside_live_data(
            destination
        ):

            QMessageBox.warning(
                self,
                "Choose a different folder",
                (
                    "Backup ZIPs cannot be stored inside "
                    "Litenova's live data folder.\n\n"
                    "Choose Documents, Downloads, Desktop, "
                    "or another drive instead."
                ),
            )

            return

        self._remember_backup_directory(
            destination
        )

    def _file_dialog_start_folder(
        self,
    ):

        directory = (
            self._backup_directory()
        )

        if directory.is_dir():

            return directory

        return (
            self._default_backup_directory()
        )

    # ========================================================
    # INTERNAL DEBUG HELPERS
    # ========================================================

    def open_log_folder(
        self,
    ):

        self._open_path(
            log_directory()
        )

    def show_debug(
        self,
    ):

        details = (
            f"Python: {sys.version.split()[0]}\n"
            f"Executable: {sys.executable}\n"
            f"Data folder: {get_data_dir()}\n"
            f"Log file: {configure_logging()}\n"
            f"Mode: "
            f"{'Packaged' if getattr(sys, 'frozen', False) else 'Development'}"
        )

        QMessageBox.information(
            self,
            "Litenova diagnostics",
            details,
        )

    # ========================================================
    # START DATA OPERATION
    # ========================================================

    def _start_data_operation(
        self,
        operation,
        path=None,
    ):

        if self._data_job is not None:
            return

        messages = {
            "export": (
                "Exporting data",
                (
                    "Creating a backup of your Library, covers, "
                    "reading progress and preferences. "
                    "This may take a few minutes."
                ),
            ),

            "import": (
                "Importing data",
                (
                    "Validating the ZIP, saving a recovery backup "
                    "and restoring your Library. "
                    "Please keep Litenova open."
                ),
            ),

            "reset": (
                "Resetting data",
                (
                    "Saving a recovery backup and clearing "
                    "application data. Litenova will refresh "
                    "its Library when the reset finishes."
                ),
            ),
        }

        title, detail = messages[
            operation
        ]

        if operation in (
            "import",
            "reset",
        ):

            self._backup_dir_before_data_operation = str(
                self._backup_directory()
            )

        self._reader_update_timer.stop()

        self.ui_settings.sync()

        self._data_dialog = DataOperationDialog(
            title,
            detail,
            self,
        )

        self._data_job = DataOperationThread(
            operation,
            path,
            self,
        )

        self._data_job.finished.connect(
            self._finish_data_operation
        )

        self._data_dialog.show()

        QTimer.singleShot(
            0,
            self._data_job.start,
        )

    # ========================================================
    # FINISH DATA OPERATION
    # ========================================================

    def _finish_data_operation(
        self,
    ):

        job = (
            self._data_job
        )

        if job is None:
            return

        self._data_job = None

        if self._data_dialog is not None:

            self._data_dialog.finish()

            self._data_dialog.deleteLater()

            self._data_dialog = None

        job.deleteLater()

        if job.failure is not None:

            QMessageBox.critical(
                self,
                (
                    f"{job.operation.capitalize()} "
                    "failed"
                ),
                job.failure,
            )

            return

        # ----------------------------------------------------
        # EXPORT
        # ----------------------------------------------------

        if job.operation == "export":

            QMessageBox.information(
                self,
                "Backup created",
                (
                    "Saved backup to:\n\n"
                    f"{job.result}"
                ),
            )

            return

        # ----------------------------------------------------
        # IMPORT / RESET
        # ----------------------------------------------------

        operation = (
            job.operation
        )

        recovery, previous = (
            job.result
        )

        main_window = (
            self.window()
        )

        try:

            chosen_backup_folder = getattr(
                self,
                "_backup_dir_before_data_operation",
                "",
            )

            if chosen_backup_folder:

                self.ui_settings.setValue(
                    "data/backup_directory",
                    chosen_backup_folder,
                )

                self.ui_settings.sync()

            from app.database.database import (
                initialize_database,
            )

            from app.services.theme_service import (
                apply_theme,
            )

            initialize_database()

            refresh = getattr(
                main_window,
                "build_ui",
                None,
            )

            if not callable(
                refresh
            ):

                raise RuntimeError(
                    "Cannot refresh the current Litenova window."
                )

            refresh()

            app = QApplication.instance()

            if app is not None:

                apply_theme(
                    app
                )

            show_settings = getattr(
                main_window,
                "show_settings",
                None,
            )

            if callable(
                show_settings
            ):

                show_settings()

        except Exception as error:

            QMessageBox.warning(
                main_window,
                (
                    f"{operation.capitalize()} "
                    "completed — refresh needed"
                ),
                (
                    "The data operation succeeded, but Litenova "
                    "could not refresh its pages automatically.\n\n"
                    "Do not run the operation again. "
                    "Please reopen Litenova when convenient.\n\n"
                    f"Details:\n{error}\n\n"
                    f"Recovery backup:\n{recovery}"
                ),
            )

            return

        if operation == "reset":

            message = (
                "Litenova has been reset and is ready to use.\n\n"
                f"Recovery backup:\n{recovery}\n\n"
                f"Previous data:\n{previous}"
            )

            title = (
                "Reset complete"
            )

        else:

            message = (
                "Your Library has been refreshed without "
                "closing Litenova.\n\n"
                f"Recovery backup:\n{recovery}\n\n"
                f"Previous data:\n{previous}"
            )

            title = (
                "Import complete"
            )

        QMessageBox.information(
            main_window,
            title,
            message,
        )

    # ========================================================
    # EXPORT DATA
    # ========================================================

    def export_data(
        self,
    ):

        if self._data_job is not None:
            return

        folder = (
            self._file_dialog_start_folder()
        )

        suggested_name = (
            "Litenova_backup_"
            + datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S"
            )
            + ".zip"
        )

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export Litenova data",
            str(
                folder
                / suggested_name
            ),
            "Litenova backup (*.zip)",
        )

        if not destination:
            return

        selected_file = (
            Path(
                destination
            )
            .expanduser()
        )

        if self._is_inside_live_data(
            selected_file.parent
        ):

            QMessageBox.warning(
                self,
                "Choose a different folder",
                (
                    "Do not export a backup inside "
                    "Litenova's live data folder.\n\n"
                    "Choose Documents, Downloads, Desktop, "
                    "or another drive."
                ),
            )

            return

        self._remember_backup_directory(
            selected_file.parent
        )

        self._start_data_operation(
            "export",
            str(selected_file),
        )

    # ========================================================
    # IMPORT DATA
    # ========================================================

    def import_data(
        self,
    ):

        if self._data_job is not None:
            return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Litenova backup",
            str(
                self._file_dialog_start_folder()
            ),
            "Litenova backup (*.zip)",
        )

        if not filename:
            return

        selected_file = (
            Path(
                filename
            )
            .expanduser()
        )

        if self._is_inside_live_data(
            selected_file.parent
        ):

            QMessageBox.warning(
                self,
                "Select a backup outside app data",
                (
                    "Choose a ZIP backup stored outside "
                    "Litenova's live data folder."
                ),
            )

            return

        answer = QMessageBox.warning(
            self,
            "Replace application data?",
            (
                "Importing replaces the current Library, "
                "history and settings.\n\n"
                "Litenova will first save a recovery backup, "
                "then refresh the application without closing it.\n\n"
                "Continue?"
            ),
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.Yes:

            self._remember_backup_directory(
                selected_file.parent
            )

            self._start_data_operation(
                "import",
                str(selected_file),
            )

    # ========================================================
    # RESET APP DATA
    # ========================================================

    def reset_app(
        self,
    ):

        if self._data_job is not None:
            return

        answer = QMessageBox.warning(
            self,
            "Reset ALL Litenova data?",
            (
                "This will clear ALL imported books, "
                "custom categories, reading history and settings.\n\n"
                "Original source files outside Litenova "
                "are not deleted.\n\n"
                "A recovery backup will be saved first. "
                "Litenova will remain open.\n\n"
                "Continue?"
            ),
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        from PySide6.QtWidgets import (
            QInputDialog,
        )

        phrase, confirmed = QInputDialog.getText(
            self,
            "Confirm reset",
            "Type RESET to erase Litenova's data:",
        )

        if (
            confirmed
            and phrase == "RESET"
        ):

            self._start_data_operation(
                "reset"
            )