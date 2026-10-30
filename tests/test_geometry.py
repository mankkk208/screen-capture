import unittest

from screen_capture.geometry import (
    Monitor, PixelRect, Rect, clamp_to_monitor, crop_rect, is_click, monitor_at,
)

EDP = Monitor("eDP-1", 0, 0, 1920, 1080, 1.0)
HDMI = Monitor("HDMI-1", 1920, 0, 2560, 1440, 1.5)


class GeometryTest(unittest.TestCase):
    def test_monitor_at_picks_right_monitor(self):
        self.assertIs(monitor_at([EDP, HDMI], 100, 100), EDP)
        self.assertIs(monitor_at([EDP, HDMI], 2000, 100), HDMI)

    def test_clamp_to_monitor_clips_drag_leaving_monitor(self):
        r = clamp_to_monitor(EDP, Rect(1800, 1000, 400, 300))
        self.assertEqual((r.x, r.y, r.w, r.h), (1800, 1000, 120, 80))
        r = clamp_to_monitor(EDP, Rect(-50, -10, 100, 100))
        self.assertEqual((r.x, r.y, r.w, r.h), (0, 0, 50, 90))

    def test_crop_rect_fractional_scale(self):
        m = Monitor("m", 0, 0, 1000, 1000, 1.5)
        self.assertEqual(crop_rect(m, Rect(10, 20, 100, 50), 1.5), PixelRect(15, 30, 150, 75))

    def test_crop_rect_offset_monitor(self):
        p = crop_rect(HDMI, Rect(0, 0, 10, 10), 1.5)
        self.assertEqual(p.x, round(1920 * 1.5))

    def test_crop_rect_rounds_to_whole_pixels_and_never_zero_size(self):
        p = crop_rect(EDP, Rect(10.4, 10.4, 0.1, 0.1), 1.0)
        self.assertIsInstance(p.x, int)
        self.assertGreaterEqual(p.w, 1)
        self.assertGreaterEqual(p.h, 1)

    def test_adjacent_regions_share_no_gap(self):
        a = crop_rect(EDP, Rect(0, 0, 10.5, 10), 1.5)
        b = crop_rect(EDP, Rect(10.5, 0, 10, 10), 1.5)
        self.assertEqual(a.x + a.w, b.x)

    def test_is_click_within_threshold_true(self):
        self.assertTrue(is_click((100, 100), (103, 102)))

    def test_is_click_beyond_threshold_false(self):
        self.assertFalse(is_click((100, 100), (120, 100)))
