import tempfile
import unittest
from pathlib import Path
from unittest import mock

from screen_capture.config import Config, ConfigError
from screen_capture.pipeline import deliver
from screen_capture.upload import UploadError, upload_png

SENTINEL = "SENTINEL-TOKEN-123"


class FakeResp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.text = status, body, ""

    def json(self):
        return self._body


class DeliverTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.cfg = Config(token=SENTINEL, save_dir=self.dir / "failed")

    def test_success_returns_url(self):
        r = deliver(lambda: b"PNG", lambda: self.cfg, lambda png, cfg: "https://capture.avada.io/i/x")
        self.assertEqual(r, ("ok", "https://capture.avada.io/i/x"))

    def test_unexpected_upload_error_saves_image_and_hides_details(self):
        def boom(png, cfg):
            raise UnicodeEncodeError("latin-1", SENTINEL, 0, 1, "bad header")

        status, message = deliver(lambda: b"PNG", lambda: self.cfg, boom)
        self.assertEqual(status, "failed")
        self.assertNotIn(SENTINEL, message)
        self.assertTrue(any((self.dir / "failed").iterdir()))

    def test_config_error_saves_to_default_dir(self):
        def no_cfg():
            raise ConfigError("upload token not configured")

        with mock.patch("screen_capture.pipeline.DEFAULT_SAVE_DIR", self.dir / "default"):
            status, message = deliver(lambda: b"PNG", no_cfg, self.fail)
        self.assertEqual(status, "failed")
        self.assertIn("token not configured", message)
        self.assertTrue(any((self.dir / "default").iterdir()))

    def test_unwritable_save_dir_falls_back_to_tmp(self):
        bad = Config(token=SENTINEL, save_dir=Path("/proc/screen-capture-cannot-write"))

        def fail(png, cfg):
            raise UploadError("network error: cannot reach the upload server")

        with mock.patch("screen_capture.pipeline.FALLBACK_DIR", self.dir / "fallback"):
            status, message = deliver(lambda: b"PNG", lambda: bad, fail)
        self.assertEqual(status, "failed")
        self.assertIn(str(self.dir / "fallback"), message)

    def test_render_failure_reports_without_crashing(self):
        def bad_render():
            raise MemoryError()

        status, message = deliver(bad_render, lambda: self.cfg, self.fail)
        self.assertEqual(status, "failed")
        self.assertIn("could not create", message.lower())


class RedirectTest(unittest.TestCase):
    def test_upload_does_not_follow_redirects(self):
        calls = []

        class S:
            def post(self, url, **kw):
                calls.append(kw)
                return FakeResp(302)

        with self.assertRaises(UploadError):
            upload_png(b"PNG", Config(token=SENTINEL), session=S())
        self.assertIs(calls[0]["allow_redirects"], False)


class ReentrancyTest(unittest.TestCase):
    def test_second_activation_during_capture_does_not_stack_sessions(self):
        from screen_capture import app as app_mod

        a = app_mod.CaptureApp()
        created = []

        class FakeSession:
            def __init__(self, *args, **kw):
                self.closed = False
                created.append(self)

            def present(self):
                pass

        def capture(monitors):
            a.start_session()  # D-Bus Activate arriving inside the nested main loop
            return {}

        with mock.patch.object(app_mod, "capture_backdrops", capture), \
                mock.patch.object(app_mod, "CaptureSession", FakeSession), \
                mock.patch.object(a, "_monitors", lambda: []):
            a.start_session()
        self.assertEqual(len(created), 1)


class FocusTest(unittest.TestCase):
    def test_upload_finishing_during_open_capture_does_not_show_toast(self):
        from screen_capture import app as app_mod

        a = app_mod.CaptureApp()
        a.session = mock.Mock(closed=False)
        with mock.patch.object(app_mod, "show_toast") as toast, \
                mock.patch.object(app_mod, "notify") as note, \
                mock.patch.object(app_mod, "_set_clipboard_text") as clip:
            a._uploaded("https://capture.avada.io/i/x")
        toast.assert_not_called()
        clip.assert_called_once_with("https://capture.avada.io/i/x")
        note.assert_called_once()


class CopyFailureTest(unittest.TestCase):
    def test_finish_copy_closes_overlay_even_if_copy_fails(self):
        from screen_capture.geometry import Monitor, Rect
        from screen_capture.overlay import CaptureSession

        s = CaptureSession.__new__(CaptureSession)  # no GTK windows needed for this path
        s.closed, s.windows = False, []
        s.histories = {"eDP-1": mock.Mock(shapes=[])}
        s.on_copy = mock.Mock(side_effect=RuntimeError("clipboard broke"))
        s.on_copy_failed = mock.Mock()
        s.finish(Monitor("eDP-1", 0, 0, 10, 10, 1.0), Rect(0, 0, 5, 5), copy=True)
        self.assertTrue(s.closed)
        s.on_copy_failed.assert_called_once()


class ClipboardContentTest(unittest.TestCase):
    def test_image_clipboard_content_offers_png(self):
        import cairo

        from screen_capture.overlay import image_clipboard_content

        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 8, 4)
        formats = image_clipboard_content(surface).ref_formats().union_serialize_mime_types()
        self.assertTrue(formats.contain_mime_type("image/png"))
