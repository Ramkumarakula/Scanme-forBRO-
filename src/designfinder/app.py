"""The search window, opened from the floating symbol (see bubble.py).

This module pulls in OpenCV, numpy and Pillow, so bubble.py imports it only when the
window is first opened; until then the app stays small.
"""

import os
import queue
# subprocess is only used to open Explorer, see open_in_explorer
import subprocess  # nosec B404
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageGrab, ImageTk

from . import IMAGE_EXTENSIONS, startup
from .fingerprint import fingerprint_image, load_image
from .icon import icon_image
from .index import connect, index_roots
from .search import FolderMatch, Index
from .settings import Settings

WIDTH, HEIGHT = 460, 660
QUERY_THUMB = 150
RESULT_THUMB = 84
TOP_RESULTS = 5
WRAP = 300  # text width in result cards, px
PAD = 8

EXPLORER = Path(os.environ.get("WINDIR", r"C:\Windows")) / "explorer.exe"


def open_in_explorer(match: FolderMatch) -> None:
    """Open Explorer at the folder, with the newest master file selected if there is one."""
    master = next((m for m in match.masters if m.is_file()), None)
    if master and '"' not in str(master):
        # Full path to explorer.exe (no PATH lookup), no shell. explorer parses its own
        # command line, and the quote check keeps the path inside its argument.
        subprocess.Popen(f'"{EXPLORER}" /select,"{master}"')  # nosec B603
    elif Path(match.folder).is_dir():
        # folder path comes from our own index
        os.startfile(match.folder)  # nosec B606


def bgr_from_pil(img: Image.Image) -> np.ndarray:
    return np.array(img.convert("RGB"))[:, :, ::-1].copy()


def thumbnail(img: Image.Image, size: int) -> ImageTk.PhotoImage:
    img = img.convert("RGB")
    img.thumbnail((size, size))
    return ImageTk.PhotoImage(img)


