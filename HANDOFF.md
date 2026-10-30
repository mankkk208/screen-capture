# Handoff — screen-capture

Written 2026-10-30 from a session started in `/home/avada/chatty-agent`. Continue here.

## What this project is

A ShareX-style screenshot tool for the owner's Ubuntu 26.04 / GNOME 50 / **Wayland**
machine, replacing Flameshot on `Ctrl+Alt+S`. One shortcut opens a frozen overlay on
every monitor; click = capture the monitor under the mouse; drag = region; draw
annotations first or after picking a tool; on finish it auto-uploads to
capture.avada.io and copies the URL. Nothing is built yet — no code exists.

**Read first:** `docs/superpowers/specs/2026-10-30-screen-capture-design.md`
(goals, non-goals, anti-goals, interaction model, owner decisions vs. designer calls,
open items to verify).

## State of the process

- Brainstorming is done; the design doc was written and passed a builder check.
- The owner decided: `Ctrl+Alt+S` → this tool, Flameshot → `Print`.
- **The owner has NOT yet explicitly approved the design doc.** Ask for that, then
  invoke `superpowers:writing-plans` (next step), then build. Do not write product
  code before approval.
- The design doc is **not committed** (the owner only wants commits when they ask).
- The owner wants the UI "a bit prettier" than the rough mockup (dark, rounded
  toolbar at top-center, lit monitor with blue outline, dimmed other monitors,
  smooth, no flicker).
- The owner talks Vietnamese; reply in Vietnamese.

## Facts established (verified in this session)

- Wayland only. No `/usr/share/xsessions`, no X11 option on GNOME 50. Do not suggest
  switching to X11 (an XFCE install was tried and removed; it polluted GNOME theme
  settings and the portal config).
- Monitors: `eDP-1` (laptop) and `HDMI-1`.
- Python 3.14.4, GTK 4.22, pycairo 1.27 are installed system-wide.
- Upload: `POST https://capture-api.avada.io/api/v1/upload`, multipart form, image in
  field **`image`**, header **`X-Avada-Token`**. Without the token the server returns
  `401 {"error":"Missing access token"}`. The **success response shape is unknown** —
  verify with one real upload of a tiny image (do not spam the API).
- Token location: `customUploadToken` in `~/.config/flameshot/flameshot.ini`. Never
  print, log or commit it.
- Flameshot v14.0.0 (build e9238e30) is installed and stays as fallback. Its config
  has `captureActiveMonitor=false` (the `true` value is unsupported on Wayland and
  made every capture abort). Flameshot works through
  `org.freedesktop.portal.Screenshot`, so the portal route is proven to exist.
- If Flameshot/portal says "No such interface org.freedesktop.portal.Screenshot",
  restart `xdg-desktop-portal` and `xdg-desktop-portal-gnome` (user services); the
  portal had cached a non-GNOME desktop config.

## Machine changes made today (so you don't undo or repeat them)

- GNOME custom keybinding `custom1` ("Flameshot", `/usr/bin/flameshot gui`) is now
  bound to **`Print`**. GNOME's `org.gnome.shell.keybindings show-screenshot-ui` was
  cleared (`[]`) to avoid a conflict. `Ctrl+Alt+S` is currently unbound, waiting for
  this tool.
- GNOME theme was restored to WhiteSur: gtk-theme `WhiteSur-Dark`, icon-theme
  `WhiteSur-dark`, cursor-theme `WhiteSur-cursors`, color-scheme `prefer-dark`.
- Flameshot config backup: `~/.config/flameshot/flameshot.ini.bak`.
- The owner's Chrome may still need `chrome://restart` to pick up the theme.

## Next steps

1. Ask the owner to approve the design doc (or request changes).
2. `superpowers:writing-plans` → implementation plan in `docs/superpowers/plans/`.
3. First thing to build and measure: portal screenshot latency + per-monitor fullscreen
   GTK4 overlay under Mutter (focus, keyboard grab for single-key tool shortcuts and
   `Esc`, cursor shape, HiDPI/fractional scale crops). Report numbers; if latency is
   bad, propose alternatives rather than dropping the frozen backdrop.
4. Then upload + clipboard + notification, then tools in the order from the design doc.
5. Install script: create a GNOME custom keybinding for `Ctrl+Alt+S`; never touch the
   Flameshot `Print` binding.

## Pitfalls

- Don't probe the upload API with repeated or malformed POSTs.
- Keep the token out of logs, errors, tests and git.
- Wayland: no global shortcut registration by the app, no layer-shell on GNOME, no
  direct screen grab; use the portal and GNOME custom keybindings.
