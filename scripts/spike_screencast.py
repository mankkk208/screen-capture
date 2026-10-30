#!/usr/bin/env python3
"""Throwaway spike: grab one frame per monitor via org.gnome.Mutter.ScreenCast + PipeWire (no flash)."""
import sys
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gio, GLib, Gst  # noqa: E402

Gst.init(None)
BUS = "org.gnome.Mutter.ScreenCast"


def call(bus, path, iface, method, params, reply=None):
    return bus.call_sync(BUS, path, iface, method, params, reply, Gio.DBusCallFlags.NONE, 5000, None)


def grab(connector: str, out: str) -> float:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    t0 = time.perf_counter()
    session = call(bus, "/org/gnome/Mutter/ScreenCast", "org.gnome.Mutter.ScreenCast", "CreateSession",
                   GLib.Variant("(a{sv})", ({},)))[0]
    stream = call(bus, session, "org.gnome.Mutter.ScreenCast.Session", "RecordMonitor",
                  GLib.Variant("(sa{sv})", (connector, {"cursor-mode": GLib.Variant("u", 0)})))[0]
    loop = GLib.MainLoop()
    node = {}

    def on_added(_c, _s, _p, _i, _sig, params):
        node["id"] = params.unpack()[0]
        loop.quit()

    sub = bus.signal_subscribe(BUS, "org.gnome.Mutter.ScreenCast.Stream", "PipeWireStreamAdded", stream,
                               None, Gio.DBusSignalFlags.NONE, on_added)
    call(bus, session, "org.gnome.Mutter.ScreenCast.Session", "Start", None)
    GLib.timeout_add(3000, lambda: (loop.quit(), False)[1])
    if "id" not in node:
        loop.run()
    bus.signal_unsubscribe(sub)
    t_node = time.perf_counter()
    pipe = Gst.parse_launch(
        f"pipewiresrc path={node['id']} num-buffers=1 ! videoconvert ! pngenc ! filesink location={out}")
    pipe.set_state(Gst.State.PLAYING)
    msg = pipe.get_bus().timed_pop_filtered(5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
    t_frame = time.perf_counter()
    if msg and msg.type == Gst.MessageType.ERROR:
        print("gst error:", msg.parse_error()[0].message)
    pipe.set_state(Gst.State.NULL)
    call(bus, session, "org.gnome.Mutter.ScreenCast.Session", "Stop", None)
    print(f"{connector}: session+node {1000 * (t_node - t0):.0f} ms, frame {1000 * (t_frame - t_node):.0f} ms, "
          f"total {1000 * (t_frame - t0):.0f} ms")
    return t_frame - t0


if __name__ == "__main__":
    for i in range(3):
        for c in sys.argv[1:] or ["eDP-1", "HDMI-1"]:
            grab(c, f"/tmp/sc-spike-{c}.png")
