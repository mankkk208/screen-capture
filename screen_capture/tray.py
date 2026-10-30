"""Top-bar icon: a StatusNotifierItem plus a com.canonical.dbusmenu menu, spoken directly over D-Bus
(GNOME shows it through the ubuntu-appindicators extension; no GTK3/libappindicator needed)."""
import os
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gio, GLib  # noqa: E402

from .tray_menu import MenuItem, build_node, flatten, item_props  # noqa: E402

ICON_DIR = Path(__file__).resolve().parent.parent / "data" / "icons"
ICON_NAME = "io.avada.ScreenCapture"
WATCHER = "org.kde.StatusNotifierWatcher"
ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"

_SNI_XML = """
<node><interface name="org.kde.StatusNotifierItem">
  <property name="Category" type="s" access="read"/>
  <property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconName" type="s" access="read"/>
  <property name="IconThemePath" type="s" access="read"/>
  <property name="IconPixmap" type="a(iiay)" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
  <signal name="NewIcon"/>
  <signal name="NewStatus"><arg type="s"/></signal>
</interface></node>"""

_MENU_XML = """
<node><interface name="com.canonical.dbusmenu">
  <property name="Version" type="u" access="read"/>
  <property name="TextDirection" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconThemePath" type="as" access="read"/>
  <method name="GetLayout">
    <arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
    <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/>
  </method>
  <method name="GetGroupProperties">
    <arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/>
  </method>
  <method name="GetProperty">
    <arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/>
  </method>
  <method name="Event">
    <arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/>
    <arg type="u" direction="in"/>
  </method>
  <method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
  <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
  <method name="AboutToShowGroup">
    <arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/>
  </method>
  <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
  <signal name="ItemsPropertiesUpdated"><arg type="a(ia{sv})"/><arg type="a(ias)"/></signal>
</interface></node>"""


def _pixmaps() -> list:
    """Icon as ARGB32 (network byte order) at a few sizes, for hosts that don't search IconThemePath."""
    out = []
    for size in (16, 22, 24, 32, 48):
        pb = GdkPixbuf.Pixbuf.new_from_file_at_size(str(ICON_DIR / f"{ICON_NAME}.svg"), size, size)
        if not pb.get_has_alpha():
            pb = pb.add_alpha(False, 0, 0, 0)
        w, h, stride, px = pb.get_width(), pb.get_height(), pb.get_rowstride(), pb.get_pixels()
        argb = bytearray()
        for y in range(h):
            row = px[y * stride: y * stride + w * 4]
            for x in range(0, w * 4, 4):
                r, g, b, a = row[x:x + 4]
                argb += bytes((a, r, g, b))
        out.append((w, h, bytes(argb)))
    return out


class Tray:
    """`items()` returns the current menu (list[MenuItem]); call refresh() when it changes."""

    def __init__(self, items, title: str = "Screen Capture"):
        self._items_fn = items
        self._items: dict[int, MenuItem] = {}
        self._title = title
        self._revision = 1
        self._bus = None
        self._name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self._pixmaps = None

    def start(self) -> None:
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        sni = Gio.DBusNodeInfo.new_for_xml(_SNI_XML).interfaces[0]
        menu = Gio.DBusNodeInfo.new_for_xml(_MENU_XML).interfaces[0]
        self._bus.register_object(ITEM_PATH, sni, self._sni_call, self._sni_prop, None)
        self._bus.register_object(MENU_PATH, menu, self._menu_call, self._menu_prop, None)
        Gio.bus_own_name_on_connection(self._bus, self._name, Gio.BusNameOwnerFlags.NONE, None, None)
        # Register now and again whenever the watcher (re)appears, e.g. after GNOME Shell restarts.
        Gio.bus_watch_name_on_connection(self._bus, WATCHER, Gio.BusNameWatcherFlags.NONE,
                                         lambda *_a: self._register(), None)

    def _register(self) -> None:
        self._bus.call(WATCHER, "/StatusNotifierWatcher", WATCHER, "RegisterStatusNotifierItem",
                       GLib.Variant("(s)", (self._name,)), None, Gio.DBusCallFlags.NONE, 2000, None, None)

    def refresh(self) -> None:
        self._revision += 1
        if self._bus is not None:
            self._bus.emit_signal(None, MENU_PATH, "com.canonical.dbusmenu", "LayoutUpdated",
                                  GLib.Variant("(ui)", (self._revision, 0)))

    # ---- StatusNotifierItem ---------------------------------------------------

    def _sni_prop(self, _conn, _sender, _path, _iface, name):
        if name == "IconPixmap" and self._pixmaps is None:
            self._pixmaps = _pixmaps()
        values = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "screen-capture"),
            "Title": GLib.Variant("s", self._title),
            "Status": GLib.Variant("s", "Active"),
            "IconName": GLib.Variant("s", ICON_NAME),
            "IconThemePath": GLib.Variant("s", str(ICON_DIR)),
            "IconPixmap": GLib.Variant("a(iiay)", self._pixmaps or []),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", ("", [], self._title, "")),
            "ItemIsMenu": GLib.Variant("b", True),
            "Menu": GLib.Variant("o", MENU_PATH),
        }
        return values.get(name)

    def _sni_call(self, _conn, _sender, _path, _iface, _method, _params, invocation):
        invocation.return_value(None)  # ItemIsMenu: the host opens the menu itself

    # ---- dbusmenu -------------------------------------------------------------

    def _menu_prop(self, _conn, _sender, _path, _iface, name):
        return {"Version": GLib.Variant("u", 3), "TextDirection": GLib.Variant("s", "ltr"),
                "Status": GLib.Variant("s", "normal"), "IconThemePath": GLib.Variant("as", [])}.get(name)

    def _menu_call(self, _conn, _sender, _path, _iface, method, params, invocation):
        if method == "GetLayout":
            parent = params.unpack()[0]
            items = self._items_fn()
            self._items = flatten(items)
            root = MenuItem(0, "", children=items) if parent == 0 else self._items.get(parent)
            node = build_node(root or MenuItem(parent, ""), root=parent == 0)
            invocation.return_value(GLib.Variant.new_tuple(GLib.Variant("u", self._revision), node))
        elif method == "GetGroupProperties":
            ids = params.unpack()[0]
            if not self._items:
                self._items = flatten(self._items_fn())
            props = [(i, item_props(self._items[i])) for i in ids if i in self._items]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (props,)))
        elif method == "GetProperty":
            invocation.return_value(GLib.Variant("(v)", (GLib.Variant("s", ""),)))
        elif method == "Event":
            item_id, event = params.unpack()[0], params.unpack()[1]
            item = self._items.get(item_id)
            if event == "clicked" and item is not None and item.on_click is not None:
                GLib.idle_add(lambda: (item.on_click(), False)[1])
            invocation.return_value(None)
        elif method == "EventGroup":
            for item_id, event, _data, _ts in params.unpack()[0]:
                item = self._items.get(item_id)
                if event == "clicked" and item is not None and item.on_click is not None:
                    GLib.idle_add(lambda it=item: (it.on_click(), False)[1])
            invocation.return_value(GLib.Variant("(ai)", ([],)))
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method == "AboutToShowGroup":
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            invocation.return_value(None)

