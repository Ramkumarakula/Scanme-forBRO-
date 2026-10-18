"""SQLite index of image fingerprints."""

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .fingerprint import SIGNATURE_VERSION, fingerprint_file
from .scanner import iter_images

_SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    path   TEXT PRIMARY KEY,
    folder TEXT NOT NULL,
    mtime  REAL NOT NULL,
    size   INTEGER NOT NULL,
    edge   BLOB NOT NULL,
    tone   BLOB NOT NULL
)
"""


@dataclass
class IndexStats:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    failed: int = 0


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open the index; if it was built with a different signature format, start it fresh."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SIGNATURE_VERSION:
        conn.execute("DROP TABLE IF EXISTS images")
        conn.execute(f"PRAGMA user_version = {int(SIGNATURE_VERSION)}")
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def index_roots(conn: sqlite3.Connection, roots: list[str | Path],
                on_error=None, only_these_roots: bool = False) -> IndexStats:
    """Fingerprint new/changed images under roots; drop rows for deleted files.

    only_these_roots: also drop images outside every given root (the app passes True, so a
    folder removed from its list disappears from results; the CLI adds roots one at a time).
    """
    stats = IndexStats()
    # Windows paths are case-insensitive: compare on normcase, keep the stored spelling.
    known = {os.path.normcase(path): (path, mtime, size)
             for path, mtime, size in conn.execute("SELECT path, mtime, size FROM images")}

    def drop(keys: list[str]) -> None:
        conn.executemany("DELETE FROM images WHERE path = ?", [(known[k][0],) for k in keys])
        stats.removed += len(keys)
        for k in keys:
            del known[k]

    if only_these_roots:
        prefixes = tuple(_prefix(r) for r in roots)
        drop([k for k in known if not k.startswith(prefixes)])

    for root in roots:
        root_abs = os.path.abspath(root)
        seen: set[str] = set()
        for path in iter_images(root_abs):
            key = os.path.normcase(str(path))
            seen.add(key)
            old = known.get(key)
            try:
                st = path.stat()
                if old and old[1:] == (st.st_mtime, st.st_size):
                    stats.unchanged += 1
                    continue
                fp = fingerprint_file(path)
            except (OSError, ValueError) as exc:
                stats.failed += 1
                if on_error:
                    on_error(path, exc)
                continue
            if old:
                conn.execute("DELETE FROM images WHERE path = ?", (old[0],))
            conn.execute(
                "INSERT OR REPLACE INTO images VALUES (?, ?, ?, ?, ?, ?)",
                (str(path), str(path.parent), st.st_mtime, st.st_size,
                 fp.edge.tobytes(), fp.tone.tobytes()))
            known[key] = (str(path), st.st_mtime, st.st_size)
            if old:
                stats.updated += 1
            else:
                stats.added += 1

        prefix = _prefix(root_abs)
        drop([k for k in known if k.startswith(prefix) and k not in seen])

    conn.commit()
    return stats


def _prefix(root: str | Path) -> str:
    """Case-insensitive (on Windows) path prefix that matches files inside root."""
    return os.path.normcase(os.path.abspath(root)).rstrip("\\/") + os.sep
