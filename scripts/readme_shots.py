#!/usr/bin/env python3
"""Regenerate the README screenshots in docs/images/ with the real UI on a synthetic backdrop.

No real screen content is ever captured into the images: the overlay shows a mock "support ticket"
window drawn here, and the Settings window uses a fake token and fake keybinding store.
Usage: python3 scripts/readme_shots.py   (the overlay appears on screen for a few seconds)
"""
import math
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gi  # noqa: E402

gi.require_foreign("cairo")
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Graphene, Gtk, Pango, PangoCairo  # noqa: E402

import cairo  # noqa: E402

from screen_capture.annotations import Arrow, Blur, Rectangle, Step, Style, Text  # noqa: E402
from screen_capture.capture import capture_backdrops  # noqa: E402
from screen_capture.geometry import Monitor, Rect  # noqa: E402
from screen_capture.overlay import CaptureSession  # noqa: E402
from screen_capture.toolbar import CSS, RED  # noqa: E402

OUT = ROOT / "docs" / "images"
FONT = "Ubuntu Sans"


# ---- synthetic backdrop ------------------------------------------------------------------

def _rr(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _text(cr, x, y, text, size, rgb, weight="Regular"):
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription.from_string(f"{FONT} {weight} {size}"))
    layout.set_text(text, -1)
    cr.set_source_rgb(*rgb)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)


def demo_backdrop(w: int, h: int) -> cairo.ImageSurface:
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    cr = cairo.Context(s)
    g = cairo.LinearGradient(0, 0, w, h)
    g.add_color_stop_rgb(0, 0.12, 0.16, 0.32)
    g.add_color_stop_rgb(1, 0.30, 0.18, 0.42)
    cr.set_source(g)
    cr.paint()
    # top bar
    cr.set_source_rgb(0.05, 0.05, 0.07)
    cr.rectangle(0, 0, w, 32)
    cr.fill()
    # app window
    x, y, ww, wh = 150, 90, w - 300, h - 170
    cr.set_source_rgba(0, 0, 0, 0.35)
    _rr(cr, x + 4, y + 10, ww, wh, 14)
    cr.fill()
    cr.set_source_rgb(0.97, 0.97, 0.98)
    _rr(cr, x, y, ww, wh, 14)
    cr.fill()
    cr.set_source_rgb(0.93, 0.94, 0.96)
    _rr(cr, x, y, ww, 52, 14)
    cr.rectangle(x, y + 30, ww, 22)
    cr.fill()
    for i, c in enumerate([(1, 0.37, 0.34), (1, 0.74, 0.18), (0.16, 0.79, 0.25)]):
        cr.set_source_rgb(*c)
        cr.arc(x + 24 + i * 22, y + 26, 7, 0, 2 * math.pi)
        cr.fill()
    cr.set_source_rgb(1, 1, 1)
    _rr(cr, x + ww / 2 - 260, y + 12, 520, 28, 8)
    cr.fill()
    _text(cr, x + ww / 2 - 240, y + 17, "helpdesk.example.com/tickets/4821", 10.5, (0.35, 0.38, 0.45))
    # sidebar
    cr.set_source_rgb(0.95, 0.96, 0.98)
    cr.rectangle(x, y + 52, 260, wh - 52)
    cr.fill()
    for i, item in enumerate(["Inbox", "Assigned to me", "Waiting", "Solved", "Reports"]):
        if i == 1:
            cr.set_source_rgb(0.86, 0.91, 1)
            _rr(cr, x + 14, y + 76 + i * 44, 232, 34, 8)
            cr.fill()
        _text(cr, x + 32, y + 83 + i * 44, item, 11.5, (0.15, 0.2, 0.3) if i == 1 else (0.35, 0.38, 0.45),
              "Bold" if i == 1 else "Regular")
    # ticket content
    cx, cy = x + 300, y + 84
    _text(cr, cx, cy, "Checkout button does nothing on mobile", 20, (0.1, 0.12, 0.18), "Bold")
    cr.set_source_rgb(0.87, 0.95, 0.89)
    _rr(cr, cx, cy + 46, 92, 26, 13)
    cr.fill()
    _text(cr, cx + 16, cy + 50, "Open", 10.5, (0.08, 0.5, 0.25), "Bold")
    _text(cr, cx + 110, cy + 50, "Ticket #4821 · Priority: High · Store: demo-shop.example.com", 11,
          (0.4, 0.43, 0.5))
    # customer card with data to blur
    cr.set_source_rgb(1, 1, 1)
    _rr(cr, cx, cy + 100, 560, 150, 12)
    cr.fill()
    cr.set_source_rgb(0.88, 0.89, 0.92)
    cr.set_line_width(1)
    _rr(cr, cx + 0.5, cy + 100.5, 559, 149, 12)
    cr.stroke()
    _text(cr, cx + 24, cy + 118, "Customer", 10, (0.45, 0.48, 0.55), "Bold")
    _text(cr, cx + 24, cy + 142, "Jane Doe", 14, (0.1, 0.12, 0.18), "Bold")
    _text(cr, cx + 24, cy + 172, "jane.doe@example.com", 12, (0.25, 0.28, 0.35))
    _text(cr, cx + 24, cy + 198, "+1 555 0100 · Card •••• 4242", 12, (0.25, 0.28, 0.35))
    # message thread
    my = cy + 290
    for who, lines in (("Jane Doe", [0.92, 0.85, 0.6]), ("Support (you)", [0.8, 0.95, 0.7, 0.4])):
        _text(cr, cx, my, who, 12, (0.1, 0.12, 0.18), "Bold")
        my += 30
        for frac in lines:
            cr.set_source_rgb(0.86, 0.87, 0.9)
            _rr(cr, cx, my, (ww - 380) * frac, 12, 6)
            cr.fill()
            my += 24
        my += 24
    # product preview with a broken button
    px, py = x + ww - 560, cy + 100
    cr.set_source_rgb(0.12, 0.13, 0.18)
    _rr(cr, px, py, 300, 520, 28)
    cr.fill()
    cr.set_source_rgb(1, 1, 1)
    _rr(cr, px + 12, py + 12, 276, 496, 20)
    cr.fill()
    cr.set_source_rgb(0.93, 0.9, 0.98)
    _rr(cr, px + 28, py + 40, 244, 200, 12)
    cr.fill()
    _text(cr, px + 28, py + 256, "Linen Overshirt", 14, (0.1, 0.12, 0.18), "Bold")
    _text(cr, px + 28, py + 282, "$68.00", 13, (0.3, 0.33, 0.4))
    cr.set_source_rgb(0.1, 0.12, 0.18)
    _rr(cr, px + 28, py + 420, 244, 48, 10)
    cr.fill()
    _text(cr, px + 104, py + 432, "Checkout", 13, (1, 1, 1), "Bold")
    s.flush()
    return s


