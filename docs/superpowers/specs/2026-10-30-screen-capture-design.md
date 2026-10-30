# Screen Capture — Design

Date: 2026-10-30
Status: draft, awaiting owner approval

## Intent and why

The owner (a support engineer who takes many screenshots per day for tickets and
bug reports) currently uses Flameshot (an Avada build that uploads to
capture.avada.io). On this machine (Ubuntu 26.04, GNOME 50, **Wayland only**, no X11
session available) Flameshot is painful:

- It cannot pick the active monitor on Wayland (`captureActiveMonitor` is
  unsupported there), so the owner has to select a region manually every time.
- The flow is not as fast as ShareX on Windows.

Goal: a ShareX-smooth capture tool for this machine. One shortcut, a frozen
overlay appears immediately, one click captures the monitor under the mouse,
drag captures a region, and the result is uploaded and its URL copied to the
clipboard without any confirmation step.

Success = the owner can go from pressing the shortcut to having an uploaded link
in the clipboard in about one second of their own action, on either of two
monitors, without thinking about it.

## Environment (facts)

- Ubuntu 26.04.1, GNOME Shell 50.1 on Wayland. No `/usr/share/xsessions`; X11 is
  not an option.
- Two monitors: `eDP-1` (laptop) and `HDMI-1` (external).
- Python 3.14, GTK 4.22 and pycairo 1.27 are already installed system-wide.
- Upload endpoint: `POST https://capture-api.avada.io/api/v1/upload`,
  multipart form with the image in field **`image`**, auth header
  **`X-Avada-Token: <token>`** (taken from the Flameshot binary's strings and a
  live unauthenticated probe returning `401 {"error":"Missing access token"}`).
  The success response format (where the URL lives in the JSON) is **not yet
  known** and must be verified with one real upload during build.
- The owner already has a valid token in `~/.config/flameshot/flameshot.ini`
  (`customUploadToken`). Never print, log or commit it.
