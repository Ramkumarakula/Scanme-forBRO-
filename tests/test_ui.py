"""Floating symbol, screen capture and window flow (needs a desktop session for Tk)."""

import subprocess
import sys
import tkinter as tk

import pytest
from PIL import Image

from designfinder import bubble, startup
from designfinder.capture import ScreenCapture, normalize_rect
from designfinder.screen import clamp
from designfinder.settings import Settings

from conftest import draw_design


@pytest.fixture(scope="session")
def tk_root():
    # One Tk interpreter for the whole run, like the real app: creating and destroying
    # several tk.Tk() roots in one process is unreliable on Windows.
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def root(tk_root):
    """A fresh top-level window per test (Bubble and ScreenCapture accept any Tk window)."""
    win = tk.Toplevel(tk_root)
    yield win
    win.destroy()


def test_symbol_does_not_load_image_libraries():
    code = ("import sys, designfinder.bubble; "
            "print(sorted(m for m in ('cv2', 'numpy', 'PIL') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True).stdout.strip()
    assert out == "[]"


def test_normalize_rect_orders_and_clamps():
    assert normalize_rect(300, 200, 100, 50, 1000, 800) == (100, 50, 300, 200)
    assert normalize_rect(-20, -5, 1200, 900, 1000, 800) == (0, 0, 1000, 800)


def test_clamp_keeps_symbol_on_screen():
    screen = (-1920, 0, 3840, 1080)  # second monitor on the left
    assert clamp(5000, 2000, 52, screen) == (1920 - 52, 1080 - 52)
    assert clamp(-3000, -10, 52, screen) == (-1920, 0)
    assert clamp(100, 100, 52, screen) == (100, 100)


def test_capture_returns_only_the_framed_region(root):
    shot = Image.new("RGB", (400, 300), "white")
    got = []
    cap = ScreenCapture(root, got.append, shot=shot, origin=(0, 0))
    cap.press(50, 40)
    cap.drag(150, 120)
    cap.release(250, 190)
    assert len(got) == 1 and got[0].size == (200, 150)
    assert cap._shot is None  # full screenshot released


def test_capture_tiny_drag_is_ignored_and_escape_cancels(root):
    got = []
    cap = ScreenCapture(root, got.append, shot=Image.new("RGB", (400, 300)), origin=(0, 0))
    cap.press(10, 10)
    cap.release(14, 13)
    assert got == []  # still open, waiting for a real drag
    cap.finish(None)
    assert got == [None]


def test_tap_opens_window_searches_and_collapse_forgets(root, tmp_path, monkeypatch,
                                                        design_root):
    monkeypatch.setattr(bubble, "data_dir", lambda: tmp_path)
    Settings(roots=[str(design_root)]).save(tmp_path / "settings.json")
    b = bubble.Bubble(root)

    window = b.open()
    assert window.scanning
    window.search_image(Image.fromarray(draw_design("table")[:, :, ::-1]), "Screen capture")
    assert window.pending_search is not None  # waits for the scan
    while window.scanning:
        root.update()
        window._poll_events()
    root.update()
    assert window.index is not None and len(window.index) == 3
    assert len(window.results.winfo_children()) > 0

    b.collapse()
    assert window.index is None and window._photos == []
    assert window.results.winfo_children() == []


def test_bubble_position_is_remembered(root, tmp_path, monkeypatch):
    monkeypatch.setattr(bubble, "data_dir", lambda: tmp_path)
    b = bubble.Bubble(root)

    class Event:
        def __init__(self, x, y):
            self.x_root, self.y_root = x, y

    root.geometry("+300+300")
    root.update()
    b._on_press(Event(310, 310))
    b._on_drag(Event(410, 360))
    b._on_release(Event(410, 360))
    saved = Settings.load(tmp_path / "settings.json")
    assert (saved.bubble_x, saved.bubble_y) == (root.winfo_x(), root.winfo_y())


def test_startup_registry_entry(monkeypatch):
    store = {}

    class FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class FakeWinreg:
        HKEY_CURRENT_USER, REG_SZ = object(), 1

        @staticmethod
        def CreateKey(hive, path):
            return FakeKey()

        OpenKey = CreateKey

        @staticmethod
        def SetValueEx(key, name, reserved, kind, value):
            store[name] = value

        @staticmethod
        def QueryValueEx(key, name):
            if name not in store:
                raise FileNotFoundError(name)
            return store[name], 1

        @staticmethod
        def DeleteValue(key, name):
            if name not in store:
                raise FileNotFoundError(name)
            del store[name]

    monkeypatch.setattr(startup, "_winreg", lambda: FakeWinreg)
    monkeypatch.setattr(startup.sys, "platform", "win32")
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    monkeypatch.setattr(startup.sys, "executable", r"C:\Tools\DesignFinder\DesignFinder.exe")

    startup.set_enabled(True)
    assert store == {"DesignFinder": r'"C:\Tools\DesignFinder\DesignFinder.exe"'}
    assert startup.is_enabled()
    monkeypatch.setattr(startup.sys, "executable", r"D:\Moved\DesignFinder.exe")
    startup.repair()
    assert store["DesignFinder"] == r'"D:\Moved\DesignFinder.exe"'
    startup.set_enabled(False)
    startup.set_enabled(False)  # already off: no error
    assert store == {} and not startup.is_enabled()
