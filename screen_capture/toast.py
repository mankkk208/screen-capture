"""Small focused confirmation window. On Wayland an app may only set the clipboard while one
of its surfaces has focus, so the toast is also what lets us copy the link after upload."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from .toolbar import icon_image  # noqa: E402

SHOW_MS = 1100
FOCUS_WAIT_MS = 800


def show_toast(app: Gtk.Application, title: str, detail: str, on_focus, on_no_focus) -> None:
    """Show the toast; call on_focus() once it has keyboard focus, on_no_focus() if it never gets it."""
    win = Gtk.Window(application=app)
    win.set_decorated(False)
    win.set_resizable(False)
    win.add_css_class("sc-toast-window")
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    box.add_css_class("sc-toast")
    badge = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    badge.add_css_class("badge")
    check = icon_image("check", scale=2, color="#FFFFFF", px=18)
    check.set_hexpand(True)
    check.set_halign(Gtk.Align.CENTER)
    badge.append(check)
    box.append(badge)
    texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
    heading = Gtk.Label(label=title, xalign=0)
    heading.add_css_class("title")
    texts.append(heading)
    if detail:
        url = Gtk.Label(label=detail, xalign=0, max_width_chars=48, ellipsize=Pango.EllipsizeMode.MIDDLE)
        url.add_css_class("url")
        texts.append(url)
    box.append(texts)
    win.set_child(box)
    state = {"focused": False}

    def on_active(w, _pspec):
        if w.is_active() and not state["focused"]:
            state["focused"] = True
            on_focus()

    def close():
        if not state.get("closed"):
            state["closed"] = True
            win.destroy()
        return False

    def check_focus():
        if not state["focused"]:
            close()
            on_no_focus()
        return False

    win.connect("notify::is-active", on_active)
    win.present()
    GLib.timeout_add(FOCUS_WAIT_MS, check_focus)
    GLib.timeout_add(SHOW_MS, close)
