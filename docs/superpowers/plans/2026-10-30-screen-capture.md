# Screen Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A ShareX-style screenshot tool for GNOME/Wayland: one shortcut opens a frozen per-monitor overlay; click = that monitor, drag = region, optional annotations; result is auto-uploaded to capture.avada.io and the URL is copied.

**Architecture:** A resident `Gtk.Application` (unique app id, so the shortcut command just re-activates the running instance over D-Bus; this also keeps the process alive to own the clipboard). On activation it takes one portal screenshot of the whole desktop, opens one fullscreen GTK4 window per monitor showing its slice as backdrop, and draws annotations with Cairo on a per-monitor canvas. On finish it crops backdrop + annotations to PNG, uploads, copies the URL, notifies. Geometry, config, upload parsing and annotation rendering are pure modules with unit tests; the GTK/portal layer is verified by measured manual checks.

**Tech Stack:** Python 3.14, GTK 4.22 (PyGObject), pycairo 1.27, `requests` (already installed), stdlib `unittest` (pytest is NOT installed; do not add it). No new system packages (`wl-copy` is not installed either; clipboard goes through `Gdk.Clipboard`).

**Spec:** `docs/superpowers/specs/2026-10-30-screen-capture-design.md`

## Global Constraints

- Wayland only (GNOME 50, Ubuntu 26.04). No X11 code paths, no suggesting X11.
- Screen content only via `org.freedesktop.portal.Screenshot`; no layer-shell; one fullscreen window per monitor.
- Monitors: `eDP-1` (laptop), `HDMI-1` (external); scales may differ, so each monitor has its own independent canvas; shapes and regions never cross monitors; a drag leaving its start monitor is clamped.
- Upload: `POST https://capture-api.avada.io/api/v1/upload`, multipart form, image in field `image`, header `X-Avada-Token`. Success response shape is unknown until one real upload.
- Token comes from `customUploadToken` in `~/.config/flameshot/flameshot.ini` unless overridden in this tool's own config. **Never print, log, put in exceptions/tests/fixtures, or commit it.**
- Do not probe the API with repeated or malformed POSTs. One real upload of a tiny image only.
- Shortcut `Ctrl+Alt+S` is created by the install script as a new GNOME custom keybinding. Never touch Flameshot's `custom1` (`Print`) binding or the Flameshot install.
- Tool keys: `S` select, `A` arrow, `L` line, `R` rectangle, `C` circle, `P` pen, `T` text, `H` highlighter, `N` numbered step, `B` blur; `Ctrl+Z` / `Ctrl+Shift+Z` undo/redo; `Esc` cancels the whole capture.
- Overlay opens in Select mode; a tool key/button enters Draw mode (plain click does nothing there); `S`, right-click or the Select button returns to Select mode.
- Toolbar: top-center of every monitor's overlay, not part of the output (backdrop is captured before the overlay opens). Dark, rounded, lit monitor with blue outline, other monitors dimmed, no flicker.
- Failed upload keeps the PNG in a local folder and says so in the notification. No confirmation dialog between "done selecting" and "uploaded".
- Reply to the owner in Vietnamese. Owner only wants git commits when they ask, so this plan has no commit steps.
- Test command everywhere: `python3 -m unittest discover -s tests -v`.

## Review Focus

1. Mixed-scale / fractional-scale monitors: crop is pixel-correct on both (Task 1 tests, Task 2 measurement).
2. Click with a few pixels of mouse jitter must still count as a click, not a 3px region (Task 1 `is_click`).
3. Shortcut pressed again while the overlay is open or an upload is running must not stack overlays or lose the first upload (Task 5).
4. Upload failure paths (offline, 401, 5xx, unexpected JSON, timeout) save the image locally and never leak the token in any message (Task 4).
5. Portal failures (permission denied, cancelled, missing interface) end with a notification and no stuck overlay (Task 2).
6. Missing token / missing Flameshot config gives a clear "token not configured" notification, not a traceback (Task 1).

---

## File Structure

```
screen_capture/
  __init__.py
  config.py        # Config dataclass, load_config(); token redaction
  geometry.py      # Monitor, Rect, PixelRect, crop math, click-vs-drag
  portal.py        # take_screenshot(): portal D-Bus call -> image path
  annotations.py   # Shape classes with draw(cr), History (undo/redo)
  compose.py       # render_png(): backdrop crop + shapes -> PNG bytes
  upload.py        # parse_url(), upload_png(), save_failed()
  notify.py        # notify(summary, body)
  overlay.py       # OverlayWindow (one per monitor): backdrop, select/draw input, toolbar
  toolbar.py       # Toolbar widget (tools, colour, width, undo/redo)
  app.py           # CaptureApp(Gtk.Application): activation, session lifecycle
  __main__.py      # python3 -m screen_capture
tests/
  test_config.py test_geometry.py test_annotations.py test_compose.py test_upload.py
scripts/
  spike_latency.py # Task 2 throwaway measurement script
  install.sh       # Task 7
docs/superpowers/notes/  # measured numbers, upload response shape (no token)
```