- The existing Flameshot GNOME custom shortcut is `Ctrl+Alt+S` →
  `/usr/bin/flameshot gui`. The new tool will take over a shortcut (owner's
  choice which; `Print` is currently bound to GNOME's own screenshot UI).

## Goals

1. **Instant overlay.** Shortcut → overlay on every monitor with the screen
   frozen (screenshot as backdrop). Dim all monitors; the monitor under the mouse
   is lit and outlined.
2. **Click = capture that monitor only.** A plain click (no drag) captures only the
   monitor the mouse is on, never both.
3. **Drag = region.** Press and hold, then drag, to select a region; release
   completes the capture.
4. **Annotate before selecting.** The owner can pick a tool, draw on the frozen
   screen first, then select the region that contains the drawing. Annotations
   are baked into the output image.
5. **Toolbar at the top** of the screen with single-key tool shortcuts
   (e.g. `A` arrow). `Esc` cancels.
6. **Auto upload + clipboard.** On completion the image (PNG, annotations
   included) is uploaded and the returned URL is copied to the clipboard. A small
   notification confirms ("Link copied") or reports failure.
7. **Looks good.** Clean, modern, dark, rounded toolbar; smooth, no flicker. The
   owner asked for "a bit prettier than the mockup".

### Tools

Required: arrow, line, rectangle, circle/ellipse.

Added by the designer (owner said "add what's useful, or not"): freehand pen,
text, highlighter, **numbered step markers** (1, 2, 3 for bug reports),
**blur/pixelate** (hide customer data), undo/redo (`Ctrl+Z` / `Ctrl+Shift+Z`),
colour and stroke-width choice.

Default tool-key map (designer's call, can change): `S` select, `A` arrow,
`L` line, `R` rectangle, `C` circle, `P` pen, `T` text, `H` highlighter,
`N` numbered step, `B` blur.

### Interaction model (designer's calls, added after the builder check)

- The overlay opens in **Select mode**. In Select mode: plain click = capture the
  monitor under the pointer; press-and-drag = region; release = done.
- Pressing a tool key or clicking a tool switches to **Draw mode**. In Draw mode a
  drag draws a shape and a plain click does nothing. The tool stays active until
  the owner returns to Select mode with `S`, a right-click, or the toolbar's Select
  button. `Esc` always cancels the whole capture.
- Each monitor has its **own independent canvas**. A region or a shape cannot cross
  monitors, because monitors can have different scales. A drag that leaves its
  starting monitor is clamped to that monitor.
- The toolbar appears at the top-center of **every** monitor's overlay. It is not
  part of the output: the backdrop is captured before the overlay opens.
- The final image is the backdrop crop plus the owner's annotations.
- A failed upload keeps the image (saved to a local folder) and reports the
  failure in the notification instead of silently losing it.

### Scope and order (designer's call)

All tools in the list above are in scope. Build order: overlay + capture + upload
first, then arrow/line/rectangle/circle with undo and colour, then pen, text,
highlighter, numbered markers, blur.

### Latency (designer's call)

The frozen backdrop is the priority. First build the portal approach and measure
it. A shutter flash or one-time permission prompt is acceptable; repeated lag or a
repeated prompt is not. If the measured latency is unacceptable the builder
reports it and proposes an alternative rather than silently dropping the frozen
backdrop.

## Non-goals

- No image editor after capture, no history browser, no settings GUI at first
  (a small config file is fine).
- No video/GIF recording.
- No X11 support, no other OS.
- No support for uploading anywhere except the Avada capture API.
- No packaging beyond a simple install script / `.desktop` + shortcut setup.

## Anti-goals (would make this a failure even if it technically works)

- Capturing both monitors when the owner clicked on one.
- Any confirmation dialog or extra click between "done selecting" and "uploaded".
- Visible lag/flicker between the shortcut and the overlay appearing.
- Leaking the token (logs, git, error messages, screenshots).
- Annotations missing from the uploaded image.

## Constraints

- Wayland: apps cannot grab the screen directly. Screen content must come from
  the XDG desktop portal (`org.freedesktop.portal.Screenshot`) or an equivalent
  allowed mechanism. GNOME's own `org.gnome.Shell.Screenshot` D-Bus API is
  restricted to privileged callers.
- Wayland: global shortcuts are registered through GNOME custom keybindings
  (gsettings), not by the app itself.
- Wayland: no layer-shell on GNOME, so the overlay is one fullscreen window per
  monitor.
- Must not touch the Flameshot install; the owner may keep it as fallback.

## Decisions the owner made

- Flow exactly as described in the mockup (accepted: "giống rồi đấy").
- Click captures monitor under cursor; hold + drag selects region.
- Draw before selecting is required.
- Auto upload and copy URL, no confirmation.
- The project lives at `/home/avada/orca/projects/screen-capture`.

## Designer's calls (owner has not confirmed)

- Python + GTK4 + Cairo (already installed, no new dependencies).
- Capture via the XDG portal, then crop per monitor from the full-desktop image.
- Extra tools listed above and their key letters.
- Reuse the token from the Flameshot config instead of a new token; expose an
  override in this tool's own config.
- Possible first-use permission prompt from GNOME for screenshots.
- **Shortcut (owner decided):** the new tool takes `Ctrl+Alt+S`, replacing
  Flameshot there. Flameshot has been moved to `Print` (GNOME's own `Print`
  screenshot binding was cleared) and stays installed as a fallback. Until the new
  tool exists, `Ctrl+Alt+S` is unbound. The install script creates a GNOME custom
  keybinding for `Ctrl+Alt+S` and must not touch the Flameshot `Print` binding.

## Left to the builder

- Process model: single-shot process per shortcut press vs. a resident daemon for
  lower latency (choose whatever meets the "no visible lag" goal; measure it).
- Exact visual design, icons, animation, toolbar layout details.
- How to detect which monitor the pointer is on and each monitor's geometry/scale
  (HiDPI/fractional scaling) so crops are pixel-correct.
- The upload response format, error handling, retry policy, notification
  mechanism.
- Code structure, tests, install script.

## Open items to verify during build

1. Does the portal screenshot approach give an acceptable latency, and does it
   produce visible UI feedback (flash/sound/prompt) every time?
2. Upload response JSON shape (one real upload of a small test image is
   acceptable; do not spam the API).
3. Behaviour of fullscreen windows per monitor under Mutter (focus, keyboard
   grab, cursor shape) so single-key tool shortcuts and `Esc` always work.
