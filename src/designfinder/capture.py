"""Snip part of the screen. The screenshot only ever lives in memory.

The whole (virtual, all-monitor) screen is grabbed into RAM and shown frozen and dimmed
in a borderless full-screen window; the user drags a frame around the design. Only the
cropped region is handed back, and every reference to the full screenshot is dropped.
Nothing is written to disk or to the clipboard.
"""

import tkinter as tk
from collections.abc import Callable

from PIL import Image, ImageEnhance, ImageGrab, ImageTk

from .screen import virtual_screen

MIN_SIZE = 12  # px; smaller drags count as a cancel (an accidental click)
FRAME_COLOR = "#ff3b30"


def normalize_rect(x0: int, y0: int, x1: int, y1: int, width: int, height: int):
    """Order the corners of a drag and clamp them to the image."""
    left, right = sorted((max(0, min(x0, width)), max(0, min(x1, width))))
    top, bottom = sorted((max(0, min(y0, height)), max(0, min(y1, height))))
    return left, top, right, bottom


class ScreenCapture(tk.Toplevel):
    """Full-screen frozen-screen overlay; calls on_done(cropped image or None)."""

    def __init__(self, master: tk.Misc, on_done: Callable[[Image.Image | None], None],
                 shot: Image.Image | None = None, origin: tuple[int, int] | None = None):
        super().__init__(master)
        if shot is None:
            left, top, _width, _height = virtual_screen(master)
            shot = ImageGrab.grab(all_screens=True)
            origin = (left, top)
        self._shot = shot
        self._on_done = on_done
        self._start: tuple[int, int] | None = None
        ox, oy = origin or (0, 0)

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{shot.width}x{shot.height}+{ox}+{oy}")
        self.configure(cursor="crosshair")

        self.canvas = tk.Canvas(self, width=shot.width, height=shot.height,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self._dim = ImageTk.PhotoImage(ImageEnhance.Brightness(shot).enhance(0.55))
        self.canvas.create_image(0, 0, image=self._dim, anchor="nw")
        self._bright_item = self.canvas.create_image(0, 0, anchor="nw")
        self._bright: ImageTk.PhotoImage | None = None
        self._frame = self.canvas.create_rectangle(0, 0, 0, 0, outline=FRAME_COLOR, width=2,
                                                   state="hidden")
        self._hint(shot.width)

        self.canvas.bind("<ButtonPress-1>", lambda e: self.press(e.x, e.y))
        self.canvas.bind("<B1-Motion>", lambda e: self.drag(e.x, e.y))
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.release(e.x, e.y))
        self.bind("<Escape>", lambda _e: self.finish(None))
        self.bind("<ButtonPress-3>", lambda _e: self.finish(None))
        self.focus_force()

    def _hint(self, width: int) -> None:
        text = "Drag a frame around the design  ·  Esc or right-click to cancel"
        x = width // 2
        self.canvas.create_rectangle(x - 260, 14, x + 260, 50, fill="#222", outline="")
        self.canvas.create_text(x, 32, text=text, fill="white", font=("Segoe UI", 12))

    def press(self, x: int, y: int) -> None:
        self._start = (x, y)

    def drag(self, x: int, y: int) -> None:
        if not self._start:
            return
        left, top, right, bottom = normalize_rect(*self._start, x, y, *self._shot.size)
        self.canvas.coords(self._frame, left, top, right, bottom)
        self.canvas.itemconfigure(self._frame, state="normal")
        if right - left > 1 and bottom - top > 1:  # show the selected area undimmed
            self._bright = ImageTk.PhotoImage(self._shot.crop((left, top, right, bottom)))
            self.canvas.itemconfigure(self._bright_item, image=self._bright)
            self.canvas.coords(self._bright_item, left, top)
            self.canvas.tag_raise(self._frame)

    def release(self, x: int, y: int) -> None:
        if not self._start:
            return
        left, top, right, bottom = normalize_rect(*self._start, x, y, *self._shot.size)
        if right - left < MIN_SIZE or bottom - top < MIN_SIZE:
            self._start = None
            self.canvas.itemconfigure(self._frame, state="hidden")
            self.canvas.itemconfigure(self._bright_item, image="")
            return
        self.finish(self._shot.crop((left, top, right, bottom)))

    def finish(self, region: Image.Image | None) -> None:
        # Drop every reference to the full-screen image before handing back the crop.
        self._shot = self._dim = self._bright = None
        self.destroy()
        self._on_done(region)
