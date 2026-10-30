"""Annotation shapes, drawn with Cairo in monitor-local logical coordinates."""
import math
from dataclasses import dataclass, field

import cairo

from .geometry import Rect

Point = tuple[float, float]


@dataclass(frozen=True)
class Style:
    color: tuple[float, float, float, float]
    width: float


def _stroke(cr: cairo.Context, style: Style, width: float | None = None) -> None:
    cr.set_source_rgba(*style.color)
    cr.set_line_width(width or style.width)
    cr.stroke()


@dataclass
class Line:
    p0: Point
    p1: Point
    style: Style

    def draw(self, cr, backdrop=None, image_scale=1.0):
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(*self.p0)
        cr.line_to(*self.p1)
        _stroke(cr, self.style)


@dataclass
class Arrow:
    p0: Point
    p1: Point
    style: Style

    def draw(self, cr, backdrop=None, image_scale=1.0):
        (x0, y0), (x1, y1) = self.p0, self.p1
        angle = math.atan2(y1 - y0, x1 - x0)
        head = max(12.0, self.style.width * 4)
        spread = math.radians(25)
        # Stop the shaft inside the head so the round cap doesn't poke through the tip.
        bx, by = x1 - math.cos(angle) * head * 0.8, y1 - math.sin(angle) * head * 0.8
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(x0, y0)
        cr.line_to(bx, by)
        _stroke(cr, self.style)
        cr.move_to(x1, y1)
        cr.line_to(x1 - head * math.cos(angle - spread), y1 - head * math.sin(angle - spread))
        cr.line_to(x1 - head * math.cos(angle + spread), y1 - head * math.sin(angle + spread))
        cr.close_path()
        cr.set_source_rgba(*self.style.color)
        cr.fill()


@dataclass
class Rectangle:
    rect: Rect
    style: Style

    def draw(self, cr, backdrop=None, image_scale=1.0):
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.rectangle(self.rect.x, self.rect.y, self.rect.w, self.rect.h)
        _stroke(cr, self.style)


@dataclass
class Ellipse:
    rect: Rect
    style: Style

    def draw(self, cr, backdrop=None, image_scale=1.0):
        r = self.rect
        if r.w == 0 or r.h == 0:
            return
        cr.save()
        cr.translate(r.x + r.w / 2, r.y + r.h / 2)
        cr.scale(r.w / 2, r.h / 2)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()  # stroke in unscaled space so the line width stays uniform
        _stroke(cr, self.style)


@dataclass
class Pen:
    points: list[Point]
    style: Style

    def _path(self, cr):
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.move_to(*self.points[0])
        for p in self.points[1:]:
            cr.line_to(*p)
        if len(self.points) == 1:
            cr.line_to(*self.points[0])

    def draw(self, cr, backdrop=None, image_scale=1.0):
        if self.points:
            self._path(cr)
            _stroke(cr, self.style)


@dataclass
class Highlighter(Pen):
    def draw(self, cr, backdrop=None, image_scale=1.0):
        if not self.points:
            return
        self._path(cr)
        r, g, b, _a = self.style.color
        cr.set_source_rgba(r, g, b, 0.35)
        cr.set_line_width(max(14.0, self.style.width * 5))
        cr.stroke()


def font_size(style: Style) -> float:
    return max(16.0, style.width * 6)


@dataclass
class Text:
    pos: Point
    text: str
    style: Style

    def draw(self, cr, backdrop=None, image_scale=1.0):
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(font_size(self.style))
        cr.set_source_rgba(*self.style.color)
        cr.move_to(self.pos[0], self.pos[1] + font_size(self.style))
        cr.show_text(self.text)


@dataclass
class Step:
    center: Point
    number: int
    style: Style

    def draw(self, cr, backdrop=None, image_scale=1.0):
        radius = max(13.0, self.style.width * 4)
        x, y = self.center
        cr.arc(x, y, radius, 0, 2 * math.pi)
        cr.set_source_rgba(*self.style.color)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 1)
        cr.set_line_width(2)
        cr.stroke()
        label = str(self.number)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(radius * 1.1)
        ext = cr.text_extents(label)
        cr.move_to(x - ext.width / 2 - ext.x_bearing, y - ext.height / 2 - ext.y_bearing)
        cr.show_text(label)


@dataclass
class Blur:
    """Pixelates the backdrop under `rect` (hides customer data)."""

    rect: Rect
    block: int = 10
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    def _small(self, backdrop: cairo.ImageSurface, image_scale: float) -> cairo.ImageSurface:
        key = (id(backdrop), image_scale)
        if key not in self._cache:
            r = self.rect
            px, py = r.x * image_scale, r.y * image_scale
            pw, ph = max(1.0, r.w * image_scale), max(1.0, r.h * image_scale)
            block = self.block * image_scale
            sw, sh = max(1, math.ceil(pw / block)), max(1, math.ceil(ph / block))
            small = cairo.ImageSurface(cairo.FORMAT_RGB24, sw, sh)
            scr = cairo.Context(small)
            scr.scale(sw / pw, sh / ph)
            scr.set_source_surface(backdrop, -px, -py)
            scr.get_source().set_filter(cairo.FILTER_GOOD)  # box-averages when downscaling
            scr.paint()
            self._cache.clear()
            self._cache[key] = small
        return self._cache[key]

    def draw(self, cr, backdrop=None, image_scale=1.0):
        r = self.rect
        if backdrop is None or r.w <= 0 or r.h <= 0:
            return
        small = self._small(backdrop, image_scale)
        cr.save()
        cr.rectangle(r.x, r.y, r.w, r.h)
        cr.clip()
        cr.translate(r.x, r.y)
        cr.scale(r.w / small.get_width(), r.h / small.get_height())
        cr.set_source_surface(small, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_NEAREST)
        cr.paint()
        cr.restore()


class History:
    def __init__(self):
        self._done: list = []
        self._undone: list = []

    @property
    def shapes(self) -> list:
        return list(self._done)

    @property
    def can_undo(self) -> bool:
        return bool(self._done)

    @property
    def can_redo(self) -> bool:
        return bool(self._undone)

    def add(self, shape) -> None:
        self._done.append(shape)
        self._undone.clear()

    def undo(self) -> None:
        if self._done:
            self._undone.append(self._done.pop())

    def redo(self) -> None:
        if self._undone:
            self._done.append(self._undone.pop())

    def next_step_number(self) -> int:
        return sum(isinstance(s, Step) for s in self._done) + 1
