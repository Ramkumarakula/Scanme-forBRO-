"""Find the folders whose images best match a query image."""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .fingerprint import SIGNATURE_LEN, Fingerprint
from .scanner import master_files


@dataclass
class FolderMatch:
    folder: str
    score: float          # cosine similarity; 1.0 = same design, near 0 = unrelated
    best_image: str
    masters: list[Path] = field(default_factory=list)


class Index:
    """Fingerprints held in memory for fast comparison."""

    def __init__(self, conn: sqlite3.Connection):
        rows = conn.execute("SELECT path, folder, edge, tone FROM images").fetchall()
        self.paths = [r[0] for r in rows]
        self.folders = [r[1] for r in rows]
        self.edge = _matrix([r[2] for r in rows])
        self.tone = _matrix([r[3] for r in rows])

    def __len__(self) -> int:
        return len(self.paths)

    def scores(self, fp: Fingerprint) -> np.ndarray:
        """Per-image similarity: mean of edge-map and tone cosine (abs, so inversions match).

        Mean rather than max: on boxy furniture drawings either signature alone often
        scores a different design highly; requiring both separates them better.
        """
        return (self.edge @ fp.edge + np.abs(self.tone @ fp.tone)) / 2

    def search(self, fp: Fingerprint, top: int = 5) -> list[FolderMatch]:
        if not self.paths:
            return []
        scores = self.scores(fp)
        best: dict[str, int] = {}
        for i in np.argsort(-scores, kind="stable"):
            folder = self.folders[i]
            if folder not in best:
                best[folder] = int(i)
                if len(best) == top:
                    break
        return [FolderMatch(folder=f, score=float(scores[i]), best_image=self.paths[i],
                            masters=master_files(f))
                for f, i in best.items()]


def _matrix(blobs: list[bytes]) -> np.ndarray:
    if not blobs:
        return np.empty((0, SIGNATURE_LEN), dtype=np.float32)
    return np.frombuffer(b"".join(blobs), dtype=np.float32).reshape(len(blobs), SIGNATURE_LEN)
