"""End-to-end check on the generated mock library (recolored, WhatsApp JPEG, screenshot...)."""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import eval_queries  # noqa: E402
import make_mock_data  # noqa: E402

from designfinder.index import connect  # noqa: E402


def test_mock_queries_find_their_folders(tmp_path):
    make_mock_data.build(tmp_path)
    results = eval_queries.evaluate(tmp_path)
    known = [r for r in results if r["correct"] is not None]
    new = [r for r in results if r["correct"] is None]
    assert all(r["correct"] for r in known), [r["query"] for r in known if not r["correct"]]
    assert max(r["score"] for r in new) < min(r["score"] for r in known)


def test_index_from_older_signature_version_is_rebuilt(tmp_path):
    db = tmp_path / "old.db"
    old = sqlite3.connect(db)
    old.execute("CREATE TABLE images (path TEXT PRIMARY KEY, junk TEXT)")
    old.execute("INSERT INTO images VALUES ('x', 'y')")
    old.commit()
    old.close()
    conn = connect(db)
    assert conn.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 0
