"""Frosted dark toolbar shown at the top-centre of every overlay.

Design tokens come from the ui-ux-pro-max design system for this project (Minimalism/Swiss,
dark slate palette, frosted-glass surface); the accent stays blue per the owner's spec.
"""
import colorsys
import math

import gi

gi.require_foreign("cairo")
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from .icons import ICON_FOR, icon_svg  # noqa: E402

TOOLS = [
    # (tool id, key, tooltip)
    ("select", "S", "Select / capture"),
    ("arrow", "A", "Arrow"),
    ("line", "L", "Line"),
    ("rect", "R", "Rectangle"),
    ("ellipse", "C", "Circle"),
    ("pen", "P", "Pen"),
    ("text", "T", "Text"),
    ("highlighter", "H", "Highlighter"),
    ("step", "N", "Numbered step"),
    ("blur", "B", "Blur / hide"),
]
KEY_TO_TOOL = {key.lower(): tool for tool, key, _tip in TOOLS}

RED = (0.94, 0.27, 0.27, 1)  # red-500 #EF4444, the default annotation colour
WIDTHS = [2.0, 4.0, 8.0]
WIDTH_NAMES = {2.0: "Thin", 4.0: "Medium", 8.0: "Thick"}

FG = "#F1F5F9"
ICON_PX = 20

CSS = b"""
@define-color sc_surface rgba(15, 23, 42, 0.88);
@define-color sc_border rgba(148, 163, 184, 0.20);
@define-color sc_fg #F1F5F9;
@define-color sc_muted #94A3B8;
@define-color sc_accent #3B82F6;
@define-color sc_hover rgba(148, 163, 184, 0.16);

.sc-overlay-window { background-color: black; }

.sc-toolbar {
  background-color: @sc_surface;
  border: 1px solid @sc_border;
  border-radius: 16px;
  padding: 6px;
  margin-top: 16px;
  box-shadow: 0 12px 40px rgba(2, 6, 23, 0.55), 0 2px 6px rgba(2, 6, 23, 0.35);
}
.sc-toolbar button {
  min-width: 36px; min-height: 36px; padding: 0; margin: 0 1px;
  border-radius: 10px; border: none; box-shadow: none; outline: none;
  background-color: transparent; background-image: none; color: @sc_fg;
  text-shadow: none; -gtk-icon-shadow: none;
  transition: background-color 150ms ease-out, opacity 150ms ease-out;
}
.sc-toolbar button:hover { background-color: @sc_hover; background-image: none; }
.sc-toolbar button:active { background-color: rgba(148, 163, 184, 0.26); }
.sc-toolbar button.active { background-color: @sc_accent; box-shadow: 0 2px 10px rgba(59, 130, 246, 0.45); }
.sc-toolbar button:disabled { opacity: 0.35; }
.sc-toolbar button.swatch { min-width: 28px; }
.sc-toolbar button.close:hover { background-color: rgba(239, 68, 68, 0.85); }
.sc-picker > contents { background-color: rgba(15, 23, 42, 0.96); border: 1px solid @sc_border;
  border-radius: 14px; padding: 10px; color: @sc_fg; }
.sc-toolbar .sep { background-color: @sc_border; min-width: 1px; margin: 8px 6px; }

.sc-hint {
  background-color: @sc_surface;
  border: 1px solid @sc_border;
  border-radius: 12px;
  padding: 8px 14px;
  margin-bottom: 28px;
  color: @sc_muted;
  font-size: 13px;
  box-shadow: 0 8px 28px rgba(2, 6, 23, 0.5);
}
.sc-hint .em { color: @sc_fg; font-weight: 600; }
.sc-hint .kbd {
  color: @sc_fg; font-size: 12px; font-weight: 600;
  background-color: rgba(148, 163, 184, 0.18);
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 6px; padding: 1px 7px;
}

.sc-text-entry, .sc-text-entry text {
  background: none; border: none; box-shadow: none; outline: none;
  font-weight: bold; padding: 0; margin: 0; min-height: 0;
}

.sc-toast-window { background: transparent; }
.sc-toast {
  background-color: rgba(15, 23, 42, 0.94);
  border: 1px solid @sc_border;
  border-radius: 16px;
  padding: 12px 18px 12px 12px;
  box-shadow: 0 12px 40px rgba(2, 6, 23, 0.55);
}
.sc-toast .badge { background-color: #22C55E; border-radius: 999px; min-width: 32px; min-height: 32px; }
.sc-toast .title { color: @sc_fg; font-weight: 600; font-size: 15px; }
.sc-toast .url { color: @sc_muted; font-size: 12px; }
"""


def _to_gdk(rgba) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = rgba
    return c


def icon_image(name: str, scale: int = 1, color: str = FG, px: int = ICON_PX) -> Gtk.Image:
    """Lucide SVG rendered at the monitor's scale so it stays crisp on HiDPI."""
    size = px * max(1, scale)
    svg = icon_svg(ICON_FOR[name], color).replace(b'width="24"', f'width="{size}"'.encode(), 1)
    svg = svg.replace(b'height="24"', f'height="{size}"'.encode(), 1)
    texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(svg))
    image = Gtk.Image.new_from_paintable(texture)
    image.set_pixel_size(px)
    return image


def _drawn(draw, width=24, height=24) -> Gtk.DrawingArea:
    area = Gtk.DrawingArea()
    area.set_content_width(width)
    area.set_content_height(height)
    area.set_draw_func(lambda _a, cr, w, h: draw(cr, w, h))
    area.set_can_target(False)
    return area


