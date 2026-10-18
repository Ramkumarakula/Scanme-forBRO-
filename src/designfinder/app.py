"""Small always-on-top window: give it an image, see which design folders match.

    python -m designfinder.app [image]
"""

import os
import queue
# subprocess is only used to open Explorer, see open_in_explorer
import subprocess  # nosec B404
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageGrab, ImageTk

from . import IMAGE_EXTENSIONS
from .fingerprint import fingerprint_image, load_image
from .index import connect, index_roots
from .search import FolderMatch, Index
from .settings import Settings, data_dir

WINDOW_SIZE = "460x640"
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


class App:
    def __init__(self, root: tk.Tk, query: Path | None = None):
        self.root = root
        self.data = data_dir()
        self.settings_path = self.data / "settings.json"
        self.db_path = self.data / "index.db"
        self.settings = Settings.load(self.settings_path)
        self.index: Index | None = None
        self.events: queue.Queue = queue.Queue()
        self._photos: list[ImageTk.PhotoImage] = []  # keep references so Tk shows them
        self.scanning = False
        self.pending_search = None  # search asked for while a scan was running

        root.title("Design Finder")
        root.geometry(WINDOW_SIZE)
        root.resizable(False, False)
        root.attributes("-topmost", self.settings.on_top)
        self._build()
        root.bind_all("<Control-v>", lambda _e: self.paste())
        root.after(100, self._poll_events)

        self._reload_index()
        if self.settings.roots:
            self.rescan()  # picks up designs added since last time; unchanged files are skipped
        else:
            root.after(300, self.choose_folders)
        if query:
            root.after(200, lambda: self.search_file(query))

    # --- layout -----------------------------------------------------------------------

    def _build(self) -> None:
        bar = ttk.Frame(self.root, padding=PAD)
        bar.pack(fill="x")
        ttk.Button(bar, text="Open image…", command=self.open_image).pack(side="left")
        ttk.Button(bar, text="Paste  (Ctrl+V)", command=self.paste).pack(side="left", padx=PAD)
        self.on_top_var = tk.BooleanVar(value=self.settings.on_top)
        ttk.Checkbutton(bar, text="Keep on top", variable=self.on_top_var,
                        command=self._toggle_on_top).pack(side="right")

        self.query_frame = ttk.Frame(self.root, padding=(PAD, 0))
        self.query_frame.pack(fill="x")
        self.query_img = ttk.Label(self.query_frame)
        self.query_img.pack(side="left")
        self.query_text = ttk.Label(
            self.query_frame, wraplength=280, justify="left",
            text="Open an image, or snip part of the screen with Win+Shift+S "
                 "and press Ctrl+V here.")
        self.query_text.pack(side="left", padx=PAD, fill="x")

        ttk.Separator(self.root).pack(fill="x", pady=PAD)

        holder = ttk.Frame(self.root)
        holder.pack(fill="both", expand=True)
        canvas = tk.Canvas(holder, highlightthickness=0)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        self.results = ttk.Frame(canvas, padding=(PAD, 0))
        self.results.bind("<Configure>",
                          lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        inner = canvas.create_window((0, 0), window=self.results, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(inner, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        status = ttk.Frame(self.root, padding=PAD)
        status.pack(fill="x", side="bottom")
        self.status = ttk.Label(status, text="")
        self.status.pack(side="left")
        self.rescan_btn = ttk.Button(status, text="Re-scan", command=self.rescan)
        self.rescan_btn.pack(side="right")
        ttk.Button(status, text="Folders…", command=self.choose_folders).pack(side="right",
                                                                              padx=PAD)

    def _toggle_on_top(self) -> None:
        self.settings.on_top = self.on_top_var.get()
        self.root.attributes("-topmost", self.settings.on_top)
        self.settings.save(self.settings_path)

    # --- input ------------------------------------------------------------------------

    def open_image(self) -> None:
        types = " ".join(f"*{ext}" for ext in sorted(IMAGE_EXTENSIONS))
        path = filedialog.askopenfilename(parent=self.root, title="Choose an image",
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
                                "Use Win+Shift+S to snip the screen, or copy an image file.",
                                parent=self.root)

    def search_file(self, path: Path) -> None:
        try:
            bgr = load_image(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Design Finder", f"Cannot read this image:\n{exc}",
                                 parent=self.root)
            return
        self.search_image(Image.fromarray(bgr[:, :, ::-1]), path.name, bgr)

    def search_image(self, img: Image.Image, label: str, bgr: np.ndarray | None = None) -> None:
        self._photos = [thumbnail(img, QUERY_THUMB)]
        self.query_img.configure(image=self._photos[0])
        if self.scanning:
            self.pending_search = lambda: self.search_image(img, label, bgr)
            self.query_text.configure(text=f"{label}\n\nScanning design folders… "
                                           "results will appear when it finishes.")
            self._show_results([])
            return
        if not self.index or not len(self.index):
            self.query_text.configure(text=f"{label}\n\nNo designs indexed yet. "
                                           "Click Folders… to choose your design folders.")
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

    # --- folders and indexing ---------------------------------------------------------

    def choose_folders(self) -> None:
        FolderDialog(self.root, self.settings.roots, self._folders_saved)

    def _folders_saved(self, roots: list[str]) -> None:
        self.settings.roots = roots
        self.settings.save(self.settings_path)
        self.rescan()

    def rescan(self) -> None:
        if not self.settings.roots:
            self.status.configure(text="No design folders chosen.")
            return
        if self.scanning:
            return
        self.scanning = True
        self.rescan_btn.state(["disabled"])
        self.status.configure(text="Scanning design folders…")
        roots = list(self.settings.roots)
        threading.Thread(target=self._index_worker, args=(roots,), daemon=True).start()

    def _index_worker(self, roots: list[str]) -> None:
        try:
            conn = connect(self.db_path)
            missing = [r for r in roots if not Path(r).is_dir()]
            stats = index_roots(conn, [r for r in roots if r not in missing], only_these_roots=True)
            conn.close()
            self.events.put(("indexed", stats, missing))
        except Exception as exc:  # report any failure in the UI instead of dying silently
            self.events.put(("error", exc, None))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload, extra = self.events.get_nowait()
                self.scanning = False
                self.rescan_btn.state(["!disabled"])
                if kind == "indexed":
                    self._reload_index()
                    if payload.failed:
                        self.status.configure(text=self.status.cget("text") +
                                              f"  ({payload.failed} unreadable)")
                    if extra:
                        messagebox.showwarning("Design Finder", "These folders were not found:\n"
                                               + "\n".join(extra), parent=self.root)
                else:
                    messagebox.showerror("Design Finder", f"Scanning failed:\n{payload}",
                                         parent=self.root)
                if self.pending_search:
                    run, self.pending_search = self.pending_search, None
                    run()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _reload_index(self) -> None:
        conn = connect(self.db_path)
        self.index = Index(conn)
        conn.close()
        folders = len(set(self.index.folders))
        self.status.configure(text=f"{len(self.index)} images in {folders} folders")


class FolderDialog(tk.Toplevel):
    """Pick the design root folders to scan."""

    def __init__(self, parent: tk.Tk, roots: list[str], on_save):
        super().__init__(parent)
        self.title("Design folders")
        self.geometry(f"+{parent.winfo_rootx() + 20}+{parent.winfo_rooty() + 60}")
        self.attributes("-topmost", True)
        self.transient(parent)
        self.on_save = on_save
        ttk.Label(self, padding=PAD, wraplength=380,
                  text="Choose the folders that contain your designs. "
                       "Sub-folders are included.").pack(anchor="w")
        self.listbox = tk.Listbox(self, width=60, height=8)
        self.listbox.pack(padx=PAD, fill="both", expand=True)
        for r in roots:
            self.listbox.insert("end", r)
        buttons = ttk.Frame(self, padding=PAD)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Add folder…", command=self._add).pack(side="left")
        ttk.Button(buttons, text="Remove", command=self._remove).pack(side="left", padx=PAD)
        ttk.Button(buttons, text="Save and scan", command=self._save).pack(side="right")
        self.grab_set()

    def _add(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="Choose a design folder")
        if folder and folder not in self.listbox.get(0, "end"):
            self.listbox.insert("end", str(Path(folder)))

    def _remove(self) -> None:
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)

    def _save(self) -> None:
        roots = list(self.listbox.get(0, "end"))
        self.destroy()
        self.on_save(roots)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp text on scaled displays
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    App(root, Path(argv[0]) if argv else None)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
