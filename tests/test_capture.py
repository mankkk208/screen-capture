import unittest

import cairo

from screen_capture.capture import capture_backdrops, surface_from_bgrx
from screen_capture.geometry import Monitor
from screen_capture.portal import ScreenshotError

EDP = Monitor("eDP-1", 0, 0, 4, 2, 1.0)
HDMI = Monitor("HDMI-1", 4, 0, 4, 2, 1.0)


def solid(w, h, rgb):
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgb(*rgb)
    cr.paint()
    return s


def pixel(s, x, y):
    s.flush()
    d = s.get_data()
    i = y * s.get_stride() + x * 4
    return d[i + 2], d[i + 1], d[i]  # BGRx little endian -> RGB


class CaptureTest(unittest.TestCase):
    def test_surface_from_bgrx_keeps_pixels(self):
        w, h, stride = 2, 1, 8
        data = bytes([0, 0, 255, 0, 255, 0, 0, 0])  # red, blue
        s = surface_from_bgrx(data, w, h, stride)
        self.assertEqual((s.get_width(), s.get_height()), (2, 1))
        self.assertEqual(pixel(s, 0, 0), (255, 0, 0))
        self.assertEqual(pixel(s, 1, 0), (0, 0, 255))

    def test_screencast_used_when_it_works(self):
        surfaces = {"eDP-1": solid(4, 2, (1, 0, 0)), "HDMI-1": solid(4, 2, (0, 1, 0))}
        got = capture_backdrops([EDP, HDMI], screencast=lambda ms: surfaces, portal=self.fail)
        self.assertIs(got["HDMI-1"], surfaces["HDMI-1"])

    def test_falls_back_to_portal_and_crops_per_monitor(self):
        def broken(ms):
            raise ScreenshotError("no screencast")

        desktop = cairo.ImageSurface(cairo.FORMAT_RGB24, 8, 2)
        cr = cairo.Context(desktop)
        cr.set_source_rgb(1, 0, 0)
        cr.rectangle(0, 0, 4, 2)
        cr.fill()
        cr.set_source_rgb(0, 0, 1)
        cr.rectangle(4, 0, 4, 2)
        cr.fill()
        got = capture_backdrops([EDP, HDMI], screencast=broken, portal=lambda: desktop)
        self.assertEqual(got["eDP-1"].get_width(), 4)
        self.assertEqual(pixel(got["eDP-1"], 3, 1), (255, 0, 0))
        self.assertEqual(pixel(got["HDMI-1"], 0, 0), (0, 0, 255))

    def test_both_paths_failing_raises(self):
        def broken(*a):
            raise ScreenshotError("x")

        with self.assertRaises(ScreenshotError):
            capture_backdrops([EDP], screencast=broken, portal=broken)
