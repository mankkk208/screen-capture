"""Frozen fullscreen overlay: one window per monitor, each with its own canvas and history."""
import math

import gi

gi.require_foreign("cairo")
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, GObject, Gtk, Pango, PangoCairo  # noqa: E402

import cairo  # noqa: E402

from .annotations import Arrow, Blur, Ellipse, Highlighter, History, Line, Pen, Rectangle, Step, Style, Text, font_size  # noqa: E402,E501
from .geometry import Monitor, Rect, clamp_to_monitor, is_click  # noqa: E402
from .toolbar import KEY_TO_TOOL, RED, WIDTHS, Toolbar  # noqa: E402

SCRIM = (0.008, 0.024, 0.09, 0.55)  # slate-950 at 55%
SURFACE = (0.06, 0.09, 0.16, 0.92)  # slate-900

HINTS = {
    "select": [("Click", "upload this screen"), ("Double-click", "copy it"), ("Drag", "select an area"),
               ("Esc", "cancel")],
    "draw": [("Drag", "draw"), ("S", "back to select"), ("Ctrl+Z", "undo"), ("Esc", "cancel")],
    "click": [("Click", "place"), ("S", "back to select"), ("Ctrl+Z", "undo"), ("Esc", "cancel")],
}


def _rect(p0, p1) -> Rect:
    x0, x1 = sorted((p0[0], p1[0]))
    y0, y1 = sorted((p0[1], p1[1]))
    return Rect(x0, y0, x1 - x0, y1 - y0)


def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _dashed_outline(cr) -> None:
    """Thin white dashed line on the current path; dark gaps keep it visible on white content."""
    cr.set_line_width(1.5)
    cr.set_source_rgba(0.06, 0.09, 0.16, 0.55)
    cr.stroke_preserve()
    cr.set_dash([6, 4])
    cr.set_source_rgb(1, 1, 1)
    cr.stroke()
    cr.set_dash([])


def texture_from_surface(surface: cairo.ImageSurface) -> Gdk.Texture:
    surface.flush()
    data = GLib.Bytes.new(bytes(surface.get_data()))
    return Gdk.MemoryTexture.new(surface.get_width(), surface.get_height(),
                                 Gdk.MemoryFormat.B8G8R8X8, data, surface.get_stride())


def image_clipboard_content(surface: cairo.ImageSurface) -> Gdk.ContentProvider:
    # Must be typed as GdkTexture: a provider for the concrete GdkMemoryTexture type offers no image
    # formats, so other apps see nothing to paste.
    return Gdk.ContentProvider.new_for_value(GObject.Value(Gdk.Texture, texture_from_surface(surface)))


class CaptureSession:
    """State shared by all overlay windows of one capture."""

    def __init__(self, app, monitors: list[tuple[Monitor, Gdk.Monitor]], backdrops: dict, on_done, on_cancel,
                 on_copy=None):
        self.app = app
        self.backdrops = backdrops
        self.on_done = on_done
        self.on_copy = on_copy
        self.on_copy_failed = lambda: None
        self.on_cancel = on_cancel
        self.histories = {m.name: History() for m, _g in monitors}
        self.tool = "select"
        self.style = Style(RED, WIDTHS[1])
        self.active: str | None = None
        self.closed = False
        self.windows = [OverlayWindow(self, m, g) for m, g in monitors]

    def present(self) -> None:
        for w in self.windows:
            w.present()

    def redraw(self) -> None:
        for w in self.windows:
            w.area.queue_draw()

    def set_active(self, name: str) -> None:
        if name != self.active:
            self.active = name
            self.sync()

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        for w in self.windows:
            w.reset_interaction()
        self.sync()

    def set_color(self, color) -> None:
        self.style = Style(color, self.style.width)
        self.sync()

    def set_width(self, width: float) -> None:
        self.style = Style(self.style.color, width)
        self.sync()

    def sync(self) -> None:
        """Push shared state to every window's toolbar, hint and canvas."""
        for w in self.windows:
            w.sync()

    def active_history(self) -> History | None:
        return self.histories.get(self.active) if self.active else None

    def undo(self) -> None:
        if h := self.active_history():
            h.undo()
            self.sync()

    def redo(self) -> None:
        if h := self.active_history():
            h.redo()
            self.sync()

    def finish(self, monitor: Monitor, sel: Rect, copy: bool = False) -> None:
        """Upload the selection, or with copy=True put the image on the clipboard without uploading."""
        if self.closed:
            return
        for w in self.windows:
            w.commit_text()
        shapes = self.histories[monitor.name].shapes
        if copy:
            # Clipboard must be set while an overlay window still has focus (Wayland).
            try:
                done = self.on_copy(monitor, sel, shapes)
            except Exception:
                self.close()
                self.on_copy_failed()
                return
            self.close()
            done()
            return
        self.close()
        self.on_done(monitor, sel, shapes)

    def cancel(self) -> None:
        if not self.closed:
            self.close()
            self.on_cancel()

    def close(self) -> None:
        self.closed = True
        for w in self.windows:
            w.cancel_pending_click()
            w.destroy()


