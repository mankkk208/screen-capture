"""Configuration. The upload token is read here and must never be printed or logged."""
import configparser
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_UPLOAD_URL = "https://capture-api.avada.io/api/v1/upload"
DEFAULT_OWN_PATH = Path.home() / ".config" / "screen-capture" / "config.ini"
DEFAULT_FLAMESHOT_PATH = Path.home() / ".config" / "flameshot" / "flameshot.ini"
DEFAULT_SAVE_DIR = Path.home() / "Pictures" / "screen-capture-failed"


class ConfigError(Exception):
    pass


@dataclass
class Config:
    token: str = field(repr=False)
    upload_url: str = DEFAULT_UPLOAD_URL
    save_dir: Path = DEFAULT_SAVE_DIR

    def __repr__(self) -> str:
        return f"Config(token=<redacted>, upload_url={self.upload_url!r}, save_dir={str(self.save_dir)!r})"

    __str__ = __repr__


def _read(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # Flameshot keys are case-sensitive (customUploadToken)
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError):
        raise ConfigError(f"cannot read config file {path}") from None
    return parser


def load_config(own_path: Path = DEFAULT_OWN_PATH, flameshot_path: Path = DEFAULT_FLAMESHOT_PATH) -> Config:
    own = _read(Path(own_path))
    flame = _read(Path(flameshot_path))
    token = own.get("General", "token", fallback="").strip() or flame.get(
        "General", "customUploadToken", fallback=""
    ).strip()
    if not token:
        raise ConfigError(
            f"upload token not configured: set 'token' in {own_path} or customUploadToken in {flameshot_path}"
        )
    return Config(
        token=token,
        upload_url=own.get("General", "upload_url", fallback=DEFAULT_UPLOAD_URL),
        save_dir=Path(own.get("General", "save_dir", fallback=str(DEFAULT_SAVE_DIR))).expanduser(),
    )
