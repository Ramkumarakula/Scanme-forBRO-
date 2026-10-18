"""Where the app keeps its index and settings, and which design folders to scan."""

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "DesignFinder"


def data_dir() -> Path:
    """Folder for settings.json and index.db.

    Installed .exe: next to the exe (portable, e.g. C:\\Tools\\DesignFinder), falling back
    to %LOCALAPPDATA%\\DesignFinder if that folder is not writable.
    Running from source: the repo's data\\ folder (gitignored).
    """
    if getattr(sys, "frozen", False):
        beside_exe = Path(sys.executable).resolve().parent
        if _writable(beside_exe):
            return beside_exe
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
    else:
        base = Path.cwd() / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _writable(folder: Path) -> bool:
    probe = folder / ".write_test"
    try:
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


@dataclass
class Settings:
    roots: list[str] = field(default_factory=list)
    on_top: bool = True
    bubble_x: int | None = None  # where the floating symbol was last dropped
    bubble_y: int | None = None

    @classmethod
    def load(cls, path: Path) -> "Settings":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        roots = [r for r in raw.get("roots", []) if isinstance(r, str)]
        return cls(roots=roots, on_top=bool(raw.get("on_top", True)),
                   bubble_x=_int_or_none(raw.get("bubble_x")),
                   bubble_y=_int_or_none(raw.get("bubble_y")))

    def save(self, path: Path) -> None:
        data = {"roots": self.roots, "on_top": self.on_top,
                "bubble_x": self.bubble_x, "bubble_y": self.bubble_y}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _int_or_none(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
