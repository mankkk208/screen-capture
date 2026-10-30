import unittest

from screen_capture.icons import ICON_FOR, icon_svg
from screen_capture.toolbar import TOOLS


class IconTest(unittest.TestCase):
    def test_every_tool_and_action_has_an_icon_file(self):
        for tool, _key, _tip in TOOLS:
            self.assertIn(b"<svg", icon_svg(ICON_FOR[tool], "#ffffff"))
        for action in ("undo", "redo", "close", "check"):
            self.assertIn(b"<svg", icon_svg(ICON_FOR[action], "#ffffff"))

    def test_icon_svg_recolored(self):
        svg = icon_svg(ICON_FOR["arrow"], "#f1f5f9")
        self.assertNotIn(b"currentColor", svg)
        self.assertIn(b'stroke="#f1f5f9"', svg)
