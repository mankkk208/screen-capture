import tempfile
import unittest
from pathlib import Path

from screen_capture.config import ConfigError, load_config

SENTINEL = "SENTINEL-TOKEN-123"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.own = self.tmp / "own" / "config.ini"
        self.fs = self.tmp / "flameshot" / "flameshot.ini"

    def test_flameshot_token_loaded(self):
        write(self.fs, f"[General]\ncustomUploadToken={SENTINEL}\n")
        cfg = load_config(self.own, self.fs)
        self.assertEqual(cfg.token, SENTINEL)
        self.assertEqual(cfg.upload_url, "https://capture-api.avada.io/api/v1/upload")

    def test_own_config_overrides(self):
        write(self.fs, "[General]\ncustomUploadToken=from-flameshot\n")
        write(self.own, "[General]\ntoken=from-own\n")
        self.assertEqual(load_config(self.own, self.fs).token, "from-own")

    def test_missing_token_raises_configerror_without_leaking(self):
        write(self.fs, "[General]\nsomethingElse=1\n")
        with self.assertRaises(ConfigError) as ctx:
            load_config(self.own, self.fs)
        self.assertNotIn(SENTINEL, str(ctx.exception))

    def test_missing_files_raise_configerror(self):
        with self.assertRaises(ConfigError):
            load_config(self.own, self.fs)

    def test_repr_and_str_redact_token(self):
        write(self.fs, f"[General]\ncustomUploadToken={SENTINEL}\n")
        cfg = load_config(self.own, self.fs)
        self.assertNotIn(SENTINEL, repr(cfg))
        self.assertNotIn(SENTINEL, str(cfg))