class MainWindow(tk.Toplevel):
    """Search window. Closing it (X or Esc) collapses back to the floating symbol."""

    def __init__(self, master: tk.Misc, settings: Settings, settings_path: Path,
                 db_path: Path, on_collapse: Callable[[], None],
                 on_capture: Callable[[], None]):
        super().__init__(master)
        self.settings = settings
        self.settings_path = settings_path
        self.db_path = db_path
        self.on_collapse = on_collapse
        self.index: Index | None = None
        self.events: queue.Queue = queue.Queue()
        self.scanning = False
        self.pending_search: Callable[[], None] | None = None
        self._photos: list[ImageTk.PhotoImage] = []  # keep references so Tk shows them

        self.title("Design Finder")
        self._icon = ImageTk.PhotoImage(icon_image(64))
        self.iconphoto(False, self._icon)
        self.resizable(False, False)
        self.attributes("-topmost", settings.on_top)
        self.protocol("WM_DELETE_WINDOW", on_collapse)
        self.bind("<Escape>", lambda _e: on_collapse())
        self.bind("<Control-v>", lambda _e: self.paste())
        self._build(on_capture)

    # --- layout -----------------------------------------------------------------------

    def _build(self, on_capture: Callable[[], None]) -> None:
        bar = ttk.Frame(self, padding=PAD)
        bar.pack(fill="x")
        ttk.Button(bar, text="Capture screen", command=on_capture).pack(side="left")
        ttk.Button(bar, text="Open image…", command=self.open_image).pack(side="left",
                                                                          padx=PAD)
        ttk.Button(bar, text="Paste", command=self.paste).pack(side="left")
        self.on_top_var = tk.BooleanVar(value=self.settings.on_top)
        ttk.Checkbutton(bar, text="On top", variable=self.on_top_var,
                        command=self._toggle_on_top).pack(side="right")

        self.query_frame = ttk.Frame(self, padding=(PAD, 0))
        self.query_frame.pack(fill="x")
        self.query_img = ttk.Label(self.query_frame)
        self.query_img.pack(side="left")
        self.query_text = ttk.Label(self.query_frame, wraplength=280, justify="left")
        self.query_text.pack(side="left", padx=PAD, fill="x")

        ttk.Separator(self).pack(fill="x", pady=PAD)

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True)
        canvas = tk.Canvas(holder, highlightthickness=0, width=WIDTH, height=HEIGHT - 260)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        self.results = ttk.Frame(canvas, padding=(PAD, 0))
        self.results.bind("<Configure>",
                          lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        inner = canvas.create_window((0, 0), window=self.results, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(inner, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        status = ttk.Frame(self, padding=PAD)
        status.pack(fill="x", side="bottom")
        self.status = ttk.Label(status, text="")
        self.status.pack(side="left")
        self.rescan_btn = ttk.Button(status, text="Re-scan", command=self.refresh)
        self.rescan_btn.pack(side="right")
        ttk.Button(status, text="Settings…", command=self.open_settings).pack(side="right",
                                                                              padx=PAD)
        self.clear()

    def _toggle_on_top(self) -> None:
        self.settings.on_top = self.on_top_var.get()
        self.attributes("-topmost", self.settings.on_top)
        self.settings.save(self.settings_path)

    def place_near(self, x: int, y: int, size: int, screen: tuple[int, int, int, int]) -> None:
        """Open beside the floating symbol, on whichever side has room."""
        left, top, width, height = screen
        wx = x - WIDTH - 8 if x + size / 2 > left + width / 2 else x + size + 8
        wy = min(max(top, y - 40), top + height - HEIGHT - 60)
        self.geometry(f"{WIDTH}x{HEIGHT}+{max(left, wx)}+{max(top, wy)}")

    # --- show / hide ------------------------------------------------------------------

    def clear(self) -> None:
        """Forget the query and results (nothing from a search is kept after closing)."""
        self._photos = []
        self.query_img.configure(image="")
        self.query_text.configure(
            text="Capture screen: drag a frame around a design.\n"
                 "Or open an image, or copy one and press Ctrl+V.")
        self._show_results([])

    def release(self) -> None:
        """Called when collapsing: drop the query, results and in-memory index."""
        self.clear()
        self.index = None

    def refresh(self) -> None:
        """Scan for new/changed designs and (re)load the index, in the background."""
        if self.scanning:
            return
        self.scanning = True
        self.rescan_btn.state(["disabled"])
        self.status.configure(text="Checking design folders…")
        roots = list(self.settings.roots)
        threading.Thread(target=self._scan_worker, args=(roots,), daemon=True).start()
        self.after(100, self._poll_events)

    # --- input ------------------------------------------------------------------------

    def open_image(self) -> None:
        types = " ".join(f"*{ext}" for ext in sorted(IMAGE_EXTENSIONS))
        path = filedialog.askopenfilename(parent=self, title="Choose an image",
                                          filetypes=[("Images", types), ("All files", "*.*")])
        if path:
            self.search_file(Path(path))

    def paste(self) -> None:
        clip = ImageGrab.grabclipboard()
        if isinstance(clip, Image.Image):
            self.search_image(clip, "Pasted image")
        elif isinstance(clip, list) and clip:  # files copied in Explorer
            self.search_file(Path(clip[0]))
        else:
            messagebox.showinfo("Design Finder", "The clipboard has no image.\n\n"
                                "Use Capture screen, or copy an image file.", parent=self)

    def search_file(self, path: Path) -> None:
        try:
            bgr = load_image(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Design Finder", f"Cannot read this image:\n{exc}",
                                 parent=self)
            return
        self.search_image(Image.fromarray(bgr[:, :, ::-1]), path.name, bgr)

    def search_image(self, img: Image.Image, label: str, bgr: np.ndarray | None = None) -> None:
        self._photos = [thumbnail(img, QUERY_THUMB)]
        self.query_img.configure(image=self._photos[0])
        if self.scanning:
            self.pending_search = lambda: self.search_image(img, label, bgr)
            self.query_text.configure(text=f"{label}\n\nChecking design folders… "
                                           "results will appear in a moment.")
            self._show_results([])
            return
        if not self.index or not len(self.index):
            self.query_text.configure(text=f"{label}\n\nNo designs indexed yet. "
                                           "Click Settings… to choose your design folders.")
            self._show_results([])
            return
        matches = self.index.search(fingerprint_image(bgr if bgr is not None
                                                      else bgr_from_pil(img)), TOP_RESULTS)
        self.query_text.configure(text=f"{label}\n\nClosest designs below "
                                       "(score: 1.00 = same design).")
        self._show_results(matches)

    # --- results ----------------------------------------------------------------------

    def _show_results(self, matches: list[FolderMatch]) -> None:
        for child in self.results.winfo_children():
            child.destroy()
        for rank, m in enumerate(matches, 1):
            card = ttk.Frame(self.results, padding=(0, 4))
            card.pack(fill="x")
            try:
                photo = thumbnail(Image.fromarray(load_image(m.best_image)[:, :, ::-1]),
                                  RESULT_THUMB)
                self._photos.append(photo)
                ttk.Label(card, image=photo).pack(side="left")
            except (OSError, ValueError):
                ttk.Label(card, text="(no preview)", width=12).pack(side="left")
            info = ttk.Frame(card, padding=(PAD, 0))
            info.pack(side="left", fill="x", expand=True)
            ttk.Label(info, text=f"{rank}.  score {m.score:.2f}",
                      font=("Segoe UI", 10, "bold")).pack(anchor="w")
            ttk.Label(info, text=m.folder, wraplength=WRAP).pack(anchor="w")
            masters = ", ".join(p.name for p in m.masters) or "no .skp/.skb in this folder"
            ttk.Label(info, text=masters, foreground="#555", wraplength=WRAP).pack(anchor="w")
            ttk.Button(info, text="Open folder",
                       command=lambda m=m: open_in_explorer(m)).pack(anchor="w", pady=(4, 0))
            ttk.Separator(self.results).pack(fill="x", pady=2)

    # --- settings and indexing --------------------------------------------------------

    def open_settings(self) -> None:
        SettingsDialog(self, self.settings.roots, self._settings_saved)

    def _settings_saved(self, roots: list[str]) -> None:
        self.settings.roots = roots
        self.settings.save(self.settings_path)
        self.refresh()

    def _scan_worker(self, roots: list[str]) -> None:
        try:
            conn = connect(self.db_path)
            present = [r for r in roots if Path(r).is_dir()]
            stats = index_roots(conn, present, keep_only=roots)
            index = Index(conn)
            conn.close()
            self.events.put(("ready", (index, stats), [r for r in roots if r not in present]))
        except Exception as exc:  # report any failure in the UI instead of dying silently
            self.events.put(("error", exc, None))

    def _poll_events(self) -> None:
        try:
            kind, payload, missing = self.events.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_events)  # polls only while a scan is running
            return
        self.scanning = False
        self.rescan_btn.state(["!disabled"])
        if kind == "ready":
            self.index, stats = payload
            text = f"{len(self.index)} images in {len(set(self.index.folders))} folders"
            if stats.failed:
                text += f"  ({stats.failed} unreadable)"
            if missing:
                text += f"  ({len(missing)} folder(s) not found)"
            self.status.configure(text=text)
        else:
            self.status.configure(text="Scanning failed")
            messagebox.showerror("Design Finder", f"Scanning failed:\n{payload}", parent=self)
        if self.pending_search:
            run, self.pending_search = self.pending_search, None
            run()


class SettingsDialog(tk.Toplevel):
    """Design folders to scan, and whether to start with Windows."""

    def __init__(self, parent: tk.Toplevel, roots: list[str], on_save):
        super().__init__(parent)
        self.title("Settings")
        self.geometry(f"+{parent.winfo_rootx() + 20}+{parent.winfo_rooty() + 60}")
        self.attributes("-topmost", True)
        self.transient(parent)
        self.on_save = on_save
        ttk.Label(self, padding=PAD, wraplength=380,
                  text="Folders that contain your designs (sub-folders are included):"
                  ).pack(anchor="w")
        self.listbox = tk.Listbox(self, width=60, height=8)
        self.listbox.pack(padx=PAD, fill="both", expand=True)
        for r in roots:
            self.listbox.insert("end", r)
        buttons = ttk.Frame(self, padding=PAD)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Add folder…", command=self._add).pack(side="left")
        ttk.Button(buttons, text="Remove", command=self._remove).pack(side="left", padx=PAD)

        self.autostart = tk.BooleanVar(value=startup.is_enabled())
        box = ttk.Checkbutton(self, text="Start with Windows (shows the small symbol)",
                              variable=self.autostart, padding=(PAD, 0))
        box.pack(anchor="w")
        if not startup.supported():
            box.state(["disabled"])
            ttk.Label(self, text="(available in the installed DesignFinder.exe)",
                      foreground="#777", padding=(PAD * 3, 0)).pack(anchor="w")
        ttk.Button(self, text="Save and scan", command=self._save).pack(anchor="e",
                                                                       padx=PAD, pady=PAD)
        self.grab_set()

    def _add(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="Choose a design folder")
        if folder and str(Path(folder)) not in self.listbox.get(0, "end"):
            self.listbox.insert("end", str(Path(folder)))

    def _remove(self) -> None:
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)

    def _save(self) -> None:
        roots = list(self.listbox.get(0, "end"))
        if startup.supported():
            startup.set_enabled(self.autostart.get())
        self.destroy()
        self.on_save(roots)


def main(argv: list[str] | None = None) -> int:
    """`python -m designfinder.app [image]`: start with the window already open."""
    from .bubble import main as bubble_main
    return bubble_main(argv, open_now=True)


if __name__ == "__main__":
    raise SystemExit(main())
