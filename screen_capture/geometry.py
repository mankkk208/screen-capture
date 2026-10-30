"""Pure geometry: monitors, selections and crop maths. Logical px vs image px."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class PixelRect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Monitor:
    name: str
    x: float  # logical position in the global desktop space
    y: float
    width: float  # logical size
    height: float
    scale: float


def monitor_at(monitors: list[Monitor], px: float, py: float) -> Monitor:
    for m in monitors:
        if m.x <= px < m.x + m.width and m.y <= py < m.y + m.height:
            return m
    # Pointer outside every monitor (e.g. on an edge): nearest by centre.
    return min(monitors, key=lambda m: (px - (m.x + m.width / 2)) ** 2 + (py - (m.y + m.height / 2)) ** 2)


def clamp_to_monitor(monitor: Monitor, r: Rect) -> Rect:
    x0 = min(max(r.x, 0), monitor.width)
    y0 = min(max(r.y, 0), monitor.height)
    x1 = min(max(r.x + r.w, 0), monitor.width)
    y1 = min(max(r.y + r.h, 0), monitor.height)
    return Rect(x0, y0, x1 - x0, y1 - y0)


def crop_rect(monitor: Monitor, sel: Rect, image_scale: float) -> PixelRect:
    """Map a monitor-local logical selection to a rect in the portal image.

    Edges are rounded independently so neighbouring regions never gain or lose a pixel.
    """
    left = round((monitor.x + sel.x) * image_scale)
    top = round((monitor.y + sel.y) * image_scale)
    right = round((monitor.x + sel.x + sel.w) * image_scale)
    bottom = round((monitor.y + sel.y + sel.h) * image_scale)
    return PixelRect(left, top, max(1, right - left), max(1, bottom - top))


def clamp_pixel_rect(p: PixelRect, width: int, height: int) -> PixelRect:
    """Keep a crop inside an image (rounding at fractional scales can overshoot by a pixel)."""
    x = min(max(p.x, 0), width - 1)
    y = min(max(p.y, 0), height - 1)
    return PixelRect(x, y, max(1, min(p.w, width - x)), max(1, min(p.h, height - y)))


def is_sliver(r: Rect, min_size: float = 4.0) -> bool:
    """A drag this thin is almost certainly a slip, not a region worth capturing."""
    return min(r.w, r.h) < min_size


def is_click(press: tuple[float, float], release: tuple[float, float], threshold: float = 5.0) -> bool:
    return (release[0] - press[0]) ** 2 + (release[1] - press[1]) ** 2 <= threshold**2
