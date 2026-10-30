import tempfile
import unittest
from pathlib import Path

import requests

from screen_capture.config import Config
from screen_capture.upload import UploadError, parse_url, save_failed, upload_png

SENTINEL = "SENTINEL-TOKEN-123"


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.exc:
            raise self.exc
        return self.response


def cfg(tmp=None):
    return Config(token=SENTINEL, save_dir=Path(tmp or tempfile.mkdtemp()))


class UploadTest(unittest.TestCase):
    def test_upload_sends_image_field_and_token_header(self):
        s = FakeSession(FakeResponse(200, {"url": "https://capture.avada.io/x.png"}))
        try:
            upload_png(b"PNG", cfg(), session=s)
        except UploadError:
            pass  # parse_url may not know this shape; the request is what is under test
        url, kw = s.calls[0]
        self.assertEqual(url, "https://capture-api.avada.io/api/v1/upload")
        self.assertIn("image", kw["files"])
        self.assertEqual(kw["headers"]["X-Avada-Token"], SENTINEL)
        self.assertIn("timeout", kw)

    def test_401_raises_uploaderror_without_token_in_message(self):
        s = FakeSession(FakeResponse(401, {"error": f"bad token {SENTINEL}"}))
        with self.assertRaises(UploadError) as ctx:
            upload_png(b"PNG", cfg(), session=s)
        self.assertIn("token", str(ctx.exception).lower())
        self.assertNotIn(SENTINEL, str(ctx.exception))

    def test_500_raises_server_error(self):
        s = FakeSession(FakeResponse(503, "down"))
        with self.assertRaises(UploadError) as ctx:
            upload_png(b"PNG", cfg(), session=s)
        self.assertIn("server", str(ctx.exception).lower())

    def test_timeout_raises_network_error(self):
        s = FakeSession(exc=requests.Timeout(f"timed out {SENTINEL}"))
        with self.assertRaises(UploadError) as ctx:
            upload_png(b"PNG", cfg(), session=s)
        self.assertIn("network", str(ctx.exception).lower())
        self.assertNotIn(SENTINEL, str(ctx.exception))

    def test_save_failed_writes_png_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = save_failed(b"\x89PNG", cfg(Path(tmp) / "sub"))
            self.assertTrue(path.exists())
            self.assertEqual(path.suffix, ".png")
            self.assertEqual(path.read_bytes(), b"\x89PNG")

    def test_save_failed_twice_same_second_keeps_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = cfg(tmp)
            self.assertNotEqual(save_failed(b"a", c), save_failed(b"b", c))

    def test_parse_url_unexpected_shape_raises(self):
        for body in ({}, [], "x", {"data": {}}, None):
            with self.assertRaises(UploadError):
                parse_url(body)


class ParseRealShapeTest(unittest.TestCase):
    def test_parse_url_real_shape(self):
        body = {"success": True, "url": "https://capture.avada.io/i/abc123", "imageId": "abc123",
                "width": 1, "height": 1, "bytes": 44}
        self.assertEqual(parse_url(body), "https://capture.avada.io/i/abc123")

    def test_parse_url_success_false_raises(self):
        with self.assertRaises(UploadError):
            parse_url({"success": False, "url": "https://capture.avada.io/i/x"})

    def test_upload_returns_url_from_real_shape(self):
        s = FakeSession(FakeResponse(200, {"success": True, "url": "https://capture.avada.io/i/q"}))
        self.assertEqual(upload_png(b"PNG", cfg(), session=s), "https://capture.avada.io/i/q")

    def test_non_json_200_raises(self):
        s = FakeSession(FakeResponse(200, ValueError("not json")))
        with self.assertRaises(UploadError):
            upload_png(b"PNG", cfg(), session=s)
