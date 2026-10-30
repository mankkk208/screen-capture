"""Build the final image: backdrop crop + annotations -> PNG bytes."""
import io

import cairo

from .geometry import Monitor, Rect, crop_rect


def render_surface(backdrop: cairo.ImageSurface, sel: Rect, image_scale: float, shapes: list) -> cairo.ImageSurface:
    """`backdrop` is one monitor's pixels; `sel` and shapes are monitor-local logical coordinates."""
    origin = Monitor("", 0, 0, backdrop.get_width() / image_scale, backdrop.get_height() / image_scale, image_scale)
    p = crop_rect(origin, sel, image_scale)
    out = cairo.ImageSurface(cairo.FORMAT_RGB24, p.w, p.h)
    cr = cairo.Context(out)
    cr.translate(-p.x, -p.y)
    cr.set_source_surface(backdrop, 0, 0)
    cr.paint()
    cr.scale(image_scale, image_scale)
    for shape in shapes:
        cr.save()
        shape.draw(cr, backdrop=backdrop, image_scale=image_scale)
        cr.restore()
    out.flush()
    return out


def render_png(backdrop: cairo.ImageSurface, sel: Rect, image_scale: float, shapes: list) -> bytes:
    buf = io.BytesIO()
    render_surface(backdrop, sel, image_scale, shapes).write_to_png(buf)
    return buf.getvalue()
