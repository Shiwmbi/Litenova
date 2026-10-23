from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
)

from PySide6.QtGui import QFont

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WelcomeDialog(QDialog):
    """
    Litenova's first-launch welcome screen.

    The dialog intentionally stays simple:
    - Explain what Litenova is.
    - Let the user import a book.
    - Let the user open the Library.
    - Never overwhelm a new user with settings.
    """

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.action = None

        self.setWindowTitle(
            "Welcome to Litenova"
        )

        self.setModal(
            True
        )

        self.setMinimumSize(
            650,
            500,
        )

        self.resize(
            700,
            520,
        )

        self.setWindowFlag(
            Qt.WindowContextHelpButtonHint,
            False,
        )

        self.build_ui()

        self.start_fade_animation()

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(
        self,
    ):
        self.setObjectName(
            "welcomeDialog"
        )

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            28,
            28,
            28,
            28,
        )

        root.setSpacing(
            0
        )

        card = QFrame(
            self
        )

        card.setObjectName(
            "welcomeCard"
        )

        card_layout = QVBoxLayout(
            card
        )

        card_layout.setContentsMargins(
            42,
            38,
            42,
            36,
        )

        card_layout.setSpacing(
            18
        )

        # ====================================================
        # ICON
        # ====================================================

        icon_label = QLabel(
            card
        )

        icon_label.setObjectName(
            "welcomeIcon"
        )

        icon_label.setAlignment(
            Qt.AlignCenter
        )

        icon_label.setFixedSize(
            82,
            82,
        )

        app = QApplication.instance()

        if app is not None:

            icon = app.windowIcon()

            if not icon.isNull():

                icon_label.setPixmap(
                    icon.pixmap(
                        68,
                        68,
                    )
                )

        icon_row = QHBoxLayout()

        icon_row.addStretch()

        icon_row.addWidget(
            icon_label
        )

        icon_row.addStretch()

        card_layout.addLayout(
            icon_row
        )

        # ====================================================
        # TITLE
        # ====================================================

        title = QLabel(
            "Welcome to Litenova",
            card,
        )

        title.setObjectName(
            "welcomeTitle"
        )

        title.setAlignment(
            Qt.AlignCenter
        )

        title_font = QFont()

        title_font.setPointSize(
            24
        )

        title_font.setWeight(
            QFont.Weight.DemiBold
        )

        title.setFont(
            title_font
        )

        card_layout.addWidget(
            title
        )

        # ====================================================
        # DESCRIPTION
        # ====================================================

        description = QLabel(
            (
                "A quiet place for your light novels, "
                "manga, and manhwa."
            ),
            card,
        )

        description.setObjectName(
            "welcomeDescription"
        )

        description.setAlignment(
            Qt.AlignCenter
        )

        description.setWordWrap(
            True
        )

        card_layout.addWidget(
            description
        )

        # ====================================================
        # FEATURE ROW
        # ====================================================

        features = QWidget(
            card
        )

        feature_layout = QHBoxLayout(
            features
        )

        feature_layout.setContentsMargins(
            0,
            8,
            0,
            8,
        )

        feature_layout.setSpacing(
            10
        )

        feature_layout.addWidget(
            self.feature(
                "EPUB + CBZ",
                "Read novels and comics",
            )
        )

        feature_layout.addWidget(
            self.feature(
                "Local Library",
                "Your collection stays organized",
            )
        )

        feature_layout.addWidget(
            self.feature(
                "Private",
                "Your books stay on your device",
            )
        )

        card_layout.addWidget(
            features
        )

        card_layout.addStretch(
            1
        )

        # ====================================================
        # MAIN ACTION
        # ====================================================

        import_button = QPushButton(
            "Import a Book",
            card,
        )

        import_button.setObjectName(
            "welcomePrimaryButton"
        )

        import_button.setCursor(
            Qt.PointingHandCursor
        )

        import_button.setMinimumHeight(
            48
        )

        import_button.clicked.connect(
            self.choose_import
        )

        card_layout.addWidget(
            import_button
        )

        # ====================================================
        # SECONDARY ACTION
        # ====================================================

        library_button = QPushButton(
            "Open Library",
            card,
        )

        library_button.setObjectName(
            "welcomeSecondaryButton"
        )

        library_button.setCursor(
            Qt.PointingHandCursor
        )

        library_button.setMinimumHeight(
            46
        )

        library_button.clicked.connect(
            self.choose_library
        )

        card_layout.addWidget(
            library_button
        )

        # ====================================================
        # PRIVACY NOTE
        # ====================================================

        privacy = QLabel(
            (
                "Litenova stores your Library locally. "
                "Nothing needs to be uploaded to use the reader."
            ),
            card,
        )

        privacy.setObjectName(
            "welcomePrivacy"
        )

        privacy.setAlignment(
            Qt.AlignCenter
        )

        privacy.setWordWrap(
            True
        )

        card_layout.addWidget(
            privacy
        )

        root.addWidget(
            card
        )

        # ====================================================
        # LOCAL STYLE
        # ====================================================

        self.setStyleSheet(
            """
            QDialog#welcomeDialog {
                background: #15171e;
            }

            QFrame#welcomeCard {
                background: #1f212b;
                border: 1px solid #363947;
                border-radius: 20px;
            }

            QLabel#welcomeIcon {
                background: #292c38;
                border: 1px solid #3c3f4d;
                border-radius: 18px;
            }

            QLabel#welcomeTitle {
                color: #eeeeee;
                background: transparent;
                border: none;
            }

            QLabel#welcomeDescription {
                color: #b9bdca;
                font-size: 15px;
                background: transparent;
                border: none;
            }

            QFrame#welcomeFeature {
                background: #252833;
                border: 1px solid #363947;
                border-radius: 13px;
            }

            QLabel#welcomeFeatureTitle {
                color: #eeeeee;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
                border: none;
            }

            QLabel#welcomeFeatureText {
                color: #9fa4b6;
                font-size: 11px;
                background: transparent;
                border: none;
            }

            QPushButton#welcomePrimaryButton {
                background: #625ca8;
                color: #ffffff;
                border: 1px solid #756fc0;
                border-radius: 12px;
                padding: 0 18px;
                font-size: 14px;
                font-weight: 600;
            }

            QPushButton#welcomePrimaryButton:hover {
                background: #756fc0;
            }

            QPushButton#welcomePrimaryButton:pressed {
                background: #514d73;
            }

            QPushButton#welcomeSecondaryButton {
                background: #292c38;
                color: #e7e8f2;
                border: 1px solid #3c3f4d;
                border-radius: 12px;
                padding: 0 18px;
                font-size: 14px;
            }

            QPushButton#welcomeSecondaryButton:hover {
                background: #363947;
            }

            QPushButton#welcomeSecondaryButton:pressed {
                background: #252833;
            }

            QLabel#welcomePrivacy {
                color: #858b9e;
                font-size: 11px;
                background: transparent;
                border: none;
                padding-top: 5px;
            }
            """
        )

    # ========================================================
    # FEATURE CARD
    # ========================================================

    def feature(
        self,
        title,
        text,
    ):
        card = QFrame(
            self
        )

        card.setObjectName(
            "welcomeFeature"
        )

        card.setMinimumHeight(
            78
        )

        layout = QVBoxLayout(
            card
        )

        layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )

        layout.setSpacing(
            5
        )

        heading = QLabel(
            title,
            card,
        )

        heading.setObjectName(
            "welcomeFeatureTitle"
        )

        heading.setAlignment(
            Qt.AlignCenter
        )

        detail = QLabel(
            text,
            card,
        )

        detail.setObjectName(
            "welcomeFeatureText"
        )

        detail.setAlignment(
            Qt.AlignCenter
        )

        detail.setWordWrap(
            True
        )

        layout.addWidget(
            heading
        )

        layout.addWidget(
            detail
        )

        return card

    # ========================================================
    # ACTIONS
    # ========================================================

    def choose_import(
        self,
    ):
        self.action = "import"

        self.accept()

    def choose_library(
        self,
    ):
        self.action = "library"

        self.accept()

    # ========================================================
    # SUBTLE ENTRANCE ANIMATION
    # ========================================================

    def start_fade_animation(
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