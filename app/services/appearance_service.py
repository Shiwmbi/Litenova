"""Dark-only appearance preferences shared by Settings, app QSS and EPUB reader.

Stored in Litenova's existing QSettings, so appearance is included in the
application's existing ZIP export/import rather than requiring a DB migration.
"""
import copy
import json
import re
from PySide6.QtCore import QSettings

THEMES = {
    "mercury": {"background": "#15171e", "foreground": "#eeeeee", "accent": "#8f88ff"},
    "neptune": {"background": "#101823", "foreground": "#e1eafb", "accent": "#89b9ff"},
    "aurora": {"background": "#111c19", "foreground": "#e1f2e9", "accent": "#a1e5c2"},
}


def default_state():
    return {
        "theme": "mercury", "pure_dark": "disabled", "absolute_dark": False,
        "active_preset": "1", "quick_switch": False,
        "presets": [
            {"id": "1", "name": "Preset 1", "background": None, "foreground": None},
            {"id": "2", "name": "Preset 2", "background": "#080a11", "foreground": "#c3c6d6"},
        ],
    }


def _hex(value):
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value.lower()
    return None


def validated_state(data):
    state = default_state()
    if not isinstance(data, dict):
        return state
    if data.get("theme") in THEMES:
        state["theme"] = data["theme"]
    if data.get("pure_dark") in ("disabled", "enabled", "saver"):
        state["pure_dark"] = data["pure_dark"]
    state["absolute_dark"] = data.get("absolute_dark") is True
    state["quick_switch"] = data.get("quick_switch") is True
    presets = []
    seen = set()
    incoming = data.get("presets")
    if isinstance(incoming, list):
        for entry in incoming[:10]:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("id", ""))[:40]
            if not key or key in seen:
                continue
            seen.add(key)
            presets.append({
                "id": key,
                "name": str(entry.get("name", "Custom"))[:32] or "Custom",
                "background": _hex(entry.get("background")),
                "foreground": _hex(entry.get("foreground")),
            })
    for default in default_state()["presets"]:
        if default["id"] not in seen:
            presets.insert(int(default["id"]) - 1, copy.deepcopy(default))
            seen.add(default["id"])
    state["presets"] = presets
    active = str(data.get("active_preset", "1"))
    if any(p["id"] == active for p in presets):
        state["active_preset"] = active
    return state


def load_state():
    value = QSettings("Litenova", "Litenova").value("appearance/state", "")
    try:
        return validated_state(json.loads(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default_state()


def save_state(state):
    cleaned = validated_state(state)
    QSettings("Litenova", "Litenova").setValue(
        "appearance/state", json.dumps(cleaned, separators=(",", ":"))
    )
    return cleaned


def active_preset(state):
    return next((p for p in state["presets"] if p["id"] == state["active_preset"]),
                state["presets"][0])


def _mix(a, b, fraction):
    left = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    right = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * (1 - fraction) + y * fraction):02x}"
                         for x, y in zip(left, right))


def resolved_colors(state=None):
    state = validated_state(state if state is not None else load_state())
    theme = THEMES[state["theme"]]
    preset = active_preset(state)
    bg = preset["background"] or theme["background"]
    fg = preset["foreground"] or theme["foreground"]
    accent = theme["accent"]
    if state["pure_dark"] == "enabled":
        bg = "#08090c"
    elif state["pure_dark"] == "saver":
        bg = "#020203"
    if state["absolute_dark"]:
        bg = "#000000"
    # Dark-only fixed theme: custom background and foreground affect reader
    # and broad Qt UI elements. Fine-grained page-local QSS can override them.
    return {
        "background": bg, "foreground": fg, "accent": accent,
        "sidebar": _mix(bg, fg, 0.052),
        "panel": _mix(bg, fg, 0.082),
        "input": _mix(bg, fg, 0.12),
        "border": _mix(bg, fg, 0.19),
        "selected": _mix(bg, accent, 0.39),
        "button": _mix(bg, accent, 0.49),
        "hover": _mix(bg, fg, 0.16),
        "reader_background": ("#12141a" if bg == "#15171e" else bg),
    }
