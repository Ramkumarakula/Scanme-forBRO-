"""SQLite index of image fingerprints."""

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .fingerprint import fingerprint_file
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
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(_SCHEMA)
    return conn


def index_roots(conn: sqlite3.Connection, roots: list[str | Path],
                on_error=None) -> IndexStats:
    """Fingerprint new/changed images under roots; drop rows for deleted files."""
    stats = IndexStats()
    known = {row[0]: (row[1], row[2])
             for row in conn.execute("SELECT path, mtime, size FROM images")}

    for root in roots:
        root_abs = os.path.abspath(root)
        seen: set[str] = set()
        for path in iter_images(root_abs):
            key = str(path)
            seen.add(key)
            try:
                st = path.stat()
                if known.get(key) == (st.st_mtime, st.st_size):
                    stats.unchanged += 1
                    continue
                fp = fingerprint_file(path)
            except (OSError, ValueError) as exc:
                stats.failed += 1
                if on_error:
                    on_error(path, exc)
                continue
            conn.execute(
                "INSERT OR REPLACE INTO images VALUES (?, ?, ?, ?, ?, ?)",
                (key, str(path.parent), st.st_mtime, st.st_size,
                 fp.edge.tobytes(), fp.tone.tobytes()))
            if key in known:
                stats.updated += 1
            else:
                stats.added += 1

        prefix = root_abs.rstrip("\\/") + os.sep
        gone = [p for p in known if p.startswith(prefix) and p not in seen]
        conn.executemany("DELETE FROM images WHERE path = ?", [(p,) for p in gone])
        stats.removed += len(gone)
        for p in gone:
            del known[p]

    conn.commit()
    return stats
