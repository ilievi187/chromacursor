#!/usr/bin/env bash
# Omarchy theme-set hook: automatically regenerates and applies ChromaCursor on every theme switch
set -euo pipefail
APP_DIR="/home/iliev/projects/chromacursor"
if [ ! -f "$APP_DIR/generator.py" ]; then
  APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/chromacursor"
fi
if [ -f "$APP_DIR/generator.py" ]; then
  QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME="" python3 "$APP_DIR/generator.py" >/dev/null 2>&1 &
fi
