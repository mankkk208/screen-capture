"""Screenshot through org.freedesktop.portal.Screenshot (the only allowed grab on Wayland)."""
import secrets
from pathlib import Path
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"


class ScreenshotError(Exception):
    pass


def request_path(unique_name: str, token: str) -> str:
    sender = unique_name.lstrip(":").replace(".", "_")
    return f"{PORTAL_PATH}/request/{sender}/{token}"


def take_screenshot(timeout_s: float = 5.0) -> Path:
    """Blocking. Returns the path of a PNG of the whole desktop, or raises ScreenshotError."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(
            bus, Gio.DBusProxyFlags.NONE, None, PORTAL_BUS, PORTAL_PATH,
            "org.freedesktop.portal.Screenshot", None,
        )
    except GLib.Error as e:
        raise ScreenshotError(f"portal unavailable: {e.message}") from None

    token = "sc" + secrets.token_hex(6)
    expected = request_path(bus.get_unique_name(), token)
    loop = GLib.MainLoop()
    result: dict = {}

    def on_response(_conn, _sender, _path, _iface, _signal, params):
        result["code"], result["results"] = params.unpack()
        loop.quit()

    sub = bus.signal_subscribe(
        PORTAL_BUS, "org.freedesktop.portal.Request", "Response", expected, None,
        Gio.DBusSignalFlags.NONE, on_response,
    )
    try:
        options = {"handle_token": GLib.Variant("s", token), "interactive": GLib.Variant("b", False)}
        try:
            proxy.call_sync(
                "Screenshot", GLib.Variant("(sa{sv})", ("", options)),
                Gio.DBusCallFlags.NONE, int(timeout_s * 1000), None,
            )
        except GLib.Error as e:
            raise ScreenshotError(f"portal call failed: {e.message}") from None
        if "code" not in result:
            timer = GLib.timeout_add(int(timeout_s * 1000), lambda: (loop.quit(), False)[1])
            loop.run()
            GLib.source_remove(timer) if GLib.MainContext.default().find_source_by_id(timer) else None
    finally:
        bus.signal_unsubscribe(sub)

    if "code" not in result:
        raise ScreenshotError("portal timed out")
    if result["code"] == 1:
        raise ScreenshotError("screenshot cancelled or permission denied")
    if result["code"] != 0:
        raise ScreenshotError("portal screenshot failed")
    uri = result["results"].get("uri")
    if not uri:
        raise ScreenshotError("portal returned no image")
    return Path(unquote(urlparse(uri).path))
