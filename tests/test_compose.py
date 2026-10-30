import io
import unittest

import cairo

from screen_capture.annotations import Blur, Rectangle, Style
from screen_capture.compose import render_png
from screen_capture.geometry import Rect

RED = Style((1, 0, 0, 1), 4)


def white(w, h):
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    return s


def decode(png: bytes) -> cairo.ImageSurface:
    return cairo.ImageSurface.create_from_png(io.BytesIO(png))


def rgb(s, x, y):
    s.flush()
    d = s.get_data()
    i = y * s.get_stride() + x * 4
    return d[i + 2], d[i + 1], d[i]


class ComposeTest(unittest.TestCase):
    def test_render_png_size_matches_selection_times_scale(self):
        out = decode(render_png(white(300, 200), Rect(10, 10, 100, 50), 1.5, []))
        self.assertEqual((out.get_width(), out.get_height()), (150, 75))

    def test_rectangle_annotation_changes_pixels_inside_crop(self):
        shapes = [Rectangle(Rect(20, 20, 40, 40), RED)]
        out = decode(render_png(white(100, 100), Rect(10, 10, 80, 80), 1.0, shapes))
        self.assertEqual(rgb(out, 10, 30), (255, 0, 0))  # left edge at x=20 -> 10 in crop
        self.assertEqual(rgb(out, 30, 30), (255, 255, 255))  # inside is not filled

    def test_annotation_scaled_with_image_scale(self):
        shapes = [Rectangle(Rect(20, 20, 40, 40), RED)]
        out = decode(render_png(white(200, 200), Rect(0, 0, 100, 100), 2.0, shapes))
        self.assertEqual(rgb(out, 40, 60), (255, 0, 0))

    def test_annotation_outside_selection_not_in_output(self):
        shapes = [Rectangle(Rect(70, 70, 20, 20), RED)]
        out = decode(render_png(white(100, 100), Rect(0, 0, 50, 50), 1.0, shapes))
        for x in range(50):
            for y in range(50):
                self.assertEqual(rgb(out, x, y), (255, 255, 255))

    def test_blur_pixelates_region(self):
        bd = cairo.ImageSurface(cairo.FORMAT_RGB24, 40, 40)
        cr = cairo.Context(bd)
        for x in range(40):  # 1px vertical black/white stripes
            cr.set_source_rgb(x % 2, x % 2, x % 2)
            cr.rectangle(x, 0, 1, 40)
            cr.fill()
        out = decode(render_png(bd, Rect(0, 0, 40, 40), 1.0, [Blur(Rect(0, 0, 20, 20), block=10)]))
        a, b = rgb(out, 2, 2), rgb(out, 3, 2)
        self.assertEqual(a, b)
        self.assertTrue(100 < a[0] < 155)
        self.assertNotEqual(rgb(out, 30, 30), rgb(out, 31, 30))  # outside blur untouched


class RenderSurfaceTest(unittest.TestCase):
    def test_render_surface_matches_png_output(self):
        from screen_capture.compose import render_surface

        shapes = [Rectangle(Rect(20, 20, 40, 40), RED)]
        surf = render_surface(white(100, 100), Rect(10, 10, 80, 80), 1.0, shapes)
        self.assertEqual((surf.get_width(), surf.get_height()), (80, 80))
        self.assertEqual(rgb(surf, 10, 30), (255, 0, 0))
