#!/usr/bin/env bash
# Install Screen Capture for the current user. Idempotent.
#   scripts/install.sh               D-Bus service, app entry, Ctrl+Alt+S shortcut
#   scripts/install.sh --autostart   ...and launch on startup
# Never modifies other custom keybindings (Flameshot stays on Print).
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
APP_ID="io.avada.ScreenCapture"
TRIGGER="gdbus call --session --dest $APP_ID --object-path /io/avada/ScreenCapture --method org.freedesktop.Application.Activate {}"
NAME="Screen Capture"
BINDING="<Control><Alt>s"

# 1. D-Bus service: the shortcut's gdbus call starts the app if it is not running yet.
mkdir -p "$HOME/.local/share/dbus-1/services"
cat > "$HOME/.local/share/dbus-1/services/$APP_ID.service" <<SERVICE
[D-BUS Service]
Name=$APP_ID
Exec=/usr/bin/env PYTHONPATH=$PROJECT python3 -m screen_capture --background
SERVICE

# 2. App entry (shows in the app grid, also starts a capture).
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$NAME
Comment=Capture a monitor or region, upload, copy the link
Exec=$TRIGGER
Icon=camera-photo
Categories=Utility;
DESKTOP

# 3. GNOME custom keybinding: reuse our own entry if present, else the next free customN.
python3 - "$NAME" "$TRIGGER" "$BINDING" <<'PY'
import ast, subprocess, sys
name, command, binding = sys.argv[1:]
SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
ITEM = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"

def get(*args):
    return subprocess.run(["gsettings", "get", *args], check=True, capture_output=True, text=True).stdout.strip()

raw = get(SCHEMA, "custom-keybindings")
paths = [] if raw.startswith("@as") else ast.literal_eval(raw)
ours = None
for p in paths:
    # Ours = same name AND our app id in the command, so a user binding that happens to be
    # called "Screen Capture" is never taken over.
    if (ast.literal_eval(get(f"{ITEM}:{p}", "name")) == name
            and "io.avada.ScreenCapture" in ast.literal_eval(get(f"{ITEM}:{p}", "command"))):
        ours = p
if ours is None:
    n = 0
    while f"{BASE}custom{n}/" in paths:
        n += 1
    ours = f"{BASE}custom{n}/"
    paths.append(ours)
    subprocess.run(["gsettings", "set", SCHEMA, "custom-keybindings", str(paths)], check=True)
for key, value in (("name", name), ("command", command), ("binding", binding)):
    subprocess.run(["gsettings", "set", f"{ITEM}:{ours}", key, value], check=True)
print(f"shortcut {binding} -> {ours}")
PY

# 4. Optional: launch on startup.
if [[ "${1:-}" == "--autostart" ]]; then
    (cd "$PROJECT" && python3 -m screen_capture --autostart on)
fi
echo "Installed. Press Ctrl+Alt+S to capture."
