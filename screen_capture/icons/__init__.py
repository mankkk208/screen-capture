"""Lucide icons (ISC, see LICENSE-lucide) plus circle-one.svg drawn in the same style."""
from functools import lru_cache
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent

ICON_FOR = {
    "select": "square-dashed-mouse-pointer",
    "arrow": "move-up-right",
    "line": "slash",
    "rect": "square",
    "ellipse": "circle",
    "pen": "pencil",
    "text": "type",
    "highlighter": "highlighter",
    "step": "circle-one",
    "blur": "eye-off",
    "undo": "undo-2",
    "redo": "redo-2",
    "close": "x",
    "check": "check",
}


@lru_cache(maxsize=None)
def icon_svg(name: str, color: str) -> bytes:
    return (ICON_DIR / f"{name}.svg").read_bytes().replace(b"currentColor", color.encode())
