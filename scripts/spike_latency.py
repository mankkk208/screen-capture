#!/usr/bin/env python3
"""Throwaway spike (Task 2): portal latency, monitor/scale facts, per-monitor fullscreen windows.

Usage: python3 scripts/spike_latency.py [--overlay]
Without --overlay it only measures the portal and prints monitor geometry.
"""
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from screen_capture.portal import take_screenshot  # noqa: E402


def monitors():
    out = []
    for m in Gdk.Display.get_default().get_monitors():
        g = m.get_geometry()
        out.append((m, m.get_connector(), g.x, g.y, g.width, g.height, m.get_scale()))
    return out


def main():
    Gtk.init()
    mons = monitors()
    for _m, name, x, y, w, h, s in mons:
        print(f"monitor {name}: logical {w}x{h} at ({x},{y}) scale {s}")
    dw = max(x + w for _m, _n, x, _y, w, _h, _s in mons) - min(x for _m, _n, x, _y, _w, _h, _s in mons)
    dh = max(y + h for _m, _n, _x, y, _w, h, _s in mons) - min(y for _m, _n, _x, y, _w, _h, _s in mons)
    print(f"desktop logical bounding box: {dw}x{dh}")

    times, path = [], None
    for i in range(10):
        t0 = time.perf_counter()
        path = take_screenshot()
        times.append((time.perf_counter() - t0) * 1000)
        print(f"  portal #{i + 1}: {times[-1]:.0f} ms")
        time.sleep(0.3)
    print(f"portal ms: min {min(times):.0f} median {statistics.median(times):.0f} max {max(times):.0f}")

    tex = Gdk.Texture.new_from_filename(str(path))
    print(f"portal image: {tex.get_width()}x{tex.get_height()} px -> image_scale = {tex.get_width() / dw:.4f} (x), {tex.get_height() / dh:.4f} (y)")

    if "--overlay" not in sys.argv:
        return

    loop = GLib.MainLoop()
    wins = []
    t_open = time.perf_counter()
    for m, name, x, y, w, h, s in mons:
        win = Gtk.Window(title=f"spike {name}")
        pic = Gtk.Picture.new_for_paintable(tex)
        pic.set_content_fit(Gtk.ContentFit.COVER)
        win.set_child(pic)
        win.set_cursor_from_name("crosshair")
        key = Gtk.EventControllerKey()

        def on_key(_c, keyval, _code, _state, name=name):
            print(f"  key {Gdk.keyval_name(keyval)} reached window {name}")
            if keyval == Gdk.KEY_Escape:
                loop.quit()
            return True

        key.connect("key-pressed", on_key)
        win.add_controller(key)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda _c, px, py, name=name: print(f"  pointer enter {name} at {px:.0f},{py:.0f}"))
        win.add_controller(motion)
        win.fullscreen_on_monitor(m)
        win.present()
        wins.append(win)
    print(f"overlay windows presented in {(time.perf_counter() - t_open) * 1000:.0f} ms (call time, not first paint)")
    print("Move the pointer across monitors, press some keys, press Esc to quit.")
    GLib.timeout_add_seconds(60, loop.quit)
    loop.run()
    for w in wins:
        w.destroy()


if __name__ == "__main__":
    main()
