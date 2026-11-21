#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_DIR="${HOME}/.local/share/applications"
HOOK_DIR="${HOME}/.config/omarchy/hooks/theme-set.d"

chmod +x "$ROOT/run.sh" "$ROOT/generator.py" "$ROOT/gui.py" "$ROOT/hook-theme-set.sh"

# 1. Install desktop launcher shortcut
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/chromacursor.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=ChromaCursor
GenericName=Dynamic Theme-Synced Cursor Studio
Comment=Automatically generates and syncs Linux Xcursors with your active Omarchy theme
Exec=$ROOT/run.sh
Icon=$ROOT/icon.svg
Terminal=false
Categories=Settings;DesktopSettings;Utility;
Keywords=cursor;theme;omarchy;hyprland;wayland;accent;
StartupWMClass=chromacursor
EOF
update-desktop-database "$APPS_DIR" 2>/dev/null || true

# 2. Install Omarchy theme-set hook (points to this exact repo path)
TMP_HOOK="$(mktemp)"
cat > "$TMP_HOOK" << EOF
#!/usr/bin/env bash
set -euo pipefail
(sleep 0.3 && QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME="" python3 "$ROOT/generator.py" >/dev/null 2>&1) &
EOF
chmod +x "$TMP_HOOK"

if command -v omarchy >/dev/null 2>&1; then
  omarchy hook install theme-set "$TMP_HOOK" 2>/dev/null || {
    mkdir -p "$HOOK_DIR"
    cp "$TMP_HOOK" "$HOOK_DIR/chromacursor"
    chmod +x "$HOOK_DIR/chromacursor"
  }
  # Ensure clean filename 'chromacursor' inside theme-set.d
  if [ ! -f "$HOOK_DIR/chromacursor" ]; then
    mkdir -p "$HOOK_DIR"
    cp "$TMP_HOOK" "$HOOK_DIR/chromacursor"
    chmod +x "$HOOK_DIR/chromacursor"
  fi
else
  mkdir -p "$HOOK_DIR"
  cp "$TMP_HOOK" "$HOOK_DIR/chromacursor"
  chmod +x "$HOOK_DIR/chromacursor"
fi
rm -f "$TMP_HOOK"

# 3. Generate and apply ChromaCursor right now
QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME="" python3 "$ROOT/generator.py"
echo "✓ ChromaCursor installed! Launch from Super + Space or change your Omarchy theme to see it auto-sync."
