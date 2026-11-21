"""Live Omarchy theme watcher & QSS generator for ChromaCursor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

OMARCHY_COLORS = Path.home() / ".local/state/omarchy/current/theme/colors.toml"


@dataclass
class ThemePalette:
    mode: str = "dark"
    bg: str = "#0b0e14"
    surface: str = "#141926"
    card: str = "#192030"
    border: str = "#273147"
    fg: str = "#e6ecff"
    fg_muted: str = "#95a2bf"
    accent: str = "#7376b7"
    danger: str = "#ef4444"
    source_name: str = "Omarchy"


def _mix(c1: str, c2: str, t: float) -> str:
    def to_rgb(h: str) -> tuple[int, int, int]:
        h = h.strip().lstrip("#")
        if len(h) != 6:
            return (16, 20, 30)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    r1, g1, b1 = to_rgb(c1)
    r2, g2, b2 = to_rgb(c2)
    return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"


def load_palette() -> ThemePalette:
    if OMARCHY_COLORS.is_file():
        try:
            raw = OMARCHY_COLORS.read_text(encoding="utf-8", errors="replace")
            vals = dict(re.findall(r'^(\w+)\s*=\s*"([^"]+)"', raw, flags=re.MULTILINE))
            bg = vals.get("background", "#0b0e14")
            fg = vals.get("foreground", "#e6ecff")
            accent = vals.get("accent", "#7376b7")
            surface = vals.get("lighter_background") or _mix(bg, fg, 0.06)
            card = _mix(surface, fg, 0.05)
            border = _mix(surface, fg, 0.16)
            muted = vals.get("dark_foreground") or _mix(fg, bg, 0.35)
            return ThemePalette(
                mode=vals.get("mode", "dark"),
                bg=bg,
                surface=surface,
                card=card,
                border=border,
                fg=fg,
                fg_muted=muted,
                accent=accent,
                danger=vals.get("red", "#ef4444"),
                source_name="Omarchy",
            )
        except OSError:
            pass
    return ThemePalette()


def build_stylesheet(p: ThemePalette) -> str:
    btn_bg = _mix(p.surface, p.fg, 0.07)
    btn_hover = _mix(btn_bg, p.accent, 0.25)
    return f"""
    QMainWindow, QWidget {{ background-color: {p.bg}; color: {p.fg}; font-family: 'Inter', 'Noto Sans', sans-serif; font-size: 13px; }}
    QFrame#HeaderCard, QFrame#PreviewCard {{ background-color: {p.surface}; border: 1px solid {p.border}; border-radius: 14px; }}
    QFrame#CursorTile {{ background-color: {p.card}; border: 1px solid {p.border}; border-radius: 10px; }}
    QLabel {{ background: transparent; }}
    QLabel#TitleLabel {{ font-size: 20px; font-weight: 800; }}
    QLabel#SubtitleLabel {{ color: {p.fg_muted}; font-size: 12px; }}
    QLabel#StatPill {{ background-color: {_mix(p.surface, p.accent, 0.16)}; border: 1px solid {_mix(p.border, p.accent, 0.45)}; border-radius: 10px; padding: 5px 11px; font-weight: 700; font-size: 12px; }}
    QPushButton {{ background-color: {btn_bg}; border: 1px solid {p.border}; border-radius: 9px; padding: 8px 14px; color: {p.fg}; font-weight: 600; }}
    QPushButton:hover {{ background-color: {btn_hover}; border-color: {p.accent}; }}
    QPushButton#PrimaryButton {{ background-color: {p.accent}; color: #050810; border: 1px solid {p.accent}; font-weight: 800; }}
    QPushButton#PrimaryButton:hover {{ background-color: {_mix(p.accent, '#ffffff', 0.18)}; }}
    QPushButton#ChipButton {{ border-radius: 10px; padding: 6px 12px; font-size: 12px; }}
    QPushButton#ChipButton:checked {{ background-color: {p.accent}; color: #050810; border-color: {p.accent}; }}
    """


class ThemeWatcher(QObject):
    theme_changed = Signal(ThemePalette)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.palette = load_palette()
        self._watcher = QFileSystemWatcher(self)
        if OMARCHY_COLORS.parent.exists():
            self._watcher.addPath(str(OMARCHY_COLORS.parent))
        if OMARCHY_COLORS.exists():
            self._watcher.addPath(str(OMARCHY_COLORS))
        self._watcher.fileChanged.connect(self._schedule_reload)
        self._watcher.directoryChanged.connect(self._schedule_reload)

    def _schedule_reload(self) -> None:
        QTimer.singleShot(150, self._reload)

    def _reload(self) -> None:
        if OMARCHY_COLORS.exists() and str(OMARCHY_COLORS) not in self._watcher.files():
            self._watcher.addPath(str(OMARCHY_COLORS))
        self.palette = load_palette()
        self.theme_changed.emit(self.palette)
