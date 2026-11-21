#!/usr/bin/env python3
"""ChromaCursor GUI — Dynamic Omarchy theme-synced cursor studio (Qt 6 / PySide6)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import generator as gen
from theme import ThemePalette, ThemeWatcher, build_stylesheet

HOOK_PATH = Path.home() / ".config/omarchy/hooks/theme-set.d/chromacursor"
ROOT_DIR = Path(__file__).resolve().parent


class GlowButton(QPushButton):
    def __init__(self, text: str = "", glow_hex: str = "#7376b7", max_blur: float = 18.0, parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._max_blur = max_blur
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 0)
        self._shadow.setBlurRadius(0.0)
        self.update_glow_color(glow_hex)
        self.setGraphicsEffect(self._shadow)

        self._anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def update_glow_color(self, hex_color: str) -> None:
        c = QColor(hex_color)
        c.setAlpha(155)
        self._shadow.setColor(c)

    def enterEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._shadow.blurRadius())
        self._anim.setEndValue(self._max_blur)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._shadow.blurRadius())
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(event)


class ChromaCursorWindow(QMainWindow):
    def __init__(self, watcher: ThemeWatcher) -> None:
        super().__init__()
        self.watcher = watcher
        self.palette_data = watcher.palette
        self.cfg = gen.load_config()
        self.style_key: str = self.cfg.get("style", "neon")
        self.shape_key: str = self.cfg.get("shape", "bibata")
        self.cursor_size: int = int(self.cfg.get("size", 24))
        self._glow_buttons: list[GlowButton] = []
        self._style_btns: dict[str, GlowButton] = {}
        self._shape_btns: dict[str, GlowButton] = {}
        self._size_btns: dict[int, GlowButton] = {}
        self._preview_labels: dict[str, QLabel] = {}

        self.setWindowTitle("ChromaCursor — Dynamic Omarchy Theme Cursors")
        self.resize(820, 580)
        self.setMinimumSize(680, 480)

        self._build_ui()
        self.apply_theme(self.palette_data)
        self.watcher.theme_changed.connect(self._on_omarchy_theme_changed)

    def _btn(self, text: str, obj_name: str = "", blur: float = 16.0) -> GlowButton:
        b = GlowButton(text, glow_hex=self.palette_data.accent, max_blur=blur)
        if obj_name:
            b.setObjectName(obj_name)
        self._glow_buttons.append(b)
        return b

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(14)

        # Header card
        header = QFrame()
        header.setObjectName("HeaderCard")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 14, 18, 14)
        hl.setSpacing(12)

        tcol = QVBoxLayout()
        tcol.setSpacing(2)
        title = QLabel("ChromaCursor")
        title.setObjectName("TitleLabel")
        self.sub_lbl = QLabel("Auto-syncs your Linux cursor colors with your live Omarchy theme")
        self.sub_lbl.setObjectName("SubtitleLabel")
        tcol.addWidget(title)
        tcol.addWidget(self.sub_lbl)
        hl.addLayout(tcol, 1)

        self.accent_pill = QLabel("")
        self.accent_pill.setObjectName("StatPill")
        hl.addWidget(self.accent_pill)

        self.apply_btn = self._btn("✦  Apply Live Now", obj_name="PrimaryButton", blur=20.0)
        self.apply_btn.clicked.connect(self._apply_now)
        hl.addWidget(self.apply_btn)
        root.addWidget(header)

        # Shape Row: Bibata / Dot / Triangle / Classic
        shapes_row = QHBoxLayout()
        shapes_row.setSpacing(8)
        shapes_row.addWidget(QLabel("Shape:"))
        for key, label in gen.SHAPES.items():
            b = self._btn(label, obj_name="ChipButton", blur=12.0)
            b.setCheckable(True)
            b.setChecked(key == self.shape_key)
            b.clicked.connect(lambda checked=False, k=key: self._select_shape(k))
            self._shape_btns[key] = b
            shapes_row.addWidget(b)
        shapes_row.addStretch()
        root.addLayout(shapes_row)

        # Controls Row: Style + Size
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Style:"))
        for key, label in gen.STYLES.items():
            b = self._btn(label, obj_name="ChipButton", blur=12.0)
            b.setCheckable(True)
            b.setChecked(key == self.style_key)
            b.clicked.connect(lambda checked=False, k=key: self._select_style(k))
            self._style_btns[key] = b
            controls.addWidget(b)

        controls.addSpacing(14)
        controls.addWidget(QLabel("Size:"))
        for sz in gen.SIZES:
            b = self._btn(f"{sz}px", obj_name="ChipButton", blur=12.0)
            b.setCheckable(True)
            b.setChecked(sz == self.cursor_size)
            b.clicked.connect(lambda checked=False, s=sz: self._select_size(s))
            self._size_btns[sz] = b
            controls.addWidget(b)

        controls.addStretch()
        root.addLayout(controls)

        # Live Cursor Preview Grid
        preview_card = QFrame()
        preview_card.setObjectName("PreviewCard")
        pl = QVBoxLayout(preview_card)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(10)

        p_hdr = QLabel("Live Cursor Preview (24px / 32px / 48px + animated spinner)")
        p_hdr.setStyleSheet("font-weight: 700; font-size: 13px;")
        pl.addWidget(p_hdr)

        grid = QGridLayout()
        grid.setSpacing(10)
        names = list(gen.CURSOR_ALIASES.keys())
        for idx, name in enumerate(names):
            tile = QFrame()
            tile.setObjectName("CursorTile")
            tl = QVBoxLayout(tile)
            tl.setContentsMargins(10, 10, 10, 8)
            tl.setSpacing(6)
            tl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon_lbl = QLabel()
            icon_lbl.setFixedSize(48, 48)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._preview_labels[name] = icon_lbl

            name_lbl = QLabel(name)
            name_lbl.setObjectName("SubtitleLabel")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            tl.addWidget(icon_lbl)
            tl.addWidget(name_lbl)
            grid.addWidget(tile, idx // 4, idx % 4)

        pl.addLayout(grid)
        root.addWidget(preview_card, 1)

        # Bottom Actions: Auto-sync Hook + Restore + Support
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.hook_btn = self._btn("", obj_name="ChipButton", blur=14.0)
        self.hook_btn.clicked.connect(self._toggle_hook)
        footer.addWidget(self.hook_btn)

        restore_btn = self._btn("↺  Restore Bibata", obj_name="ChipButton", blur=12.0)
        restore_btn.clicked.connect(self._restore_default)
        footer.addWidget(restore_btn)

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setObjectName("SubtitleLabel")
        footer.addWidget(self.status_lbl, 1)

        support_btn = self._btn("☕  Support", obj_name="ChipButton", blur=14.0)
        support_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://buymeacoffee.com/aurorauap")))
        footer.addWidget(support_btn)
        root.addLayout(footer)

        self._refresh_hook_button()

    def _refresh_hook_button(self) -> None:
        installed = HOOK_PATH.is_file()
        self.hook_btn.setText("✓  Auto-Sync Hook: ON" if installed else "+  Enable Auto-Sync Hook")

    def _toggle_hook(self) -> None:
        if HOOK_PATH.is_file():
            try:
                HOOK_PATH.unlink()
                self.status_lbl.setText("Auto-sync hook removed")
            except OSError as exc:
                self.status_lbl.setText(f"Error: {exc}")
        else:
            hook_src = ROOT_DIR / "hook-theme-set.sh"
            res = subprocess.run(
                ["omarchy", "hook", "install", "theme-set", str(hook_src)],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                self.status_lbl.setText("✓ Omarchy theme-set hook installed!")
            else:
                # Fallback direct install into ~/.config/omarchy/hooks/theme-set.d/
                HOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
                HOOK_PATH.write_text(hook_src.read_text(encoding="utf-8"), encoding="utf-8")
                HOOK_PATH.chmod(0o755)
                self.status_lbl.setText("✓ Auto-sync hook installed!")
        self._refresh_hook_button()

    def _select_shape(self, key: str) -> None:
        self.shape_key = key
        for k, b in self._shape_btns.items():
            b.setChecked(k == key)
        self.cfg["shape"] = key
        gen.save_config(self.cfg)
        self._refresh_previews()
        self._apply_now()

    def _select_style(self, key: str) -> None:
        self.style_key = key
        for k, b in self._style_btns.items():
            b.setChecked(k == key)
        self.cfg["style"] = key
        gen.save_config(self.cfg)
        self._refresh_previews()
        self._apply_now()

    def _select_size(self, sz: int) -> None:
        self.cursor_size = sz
        for s, b in self._size_btns.items():
            b.setChecked(s == sz)
        self.cfg["size"] = sz
        gen.save_config(self.cfg)
        self._apply_now()

    def _refresh_previews(self) -> None:
        colors = gen.read_omarchy_colors()
        imgs = gen.render_preview_images(colors, self.style_key, shape=self.shape_key, size=48)
        for name, img in imgs.items():
            if name in self._preview_labels:
                self._preview_labels[name].setPixmap(QPixmap.fromImage(img))
        self.accent_pill.setText(f"{colors.accent} · {gen.SHAPES[self.shape_key]} · {gen.STYLES[self.style_key]}")

    def _apply_now(self) -> None:
        colors = gen.read_omarchy_colors()
        gen.build_cursor_theme(colors=colors, style=self.style_key, shape=self.shape_key)
        gen.apply_cursor_live(gen.THEME_NAME, self.cursor_size)
        self.status_lbl.setText(
            f"✓ Applied {gen.SHAPES[self.shape_key]} / {gen.STYLES[self.style_key]} ({colors.accent}, {self.cursor_size}px) live!"
        )

    def _restore_default(self) -> None:
        gen.apply_cursor_live("Bibata-Modern-Ice", self.cursor_size)
        self.status_lbl.setText("Restored Bibata-Modern-Ice cursor")

    def _on_omarchy_theme_changed(self, palette: ThemePalette) -> None:
        self.apply_theme(palette)

    def apply_theme(self, palette: ThemePalette) -> None:
        self.palette_data = palette
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet(palette))
        for b in self._glow_buttons:
            b.update_glow_color(palette.accent)
        self._refresh_previews()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ChromaCursor")
    app.setDesktopFileName("chromacursor")
    watcher = ThemeWatcher(app)
    win = ChromaCursorWindow(watcher)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
