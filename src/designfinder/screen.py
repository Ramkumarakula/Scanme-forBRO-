"""Screen geometry helpers (stdlib only, so the floating symbol stays lightweight)."""

import sys
import tkinter as tk

Rect = tuple[int, int, int, int]  # left, top, width, height


def virtual_screen(root: tk.Misc) -> Rect:
    """All monitors together, in physical pixels (the process is DPI-aware)."""
    if sys.platform == "win32":
        import ctypes
        metrics = ctypes.windll.user32.GetSystemMetrics
        return metrics(76), metrics(77), metrics(78), metrics(79)
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def clamp(x: int, y: int, size: int, screen: Rect) -> tuple[int, int]:
    """Keep a size×size window fully on screen (e.g. after a monitor was unplugged)."""
    left, top, width, height = screen
    return (min(max(left, x), left + width - size), min(max(top, y), top + height - size))


def make_dpi_aware() -> None:
    """Per-monitor DPI awareness: crisp text, and screen captures line up with the mouse."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