class Toolbar(Gtk.Box):
    """Callbacks: on_tool(id), on_color(rgba), on_width(float), on_undo(), on_redo(), on_close()."""

    def __init__(self, on_tool, on_color, on_width, on_undo, on_redo, on_close, scale: int = 1):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add_css_class("sc-toolbar")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        self.set_cursor_from_name("default")
        self._tool_buttons: dict[str, Gtk.Button] = {}
        self._swatches: list[Gtk.DrawingArea] = []
        self._width_marks: list[Gtk.DrawingArea] = []
        self._color = RED
        self._width = WIDTHS[1]

        for tool, key, tip in TOOLS:
            btn = self._button(icon_image(tool, scale), f"{tip}  ·  {key}", lambda t=tool: on_tool(t))
            self._tool_buttons[tool] = btn

        self._sep()
        red = _drawn(lambda cr, w, h: self._draw_swatch(cr, w, h, RED), 20, 24)
        self._button(red, "Red", lambda: on_color(RED)).add_css_class("swatch")
        self._swatches.append(red)

        # Custom colour: rainbow ring around the current custom colour; opens an RGB editor.
        self._custom = (0.23, 0.51, 0.96, 1)
        ring = _drawn(self._draw_picker, 24, 24)
        self._swatches.append(ring)
        self._picker = Gtk.MenuButton(child=ring, focusable=False, always_show_arrow=False)
        self._picker.set_tooltip_text("Pick a colour")
        self._picker.update_property([Gtk.AccessibleProperty.LABEL], ["Pick a colour"])
        self._picker.set_cursor_from_name("pointer")
        self._picker.add_css_class("swatch")
        chooser = Gtk.ColorChooserWidget(show_editor=True, use_alpha=False)
        chooser.set_rgba(_to_gdk(self._custom))

        def on_pick(widget, _pspec):
            c = widget.get_rgba()
            self._custom = (c.red, c.green, c.blue, 1)
            on_color(self._custom)

        chooser.connect("notify::rgba", on_pick)
        popover = Gtk.Popover(child=chooser)
        popover.add_css_class("sc-picker")
        self._picker.set_popover(popover)
        self.append(self._picker)

        self._sep()
        for width in WIDTHS:
            mark = _drawn(lambda cr, w, h, wd=width: self._draw_width(cr, w, h, wd))
            self._button(mark, WIDTH_NAMES[width], lambda wd=width: on_width(wd))
            self._width_marks.append(mark)

        self._sep()
        self._undo = self._button(icon_image("undo", scale), "Undo  ·  Ctrl+Z", on_undo)
        self._redo = self._button(icon_image("redo", scale), "Redo  ·  Ctrl+Shift+Z", on_redo)
        self._sep()
        close = self._button(icon_image("close", scale), "Cancel  ·  Esc", on_close)
        close.add_css_class("close")

    def _button(self, child, tooltip: str, callback) -> Gtk.Button:
        btn = Gtk.Button()
        btn.set_child(child)
        btn.set_tooltip_text(tooltip)
        btn.set_focusable(False)
        btn.set_cursor_from_name("pointer")
        btn.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
        btn.connect("clicked", lambda _b: callback())
        self.append(btn)
        return btn

    def _sep(self):
        sep = Gtk.Box()
        sep.add_css_class("sep")
        self.append(sep)

    def _draw_swatch(self, cr, w, h, rgba):
        selected = rgba == self._color
        cx, cy, r = w / 2, h / 2, 7.0
        if selected:
            cr.set_source_rgb(0.95, 0.96, 0.98)
            cr.set_line_width(2)
            cr.arc(cx, cy, r + 3, 0, 2 * math.pi)
            cr.stroke()
        cr.set_source_rgba(*rgba)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()
        # Hairline so white/black stay visible against the slate surface (non-text contrast).
        dark = sum(rgba[:3]) < 1.0
        cr.set_source_rgba(1, 1, 1, 0.6 if dark else 0.25)
        cr.set_line_width(1.5 if dark else 1)
        cr.arc(cx, cy, r - 0.5, 0, 2 * math.pi)
        cr.stroke()

    def _draw_picker(self, cr, w, h):
        cx, cy = w / 2, h / 2
        for i in range(36):  # hue wheel ring
            r, g, b = colorsys.hsv_to_rgb(i / 36, 0.85, 1.0)
            cr.set_source_rgb(r, g, b)
            cr.set_line_width(3)
            cr.arc(cx, cy, 9, i / 36 * 2 * math.pi, (i + 1.2) / 36 * 2 * math.pi)
            cr.stroke()
        selected = self._color == self._custom
        cr.set_source_rgba(*self._custom)
        cr.arc(cx, cy, 5.5 if selected else 4.5, 0, 2 * math.pi)
        cr.fill()
        if selected:
            cr.set_source_rgb(0.95, 0.96, 0.98)
            cr.set_line_width(1.5)
            cr.arc(cx, cy, 5.5, 0, 2 * math.pi)
            cr.stroke()

    @property
    def picker_open(self) -> bool:
        return self._picker.get_active()

    def _draw_width(self, cr, w, h, width):
        selected = width == self._width
        cr.set_source_rgba(0.95, 0.96, 0.98, 1 if selected else 0.5)
        cr.set_line_cap(1)  # round
        cr.set_line_width(width if width < 8 else 7)
        cr.move_to(5, h / 2)
        cr.line_to(w - 5, h / 2)
        cr.stroke()

    def update(self, tool: str, color, width: float, can_undo: bool, can_redo: bool) -> None:
        for t, btn in self._tool_buttons.items():
            if t == tool:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")
        self._color, self._width = color, width
        for mark in self._swatches + self._width_marks:
            mark.queue_draw()
        self._undo.set_sensitive(can_undo)
        self._redo.set_sensitive(can_redo)
