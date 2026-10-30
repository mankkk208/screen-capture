# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

ShareX-style screenshot tool for the owner's Ubuntu 26.04 / GNOME 50 **Wayland-only** machine (monitors `eDP-1`, `HDMI-1`). `Print` (default, changeable in Settings; GNOME's own screenshot UI is unbound from Print by `--install-shortcut`) → frozen overlay on every monitor → click = that monitor, drag = region, annotate → upload to capture.avada.io and copy the link. Python 3.14 + GTK 4.22 (PyGObject) + pycairo; system packages only (`python3-gi-cairo` is required). The owner talks Vietnamese and wants commits only when asked.

Spec: `docs/superpowers/specs/2026-10-30-screen-capture-design.md` (goals, anti-goals). Measured facts: `docs/superpowers/notes/`.

## Commands

```bash
python3 -m unittest discover -s tests -v              # all tests (pytest is NOT installed)
python3 -m unittest tests.test_geometry.GeometryTest.test_is_click_within_threshold_true   # one test
scripts/install.sh [--autostart]                       # D-Bus service, app entry, Print keybinding
python3 -m screen_capture --background                 # start the resident app without capturing
python3 -m screen_capture --quit                       # stop it (needed after code changes: it is long-lived)
SC_DEBUG=1 python3 -m screen_capture --background      # timing logs on stderr
python3 -m screen_capture --settings                   # open the Settings window
python3 -m screen_capture --install-shortcut           # create/repair our keybinding (used by install.sh)
python3 -m screen_capture --autostart on|off|status    # launch on login (optional, off by default)
gdbus call --session --dest io.avada.ScreenCapture --object-path /io/avada/ScreenCapture \
  --method org.freedesktop.Application.Activate {}     # what the shortcut runs: open a capture
```

After editing code, restart the resident app (`--quit`, then `setsid python3 -m screen_capture --background`) or the shortcut keeps running the old code. To check UI without a human, open a capture with the gdbus call above and screenshot it with `screen_capture.capture.capture_backdrops(...)` from another process.

## Architecture

**Process model.** `app.CaptureApp` is a resident `Gtk.Application` (`io.avada.ScreenCapture`, `HANDLES_COMMAND_LINE`). It must stay alive: on Wayland the clipboard is served by the owning process. The shortcut calls `org.freedesktop.Application.Activate` over D-Bus (~7 ms); `install.sh` adds a D-Bus `.service` so that call auto-starts the app. Capture runs a nested GLib main loop that can dispatch another Activate, hence the `_capturing` re-entry guard and callbacks bound to their own session.

**Capture** (`capture.py`). Primary: `screencast.py` — one `org.gnome.Mutter.ScreenCast` session, one `RecordArea` stream per monitor, one PipeWire frame each via GStreamer `appsink` (BGRx → cairo surface), ~70–130 ms, no flash. Fallback: `portal.py` (`org.freedesktop.portal.Screenshot`, always flashes, ~515 ms) cropped per monitor. `org.gnome.Shell.Screenshot` is AccessDenied; `RecordMonitor("eDP-1")` never yields a frame — don't switch to them. Backdrops are **per monitor**; `image_scale = backdrop_width / monitor.width` per monitor; all overlay/annotation coordinates are monitor-local logical px (`geometry.crop_rect` maps to image px).

**Overlay** (`overlay.py`). `CaptureSession` holds shared state (tool, style, active monitor, one `History` per monitor) and owns one fullscreen `OverlayWindow` per monitor. Each window = `Gtk.Picture` (backdrop texture) + `DrawingArea` (shapes, scrim, dashed outline, selection) + `Toolbar` + hint bar. Shapes and selections never cross monitors. Select mode: single click waits `gtk-double-click-time` (double-click = copy without upload); right-click while left-dragging = copy region (read via `EventControllerLegacy`, because a button-3 gesture doesn't fire during the drag). `annotations.py`/`compose.py` are pure Cairo and render the same shapes into the final image.

**Output.** Upload: `pipeline.deliver` on a worker thread (render → `upload.upload_png` → on any failure `save_failed`, with a `$XDG_RUNTIME_DIR` fallback) → back on the main thread via `GLib.idle_add`. Clipboard can only be set while one of our windows has focus, so the link is copied by a small focused `toast.py` window (or directly if an overlay is open). Image copy sets the clipboard while the overlay still has focus, using `overlay.image_clipboard_content` (must be typed `Gdk.Texture`; a raw `GdkMemoryTexture` provider offers no image formats).

**Tray and Settings.** `tray.py` speaks StatusNotifierItem + `com.canonical.dbusmenu` directly over Gio D-Bus (GNOME shows it via the `ubuntu-appindicators` extension; libappindicator is GTK3 and can't be loaded in this GTK4 process). The menu model and its D-Bus layout live in `tray_menu.py` (pure, tested); `app._tray_items` builds it and `tray.refresh()` emits `LayoutUpdated`. Recent links (`recent.py`) are per session only. `settings_window.py` is libadwaita (`Adw.init()` on first open; overlay CSS still wins at USER+100); nothing applies until Save. `keybinding.py` is the only code that edits GNOME keybindings (install.sh calls `--install-shortcut`): it finds our entry by name **and** app id, and checks conflicts against custom bindings and the wm/shell/media-keys/mutter schemas. To test the tray without clicking, act as the host: call `GetLayout`/`Event` on `/MenuBar` of the `org.kde.StatusNotifierItem-<pid>-1` name.

**Config / token.** `config.load_config` reads `token` from `~/.config/screen-capture/config.ini` (written 0600 by `settings_store.save_settings`), else `customUploadToken` from `~/.config/flameshot/flameshot.ini`. The token is never in the repo; `Config.__repr__` redacts it, and error messages are fixed strings (never `str(exc)` from requests). Uploads use `allow_redirects=False` so `X-Avada-Token` can't leak to another host. Don't make repeated or malformed POSTs to the real API.

## Gotchas

- Wayland only: no X11 paths, no layer-shell, no app-registered global shortcuts (GNOME custom keybinding instead). `install.sh` and the Settings window must never touch other keybindings (Flameshot was uninstalled on 2026-10-30; its token now lives in our config.ini, the Flameshot fallback stays for other machines).
- App CSS is registered at `STYLE_PROVIDER_PRIORITY_USER + 100`: the WhiteSur theme's `~/.config/gtk-4.0/gtk.css` (USER priority) otherwise restyles the overlay.
- PyGObject: call `gi.require_foreign("cairo")` before using cairo in GTK draw funcs; `EventControllerLegacy`'s `event` argument arrives as `None` — use `controller.get_current_event()`; `Gdk.Clipboard` has no `set_texture`.
- Toolbar icons are vendored Lucide SVGs in `screen_capture/icons/` (ISC), recoloured by `icons.icon_svg`.
- `scripts/spike_*.py` are throwaway measurement scripts, not part of the app.
- README images: regenerate with `python3 scripts/readme_shots.py` (real UI over a synthetic backdrop; it refuses to write an overlay shot unless sampled pixels match the fake backdrop, because a capture taken before the fullscreen overlay maps contains the real screen). Never put real screen captures in `docs/images/`.
