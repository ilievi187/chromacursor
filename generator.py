#!/usr/bin/env python3
"""ChromaCursor generator — renders an Omarchy theme-matched Linux Xcursor set and applies it live."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow headless execution from Omarchy theme-set hook without a display
if not os.environ.get("QT_QPA_PLATFORM") and "--gui" not in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_QPA_PLATFORMTHEME"] = ""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

from xcursor_writer import CursorFrame, write_xcursor

CONFIG_PATH = Path.home() / ".config/chromacursor/config.json"
OMARCHY_COLORS = Path.home() / ".local/state/omarchy/current/theme/colors.toml"
ICONS_DIR = Path.home() / ".local/share/icons"
THEME_NAME = "ChromaCursor"

STYLES = {
    "neon": "Neon Outline",
    "solid": "Solid Accent",
    "glass": "Minimal Glass",
}

SIZES = (24, 32, 48)

# Primary cursor names -> list of Wayland/X11/GTK/Qt aliases
CURSOR_ALIASES: dict[str, list[str]] = {
    "default": ["left_ptr", "arrow", "top_left_arrow", "right_ptr"],
    "pointer": ["hand2", "hand1", "pointing_hand", "openhand"],
    "text": ["xterm", "ibeam", "vertical-text"],
    "crosshair": ["cross", "tcross", "plus", "cell"],
    "move": ["all-scroll", "fleur", "grab", "grabbing", "closedhand", "size_all"],
    "ew-resize": ["sb_h_double_arrow", "col-resize", "size_hor", "h_double_arrow", "e-resize", "w-resize", "left_side", "right_side"],
    "ns-resize": ["sb_v_double_arrow", "row-resize", "size_ver", "v_double_arrow", "n-resize", "s-resize", "top_side", "bottom_side"],
    "nwse-resize": ["size_fdiag", "bd_double_arrow", "nw-resize", "se-resize", "top_left_corner", "bottom_right_corner"],
    "nesw-resize": ["size_bdiag", "fd_double_arrow", "ne-resize", "sw-resize", "top_right_corner", "bottom_left_corner"],
    "not-allowed": ["crossed_circle", "no-drop", "forbidden", "circle"],
    "wait": ["watch", "progress", "left_ptr_watch", "half-busy"],
}


@dataclass
class CursorColors:
    accent: str = "#7376b7"
    bg: str = "#0b0e14"
    fg: str = "#e6ecff"
    danger: str = "#ef4444"
    mode: str = "dark"
    source: str = "Fallback"


def read_omarchy_colors() -> CursorColors:
    if OMARCHY_COLORS.is_file():
        try:
            raw = OMARCHY_COLORS.read_text(encoding="utf-8", errors="replace")
            vals = dict(re.findall(r'^(\w+)\s*=\s*"([^"]+)"', raw, flags=re.MULTILINE))
            accent = vals.get("accent") or vals.get("blue") or "#7376b7"
            bg = vals.get("background") or "#0b0e14"
            fg = vals.get("foreground") or "#e6ecff"
            danger = vals.get("red") or "#ef4444"
            mode = vals.get("mode", "dark")
            return CursorColors(accent=accent, bg=bg, fg=fg, danger=danger, mode=mode, source="Omarchy Theme")
        except OSError:
            pass
    return CursorColors()


def load_config() -> dict:
    default = {"style": "neon", "size": 24, "enabled": True}
    if CONFIG_PATH.is_file():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                default.update(data)
        except Exception:
            pass
    return default


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _style_colors(colors: CursorColors, style: str) -> tuple[QColor, QColor, QColor]:
    """Return (fill, outline, glow) QColors for the chosen style."""
    accent = QColor(colors.accent)
    bg = QColor(colors.bg)
    fg = QColor(colors.fg)
    if style == "solid":
        outline = bg if bg.lightness() < 80 else QColor("#090b10")
        return accent, outline, accent
    if style == "glass":
        fill = QColor(fg)
        fill.setAlpha(235)
        return fill, accent, accent
    # Default: "neon" — deep theme background core + luminous theme accent outline
    core = QColor(bg)
    if core.lightness() > 160:
        core = QColor("#121620")
    return core, accent, accent


def _render_cursor_image(name: str, size: int, colors: CursorColors, style: str, phase: float = 0.0) -> tuple[QImage, int, int]:
    """Render a crisp anti-aliased cursor QImage (ARGB32_Premultiplied) + (xhot, yhot)."""
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    s = float(size)
    fill, outline, glow = _style_colors(colors, style)
    accent = QColor(colors.accent)
    danger = QColor(colors.danger)
    stroke_w = max(1.4, s * 0.068)

    def draw_glow_path(path: QPainterPath, pen_color: QColor, fill_color: QColor | None = None) -> None:
        # Soft outer halo for crisp readability on any wallpaper/window
        halo = QColor(pen_color)
        halo.setAlpha(75)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(halo, stroke_w * 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.setBrush(fill_color if fill_color is not None else Qt.BrushStyle.NoBrush)
        p.setPen(QPen(pen_color, stroke_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)

    xhot, yhot = int(s * 0.5), int(s * 0.5)

    if name == "default":
        xhot, yhot = int(round(s * 0.14)), int(round(s * 0.10))
        path = QPainterPath()
        path.moveTo(s * 0.14, s * 0.10)
        path.lineTo(s * 0.14, s * 0.84)
        path.lineTo(s * 0.34, s * 0.65)
        path.lineTo(s * 0.50, s * 0.90)
        path.lineTo(s * 0.61, s * 0.84)
        path.lineTo(s * 0.45, s * 0.60)
        path.lineTo(s * 0.72, s * 0.58)
        path.closeSubpath()
        draw_glow_path(path, outline, fill)
        # Subtle inner accent spine
        spine = QPainterPath()
        spine.moveTo(s * 0.22, s * 0.26)
        spine.lineTo(s * 0.22, s * 0.58)
        p.setPen(QPen(accent, max(1.0, s * 0.04), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(spine)

    elif name == "pointer":
        xhot, yhot = int(round(s * 0.36)), int(round(s * 0.10))
        path = QPainterPath()
        # Sleek geometric pointing finger + palm
        path.moveTo(s * 0.36, s * 0.10)
        path.lineTo(s * 0.47, s * 0.10)
        path.lineTo(s * 0.47, s * 0.42)
        path.lineTo(s * 0.57, s * 0.40)
        path.lineTo(s * 0.68, s * 0.44)
        path.lineTo(s * 0.77, s * 0.50)
        path.lineTo(s * 0.75, s * 0.78)
        path.lineTo(s * 0.64, s * 0.90)
        path.lineTo(s * 0.36, s * 0.90)
        path.lineTo(s * 0.22, s * 0.66)
        path.lineTo(s * 0.27, s * 0.54)
        path.lineTo(s * 0.36, s * 0.60)
        path.closeSubpath()
        draw_glow_path(path, outline, fill)

    elif name == "text":
        xhot, yhot = int(round(s * 0.5)), int(round(s * 0.5))
        path = QPainterPath()
        path.moveTo(s * 0.34, s * 0.14)
        path.lineTo(s * 0.66, s * 0.14)
        path.moveTo(s * 0.50, s * 0.14)
        path.lineTo(s * 0.50, s * 0.86)
        path.moveTo(s * 0.34, s * 0.86)
        path.lineTo(s * 0.66, s * 0.86)
        draw_glow_path(path, outline)

    elif name == "crosshair":
        xhot, yhot = int(round(s * 0.5)), int(round(s * 0.5))
        path = QPainterPath()
        path.moveTo(s * 0.50, s * 0.12); path.lineTo(s * 0.50, s * 0.38)
        path.moveTo(s * 0.50, s * 0.62); path.lineTo(s * 0.50, s * 0.88)
        path.moveTo(s * 0.12, s * 0.50); path.lineTo(s * 0.38, s * 0.50)
        path.moveTo(s * 0.62, s * 0.50); path.lineTo(s * 0.88, s * 0.50)
        draw_glow_path(path, outline)
        p.setBrush(accent)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.06, s * 0.06)

    elif name == "move":
        xhot, yhot = int(round(s * 0.5)), int(round(s * 0.5))
        path = QPainterPath()
        path.moveTo(s * 0.50, s * 0.12); path.lineTo(s * 0.50, s * 0.88)
        path.moveTo(s * 0.12, s * 0.50); path.lineTo(s * 0.88, s * 0.50)
        # Arrowheads
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            tip_x = s * (0.50 + dx * 0.38)
            tip_y = s * (0.50 + dy * 0.38)
            px, py = -dy * s * 0.11, dx * s * 0.11
            bx, by = tip_x - dx * s * 0.13, tip_y - dy * s * 0.13
            path.moveTo(bx + px, by + py)
            path.lineTo(tip_x, tip_y)
            path.lineTo(bx - px, by - py)
        draw_glow_path(path, outline)

    elif name in ("ew-resize", "ns-resize", "nwse-resize", "nesw-resize"):
        xhot, yhot = int(round(s * 0.5)), int(round(s * 0.5))
        angle = {"ew-resize": 0.0, "ns-resize": 90.0, "nwse-resize": 45.0, "nesw-resize": -45.0}[name]
        p.save()
        p.translate(s * 0.5, s * 0.5)
        p.rotate(angle)
        p.translate(-s * 0.5, -s * 0.5)
        path = QPainterPath()
        path.moveTo(s * 0.14, s * 0.50); path.lineTo(s * 0.86, s * 0.50)
        path.moveTo(s * 0.28, s * 0.35); path.lineTo(s * 0.14, s * 0.50); path.lineTo(s * 0.28, s * 0.65)
        path.moveTo(s * 0.72, s * 0.35); path.lineTo(s * 0.86, s * 0.50); path.lineTo(s * 0.72, s * 0.65)
        draw_glow_path(path, outline)
        p.restore()

    elif name == "not-allowed":
        xhot, yhot = int(round(s * 0.5)), int(round(s * 0.5))
        path = QPainterPath()
        path.addEllipse(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64))
        path.moveTo(s * 0.28, s * 0.28)
        path.lineTo(s * 0.72, s * 0.72)
        draw_glow_path(path, danger, fill)

    elif name == "wait":
        xhot, yhot = int(round(s * 0.5)), int(round(s * 0.5))
        # Subtle dark ring + animated glowing accent arc
        bg_ring = QColor(fill)
        bg_ring.setAlpha(180)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(bg_ring, stroke_w * 1.4))
        rect = QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64)
        p.drawEllipse(rect)

        start_deg = int((-phase * 360.0) * 16)
        span_deg = int(130 * 16)
        halo = QColor(accent)
        halo.setAlpha(95)
        p.setPen(QPen(halo, stroke_w * 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, start_deg, span_deg)
        p.setPen(QPen(accent, stroke_w * 1.15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, start_deg, span_deg)

    p.end()
    return img, xhot, yhot


def _ensure_qt() -> QGuiApplication:
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(sys.argv[:1])
    return app


def render_preview_images(colors: CursorColors, style: str, size: int = 48) -> dict[str, QImage]:
    _ensure_qt()
    out: dict[str, QImage] = {}
    for name in CURSOR_ALIASES:
        img, _, _ = _render_cursor_image(name, size, colors, style, phase=0.15)
        out[name] = img
    return out


def build_cursor_theme(colors: CursorColors | None = None, style: str | None = None) -> Path:
    """Generate the complete ChromaCursor Xcursor theme under ~/.local/share/icons/ChromaCursor."""
    _ensure_qt()
    cfg = load_config()
    eff_colors = colors or read_omarchy_colors()
    eff_style = style or cfg.get("style", "neon")

    theme_dir = ICONS_DIR / THEME_NAME
    cursors_dir = theme_dir / "cursors"
    cursors_dir.mkdir(parents=True, exist_ok=True)

    for primary, aliases in CURSOR_ALIASES.items():
        frames: list[CursorFrame] = []
        if primary == "wait":
            # 12-frame smooth spinning ring animation across all sizes
            n_frames = 12
            for sz in SIZES:
                for i in range(n_frames):
                    img, xhot, yhot = _render_cursor_image(primary, sz, eff_colors, eff_style, phase=i / n_frames)
                    raw = bytes(img.constBits())
                    frames.append(CursorFrame(sz, sz, sz, xhot, yhot, 55, raw))
        else:
            for sz in SIZES:
                img, xhot, yhot = _render_cursor_image(primary, sz, eff_colors, eff_style)
                raw = bytes(img.constBits())
                frames.append(CursorFrame(sz, sz, sz, xhot, yhot, 0, raw))

        out_file = cursors_dir / primary
        write_xcursor(out_file, frames)

        for alias in aliases:
            link_path = cursors_dir / alias
            if link_path.is_symlink() or link_path.exists():
                link_path.unlink()
            link_path.symlink_to(primary)

    index_text = (
        "[Icon Theme]\n"
        f"Name={THEME_NAME}\n"
        f"Comment=Dynamic Omarchy theme-synced cursor ({eff_style}, accent {eff_colors.accent})\n"
        "Inherits=Bibata-Modern-Ice,Adwaita\n"
    )
    (theme_dir / "index.theme").write_text(index_text, encoding="utf-8")
    return theme_dir


def apply_cursor_live(theme_name: str = THEME_NAME, size: int | None = None) -> None:
    """Apply cursor theme immediately on Hyprland + GTK without logging out."""
    cfg = load_config()
    sz = int(size or cfg.get("size", 24))

    # Force Hyprland to flush cached theme bitmaps by briefly toggling when re-applying ChromaCursor
    if theme_name == THEME_NAME:
        subprocess.run(["hyprctl", "setcursor", "Bibata-Modern-Ice", str(sz)], capture_output=True)
    subprocess.run(["hyprctl", "setcursor", theme_name, str(sz)], capture_output=True)

    subprocess.run(
        ["gsettings", "set", "org.gnome.desktop.interface", "cursor-theme", theme_name],
        capture_output=True,
    )
    subprocess.run(
        ["gsettings", "set", "org.gnome.desktop.interface", "cursor-size", str(sz)],
        capture_output=True,
    )

    # Also update ~/.icons/default/index.theme for XWayland / Qt / legacy apps
    default_dir = Path.home() / ".icons/default"
    default_dir.mkdir(parents=True, exist_ok=True)
    (default_dir / "index.theme").write_text(
        f"[Icon Theme]\nInherits={theme_name}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ChromaCursor — Dynamic Omarchy theme-synced cursor generator")
    parser.add_argument("--style", choices=list(STYLES), default=None, help="Cursor visual style")
    parser.add_argument("--size", type=int, choices=list(SIZES), default=None, help="Cursor size in px")
    parser.add_argument("--accent", default=None, help="Override accent hex color (e.g. #38bdf8)")
    parser.add_argument("--no-apply", action="store_true", help="Generate files without calling hyprctl/gsettings")
    parser.add_argument("--restore", action="store_true", help="Restore Bibata-Modern-Ice default cursor")
    args = parser.parse_args()

    if args.restore:
        apply_cursor_live("Bibata-Modern-Ice", args.size or 24)
        print("Restored Bibata-Modern-Ice cursor.")
        return 0

    cfg = load_config()
    if args.style:
        cfg["style"] = args.style
    if args.size:
        cfg["size"] = args.size
    if args.style or args.size:
        save_config(cfg)

    colors = read_omarchy_colors()
    if args.accent:
        colors.accent = args.accent
        colors.source = "CLI override"

    theme_dir = build_cursor_theme(colors=colors, style=cfg.get("style", "neon"))
    if not args.no_apply:
        apply_cursor_live(THEME_NAME, cfg.get("size", 24))

    print(
        f"ChromaCursor generated ({cfg.get('style', 'neon')}, accent={colors.accent}, size={cfg.get('size', 24)}px) -> {theme_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
