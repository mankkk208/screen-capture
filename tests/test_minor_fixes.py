import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cairo

from screen_capture.capture import capture_backdrops
from screen_capture.config import Config, load_config
from screen_capture.geometry import Monitor, PixelRect, Rect, clamp_pixel_rect, is_sliver
from screen_capture.screencast_geometry import record_area_rect
from screen_capture.upload import save_failed


class RecordAreaTest(unittest.TestCase):  # M1
    def test_logical_layout_uses_logical_size(self):
        m = Monitor("eDP-1", 0, 0, 1920, 1080, 2.0)
        self.assertEqual(record_area_rect(m, physical_layout=False), (0, 0, 1920, 1080))

    def test_physical_layout_scales_size_to_stage_pixels(self):
        m = Monitor("eDP-1", 3840, 0, 1920, 1080, 2.0)
        self.assertEqual(record_area_rect(m, physical_layout=True), (3840, 0, 3840, 2160))


class ClampTest(unittest.TestCase):  # M2
    def test_crop_never_exceeds_backdrop(self):
        self.assertEqual(clamp_pixel_rect(PixelRect(0, 0, 1921, 1081), 1920, 1080), PixelRect(0, 0, 1920, 1080))

    def test_render_full_monitor_at_odd_scale_has_no_black_row(self):
        from screen_capture.compose import render_surface

        bd = cairo.ImageSurface(cairo.FORMAT_RGB24, 1800, 1012)
        cr = cairo.Context(bd)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        out = render_surface(bd, Rect(0, 0, 1200, 675.4), 1.5, [])  # 675.4 * 1.5 rounds to 1013 > 1012
        self.assertEqual((out.get_width(), out.get_height()), (1800, 1012))


class SliverTest(unittest.TestCase):  # M3
    def test_thin_drag_is_sliver(self):
        self.assertTrue(is_sliver(Rect(0, 0, 300, 2)))
        self.assertTrue(is_sliver(Rect(0, 0, 3, 200)))

    def test_normal_region_is_not_sliver(self):
        self.assertFalse(is_sliver(Rect(0, 0, 40, 30)))


class ScreencastImportTest(unittest.TestCase):  # M4
    def test_missing_gstreamer_falls_back_to_portal(self):
        desktop = cairo.ImageSurface(cairo.FORMAT_RGB24, 4, 2)
        with mock.patch.dict(sys.modules, {"screen_capture.screencast": None}):
            got = capture_backdrops([Monitor("eDP-1", 0, 0, 4, 2, 1.0)], portal=lambda: desktop)
        self.assertEqual(got["eDP-1"].get_width(), 4)


class SaveRaceTest(unittest.TestCase):  # M5
    def test_save_failed_never_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(token="", save_dir=Path(tmp))
            with mock.patch("screen_capture.upload.time.strftime", return_value="capture-same"):
                first = save_failed(b"first", cfg)
                with mock.patch.object(Path, "exists", return_value=False):  # lose the check-then-write race
                    second = save_failed(b"second", cfg)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), b"first")


class BrokenFlameshotTest(unittest.TestCase):  # M7
    def test_own_token_works_even_if_flameshot_ini_is_broken(self):
        tmp = Path(tempfile.mkdtemp())
        own = tmp / "config.ini"
        own.write_text("[General]\ntoken=own-token\n")
        fs = tmp / "flameshot.ini"
        fs.write_text("[General]\na=1\n[General]\na=2\n")  # duplicate section: configparser error
        self.assertEqual(load_config(own, fs).token, "own-token")
