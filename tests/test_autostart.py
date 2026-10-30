import tempfile
import unittest
from pathlib import Path

from screen_capture.autostart import DESKTOP_NAME, is_autostart_enabled, set_autostart


class AutostartTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "autostart"
        self.project = Path("/opt/screen-capture")

    def test_enable_writes_background_entry(self):
        path = set_autostart(True, self.dir, self.project)
        self.assertEqual(path, self.dir / DESKTOP_NAME)
        text = path.read_text()
        self.assertIn("Exec=python3 -m screen_capture --background", text)
        self.assertIn("Path=/opt/screen-capture", text)
        self.assertTrue(is_autostart_enabled(self.dir))

    def test_enable_twice_is_idempotent(self):
        set_autostart(True, self.dir, self.project)
        set_autostart(True, self.dir, self.project)
        self.assertEqual(len(list(self.dir.iterdir())), 1)

    def test_disable_removes_entry(self):
        set_autostart(True, self.dir, self.project)
        self.assertIsNone(set_autostart(False, self.dir, self.project))
        self.assertFalse(is_autostart_enabled(self.dir))

    def test_disable_when_absent_is_noop(self):
        self.assertIsNone(set_autostart(False, self.dir, self.project))
        self.assertFalse(is_autostart_enabled(self.dir))