---

### Task 1: Config and geometry (pure logic)

**Files:**
- Create: `screen_capture/__init__.py`, `screen_capture/config.py`, `screen_capture/geometry.py`
- Test: `tests/test_config.py`, `tests/test_geometry.py`

**Interfaces:**
- Produces:
  - `Config` dataclass: `token: str`, `upload_url: str`, `save_dir: Path`, with `__repr__`/`__str__` that redact `token`.
  - `load_config(own_path: Path = ~/.config/screen-capture/config.ini, flameshot_path: Path = ~/.config/flameshot/flameshot.ini) -> Config`; raises `ConfigError` (message never contains the token) when no token is found. Own config key `token` overrides Flameshot's `customUploadToken`. Default `save_dir` = `~/Pictures/screen-capture-failed`.
  - `Rect(x, y, w, h)` (floats, logical px), `PixelRect(x, y, w, h)` (ints, image px), `Monitor(name, x, y, width, height, scale)` (logical geometry in the global desktop space).
  - `monitor_at(monitors: list[Monitor], px: float, py: float) -> Monitor`
  - `clamp_to_monitor(monitor: Monitor, r: Rect) -> Rect`
  - `crop_rect(monitor: Monitor, sel: Rect, image_scale: float) -> PixelRect` where `sel` is monitor-local logical coords and `image_scale` = portal image pixels per logical pixel (measured in Task 2, not assumed equal to `monitor.scale`).
  - `is_click(press: tuple[float,float], release: tuple[float,float], threshold: float = 5.0) -> bool`

- [ ] **Step 1: Write failing tests.** `test_config.py`: `test_flameshot_token_loaded`, `test_own_config_overrides`, `test_missing_token_raises_configerror_without_leaking` (assert a sentinel token string `"SENTINEL-TOKEN-123"` written to a temp ini never appears in `repr(cfg)`, `str(cfg)`, or any `ConfigError` message). `test_geometry.py`: `test_monitor_at_picks_right_monitor` (eDP-1 at 0,0 1920x1080 scale 1; HDMI-1 at 1920,0 2560x1440 scale 1.5), `test_clamp_to_monitor_clips_drag_leaving_monitor`, `test_crop_rect_fractional_scale` (sel `Rect(10,20,100,50)` on scale 1.5 -> `PixelRect(15,30,150,75)`), `test_crop_rect_offset_monitor` (monitor at x=1920 adds `1920*image_scale` to x), `test_crop_rect_rounds_to_whole_pixels_and_never_zero_size`, `test_is_click_within_threshold_true` (3px jitter), `test_is_click_beyond_threshold_false`.
- [ ] **Step 2: Run** `python3 -m unittest discover -s tests -v` — Expected: FAIL (modules missing).
- [ ] **Step 3: Implement** `config.py` (stdlib `configparser`; Flameshot ini is a `[General]` section, read with `interpolation=None`) and `geometry.py` per the signatures above. `crop_rect` uses `round()` on edges (round left/top and right/bottom separately, then subtract) so adjacent regions don't gain/lose a pixel; minimum size 1x1.
- [ ] **Step 4: Run tests** — Expected: all PASS.

---

### Task 2: Spike — portal latency and per-monitor overlay (measure before building on it)

This task decides the open items in the spec. Its output is numbers and a decision, not product code. Per spec: if latency is unacceptable, report and propose alternatives; do not drop the frozen backdrop silently.

**Files:**
- Create: `screen_capture/portal.py`, `scripts/spike_latency.py`, `docs/superpowers/notes/2026-10-30-spike-results.md`

**Interfaces:**
- Produces: `take_screenshot(timeout_s: float = 5.0) -> Path` (blocking; calls `org.freedesktop.portal.Screenshot.Screenshot` with `interactive=False` through `Gio.DBusProxy`, waits for the `org.freedesktop.portal.Request.Response` signal on the request path, converts the returned `file://` URI to a `Path`); raises `ScreenshotError(reason)` on response code != 0 (1 = cancelled, 2 = other) or timeout or missing interface.

