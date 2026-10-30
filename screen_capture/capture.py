"""Backdrop capture: ScreenCast first (no flash, ~70 ms), portal screenshot as fallback."""
import cairo

from .geometry import Monitor, Rect, crop_rect
from .portal import ScreenshotError


def surface_from_bgrx(data: bytes, width: int, height: int, stride: int) -> cairo.ImageSurface:
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    dst_stride = surface.get_stride()
    dst = surface.get_data()
    row = width * 4
    for y in range(height):
        dst[y * dst_stride: y * dst_stride + row] = data[y * stride: y * stride + row]
    surface.mark_dirty()
    return surface


def _crop(src: cairo.ImageSurface, x: int, y: int, w: int, h: int) -> cairo.ImageSurface:
    out = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    cr = cairo.Context(out)
    cr.set_source_surface(src, -x, -y)
    cr.paint()
    return out


def _portal_surface() -> cairo.ImageSurface:
    from .portal import take_screenshot

    path = take_screenshot()
    try:
        return cairo.ImageSurface.create_from_png(str(path))
    finally:
        path.unlink(missing_ok=True)


def _screencast(monitors):
    try:
        from .screencast import grab_monitors
    except (ImportError, ValueError) as e:  # GStreamer typelib missing: use the portal instead
        raise ScreenshotError(f"screencast unavailable: {e}") from None

    return grab_monitors(monitors)


def capture_backdrops(monitors: list[Monitor], screencast=_screencast, portal=_portal_surface) -> dict:
    """Return {monitor.name: cairo.ImageSurface} holding exactly that monitor's pixels."""
    try:
        return screencast(monitors)
    except ScreenshotError:
        pass
    desktop = portal()
    left = min(m.x for m in monitors)
    top = min(m.y for m in monitors)
    image_scale = desktop.get_width() / (max(m.x + m.width for m in monitors) - left)
    out = {}
    for m in monitors:
        p = crop_rect(m, Rect(-left, -top, m.width, m.height), image_scale)
        out[m.name] = _crop(desktop, p.x, p.y, p.w, p.h)
    return out
