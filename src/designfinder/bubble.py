"""The app's resting state: a small round symbol that floats above other windows.

Drag it anywhere. Tap it to open the search window; right-click it for
Capture screen / Exit. Until it is tapped only tkinter is loaded: the image libraries
and the design index are loaded when the window opens and released when it closes.

    python -m designfinder.bubble [image]
"""

import gc
import sys
import tkinter as tk
from pathlib import Path

from . import startup
from .screen import clamp, make_dpi_aware, virtual_screen
from .settings import Settings, data_dir

SIZE = 52
TRANSPARENT = "#ff00fe"  # corner color made see-through so the symbol is round
COLOR, HOVER_COLOR = "#2563eb", "#1e40af"
IDLE_ALPHA = 0.85
DRAG_THRESHOLD = 4  # px of movement before a press counts as a drag, not a tap
MUTEX_NAME = "Local\\DesignFinder-single-instance"


class Bubble:
    def __init__(self, root: tk.Tk, query: Path | None = None, open_now: bool = False):
        self.root = root
        data = data_dir()
        self.settings_path = data / "settings.json"
        self.db_path = data / "index.db"
        self.settings = Settings.load(self.settings_path)
        self.window = None  # app.MainWindow, created on first tap
        self._press: tuple[int, int, int, int] | None = None
        self._moved = False

        root.title("Design Finder")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", IDLE_ALPHA)
        if sys.platform == "win32":
            root.attributes("-transparentcolor", TRANSPARENT)
        self.canvas = tk.Canvas(root, width=SIZE, height=SIZE, bg=TRANSPARENT,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack()
        self._draw(COLOR)

        self.menu = tk.Menu(root, tearoff=False)
        self.menu.add_command(label="Open", command=self.open)
        self.menu.add_command(label="Capture screen", command=self.capture)
        self.menu.add_separator()
        self.menu.add_command(label="Exit Design Finder", command=root.destroy)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<ButtonPress-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        self.canvas.bind("<Enter>", lambda _e: self._hover(True))
        self.canvas.bind("<Leave>", lambda _e: self._hover(False))

        screen = virtual_screen(root)
        if self.settings.bubble_x is None or self.settings.bubble_y is None:
            left, top, width, height = screen
            x, y = left + width - SIZE - 16, top + height // 3  # right edge, upper third
        else:
            x, y = clamp(self.settings.bubble_x, self.settings.bubble_y, SIZE, screen)
        root.geometry(f"{SIZE}x{SIZE}+{x}+{y}")

        if query or open_now:
            root.after(50, lambda: self.open(query))

    # --- the symbol -------------------------------------------------------------------

    def _draw(self, fill: str) -> None:
        c, s = self.canvas, SIZE
        c.delete("all")
        c.create_oval(1, 1, s - 2, s - 2, fill=fill, outline="white", width=2)
        cx, cy, r = s * 0.44, s * 0.44, s * 0.17  # magnifying glass
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="white", width=3)
        c.create_line(cx + r * 0.75, cy + r * 0.75, s * 0.72, s * 0.72, fill="white",
                      width=4, capstyle="round")

    def _hover(self, inside: bool) -> None:
        self._draw(HOVER_COLOR if inside else COLOR)
        self.root.attributes("-alpha", 1.0 if inside else IDLE_ALPHA)

    def _on_press(self, e) -> None:
        self._press = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._moved = False

    def _on_drag(self, e) -> None:
        if not self._press:
            return
        px, py, wx, wy = self._press
        dx, dy = e.x_root - px, e.y_root - py
        if abs(dx) > DRAG_THRESHOLD or abs(dy) > DRAG_THRESHOLD:
            self._moved = True
        if self._moved:
            x, y = clamp(wx + dx, wy + dy, SIZE, virtual_screen(self.root))
            self.root.geometry(f"+{x}+{y}")

    def _on_release(self, _e) -> None:
        if not self._press:
            return
        self._press = None
        if self._moved:
            self.settings.bubble_x, self.settings.bubble_y = (self.root.winfo_x(),
                                                              self.root.winfo_y())
            self.settings.save(self.settings_path)
        else:
            self.open()

    # --- window -----------------------------------------------------------------------

    def _ensure_window(self):
        if self.window is None:
            from .app import MainWindow  # heavy imports happen here, on first use
            self.window = MainWindow(self.root, self.settings, self.settings_path,
                                     self.db_path, on_collapse=self.collapse,
                                     on_capture=self.capture)
            self.window.withdraw()
        return self.window

    def open(self, query: Path | None = None):
        window = self._ensure_window()
        window.place_near(self.root.winfo_x(), self.root.winfo_y(), SIZE,
                          virtual_screen(self.root))
        self.root.withdraw()
        window.deiconify()
        window.lift()
        window.focus_force()
        window.refresh()  # picks up designs added since last time; unchanged files skipped
        if not self.settings.roots:
            window.after(300, window.open_settings)
        if query:
            window.search_file(query)
        return window

    def collapse(self) -> None:
        if self.window is not None:
            self.window.release()
            self.window.withdraw()
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        gc.collect()

    # --- capture ----------------------------------------------------------------------

    def capture(self) -> None:
        """Hide everything, freeze the screen, let the user frame a design, search it."""
        was_open = self.window is not None and self.window.winfo_viewable()
        if self.window is not None:
            self.window.withdraw()
        self.root.withdraw()
        self.root.update_idletasks()
        # give Windows a moment to repaint without our windows before grabbing
        self.root.after(250, lambda: self._start_capture(was_open))

    def _start_capture(self, was_open: bool) -> None:
        from .capture import ScreenCapture

        def done(region):
            if region is not None:
                self.open().search_image(region, "Screen capture")
            elif was_open:
                self.window.deiconify()
            else:
                self.root.deiconify()

        ScreenCapture(self.root, done)


def _already_running() -> bool:
    """Single instance per user session (auto-start plus a double-click must not make two)."""
    if sys.platform != "win32":
        return False
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    _already_running.handle = handle  # keep the mutex for the life of the process
    return kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def main(argv: list[str] | None = None, open_now: bool = False) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if _already_running():
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, "Design Finder is already running.\n\nTap the small blue symbol on your "
                  "screen to open it.", "Design Finder", 0x40)
        return 0
    make_dpi_aware()
    startup.repair()
    root = tk.Tk()
    Bubble(root, Path(argv[0]) if argv else None, open_now=open_now)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
