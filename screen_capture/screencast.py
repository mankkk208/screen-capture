"""Flash-free capture: one frame per monitor from org.gnome.Mutter.ScreenCast over PipeWire.

RecordArea is used instead of RecordMonitor: RecordMonitor("eDP-1") never delivered a frame
on the owner's machine (spike, 2026-10-30).
"""
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gio, GLib, Gst  # noqa: E402

from .geometry import Monitor  # noqa: E402
from .portal import ScreenshotError  # noqa: E402
from .screencast_geometry import LAYOUT_PHYSICAL, record_area_rect  # noqa: E402

BUS = "org.gnome.Mutter.ScreenCast"
SESSION_IFACE = "org.gnome.Mutter.ScreenCast.Session"
CURSOR_HIDDEN = 0

Gst.init(None)


def _call(bus, path, iface, method, params, timeout_s):
    return bus.call_sync(BUS, path, iface, method, params, None, Gio.DBusCallFlags.NONE,
                         int(timeout_s * 1000), None)


def _physical_layout(bus) -> bool:
    try:
        state = bus.call_sync("org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig",
                              "org.gnome.Mutter.DisplayConfig", "GetCurrentState", None, None,
                              Gio.DBusCallFlags.NONE, 1000, None).unpack()
        return state[3].get("layout-mode") == LAYOUT_PHYSICAL
    except GLib.Error:
        return False


def grab_monitors(monitors: list[Monitor], timeout_s: float = 3.0) -> dict:
    """Return {monitor.name: cairo.ImageSurface}. Raises ScreenshotError on any failure."""
    from .capture import surface_from_bgrx

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        session = _call(bus, "/org/gnome/Mutter/ScreenCast", "org.gnome.Mutter.ScreenCast",
                        "CreateSession", GLib.Variant("(a{sv})", ({},)), timeout_s)[0]
    except GLib.Error as e:
        raise ScreenshotError(f"screencast unavailable: {e.message}") from None

    pipes = []
    subs = []
    try:
        streams = {}
        physical = _physical_layout(bus)
        for m in monitors:
            opts = {"cursor-mode": GLib.Variant("u", CURSOR_HIDDEN)}
            path = _call(bus, session, SESSION_IFACE, "RecordArea",
                         GLib.Variant("(iiiia{sv})", (*record_area_rect(m, physical), opts)),
                         timeout_s)[0]
            streams[path] = m.name

        loop = GLib.MainLoop()
        nodes: dict[str, int] = {}

        def on_added(_c, _s, path, _i, _sig, params):
            nodes[streams[path]] = params.unpack()[0]
            if len(nodes) == len(streams):
                loop.quit()

        for path in streams:
            subs.append(bus.signal_subscribe(BUS, "org.gnome.Mutter.ScreenCast.Stream", "PipeWireStreamAdded",
                                             path, None, Gio.DBusSignalFlags.NONE, on_added))
        _call(bus, session, SESSION_IFACE, "Start", None, timeout_s)
        if len(nodes) < len(streams):
            timer = GLib.timeout_add(int(timeout_s * 1000), lambda: (loop.quit(), False)[1])
            loop.run()
            if GLib.MainContext.default().find_source_by_id(timer):
                GLib.source_remove(timer)
        if len(nodes) < len(streams):
            raise ScreenshotError("screencast stream did not start")

        sinks = {}
        for name, node in nodes.items():
            pipe = Gst.parse_launch(
                f"pipewiresrc path={node} num-buffers=1 ! videoconvert ! "
                "video/x-raw,format=BGRx ! appsink name=sink sync=false")
            pipe.set_state(Gst.State.PLAYING)
            pipes.append(pipe)
            sinks[name] = pipe.get_by_name("sink")

        out = {}
        for name, sink in sinks.items():
            sample = sink.emit("try-pull-sample", int(timeout_s * Gst.SECOND))
            if sample is None:
                raise ScreenshotError(f"no frame from {name}")
            s = sample.get_caps().get_structure(0)
            w, h = s.get_value("width"), s.get_value("height")
            buf = sample.get_buffer()
            ok, info = buf.map(Gst.MapFlags.READ)
            if not ok:
                raise ScreenshotError(f"cannot read frame from {name}")
            try:
                out[name] = surface_from_bgrx(bytes(info.data), w, h, len(info.data) // h)
            finally:
                buf.unmap(info)
        return out
    except GLib.Error as e:
        raise ScreenshotError(f"screencast failed: {e.message}") from None
    finally:
        for pipe in pipes:
            pipe.set_state(Gst.State.NULL)
        for sub in subs:
            bus.signal_unsubscribe(sub)
        try:
            _call(bus, session, SESSION_IFACE, "Stop", None, timeout_s)
        except GLib.Error:
            pass
