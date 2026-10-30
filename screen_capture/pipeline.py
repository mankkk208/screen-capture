"""Render → upload → (on failure) save locally. Never raises; messages never contain the token."""
import os
from pathlib import Path

from .config import DEFAULT_SAVE_DIR, Config, ConfigError
from .upload import UploadError, save_failed

FALLBACK_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / "screen-capture-failed"


def _save(png: bytes, cfg: Config) -> Path:
    try:
        return save_failed(png, cfg)
    except Exception:
        return save_failed(png, Config(token="", save_dir=FALLBACK_DIR))


def deliver(render, load_config, upload) -> tuple[str, str]:
    """Return ("ok", url) or ("failed", human-readable message including where the image was saved)."""
    try:
        png = render()
    except Exception:
        return "failed", "could not create the image"

    cfg = None
    try:
        cfg = load_config()
        return "ok", upload(png, cfg)
    except (ConfigError, UploadError) as e:
        reason = str(e)  # these messages are written by us and never include the token
    except Exception:
        reason = "unexpected error while uploading"
    try:
        path = _save(png, cfg or Config(token="", save_dir=DEFAULT_SAVE_DIR))
    except Exception:
        return "failed", f"{reason}; the image could not be saved either"
    return "failed", f"{reason}\n{path}"
