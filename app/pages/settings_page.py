from PySide6.QtCore import Signal

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QFormLayout,
    QSpinBox,
    QComboBox,
    QPushButton,
    QAbstractSpinBox,
    QApplication,
)

from app.services.settings_service import (
    get_reader_font_size,
    set_reader_font_size,
    get_reader_theme,
    set_reader_theme,
)

from app.services.theme_service import (
    apply_theme,
)


class SettingsPage(QWidget):

    settings_changed = Signal()

    def __init__(self):
        super().__init__()

        self.build_ui()
        self.load_settings()

    # ========================================================
    # BUILD USER INTERFACE
    # ========================================================

    def build_ui(self):

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            30,
            30,
            30,
            30,
        )

        self.main_layout.setSpacing(
            20
        )

        # ====================================================
        # PAGE TITLE
        # ====================================================

        self.title = QLabel(
            "Settings"
        )

        self.description = QLabel(
            "Customize your Litenova reading experience."
        )

        # ====================================================
        # READING PREFERENCES CARD
        # ====================================================

        self.reading_card = QFrame()

        self.reading_card.setMaximumWidth(
            650
        )

        card_layout = QVBoxLayout(
            self.reading_card
        )

        card_layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        card_layout.setSpacing(
            15
        )

        self.card_title = QLabel(
            "Reading Preferences"
        )

        self.card_description = QLabel(
            "Changes are saved automatically."
        )

        # ====================================================
        # FORM
        # ====================================================

        form_layout = QFormLayout()

        form_layout.setSpacing(
            20
        )

        # ====================================================
        # FONT SIZE CONTROLS
        # ====================================================

        font_controls = QWidget()

        font_layout = QHBoxLayout(
            font_controls
        )

        font_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        font_layout.setSpacing(
            8
        )

        # ----------------------------------------------------
        # DECREASE FONT BUTTON
        # ----------------------------------------------------

        self.decrease_font_button = QPushButton(
            "A−"
        )

        self.decrease_font_button.setFixedSize(
            55,
            40,
        )

        self.decrease_font_button.clicked.connect(
            self.decrease_font_size
        )

        # ----------------------------------------------------
        # FONT SIZE INPUT
        # ----------------------------------------------------

        self.font_size_input = QSpinBox()

        self.font_size_input.setRange(
            12,
            32,
        )

        self.font_size_input.setSuffix(
            " px"
        )

        self.font_size_input.setFixedSize(
            110,
            40,
        )

        # Remove the built-in ▲ and ▼ buttons.
        self.font_size_input.setButtonSymbols(
            QAbstractSpinBox.NoButtons
        )

        self.font_size_input.valueChanged.connect(
            self.font_size_changed
        )

        # ----------------------------------------------------
        # INCREASE FONT BUTTON
        # ----------------------------------------------------

        self.increase_font_button = QPushButton(
            "A+"
        )

        self.increase_font_button.setFixedSize(
            55,
            40,
        )

        self.increase_font_button.clicked.connect(
            self.increase_font_size
        )

        # ----------------------------------------------------
        # ADD FONT CONTROLS
        # ----------------------------------------------------

        font_layout.addWidget(
            self.decrease_font_button
        )

        font_layout.addWidget(
            self.font_size_input
        )

        font_layout.addWidget(
            self.increase_font_button
        )

        font_layout.addStretch()

        self.font_label = QLabel(
            "Reader font size"
        )

        # ====================================================
        # READING MODE
        # ====================================================

        self.theme_input = QComboBox()

        self.theme_input.addItem(
            "Dark",
            "dark",
        )

        self.theme_input.addItem(
            "Light",
            "light",
        )

        self.theme_input.setFixedSize(
            185,
            40,
        )

        self.theme_input.currentIndexChanged.connect(
            self.theme_changed
        )

        self.theme_label = QLabel(
            "Reading mode"
        )

        # ====================================================
        # ADD FORM ROWS
        # ====================================================

        form_layout.addRow(
            self.font_label,
            font_controls,
        )

        form_layout.addRow(
            self.theme_label,
            self.theme_input,
        )

        # ====================================================
        # ADD CARD CONTENT
        # ====================================================

        card_layout.addWidget(
            self.card_title
        )

        card_layout.addWidget(
            self.card_description
        )

        card_layout.addSpacing(
            10
        )

        card_layout.addLayout(
            form_layout
        )

        # ====================================================
        # ADD PAGE CONTENT
        # ====================================================

        self.main_layout.addWidget(
            self.title
        )

        self.main_layout.addWidget(
            self.description
        )

        self.main_layout.addWidget(
            self.reading_card
        )

        self.main_layout.addStretch()

    # ========================================================
    # LOAD SAVED SETTINGS
    # ========================================================

    def load_settings(self):

        font_size = (
            get_reader_font_size()
        )

        theme = (
            get_reader_theme()
        )

        # Prevent signals while restoring values.
        self.font_size_input.blockSignals(
            True
        )

        self.theme_input.blockSignals(
            True
        )

        # ----------------------------------------------------
        # RESTORE FONT SIZE
        # ----------------------------------------------------

        self.font_size_input.setValue(
            font_size
        )

        # ----------------------------------------------------
        # RESTORE THEME
        # ----------------------------------------------------

        theme_index = (
            self.theme_input.findData(
                theme
            )
        )

        if theme_index >= 0:

            self.theme_input.setCurrentIndex(
                theme_index
            )

        self.font_size_input.blockSignals(
            False
        )

        self.theme_input.blockSignals(
            False
        )

        # Apply local Settings page colors.
        self.apply_local_theme(
            theme
        )

    # ========================================================
    # SETTINGS PAGE LOCAL THEME
    # ========================================================

    def apply_local_theme(
        self,
        theme,
    ):

        if theme == "light":

            page_background = "#f4f4f6"
            card_background = "#ffffff"

            primary_text = "#202126"
            secondary_text = "#666975"

            input_background = "#f1f1f4"
            input_border = "#d2d3d8"

            button_background = "#eeeeF2"
            button_hover = "#e1e1e7"

            accent = "#5b55b5"

        else:

            page_background = "#15171e"
            card_background = "#1f212b"

            primary_text = "#eeeeee"
            secondary_text = "#9da0ad"

            input_background = "#292c38"
            input_border = "#3c3f4d"

            button_background = "#292c38"
            button_hover = "#363947"

            accent = "#8f88ff"

        # ----------------------------------------------------
        # PAGE
        # ----------------------------------------------------

        self.setStyleSheet(
            f"""
            SettingsPage {{
                background-color: {page_background};
            }}

            QLabel {{
                color: {primary_text};
            }}

            QFrame {{
                background-color: {card_background};

                border: 1px solid {input_border};

                border-radius: 12px;
            }}

            QPushButton {{
                background-color: {button_background};

                color: {primary_text};

                border: 1px solid {input_border};

                border-radius: 7px;

                font-size: 15px;

                font-weight: 600;
            }}

            QPushButton:hover {{
                background-color: {button_hover};

                border-color: {accent};
            }}

            QSpinBox {{
                background-color: {input_background};

                color: {primary_text};

                border: 1px solid {input_border};

                border-radius: 7px;

                padding-left: 12px;

                font-size: 14px;
            }}

            QComboBox {{
                background-color: {input_background};

                color: {primary_text};

                border: 1px solid {input_border};

                border-radius: 7px;

                padding: 7px 12px;

                font-size: 14px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {card_background};

                color: {primary_text};

                selection-background-color: {accent};
            }}
            """
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        self.title.setStyleSheet(
            f"""
            font-size: 30px;

            font-weight: 600;

            color: {primary_text};
            """
        )

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        self.description.setStyleSheet(
            f"""
            font-size: 13px;

            color: {secondary_text};
            """
        )

        # ----------------------------------------------------
        # CARD TITLE
        # ----------------------------------------------------

        self.card_title.setStyleSheet(
            f"""
            font-size: 18px;

            font-weight: 600;

            color: {primary_text};

            border: none;
            """
        )

        # ----------------------------------------------------
        # CARD DESCRIPTION
        # ----------------------------------------------------

        self.card_description.setStyleSheet(
            f"""
            font-size: 12px;

            color: {secondary_text};

            border: none;
            """
        )

        # ----------------------------------------------------
        # FORM LABELS
        # ----------------------------------------------------

        self.font_label.setStyleSheet(
            f"""
            color: {primary_text};

            border: none;
            """
        )

        self.theme_label.setStyleSheet(
            f"""
            color: {primary_text};

            border: none;
            """
        )

    # ========================================================
    # DECREASE FONT SIZE
    # ========================================================

    def decrease_font_size(self):

        current_size = (
            self.font_size_input.value()
        )

        if current_size > 12:

            self.font_size_input.setValue(
                current_size - 1
            )

    # ========================================================
    # INCREASE FONT SIZE
    # ========================================================

    def increase_font_size(self):

        current_size = (
            self.font_size_input.value()
        )

        if current_size < 32:

            self.font_size_input.setValue(
                current_size + 1
            )

    # ========================================================
    # FONT SIZE CHANGED
    # ========================================================

    def font_size_changed(
        self,
        font_size,
    ):

        set_reader_font_size(
            font_size
        )

        self.settings_changed.emit()

    # ========================================================
    # THEME CHANGED
    # ========================================================

    def theme_changed(
        self,
        index,
    ):

        theme = (
            self.theme_input.itemData(
                index
            )
        )

        if theme is None:
            return

        # Save theme to SQLite.
        set_reader_theme(
            theme
        )

        # ----------------------------------------------------
        # APPLY GLOBAL APPLICATION QSS IMMEDIATELY
        # ----------------------------------------------------

        app = QApplication.instance()

        if app is not None:

            apply_theme(
                app
            )

        # ----------------------------------------------------
        # APPLY SETTINGS-SPECIFIC COLORS
        # ----------------------------------------------------

        self.apply_local_theme(
            theme
        )

        # ----------------------------------------------------
        # NOTIFY READER / MAIN WINDOW
        # ----------------------------------------------------

        self.settings_changed.emit()