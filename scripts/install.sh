#!/usr/bin/env bash
# Install Screen Capture for the current user. Idempotent.
#   scripts/install.sh               D-Bus service, app entry, Print shortcut
#   scripts/install.sh --autostart   ...and launch on startup
# Takes the key back from Flameshot's custom keybinding (its entry stays); other keybindings are untouched.
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
APP_ID="io.avada.ScreenCapture"
TRIGGER="gdbus call --session --dest $APP_ID --object-path /io/avada/ScreenCapture --method org.freedesktop.Application.Activate {}"
NAME="Screen Capture"

# 1. D-Bus service: the shortcut's gdbus call starts the app if it is not running yet.
mkdir -p "$HOME/.local/share/dbus-1/services"
cat > "$HOME/.local/share/dbus-1/services/$APP_ID.service" <<SERVICE
[D-BUS Service]
Name=$APP_ID
Exec=/usr/bin/env PYTHONPATH=$PROJECT python3 -m screen_capture --background
SERVICE

# 2. Icon and app entry (app grid / dock). Right-click the entry for Settings.
mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps" "$HOME/.local/share/applications"
cp "$PROJECT/data/icons/$APP_ID.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_ID.svg"
gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
cat > "$HOME/.local/share/applications/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$NAME
Comment=Capture a monitor or region, upload, copy the link
Exec=$TRIGGER
Icon=$APP_ID
Categories=Utility;
Actions=Settings;

[Desktop Action Settings]
Name=Settings
Exec=/usr/bin/env PYTHONPATH=$PROJECT python3 -m screen_capture --settings
DESKTOP

# 3. GNOME custom keybinding (Print unless already set), taken back from Flameshot if it holds it;
#    the logic lives in screen_capture/keybinding.py, shared with the Settings window.
(cd "$PROJECT" && python3 -m screen_capture --install-shortcut)

# 4. Copy Flameshot's upload token into our config (if we have none), so Flameshot can be removed.
(cd "$PROJECT" && python3 -m screen_capture --import-flameshot)

# 5. Optional: launch on startup.
if [[ "${1:-}" == "--autostart" ]]; then
    (cd "$PROJECT" && python3 -m screen_capture --autostart on)
fi
echo "Installed. Press Print (or the shortcut set in Settings) to capture."
