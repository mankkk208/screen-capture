"""Pure helpers for Mutter ScreenCast coordinates (kept free of GStreamer imports for tests)."""
from .geometry import Monitor

LAYOUT_LOGICAL = 1
LAYOUT_PHYSICAL = 2


def record_area_rect(monitor: Monitor, physical_layout: bool) -> tuple[int, int, int, int]:
    """RecordArea takes stage coordinates. In Mutter's physical layout mode the stage is in device
    pixels while GDK reports logical sizes, so the size must be scaled; positions already match."""
    factor = monitor.scale if physical_layout else 1.0
    return (int(monitor.x), int(monitor.y), round(monitor.width * factor), round(monitor.height * factor))
