# Spike results — 2026-10-30

Machine: eDP-1 1920x1080 @ (0,0) scale 1.0; HDMI-1 1920x1080 @ (1920,0) scale 1.0.
Fractional scale is not in use, so the crop maths for scale != 1 is covered by unit tests only.

## Capture latency

| Route | Latency | Notes |
|---|---|---|
| `org.freedesktop.portal.Screenshot` (non-interactive) | 513–519 ms, constant | Forced flash. Image 3840x1080 (image_scale 1.0). |
| `org.gnome.Shell.Screenshot` (flash=false) | — | `AccessDenied: Screenshot is not allowed` |
| `org.gnome.Mutter.ScreenCast` RecordMonitor | HDMI-1 ~80 ms; eDP-1 never delivers a frame | Not used |
| `org.gnome.Mutter.ScreenCast` RecordArea, both monitors in one session | 66–90 ms total | No flash, no prompt, cursor hidden. **Chosen.** |

Decision (owner approved): ScreenCast RecordArea is primary, portal is fallback.
Possible side effect: GNOME may show a screen-sharing indicator in the top bar for a moment.

## Process model

Resident `Gtk.Application` (owner request; also needed so the process can serve the clipboard).

## Overlay behaviour under Mutter

Pending: checked in Task 5 with the real overlay.
