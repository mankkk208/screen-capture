"""Optional "launch on startup": an XDG autostart entry that starts the resident app hidden."""
from pathlib import Path

DESKTOP_NAME = "io.avada.ScreenCapture.desktop"
DEFAULT_AUTOSTART_DIR = Path.home() / ".config" / "autostart"
PROJECT_DIR = Path(__file__).resolve().parent.parent


def _entry(project_dir: Path) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Screen Capture\n"
        "Comment=Start the screen capture tool in the background\n"
        "Exec=python3 -m screen_capture --background\n"
        f"Path={project_dir}\n"
        "Icon=camera-photo\n"
        "NoDisplay=true\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def set_autostart(enabled: bool, autostart_dir: Path = DEFAULT_AUTOSTART_DIR,
                  project_dir: Path = PROJECT_DIR) -> Path | None:
    path = Path(autostart_dir) / DESKTOP_NAME
    if not enabled:
        path.unlink(missing_ok=True)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_entry(Path(project_dir)))
    return path


def is_autostart_enabled(autostart_dir: Path = DEFAULT_AUTOSTART_DIR) -> bool:
    return (Path(autostart_dir) / DESKTOP_NAME).exists()
