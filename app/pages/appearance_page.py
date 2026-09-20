"""Full-width, dark-only Appearance editor with a live reader preview.

The window title bar is native Windows UI; changing colors here does not
recolor its native chrome or replace the user's Litenova application logo.
"""
import copy
import uuid

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QMessageBox, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from app.services.appearance_service import (
    THEMES, active_preset, default_state, load_state, resolved_colors, save_state,
)


class AppearancePage(QWidget):
    """A separate Settings sub-page, so presets do not squeeze into a small card."""

    back_requested = Signal()
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("appearancePage")
        self.state = load_state()
        self._updating = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(150)
        self._save_timer.timeout.connect(self.save_changes)
        self.build_ui()
        self.load_settings()

    def text(self, value, kind="appearanceCaption", parent=None):
        widget = QLabel(value, parent or self)
        widget.setObjectName(kind)
        widget.setWordWrap(True)
        return widget

    def button(self, text, handler, kind="appearanceButton"):
        widget = QPushButton(text, self)
        widget.setObjectName(kind)
        widget.setCursor(Qt.PointingHandCursor)
        widget.clicked.connect(handler)
        return widget

    def section(self, layout, text):
        heading = self.text(text, "appearanceSection")
        layout.addWidget(heading)
        return heading

    def setting_line(self, layout, caption, widget, detail=None):
        line = QHBoxLayout()
        line.setSpacing(12)
        description = QVBoxLayout()
        description.setSpacing(3)
        description.addWidget(self.text(caption, "appearanceCaption"))
        if detail:
            description.addWidget(self.text(detail, "appearanceDetail"))
        line.addLayout(description, 1)
        line.addWidget(widget, 0, Qt.AlignVCenter)
        layout.addLayout(line)

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(13)
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.button("← Settings", self.back, "appearanceBack"))
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title_layout.addWidget(self.text("Appearance", "appearanceTitle"))
        title_layout.addWidget(self.text("Dark themes, color presets and live preview", "appearanceDetail"))
        toolbar.addLayout(title_layout, 1)
        root.addLayout(toolbar)

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        # Independent scroll: controls can be taller than the reader preview.
        scroll = QScrollArea(self)
        scroll.setObjectName("appearanceScroll")
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("appearanceScrollContent")
        self.controls = QVBoxLayout(container)
        self.controls.setContentsMargins(2, 2, 7, 12)
        self.controls.setSpacing(12)
        scroll.setWidget(container)
        body.addWidget(scroll, 7)

        # Dark-only variants: no light-mode toggle (per user preference).
        self.section(self.controls, "Dark theme presets")
        self.controls.addWidget(self.text(
            "Litenova stays in dark mode. Select a different dark color palette.",
            "appearanceDetail"
        ))
        themes = QHBoxLayout()
        themes.setSpacing(9)
        self.theme_buttons = {}
        for key, name, summary, colors in (
            ("mercury", "Mercury", "Original lavender", ("#d6d4ff", "#6c70a4", "#b5b8cc")),
            ("neptune", "Neptune", "Cool blue", ("#89b9ff", "#a7bbd8", "#343f5a")),
            ("aurora", "Aurora", "Soft green", ("#a1e5c2", "#b4dbd1", "#394b42")),
        ):
            label = f"{name}\n{summary}\n●   ●   ●"
            button = self.button(label, lambda _checked=False, choice=key: self.set_theme(choice),
                                 "appearanceTheme")
            button.setCheckable(True)
            button.setMinimumHeight(106)
            button.setToolTip(f"{name}: {summary}")
            button.setProperty("paletteName", key)
            themes.addWidget(button, 1)
            self.theme_buttons[key] = button
        self.controls.addLayout(themes)

        self.section(self.controls, "Pure dark")
        dark_modes = QHBoxLayout()
        dark_modes.setSpacing(0)
        self.dark_buttons = {}
        for mode, label in (("disabled", "Disabled"), ("enabled", "Enabled"),
                            ("saver", "Saver")):
            button = self.button(label, lambda _checked=False, choice=mode: self.set_pure_dark(choice),
                                 "appearanceSegment")
            button.setCheckable(True)
            dark_modes.addWidget(button, 1)
            self.dark_buttons[mode] = button
        self.controls.addLayout(dark_modes)
        self.absolute_switch = QCheckBox("Absolute dark — use pure black (#000000)", self)
        self.absolute_switch.setObjectName("appearanceCheckbox")
        self.absolute_switch.toggled.connect(self.set_absolute_dark)
        self.controls.addWidget(self.absolute_switch)
        self.controls.addWidget(self.text(
            "Saver uses an almost-black background. It does not change your Windows power settings.",
            "appearanceDetail"
        ))

        self.section(self.controls, "Colors")
        self.controls.addWidget(self.text("Color preset", "appearanceCaption"))
        self.preset_bar = QHBoxLayout()
        self.preset_bar.setSpacing(7)
        self.controls.addLayout(self.preset_bar)
        self.selected_name = self.text("Preset 1", "appearanceCaption")
        self.controls.addWidget(self.selected_name)

        actions = QHBoxLayout()
        actions.addWidget(self.button("+ New preset", self.new_preset))
        actions.addWidget(self.button("Rename", self.rename_preset))
        actions.addWidget(self.button("Duplicate", self.duplicate_preset))
        actions.addWidget(self.button("Delete", self.delete_preset, "appearanceDanger"))
        self.controls.addLayout(actions)
        self.controls.addWidget(self.text(
            "Adjust the background and text colors. Changes update the preview immediately and save automatically.",
            "appearanceDetail"
        ))

        self.rgb_sliders = {}
        self.rgb_values = {}
        for channel, caption in (("background", "Background color"), ("foreground", "Font color")):
            group = QFrame(self)
            group.setObjectName("appearanceGroup")
            section = QVBoxLayout(group)
            section.setContentsMargins(12, 10, 12, 11)
            section.setSpacing(5)
            section.addWidget(self.text(caption, "appearanceCaption"))
            for index, component in enumerate(("Red", "Green", "Blue")):
                row = QHBoxLayout()
                row.setSpacing(8)
                name = self.text(component, "appearanceDetail")
                name.setFixedWidth(48)
                row.addWidget(name)
                value = self.text("0", "appearanceDetail")
                value.setFixedWidth(26)
                row.addWidget(value)
                slider = QSlider(Qt.Horizontal, self)
                slider.setRange(0, 255)
                slider.setSingleStep(1)
                slider.setObjectName("appearanceColorSlider")
                slider.valueChanged.connect(
                    lambda number, k=channel, i=index: self.set_rgb_component(k, i, number)
                )
                row.addWidget(slider, 1)
                reset = self.button("↶", lambda _checked=False, k=channel, i=index:
                                    self.reset_component(k, i), "appearanceReset")
                reset.setFixedWidth(29)
                reset.setToolTip("Reset this channel to the theme default")
                row.addWidget(reset)
                self.rgb_sliders[(channel, index)] = slider
                self.rgb_values[(channel, index)] = value
                section.addLayout(row)
            self.controls.addWidget(group)

        self.quick_switch = QCheckBox("Fast color preset change", self)
        self.quick_switch.setObjectName("appearanceCheckbox")
        self.quick_switch.toggled.connect(self.set_quick_switch)
        self.controls.addWidget(self.quick_switch)
        self.controls.addWidget(self.text(
            "When enabled, press Ctrl+Alt+← / Ctrl+Alt+→ while this page is open to cycle presets.",
            "appearanceDetail"
        ))
        self.controls.addWidget(self.button("Restore original appearance", self.restore_defaults))
        self.controls.addStretch(1)

        # Reference-style live reading preview in a right-hand card.
        self.preview_panel = QFrame(self)
        self.preview_panel.setObjectName("appearancePreviewPanel")
        self.preview_panel.setMinimumWidth(255)
        self.preview_panel.setMaximumWidth(395)
        side = QVBoxLayout(self.preview_panel)
        side.setContentsMargins(17, 17, 17, 17)
        side.setSpacing(12)
        side.addWidget(self.text("Live preview", "appearanceSection"))
        side.addWidget(self.text("See the selected background and text colors.", "appearanceDetail"))
        self.preview_canvas = QFrame(self.preview_panel)
        self.preview_canvas.setObjectName("appearancePreviewCanvas")
        preview = QVBoxLayout(self.preview_canvas)
        preview.setContentsMargins(17, 18, 17, 19)
        preview.setSpacing(15)
        self.preview_nav = self.text("←                         Aa      ♧      ⋮", "appearancePreviewNav")
        preview.addWidget(self.preview_nav)
        preview.addSpacing(9)
        self.preview_chapter = self.text("Chapter 1", "appearancePreviewSmall")
        preview.addWidget(self.preview_chapter)
        self.preview_title = self.text("A Brighter Tomorrow", "appearancePreviewTitle")
        preview.addWidget(self.preview_title)
        preview.addSpacing(4)
        self.preview_body = self.text(
            "The sky was clearer than it had been in months. Pale sunlight spilled over the rooftops, and for the first time in a long while, everything felt possible.\n\nShe took a deep breath and smiled. Another story awaited.",
            "appearancePreviewBody"
        )
        preview.addWidget(self.preview_body)
        preview.addStretch(1)
        self.preview_progress = QFrame(self.preview_canvas)
        self.preview_progress.setFixedHeight(5)
        preview.addWidget(self.preview_progress)
        self.preview_footer = self.text("Page 24 of 320                                        7%", "appearancePreviewSmall")
        preview.addWidget(self.preview_footer)
        side.addWidget(self.preview_canvas, 1)
        self.preview_note = self.text(
            "The preview updates while you adjust the colors. Some pages have additional, independent custom styling.",
            "appearanceDetail"
        )
        side.addWidget(self.preview_note)
        body.addWidget(self.preview_panel, 4)

        self.left_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Left"), self)
        self.left_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.left_shortcut.activated.connect(lambda: self.cycle_preset(-1))
        self.right_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Right"), self)
        self.right_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.right_shortcut.activated.connect(lambda: self.cycle_preset(1))

        self.setStyleSheet("""
            QWidget#appearancePage, QWidget#appearanceScrollContent { background: #15171e; color: #e9ebfb; }
            QScrollArea#appearanceScroll { background: transparent; border: none; }
            QLabel { background: transparent; border: none; }
            QLabel#appearanceTitle { color: #f3f2ff; font-size: 27px; font-weight: 700; }
            QLabel#appearanceSection { color: #c8c8fa; font-size: 16px; font-weight: 700; }
            QLabel#appearanceCaption { color: #e8e8f4; font-size: 13px; }
            QLabel#appearanceDetail { color: #aeb2c9; font-size: 11px; }
            QFrame#appearanceGroup, QFrame#appearancePreviewPanel { background: #191c24;
                border: 1px solid #383c4b; border-radius: 11px; }
            QPushButton#appearanceButton, QPushButton#appearanceBack, QPushButton#appearanceDanger,
            QPushButton#appearanceReset, QPushButton#appearanceSegment, QPushButton#appearanceTheme {
                background: #242735; color: #e6e6f7; border: 1px solid #555b72;
                border-radius: 8px; padding: 7px; font-size: 12px; }
            QPushButton#appearanceButton:hover, QPushButton#appearanceBack:hover,
            QPushButton#appearanceReset:hover, QPushButton#appearanceTheme:hover {
                border-color: #bab5ff; background: #32364e; }
            QPushButton#appearanceTheme { min-width: 95px; text-align: left; padding: 13px;
                font-size: 13px; background: #181b22; }
            QPushButton#appearanceTheme:checked, QPushButton#appearanceSegment:checked {
                background: #383d62; color: #f5f3ff; border: 2px solid #b3b0fb; }
            QPushButton#appearanceSegment { border-radius: 5px; }
            QPushButton#appearanceDanger { border-color: #ad626d; color: #ffc6cd; }
            QPushButton#appearanceReset { background: transparent; }
            QCheckBox#appearanceCheckbox { color: #e6e5fa; padding: 5px 0; font-size: 12px; }
            QCheckBox#appearanceCheckbox::indicator { width: 16px; height: 16px; }
            QCheckBox#appearanceCheckbox::indicator:checked { background: #8f88ff;
                border: 1px solid #b3adff; border-radius: 3px; }
            QSlider#appearanceColorSlider::groove:horizontal { background: #444963;
                height: 6px; border-radius: 3px; }
            QSlider#appearanceColorSlider::handle:horizontal { background: #cfccff;
                width: 13px; margin: -5px 0; border-radius: 6px; }
        """)

    def load_settings(self):
        self._save_timer.stop()
        self.state = load_state()
        self.refresh_all()

    def back(self):
        if self._save_timer.isActive():
            self._save_timer.stop()
            self.save_changes()
        self.back_requested.emit()

    def refresh_all(self):
        self._updating = True
        try:
            for name, button in self.theme_buttons.items():
                button.setChecked(name == self.state["theme"])
            for name, button in self.dark_buttons.items():
                button.setChecked(name == self.state["pure_dark"])
            self.absolute_switch.setChecked(self.state["absolute_dark"])
            self.quick_switch.setChecked(self.state["quick_switch"])
            self.refresh_preset_buttons()
            self.refresh_rgb()
            self.refresh_preview()
        finally:
            self._updating = False

    def refresh_preset_buttons(self):
        while self.preset_bar.count():
            item = self.preset_bar.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        for entry in self.state["presets"]:
            key = entry["id"]
            button = self.button(entry["name"],
                                 lambda _checked=False, selection=key: self.select_preset(selection),
                                 "appearanceSegment")
            button.setCheckable(True)
            button.setChecked(key == self.state["active_preset"])
            self.preset_bar.addWidget(button, 1)
        self.selected_name.setText(active_preset(self.state)["name"])

    def refresh_rgb(self):
        palette = resolved_colors(self.state)
        self._updating = True
        try:
            for key in ("background", "foreground"):
                color = palette[key]
                for channel, value in enumerate((int(color[1:3], 16), int(color[3:5], 16),
                                                 int(color[5:7], 16))):
                    slider = self.rgb_sliders[(key, channel)]
                    slider.blockSignals(True)
                    slider.setValue(value)
                    if key == "background":
                        slider.setEnabled(self.state["pure_dark"] == "disabled"
                                          and not self.state["absolute_dark"])
                    slider.blockSignals(False)
                    self.rgb_values[(key, channel)].setText(str(value))
        finally:
            self._updating = False

    def refresh_preview(self):
        palette = resolved_colors(self.state)
        bg, fg, accent = palette["background"], palette["foreground"], palette["accent"]
        self.preview_canvas.setStyleSheet(
            f"QFrame#appearancePreviewCanvas {{ background: {bg}; border: 1px solid {palette['border']};"
            "border-radius: 10px; }"
        )
        for widget in (self.preview_nav, self.preview_chapter, self.preview_title,
                       self.preview_body, self.preview_footer):
            widget.setStyleSheet(f"color: {fg}; background: transparent; border: none;")
        self.preview_title.setStyleSheet(
            f"color: {fg}; background: transparent; border: none; font: 21px Georgia;"
        )
        self.preview_body.setStyleSheet(
            f"color: {fg}; background: transparent; border: none; font: 15px Georgia;"
        )
        self.preview_progress.setStyleSheet(f"background: {accent}; border: none; border-radius: 2px;")

    def changed_state(self, refresh_rgb=False, rebuild_presets=False):
        if self._updating:
            return
        if rebuild_presets:
            self.refresh_preset_buttons()
        if refresh_rgb:
            self.refresh_rgb()
        self.refresh_preview()
        self._save_timer.start()

    def save_changes(self):
        self.state = save_state(self.state)
        # MainWindow already connects settings_changed to refresh_theme and
        # reload_settings. Emit once instead of repainting the app twice.
        self.changed.emit()

    def set_theme(self, name):
        self.state["theme"] = name
        for key, button in self.theme_buttons.items():
            button.setChecked(key == name)
        self.changed_state(refresh_rgb=True)

    def set_pure_dark(self, name):
        self.state["pure_dark"] = name
        for key, button in self.dark_buttons.items():
            button.setChecked(key == name)
        self.changed_state(refresh_rgb=True)

    def set_absolute_dark(self, enabled):
        self.state["absolute_dark"] = bool(enabled)
        self.changed_state(refresh_rgb=True)

    def select_preset(self, identifier):
        self.state["active_preset"] = str(identifier)
        self.changed_state(refresh_rgb=True, rebuild_presets=True)

    def set_rgb_component(self, key, index, number):
        if self._updating:
            return
        # Store the requested channel as an RGB hexadecimal string.
        entry = active_preset(self.state)
        base = entry[key] or THEMES[self.state["theme"]][key]
        channels = [int(base[pos:pos + 2], 16) for pos in (1, 3, 5)]
        channels[index] = number
        entry[key] = "#" + "".join(f"{part:02x}" for part in channels)
        self.rgb_values[(key, index)].setText(str(number))
        self.changed_state()

    def reset_component(self, key, index):
        entry = active_preset(self.state)
        current = entry[key] or THEMES[self.state["theme"]][key]
        original = THEMES[self.state["theme"]][key]
        bits = [int(current[pos:pos + 2], 16) for pos in (1, 3, 5)]
        bits[index] = int(original[1 + 2 * index:3 + 2 * index], 16)
        entry[key] = "#" + "".join(f"{part:02x}" for part in bits)
        self.changed_state(refresh_rgb=True)

    def new_preset(self):
        if len(self.state["presets"]) >= 10:
            QMessageBox.information(self, "Color presets", "You can save up to 10 presets.")
            return
        name, ok = QInputDialog.getText(self, "New color preset", "Preset name:")
        if not ok or not name.strip():
            return
        colors = resolved_colors(self.state)
        identifier = uuid.uuid4().hex[:12]
        self.state["presets"].append({"id": identifier, "name": name.strip()[:32],
                                      "background": colors["background"],
                                      "foreground": colors["foreground"]})
        self.state["active_preset"] = identifier
        self.changed_state(rebuild_presets=True, refresh_rgb=True)

    def duplicate_preset(self):
        if len(self.state["presets"]) >= 10:
            QMessageBox.information(self, "Color presets", "You can save up to 10 presets.")
            return
        item = copy.deepcopy(active_preset(self.state))
        item["id"] = uuid.uuid4().hex[:12]
        item["name"] = (item["name"][:26] + " copy")[:32]
        self.state["presets"].append(item)
        self.state["active_preset"] = item["id"]
        self.changed_state(rebuild_presets=True, refresh_rgb=True)

    def rename_preset(self):
        item = active_preset(self.state)
        name, ok = QInputDialog.getText(self, "Rename preset", "Preset name:", text=item["name"])
        if ok and name.strip():
            item["name"] = name.strip()[:32]
            self.changed_state(rebuild_presets=True)

    def delete_preset(self):
        identifier = self.state["active_preset"]
        if identifier in ("1", "2"):
            QMessageBox.information(self, "Color presets", "The two built-in presets cannot be deleted.")
            return
        self.state["presets"] = [p for p in self.state["presets"] if p["id"] != identifier]
        self.state["active_preset"] = "1"
        self.changed_state(rebuild_presets=True, refresh_rgb=True)

    def set_quick_switch(self, enabled):
        self.state["quick_switch"] = bool(enabled)
        self.changed_state()

    def cycle_preset(self, direction):
        if not self.state["quick_switch"]:
            return
        ids = [p["id"] for p in self.state["presets"]]
        idx = ids.index(self.state["active_preset"])
        self.select_preset(ids[(idx + direction) % len(ids)])

    def restore_defaults(self):
        answer = QMessageBox.question(self, "Restore appearance?",
                                      "Reset only the appearance colors and presets to the original Litenova dark style?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.state = default_state()
            self.refresh_all()
            self.changed_state()
