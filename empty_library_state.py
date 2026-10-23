from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    Signal,
)

from PySide6.QtGui import QFont

from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class EmptyLibraryState(QFrame):
    """
    Calm empty-state panel used by the Library.

    It can represent:
    - a completely new Library,
    - an empty custom category,
    - no uncategorized books,
    - or no search/filter results.
    """

    import_requested = Signal()

    def __init__(
        self,
        title,
        message,
        show_import_button=True,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.setObjectName(
            "libraryEmptyState"
        )

        self.setMaximumWidth(
            560
        )

        self.setMinimumWidth(
            420
        )

        self.build_ui(
            title,
            message,
            show_import_button,
        )

        self.start_fade_in()

    # ========================================================
    # UI
    # ========================================================

    def build_ui(
        self,
        title,
        message,
        show_import_button,
    ):
        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            42,
            40,
            42,
            38,
        )

        layout.setSpacing(
            14
        )

        # ====================================================
        # SMALL SYMBOL
        # ========================================================

        symbol = QLabel(
            "◇",
            self,
        )

        symbol.setObjectName(
            "libraryEmptySymbol"
        )

        symbol.setAlignment(
            Qt.AlignCenter
        )

        symbol_font = QFont()

        symbol_font.setPointSize(
            30
        )

        symbol.setFont(
            symbol_font
        )

        layout.addWidget(
            symbol
        )

        # ====================================================
        # TITLE
        # ========================================================

        heading = QLabel(
            title,
            self,
        )

        heading.setObjectName(
            "libraryEmptyTitle"
        )

        heading.setAlignment(
            Qt.AlignCenter
        )

        heading.setWordWrap(
            True
        )

        title_font = QFont()

        title_font.setPointSize(
            18
        )

        title_font.setWeight(
            QFont.Weight.DemiBold
        )

        heading.setFont(
            title_font
        )

        layout.addWidget(
            heading
        )

        # ====================================================
        # DESCRIPTION
        # ========================================================

        description = QLabel(
            message,
            self,
        )

        description.setObjectName(
            "libraryEmptyDescription"
        )

        description.setAlignment(
            Qt.AlignCenter
        )

        description.setWordWrap(
            True
        )

        layout.addWidget(
            description
        )

        # ====================================================
        # BUTTON
        # ========================================================

        if show_import_button:

            layout.addSpacing(
                8
            )

            import_button = QPushButton(
                "＋  Import a Book",
                self,
            )

            import_button.setObjectName(
                "libraryEmptyImport"
            )

            import_button.setCursor(
                Qt.PointingHandCursor
            )

            import_button.setMinimumHeight(
                44
            )

            import_button.setMaximumWidth(
                210
            )

            import_button.clicked.connect(
                self.import_requested.emit
            )

            layout.addWidget(
                import_button,
                0,
                Qt.AlignCenter,
            )

        # ====================================================
        # STYLE
        # ========================================================

        self.setStyleSheet(
            """
            QFrame#libraryEmptyState {
                background: #1f212b;
                border: 1px solid #3c3f4d;
                border-radius: 18px;
            }

            QLabel#libraryEmptySymbol {
                color: #8f88ff;
                background: transparent;
                border: none;
            }

            QLabel#libraryEmptyTitle {
                color: #eeeeee;
                background: transparent;
                border: none;
            }

            QLabel#libraryEmptyDescription {
                color: #aeb3c9;
                background: transparent;
                border: none;
                font-size: 13px;
            }

            QPushButton#libraryEmptyImport {
                background: #625ca8;
                color: #ffffff;
                border: 1px solid #756fc0;
                border-radius: 11px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 600;
            }

            QPushButton#libraryEmptyImport:hover {
                background: #756fc0;
            }

            QPushButton#libraryEmptyImport:pressed {
                background: #514d73;
            }
            """
        )

    # ========================================================
    # SUBTLE ANIMATION
    # ========================================================

    def start_fade_in(
        self,
    ):
        self.opacity_effect = QGraphicsOpacityEffect(
            self
        )

        self.setGraphicsEffect(
            self.opacity_effect
        )

        self.fade_animation = QPropertyAnimation(
            self.opacity_effect,
            b"opacity",
            self,
        )

        self.fade_animation.setDuration(
            180
        )

        self.fade_animation.setStartValue(
            0.0
        )

        self.fade_animation.setEndValue(
            1.0
        )

        self.fade_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        self.fade_animation.start()