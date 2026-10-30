"""Read/write the settings the Settings window edits, in ~/.config/screen-capture/config.ini."""
import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .config import DEFAULT_OWN_PATH, DEFAULT_UPLOAD_URL

SECTION = "General"


@dataclass
class Settings:
    token: str = field(default="", repr=False)
    upload_url: str = DEFAULT_UPLOAD_URL


def _parser(path: Path) -> configparser.ConfigParser:
    p = configparser.ConfigParser(interpolation=None)
    p.read(path, encoding="utf-8")
    if not p.has_section(SECTION):
        p.add_section(SECTION)
    return p


def read_settings(path: Path = DEFAULT_OWN_PATH) -> Settings:
    p = _parser(Path(path))
    return Settings(token=p.get(SECTION, "token", fallback="").strip(),
                    upload_url=p.get(SECTION, "upload_url", fallback=DEFAULT_UPLOAD_URL).strip())


def save_settings(path: Path = DEFAULT_OWN_PATH, *, token: str, upload_url: str) -> None:
    """Write token and endpoint, keeping any other keys. An empty token falls back to Flameshot's."""
    path = Path(path)
    p = _parser(path)
    if token.strip():
        p.set(SECTION, "token", token.strip())
    else:
        p.remove_option(SECTION, "token")
    p.set(SECTION, "upload_url", upload_url.strip())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # holds the token: owner-only
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        p.write(f)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def validate_endpoint(url: str) -> str | None:
    """Return an error message, or None if the endpoint is acceptable."""
    u = urlparse(url.strip())
    if u.scheme != "https" or not u.netloc:
        return "Endpoint must be an https:// URL"
    return None