class OverlayWindow(Gtk.Window):
    def __init__(self, session: CaptureSession, monitor: Monitor, gdk_monitor: Gdk.Monitor):
        super().__init__(application=session.app)
        self.session = session
        self.monitor = monitor
        self.backdrop = session.backdrops[monitor.name]
        self.image_scale = self.backdrop.get_width() / monitor.width
        self.history = session.histories[monitor.name]
        self.drag_start = None
        self.drag_point = None
        self.selection: Rect | None = None
        self.preview = None
        self.text_entry: Gtk.Entry | None = None
        self.text_pos = None
        self.pending_click = 0  # GLib source id of a single click waiting to see if it becomes a double-click

        self.set_title("Screen Capture")
        self.set_decorated(False)
        self.add_css_class("sc-overlay-window")
        self.set_default_size(int(monitor.width), int(monitor.height))

        root = Gtk.Overlay()
        picture = Gtk.Picture.new_for_paintable(texture_from_surface(self.backdrop))
        picture.set_content_fit(Gtk.ContentFit.FILL)
        picture.set_can_shrink(True)
        root.set_child(picture)

        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.area.set_draw_func(self._draw)
        self.area.set_cursor_from_name("crosshair")
        root.add_overlay(self.area)

        self.fixed = Gtk.Fixed()
        self.fixed.set_halign(Gtk.Align.START)
        self.fixed.set_valign(Gtk.Align.START)
        root.add_overlay(self.fixed)

        self.toolbar = Toolbar(session.set_tool, session.set_color, session.set_width,
                               session.undo, session.redo, session.cancel, scale=math.ceil(monitor.scale))
        root.add_overlay(self.toolbar)

        self.hint = Gtk.Box(spacing=0, halign=Gtk.Align.CENTER, valign=Gtk.Align.END, can_target=False)
        self.hint.add_css_class("sc-hint")
        self._hint_mode = None
        root.add_overlay(self.hint)
        self.set_child(root)

        drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end", self._drag_end)
        self.area.add_controller(drag)

        # Raw events: a GestureClick for button 3 would not fire while the left-button drag owns the pointer.
        raw = Gtk.EventControllerLegacy()
        raw.connect("event", self._raw_event)
        self.area.add_controller(raw)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_a: session.set_active(monitor.name))
        motion.connect("motion", lambda *_a: session.set_active(monitor.name))
        self.add_controller(motion)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)

        self.sync()
        self.fullscreen_on_monitor(gdk_monitor)

    # ---- shared state ----------------------------------------------------------

    def sync(self):
        s = self.session
        self.toolbar.update(s.tool, s.style.color, s.style.width, self.history.can_undo, self.history.can_redo)
        mode = "select" if s.tool == "select" else ("click" if s.tool in ("step", "text") else "draw")
        self._set_hint(mode)
        is_active = s.active == self.monitor.name
        self.hint.set_visible(is_active and self.selection is None and self.drag_start is None)
        self.area.queue_draw()

    def _set_hint(self, mode: str):
        if mode == self._hint_mode:
            return
        self._hint_mode = mode
        while (child := self.hint.get_first_child()) is not None:
            self.hint.remove(child)
        for i, (key, action) in enumerate(HINTS[mode]):
            if i:
                dot = Gtk.Label(label="·")
                dot.set_margin_start(10)
                dot.set_margin_end(10)
                self.hint.append(dot)
            kbd = Gtk.Label(label=key)
            kbd.add_css_class("kbd")
            kbd.set_margin_end(6)
            self.hint.append(kbd)
            self.hint.append(Gtk.Label(label=action))

    def reset_interaction(self):
        self.commit_text()
        self.selection = None
        self.preview = None

    # ---- input -------------------------------------------------------------

    def _clamp(self, x: float, y: float):
        return min(max(x, 0.0), self.monitor.width), min(max(y, 0.0), self.monitor.height)

    def _drag_begin(self, _g, x, y):
        self.commit_text()
        self.session.set_active(self.monitor.name)
        self.drag_start = self._clamp(x, y)
        self.drag_point = self.drag_start
        if self.session.tool in ("pen", "highlighter"):
            cls = Pen if self.session.tool == "pen" else Highlighter
            self.preview = cls([self.drag_start], self.session.style)

    def _drag_update(self, _g, dx, dy):
        if self.drag_start is None:
            return
        self.drag_point = self._clamp(self.drag_start[0] + dx, self.drag_start[1] + dy)
        tool, style, p0, p1 = self.session.tool, self.session.style, self.drag_start, self.drag_point
        moved = not is_click(p0, p1)
        if tool == "select":
            self.selection = _rect(p0, p1) if moved else None
            self.hint.set_visible(False)
        elif tool in ("pen", "highlighter"):
            self.preview.points.append(p1)
        elif not moved:
            self.preview = None
        elif tool == "arrow":
            self.preview = Arrow(p0, p1, style)
        elif tool == "line":
            self.preview = Line(p0, p1, style)
        elif tool == "rect":
            self.preview = Rectangle(_rect(p0, p1), style)
        elif tool == "ellipse":
            self.preview = Ellipse(_rect(p0, p1), style)
        elif tool == "blur":
            self.preview = Blur(_rect(p0, p1))
        self.area.queue_draw()

    def _drag_end(self, _g, dx, dy):
        if self.drag_start is None:
            return
        self._drag_update(_g, dx, dy)
        p0, p1, tool = self.drag_start, self.drag_point, self.session.tool
        self.drag_start = None
        click = is_click(p0, p1)
        if tool == "select":
            if self.selection is None and not click:
                return  # right-click already copied this drag
            self.selection = None
            if click:
                self._click(p1)
            else:
                self.session.finish(self.monitor, clamp_to_monitor(self.monitor, _rect(p0, p1)))
            return
        if tool == "step" and click:
            self.history.add(Step(p1, self.history.next_step_number(), self.session.style))
        elif tool == "text" and click:
            self._start_text(p1)
        elif self.preview is not None and (not click or tool in ("pen", "highlighter")):
            self.history.add(self.preview)
        self.preview = None
        self.session.sync()

    def _full(self) -> Rect:
        return Rect(0, 0, self.monitor.width, self.monitor.height)

    def _click(self, _point):
        """Single click uploads the monitor, double-click copies it; wait to tell them apart."""
        if self.pending_click:
            self.cancel_pending_click()
            self.session.finish(self.monitor, self._full(), copy=True)
            return
        delay = Gtk.Settings.get_default().props.gtk_double_click_time

        def single():
            self.pending_click = 0
            self.session.finish(self.monitor, self._full())
            return False

        self.pending_click = GLib.timeout_add(delay, single)

    def cancel_pending_click(self):
        if self.pending_click:
            GLib.source_remove(self.pending_click)
            self.pending_click = 0

    def _raw_event(self, controller, _event) -> bool:
        event = controller.get_current_event()  # PyGObject passes None for the signal's GdkEvent
        if event is None or event.get_event_type() != Gdk.EventType.BUTTON_PRESS or event.get_button() != Gdk.BUTTON_SECONDARY:
            return False
        if self.session.tool == "select" and self.drag_start is not None and self.selection is not None:
            sel = clamp_to_monitor(self.monitor, self.selection)
            self.selection = None
            self.drag_start = None
            self.session.finish(self.monitor, sel, copy=True)
        elif self.drag_start is None:
            self.session.set_tool("select")
        return True

    def _key(self, _c, keyval, _code, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if self.text_entry is not None:
            if keyval == Gdk.KEY_Escape:
                self._drop_text()
                return True
            return False  # let the entry take the keys
        if self.toolbar.picker_open:
            return False  # colour editor's hex entry gets the keys; Esc closes the popover
        if keyval == Gdk.KEY_Escape:
            self.session.cancel()
            return True
        lower = Gdk.keyval_to_lower(keyval)
        if ctrl and lower == Gdk.KEY_z:
            self.session.redo() if shift else self.session.undo()
            return True
        if ctrl and lower == Gdk.KEY_y:
            self.session.redo()
            return True
        if not ctrl and (name := Gdk.keyval_name(lower)) in KEY_TO_TOOL:
            self.session.set_tool(KEY_TO_TOOL[name])
            return True
        return False

    # ---- text tool -----------------------------------------------------------

    def _start_text(self, pos):
        style = self.session.style
        rgb = ",".join(str(int(c * 255)) for c in style.color[:3])
        entry = Gtk.Entry()
        entry.add_css_class("sc-text-entry")
        provider = Gtk.CssProvider()
        provider.load_from_string(
            f".sc-text-entry text {{ color: rgb({rgb}); caret-color: rgb({rgb}); "
            f"font-size: {font_size(style):.0f}px; }}")
        entry.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 100)
        entry.set_size_request(int(min(600, self.monitor.width - pos[0])), -1)
        entry.connect("activate", lambda *_a: self.commit_text())
        self.fixed.put(entry, pos[0], pos[1])
        self.text_entry, self.text_pos = entry, pos
        entry.grab_focus()

    def commit_text(self):
        if self.text_entry is None:
            return
        text = self.text_entry.get_text().strip()
        if text:
            self.history.add(Text(self.text_pos, text, self.session.style))
        self._drop_text()
        self.session.sync()

    def _drop_text(self):
        if self.text_entry is not None:
            self.fixed.remove(self.text_entry)
            self.text_entry = None
            self.area.queue_draw()

    # ---- drawing -------------------------------------------------------------

    def _draw(self, _area, cr, w, h):
        for shape in self.history.shapes + ([self.preview] if self.preview else []):
            cr.save()
            shape.draw(cr, backdrop=self.backdrop, image_scale=self.image_scale)
            cr.restore()

        sel = self.selection
        if sel is not None:
            cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            cr.rectangle(0, 0, w, h)
            cr.rectangle(sel.x, sel.y, sel.w, sel.h)
            cr.set_source_rgba(*SCRIM)
            cr.fill()
            cr.set_fill_rule(cairo.FILL_RULE_WINDING)
            cr.rectangle(sel.x - 0.75, sel.y - 0.75, sel.w + 1.5, sel.h + 1.5)
            _dashed_outline(cr)
            self._handles(cr, sel)
            self._size_label(cr, sel, w, h)
        elif self.session.active == self.monitor.name:
            cr.rectangle(1.5, 1.5, w - 3, h - 3)
            _dashed_outline(cr)
        else:
            cr.set_source_rgba(*SCRIM)
            cr.paint()

    def _handles(self, cr, sel: Rect):
        size = 7
        for hx in (sel.x, sel.x + sel.w):
            for hy in (sel.y, sel.y + sel.h):
                cr.rectangle(hx - size / 2, hy - size / 2, size, size)
        cr.set_source_rgb(1, 1, 1)
        cr.fill_preserve()
        cr.set_source_rgba(0.06, 0.09, 0.16, 0.6)
        cr.set_line_width(1)
        cr.stroke()

    def _size_label(self, cr, sel: Rect, w, h):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription.from_string("Sans Semi-Bold 10"))
        size = f"{round(sel.w * self.image_scale)} × {round(sel.h * self.image_scale)}"
        layout.set_markup(f"{size}  <span foreground='#94A3B8' weight='normal'>· right-click to copy</span>", -1)
        tw, th = layout.get_pixel_size()
        pw, ph = tw + 16, th + 8
        gap = 8
        x = min(max(sel.x, 0), w - pw)
        y = sel.y - ph - gap if sel.y - ph - gap > 0 else min(sel.y + sel.h + gap, h - ph)
        _rounded(cr, x, y, pw, ph, 6)
        cr.set_source_rgba(*SURFACE)
        cr.fill()
        cr.set_source_rgb(0.95, 0.96, 0.98)
        cr.move_to(x + 8, y + 4)
        PangoCairo.show_layout(cr, layout)
