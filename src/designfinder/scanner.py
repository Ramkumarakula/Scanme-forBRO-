"""Walk design roots and find image and master files."""

import os
from collections.abc import Iterator
from pathlib import Path

from . import IMAGE_EXTENSIONS, MASTER_EXTENSIONS


def iter_images(root: str | Path) -> Iterator[Path]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS:
                yield Path(dirpath) / name


def master_files(folder: str | Path) -> list[Path]:
    """SketchUp files in a folder, newest first."""
    try:
        entries = [p for p in Path(folder).iterdir()
                   if p.is_file() and p.suffix.lower() in MASTER_EXTENSIONS]
    except OSError:
        return []
    return sorted(entries, key=lambda p: p.stat().st_mtime, reverse=True)