# ---- helpers ------------------------------------------------------------------

def render_widget(widget: Gtk.Widget, path: Path, scale: float = 2.0) -> None:
    """Render a realized widget to PNG at `scale` (no screen capture involved)."""
    w, h = widget.get_width(), widget.get_height()
    snap = Gtk.Snapshot()
    snap.scale(scale, scale)
    Gtk.WidgetPaintable.new(widget).snapshot(snap, w, h)
    node = snap.to_node()
    rect = Graphene.Rect().init(0, 0, w * scale, h * scale)
    widget.get_native().get_renderer().render_texture(node, rect).save_to_png(str(path))


def matches(shot: cairo.ImageSurface, ref: cairo.ImageSurface, points, tolerance: int = 12) -> bool:
    if (shot.get_width(), shot.get_height()) != (ref.get_width(), ref.get_height()):
        return False
    shot.flush()
    ref.flush()
    a, b = shot.get_data(), ref.get_data()
    for x, y in points:
        i = int(y) * shot.get_stride() + int(x) * 4
        if any(abs(a[i + k] - b[i + k]) > tolerance for k in range(3)):
            return False
    return True


def frame(src: Path, dst: Path, pad: int = 72, radius: int = 24) -> None:
    """Put a screenshot on a soft gradient with rounded corners and a shadow."""
    img = cairo.ImageSurface.create_from_png(str(src))
    w, h = img.get_width() + 2 * pad, img.get_height() + 2 * pad
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(out)
    g = cairo.LinearGradient(0, 0, w, h)
    g.add_color_stop_rgb(0, 0.23, 0.36, 0.86)
    g.add_color_stop_rgb(1, 0.49, 0.29, 0.86)
    cr.set_source(g)
    cr.paint()
    for i in range(14, 0, -1):  # cheap soft shadow
        cr.set_source_rgba(0, 0, 0, 0.022)
        _rr(cr, pad - i, pad - i + 10, img.get_width() + 2 * i, img.get_height() + 2 * i, radius + i)
        cr.fill()
    _rr(cr, pad, pad, img.get_width(), img.get_height(), radius)
    cr.clip()
    cr.set_source_surface(img, pad, pad)
    cr.paint()
    out.write_to_png(str(dst))


def shrink(src: cairo.ImageSurface, path: Path, width: int = 1600, radius: int = 18) -> None:
    f = width / src.get_width()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, round(src.get_height() * f))
    cr = cairo.Context(out)
    _rr(cr, 0, 0, out.get_width(), out.get_height(), radius)
    cr.clip()
    cr.scale(f, f)
    cr.set_source_surface(src, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_BEST)
    cr.paint()
    out.write_to_png(str(path))