- [ ] **Step 1: Implement `portal.py`** per the signature. Derive the Request object path from the unique bus name + `handle_token` and subscribe before calling, to avoid the response race.
- [ ] **Step 2: Write `scripts/spike_latency.py`**: (a) call `take_screenshot()` 10 times, print min/median/max wall time, and whether a visible flash/sound/prompt occurred (owner observes); (b) print each `Gdk.Monitor` from `Gdk.Display.get_default().get_monitors()` — connector, geometry, `get_scale()`; (c) print portal image pixel size and compute `image_scale = image_width / desktop_logical_width` (this is the value Task 1's `crop_rect` consumes); (d) open one fullscreen `Gtk.Window` per monitor with `fullscreen_on_monitor`, show the backdrop slice, and report: does each window get keyboard focus (`Esc` closes all), does the cursor shape change work (`set_cursor_from_name("crosshair")`), does pointer position map to the right monitor, any flicker on open.
- [ ] **Step 3: Run** `python3 scripts/spike_latency.py` on the real session; the owner needs to be at the machine for the flash/prompt/flicker observations. If the portal reports `No such interface org.freedesktop.portal.Screenshot`, restart `xdg-desktop-portal` and `xdg-desktop-portal-gnome` user services and retry.
- [ ] **Step 4: Record results** in `docs/superpowers/notes/2026-10-30-spike-results.md`: latency numbers, `image_scale`, per-monitor scales, focus/cursor findings, flash/prompt behaviour. State the decision on resident vs single-shot process (resident is the plan's default; the clipboard ownership argument in Task 5 favours it regardless).
- [ ] **Step 5: Gate.** If median latency is visibly laggy (more than roughly 300 ms to overlay) or a prompt repeats, stop and report to the owner with alternatives before continuing.

---

### Task 3: Annotations and composition (pure Cairo, no GTK)

**Files:**
- Create: `screen_capture/annotations.py`, `screen_capture/compose.py`
- Test: `tests/test_annotations.py`, `tests/test_compose.py`

**Interfaces:**
- Consumes: `PixelRect`, `Rect` from Task 1.
- Produces:
  - `Style(color: tuple[float,float,float,float], width: float)`.
  - Shape classes, each with `draw(self, cr: cairo.Context) -> None` in monitor-local logical coordinates: `Arrow(p0, p1, style)`, `Line(p0, p1, style)`, `Rectangle(rect, style)`, `Ellipse(rect, style)`, `Pen(points, style)`, `Highlighter(points, style)` (translucent, wide, `OPERATOR_MULTIPLY`-like look via alpha), `Text(pos, text, style)`, `Step(center, number, style)`, `Blur(rect, block=10)` (pixelate: needs the backdrop, so `draw(cr, backdrop=None)` — all shapes accept an optional `backdrop: cairo.ImageSurface` kwarg and ignore it unless Blur).
  - `History`: `add(shape)`, `undo()`, `redo()`, `shapes -> list`, `next_step_number() -> int`; adding after an undo clears the redo stack.
  - `render_png(backdrop: cairo.ImageSurface, sel: Rect, image_scale: float, shapes: list) -> bytes` — crops the backdrop slice and draws shapes translated by `-sel.x,-sel.y` and scaled by `image_scale`; returns PNG bytes.

- [ ] **Step 1: Write failing tests.** `test_annotations.py`: `test_history_undo_redo_roundtrip`, `test_add_after_undo_clears_redo`, `test_next_step_number_follows_visible_steps` (undo of step 2 makes the next number 2 again). `test_compose.py`: `test_render_png_size_matches_selection_times_scale` (decode PNG with `cairo.ImageSurface.create_from_png` on a `BytesIO`, check size), `test_rectangle_annotation_changes_pixels_inside_crop` (solid white backdrop, red Rectangle outline: a pixel on the outline is red in output), `test_annotation_outside_selection_not_in_output`, `test_blur_pixelates_region` (backdrop with a vertical black/white stripe pattern: after Blur the stripe pixels inside the region equal their block's average).
- [ ] **Step 2: Run** the suite — Expected: FAIL.
- [ ] **Step 3: Implement** the shapes and `render_png`. Arrow head is a filled triangle sized from `style.width`. Text uses Cairo toy text API (`select_font_face`) — no Pango dependency in the pure layer.
- [ ] **Step 4: Run** the suite — Expected: PASS.

---

### Task 4: Upload, failure save, notification

**Files:**
- Create: `screen_capture/upload.py`, `screen_capture/notify.py`
- Test: `tests/test_upload.py`
- Create after the real upload: `docs/superpowers/notes/upload-response-shape.md`

**Interfaces:**
- Consumes: `Config` from Task 1.
- Produces:
  - `UploadError(Exception)` — message is human-readable and never contains the token.
  - `parse_url(body: object) -> str` — extracts the URL from the decoded JSON; raises `UploadError` on unexpected shape. **Its body is written only after Step 3.**
  - `upload_png(png: bytes, cfg: Config, session: requests.Session | None = None, timeout: float = 20.0) -> str` — multipart `image` field, `X-Avada-Token` header, returns URL; wraps `requests` exceptions and non-2xx into `UploadError` (401 -> "token rejected", 5xx -> "server error", timeout/connection -> "network error").
  - `save_failed(png: bytes, cfg: Config) -> Path` — writes `capture-YYYYmmdd-HHMMSS.png` into `cfg.save_dir` (creates it), returns the path.
  - `notify(summary: str, body: str = "") -> None` — `Gio.Notification` is unreliable for a resident app without a `.desktop` match, so shell out to `notify-send` (installed) with `subprocess.run([...])` list args, never `shell=True`; never raises.

- [ ] **Step 1: Write failing tests** with an injected fake session (no network): `test_upload_sends_image_field_and_token_header` (fake records the call; assert field name `image`, header key `X-Avada-Token`, URL `https://capture-api.avada.io/api/v1/upload`), `test_401_raises_uploaderror_without_token_in_message` (sentinel token), `test_timeout_raises_network_error`, `test_save_failed_writes_png_file`, `test_parse_url_unexpected_shape_raises`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: One real upload.** With the owner's go-ahead (it uses their token), upload a 1x1 PNG once via a one-off snippet that prints only the HTTP status and the response JSON with any token-like value masked. Record the shape in `docs/superpowers/notes/upload-response-shape.md`. Do not repeat the request.
- [ ] **Step 4: Implement** `upload.py`, `notify.py`; write `parse_url` for the recorded shape and add `test_parse_url_real_shape` using that shape (with a fake URL).
- [ ] **Step 5: Run** the suite — Expected: PASS.

---

### Task 5: Resident app, overlay and Select mode (end-to-end without annotations)

**Files:**
- Create: `screen_capture/app.py`, `screen_capture/overlay.py`, `screen_capture/__main__.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - `CaptureApp(Gtk.Application)` with id `io.avada.ScreenCapture`, `flags=Gio.ApplicationFlags.DEFAULT_FLAGS`. First `activate` calls `hold()` so it stays resident; every activation calls `start_session()`. `start_session()` is a no-op (or just re-presents windows) if a session is already open — never stacks overlays — and uses a busy flag so a second activation during an upload still works for a new capture while the first upload finishes on a worker thread.
  - `OverlayWindow(Gtk.Window)`: `__init__(app, monitor: Monitor, backdrop: cairo.ImageSurface)`; signals/callbacks `on_done(monitor, sel: Rect)` and `on_cancel()`. Handles Select mode only here: pointer motion lights the monitor under the pointer (blue outline, others dimmed), press/release decides via `is_click` (click -> whole monitor `Rect(0,0,w,h)`), drag draws the selection rectangle clamped to the start monitor, `Esc` cancels all overlays, crosshair cursor.
  - On done: build PNG via `render_png`, close all overlays first (so the screen is usable immediately), then on a worker thread `upload_png` -> `GLib.idle_add` back to the main thread -> `Gdk.Clipboard.set(url)` and `notify("Link copied", url)`; on `UploadError`/`ScreenshotError`/`ConfigError`: `save_failed` when there is a PNG, then `notify` with the reason and path.

- [ ] **Step 1: Implement** `app.py`, `overlay.py`, `__main__.py` (run with `python3 -m screen_capture`; a second invocation just activates the first via D-Bus). Backdrop slice per monitor comes from `crop_rect(monitor, Rect(0,0,w,h), image_scale)`; display it scaled to the monitor's logical size.
- [ ] **Step 2: Manual verification** (owner present), each with a pass/fail line in `docs/superpowers/notes/2026-10-30-spike-results.md`:
  - Run once, trigger twice quickly: only one set of overlays.
  - Click on `HDMI-1` -> uploaded image is exactly that monitor's size and nothing from `eDP-1`; repeat on `eDP-1`.
  - Drag a region on each monitor; drag leaving the monitor stays clamped.
  - Click with slight jitter -> full monitor, not a tiny region.
  - Link is in the clipboard after the overlay is gone and paste works in Chrome while the app is still running.
  - Disconnect network -> notification says the upload failed and the PNG path; file exists.
  - Temporarily rename the Flameshot ini -> notification "token not configured", no traceback.
- [ ] **Step 3: Run** the unit suite — Expected: still PASS.

---

### Task 6: Toolbar, Draw mode and shape tools

**Files:**
- Create: `screen_capture/toolbar.py`
- Modify: `screen_capture/overlay.py`

**Interfaces:**
- Consumes: shapes/`History` (Task 3), `OverlayWindow` (Task 5).
- Produces: `Toolbar(Gtk.Box)` with signal-style callbacks `on_tool(tool_id: str)`, `on_color(rgba)`, `on_width(float)`, `on_undo()`, `on_redo()`; tool ids: `select, arrow, line, rect, ellipse, pen, text, highlighter, step, blur`. One `History` per `OverlayWindow`. Key map exactly as in Global Constraints; right-click returns to Select mode.

- [ ] **Step 1: Implement the toolbar** (dark, rounded via CSS provider, top-center, same on every monitor; the active tool is highlighted) and Draw mode in `OverlayWindow`: in Draw mode a drag creates the tool's shape in monitor-local logical coordinates, live preview during the drag, a plain click does nothing, shapes are clamped to the monitor. Order: arrow, line, rectangle, ellipse, then colour/width, undo/redo; then pen, highlighter, text (inline `Gtk.Entry` committed on `Enter`), step markers (click places, number from `History.next_step_number()`), blur.
- [ ] **Step 2: Wire annotations into the output.** On done, pass `history.shapes` to `render_png`. Annotations drawn before the region is selected must be in the result when the region contains them.
- [ ] **Step 3: Manual verification** (owner present): draw an arrow, then select a region containing it -> arrow visible in the uploaded image; draw, `Ctrl+Z`, `Ctrl+Shift+Z`; each tool key switches tool; `S` and right-click return to Select; toolbar is absent from the uploaded image; blur hides text in a test window; no flicker when switching tools.
- [ ] **Step 4: Run** the unit suite — Expected: PASS.

---

### Task 7: Install script and shortcut

**Files:**
- Create: `scripts/install.sh`, `data/io.avada.ScreenCapture.desktop`

**Interfaces:**
- Produces: `screen_capture/autostart.py` with `set_autostart(enabled: bool, autostart_dir: Path = ~/.config/autostart) -> Path | None` (writes/removes `io.avada.ScreenCapture.desktop` with `Exec=python3 -m screen_capture --background` and `WorkingDirectory` = project dir; idempotent) and `is_autostart_enabled(autostart_dir) -> bool`; CLI flags `python3 -m screen_capture --autostart on|off|status` and `--background` (start resident without opening an overlay). Launch on startup is an **option**: `install.sh` does not enable it unless run with `--autostart` (owner request, 2026-10-30; tests in `tests/test_autostart.py` use a temp dir).
- Produces: `scripts/install.sh` that is idempotent and: installs the `.desktop` file to `~/.local/share/applications/`, optionally enables autostart via `--autostart`, and adds a GNOME custom keybinding named "Screen Capture" with command `python3 -m screen_capture` (run from this project directory) bound to `<Control><Alt>s`, using the next free `customN` path in `org.gnome.settings-daemon.plugins.media-keys custom-keybindings`. It must read the existing list and append, and must not modify any existing entry (especially `custom1`, Flameshot on `Print`).

- [ ] **Step 1: Write `install.sh`** and run it with `bash -n scripts/install.sh` first (syntax check).
- [ ] **Step 2: Run it** and verify: `gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings` lists `custom1` plus the new entry; `custom1` still reports binding `Print` and command `/usr/bin/flameshot gui`; running the script a second time adds nothing.
- [ ] **Step 3: End-to-end**: press `Ctrl+Alt+S` with the app not running (cold start time noted) and while running (warm); both give the overlay. `Print` still opens Flameshot.

---

## Self-review notes

- Spec coverage: instant overlay / dim+outline / click / drag / draw-first / toolbar / Esc / upload+clipboard+notification / look (Tasks 5–6); tools list (Tasks 3, 6); failure keeps image (Task 4–5); latency, response shape and Mutter focus open items (Tasks 2, 4); shortcut and Flameshot untouched (Task 7); token handling (Tasks 1, 4).
- `image_scale` is produced by Task 2 and consumed by `crop_rect` (Task 1) and `render_png` (Task 3); the same name is used throughout.
- Known risk: `Gdk.Clipboard` content is only served while the process lives; the resident design covers it, and Task 5 verifies it.
