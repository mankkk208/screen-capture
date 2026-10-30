"""Upload to capture.avada.io. Error messages must never contain the token or server text."""
import time
from pathlib import Path

import requests

from .config import Config


class UploadError(Exception):
    pass


def parse_url(body: object) -> str:
    # Verified shape: {"success": true, "url": "https://capture.avada.io/i/<id>", "imageId": ...}
    if not isinstance(body, dict) or body.get("success") is not True:
        raise UploadError("upload failed: unexpected server response")
    url = body.get("url")
    if not isinstance(url, str) or not url.startswith("http"):
        raise UploadError("upload failed: server returned no link")
    return url


def upload_png(png: bytes, cfg: Config, session=None, timeout: float = 20.0) -> str:
    session = session or requests
    filename = time.strftime("capture-%Y%m%d-%H%M%S.png")
    try:
        r = session.post(
            cfg.upload_url,
            files={"image": (filename, png, "image/png")},
            headers={"X-Avada-Token": cfg.token},
            timeout=timeout,
            allow_redirects=False,  # a redirect would forward X-Avada-Token to another host
        )
    except requests.Timeout:
        raise UploadError("network error: upload timed out") from None
    except requests.RequestException:
        raise UploadError("network error: cannot reach the upload server") from None
    if 300 <= r.status_code < 400:
        raise UploadError(f"upload rejected: unexpected redirect ({r.status_code})")
    if r.status_code in (401, 403):
        raise UploadError("upload token rejected by the server")
    if r.status_code >= 500:
        raise UploadError(f"server error ({r.status_code})")
    if r.status_code >= 400:
        raise UploadError(f"upload rejected ({r.status_code})")
    try:
        body = r.json()
    except ValueError:
        raise UploadError("upload failed: server response is not JSON") from None
    return parse_url(body)


def save_failed(png: bytes, cfg: Config) -> Path:
    cfg.save_dir.mkdir(parents=True, exist_ok=True)
    stem = time.strftime("capture-%Y%m%d-%H%M%S")
    n = 0
    while True:
        path = cfg.save_dir / (f"{stem}.png" if n == 0 else f"{stem}-{n}.png")
        try:
            with open(path, "xb") as f:  # exclusive create: two failures in the same second can't collide
                f.write(png)
            return path
        except FileExistsError:
            n += 1