# ---- scenes ------------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(GLib.get_tmp_dir()) / "sc-readme"
    tmp.mkdir(exist_ok=True)
    app = Gtk.Application(application_id="io.avada.ScreenCaptureReadmeShots")
    state = {}

    def activate(a):
        a.hold()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_USER + 100)
        g = Gdk.Display.get_default().get_monitors().get_item(0)
        r = g.get_geometry()
        mon = Monitor(g.get_connector(), r.x, r.y, r.width, r.height, g.get_scale())
        backdrop = demo_backdrop(round(r.width * g.get_scale()), round(r.height * g.get_scale()))
        session = CaptureSession(a, [(mon, g)], {mon.name: backdrop}, lambda *x: None, lambda: None)
        session.present()
        win = session.windows[0]
        state.update(session=session, win=win, mon=mon)

        def grab(name, points, then, attempt=0):
            """Capture only once the overlay really covers the monitor: sampled pixels must match the
            synthetic backdrop. Never write a frame that could contain the real screen."""
            ready = win.get_mapped() and win.is_fullscreen()
            shot = capture_backdrops([mon])[mon.name] if ready else None
            if shot is not None and matches(shot, backdrop, points):
                shrink(shot, OUT / name)
                print("wrote", OUT / name)
                then()
            elif attempt < 8:
                GLib.timeout_add(500, lambda: (grab(name, points, then, attempt + 1), False)[1])
            else:
                print(f"ABORT: overlay never covered {mon.name}; nothing written for {name}")
                a.quit()

        def scene_select():
            session.set_active(mon.name)
            pts = [(200, 500), (mon.width // 2, mon.height // 2), (mon.width - 120, mon.height - 160),
                   (600, 700), (mon.width - 400, 300)]
            GLib.timeout_add(600, lambda: (grab("overlay-select.png", pts, scene_annotate), False)[1])
            return False

        def scene_annotate():
            s = Style(RED, 4.0)
            h = session.histories[mon.name]
            ox, oy = 450, 174  # ticket content origin (see demo_backdrop)
            h.add(Blur(Rect(ox + 14, oy + 160, 340, 72), block=12))
            h.add(Rectangle(Rect(mon.width - 150 - 560 + 18, oy + 100 + 408, 268, 72), s))
            h.add(Arrow((mon.width - 760, oy + 330), (mon.width - 586, oy + 540), s))
            h.add(Step((mon.width - 150 - 560 + 300, oy + 100 + 420), 1, s))
            h.add(Text((mon.width - 1000, oy + 290), "Tap does nothing here", s))
            session.tool = "arrow"
            session.sync()
            win.selection = Rect(ox - 30, oy - 30, mon.width - 150 - ox + 30 - 50, 700)
            win.sync()
            pts = [(520, 760), (700, 640), (900, 300), (1100, 760)]  # inside the selection, not annotated
            GLib.timeout_add(600, lambda: (grab("overlay-annotate.png", pts, scene_settings), False)[1])

        def scene_settings():
            session.close()
            import screen_capture.settings_window as sw
            from screen_capture.settings_store import Settings
            from test_settings_features import BASE, OUR_CMD, FakeStore

            store = FakeStore({BASE + "custom0/": {"name": "Screen Capture", "command": OUR_CMD,
                                                   "binding": "<Control><Alt>s"}})
            patches = [mock.patch.object(sw, "read_settings",
                                         lambda _p: Settings(token="demo-token-not-real",
                                                             upload_url="https://capture-api.avada.io/api/v1/upload")),
                       mock.patch.object(sw, "GSettingsStore", lambda: store),
                       mock.patch.object(sw, "_flameshot_has_token", lambda: False),
                       mock.patch.object(sw.autostart, "is_autostart_enabled", lambda: True)]
            for p in patches:
                p.start()
            w = sw.SettingsWindow(a, lambda: None)
            w.present()
            w.set_focus(None)  # no selected text in the token field
            state["patches"] = patches

            def shoot():
                render_widget(w, tmp / "settings.png")
                frame(tmp / "settings.png", OUT / "settings.png")
                print("wrote", OUT / "settings.png")
                w.destroy()
                scene_toast()
                return False

            GLib.timeout_add(900, shoot)

        def scene_toast():
            from screen_capture.toast import show_toast

            show_toast(a, "Link copied", "https://capture.avada.io/i/Xq7pD2mVbe41", lambda: None, lambda: None)
            toast = [x for x in a.get_windows() if x.has_css_class("sc-toast-window")][-1]

            def shoot():
                render_widget(toast.get_child(), tmp / "toast.png")
                frame(tmp / "toast.png", OUT / "toast.png", pad=56, radius=32)
                print("wrote", OUT / "toast.png")
                for p in state["patches"]:
                    p.stop()
                a.release()
                return False

            GLib.timeout_add(400, shoot)

        GLib.timeout_add(800, scene_select)

    def guarded(fn):
        """Any error inside a GLib callback must end the run instead of leaving the app held forever."""
        def wrapper(*args):
            try:
                return fn(*args)
            except Exception:
                import traceback

                traceback.print_exc()
                app.quit()
                return False
        return wrapper

    GLib.timeout_add = (lambda orig: lambda ms, fn, *a: orig(ms, guarded(fn), *a))(GLib.timeout_add)
    app.connect("activate", guarded(activate))
    app.run([])


if __name__ == "__main__":
    main()
