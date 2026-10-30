"""Desktop notifications via notify-send. Never raises."""
import subprocess


def notify(summary: str, body: str = "", icon: str = "camera-photo") -> None:
    try:
        subprocess.run(
            ["notify-send", "--app-name=Screen Capture", f"--icon={icon}", "--expire-time=4000", summary, body],
            check=False, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        pass
