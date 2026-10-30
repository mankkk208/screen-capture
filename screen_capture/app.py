"""Resident GTK application: the shortcut command re-activates the running instance over D-Bus."""
import os
import sys
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .capture import capture_backdrops  # noqa: E402
from .compose import render_png, render_surface  # noqa: E402
from .config import load_config  # noqa: E402
from .geometry import Monitor  # noqa: E402
from .notify import notify  # noqa: E402
from .overlay import CaptureSession, image_clipboard_content  # noqa: E402
from .portal import ScreenshotError  # noqa: E402
from .toast import show_toast  # noqa: E402
from .toolbar import CSS  # noqa: E402
from .pipeline import deliver  # noqa: E402
from .upload import upload_png  # noqa: E402

APP_ID = "io.avada.ScreenCapture"
DEBUG = bool(os.environ.get("SC_DEBUG"))


def _debug(msg: str) -> None:
    if DEBUG:
        print(f"[screen-capture] {msg}", file=sys.stderr, flush=True)


class CaptureApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.session: CaptureSession | None = None
        self._capturing = False

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()  # resident: stay alive with no windows (also keeps serving the clipboard)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 100)  # above ~/.config/gtk-4.0/gtk.css themes

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if "--quit" in args:
            self.quit()
        elif "--background" not in args:
            self.start_session()
        return 0

    def do_activate(self):
        self.start_session()

    def _monitors(self) -> list[tuple[Monitor, Gdk.Monitor]]:
        model = Gdk.Display.get_default().get_monitors()
        out = []
        for i in range(model.get_n_items()):
            g = model.get_item(i)
            r = g.get_geometry()
            name = g.get_connector() or f"monitor-{i}"
            out.append((Monitor(name, r.x, r.y, r.width, r.height, g.get_scale()), g))
        return out

    def start_session(self) -> None:
        if self.session is not None and not self.session.closed:
            self.session.present()
            return
        # Capturing spins a nested main loop that also dispatches D-Bus Activate; ignore re-entry.
        if self._capturing:
            return
        self._capturing = True
        try:
            t0 = time.perf_counter()
            monitors = self._monitors()
            try:
                backdrops = capture_backdrops([m for m, _g in monitors])
            except ScreenshotError as e:
                notify("Screenshot failed", str(e), icon="dialog-error")
                return
        finally:
            self._capturing = False
        t1 = time.perf_counter()
        session = CaptureSession(self, monitors, backdrops, None, lambda: None, None)
        # Bind this session's backdrops into its callbacks rather than reading self.session later.
        session.on_done = lambda m, sel, shapes: self._done(session, m, sel, shapes)
        session.on_copy = lambda m, sel, shapes: self._copy(session, m, sel, shapes)
        session.on_copy_failed = lambda: notify("Copy failed", "The image could not be put on the clipboard.",
                                                icon="dialog-error")
        self.session = session
        session.present()
        _debug(f"capture {1000 * (t1 - t0):.0f} ms, overlay built {1000 * (time.perf_counter() - t1):.0f} ms")

    def _done(self, session, monitor: Monitor, sel, shapes) -> None:
        backdrop = session.backdrops[monitor.name]
        image_scale = backdrop.get_width() / monitor.width
        threading.Thread(target=self._render_and_upload, args=(backdrop, sel, image_scale, shapes),
                         daemon=True).start()

    def _copy(self, session, monitor: Monitor, sel, shapes):
        """Put the image on the clipboard (no upload). Returns the follow-up to run once overlays close."""
        backdrop = session.backdrops[monitor.name]
        surface = render_surface(backdrop, sel, backdrop.get_width() / monitor.width, shapes)
        Gdk.Display.get_default().get_clipboard().set_content(image_clipboard_content(surface))
        detail = f"{surface.get_width()} × {surface.get_height()} · not uploaded"
        return lambda: show_toast(self, "Image copied", detail, lambda: None, lambda: None)

    def _render_and_upload(self, backdrop, sel, image_scale, shapes) -> None:
        t0 = time.perf_counter()
        status, result = deliver(lambda: render_png(backdrop, sel, image_scale, shapes), load_config, upload_png)
        _debug(f"render+upload {1000 * (time.perf_counter() - t0):.0f} ms: {status}")
        if status == "ok":
            GLib.idle_add(self._uploaded, result)
        else:
            GLib.idle_add(self._failed, result)

    def _uploaded(self, url: str) -> bool:
        if self.session is not None and not self.session.closed:
            # A new capture is open and has focus: copy directly, don't steal focus with a toast.
            _set_clipboard_text(url)
            notify("Link copied", url)
            return False

        def no_focus():
            notify("Uploaded, but the link could not be copied", url, icon="dialog-warning")

        show_toast(self, "Link copied", url, lambda: _set_clipboard_text(url), no_focus)
        return False

    def _failed(self, message: str) -> bool:
        notify("Upload failed", message, icon="dialog-error")
        return False


def _set_clipboard_text(text: str) -> None:
    Gdk.Display.get_default().get_clipboard().set(text)
