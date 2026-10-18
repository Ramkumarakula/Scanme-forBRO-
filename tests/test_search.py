from pathlib import Path

from designfinder.__main__ import main
from designfinder.fingerprint import fingerprint_file, fingerprint_image
from designfinder.index import connect, index_roots
from designfinder.search import Index

from conftest import draw_design, save_png


def _search(root: Path, tmp_path: Path, query_img, top=3):
    conn = connect(tmp_path / "index.db")
    index_roots(conn, [root])
    return Index(conn).search(fingerprint_image(query_img), top=top)


def test_identical_design_returns_its_folder(design_root, tmp_path):
    matches = _search(design_root, tmp_path, draw_design("cabinet"))
    assert Path(matches[0].folder) == design_root / "Client A/cabinet"
    assert matches[0].score > 0.99


def test_recolored_design_matches(design_root, tmp_path):
    query = draw_design("cabinet", fg=(30, 160, 230), bg=(70, 20, 90))
    matches = _search(design_root, tmp_path, query)
    assert Path(matches[0].folder) == design_root / "Client A/cabinet"
    assert matches[0].score > matches[1].score


def test_inverted_colors_match(design_root, tmp_path):
    query = draw_design("table", fg=(255, 255, 255), bg=(0, 0, 0))
    matches = _search(design_root, tmp_path, query)
    assert Path(matches[0].folder) == design_root / "Client B/table"


def test_resized_design_with_extra_margin_matches(design_root, tmp_path):
    query = draw_design("cabinet", fg=(40, 90, 40), scale=1.6, margin=150)
    matches = _search(design_root, tmp_path, query)
    assert Path(matches[0].folder) == design_root / "Client A/cabinet"
    assert matches[0].score > matches[1].score


def test_slightly_changed_design_matches(design_root, tmp_path):
    query = draw_design("cabinet", extra_line=True, scale=0.7)
    matches = _search(design_root, tmp_path, query)
    assert Path(matches[0].folder) == design_root / "Client A/cabinet"
    assert matches[0].score > matches[1].score


def test_results_grouped_by_folder_with_masters(design_root, tmp_path):
    save_png(design_root / "Client A/cabinet/render_v2.png", draw_design("cabinet"))
    matches = _search(design_root, tmp_path, draw_design("cabinet"), top=5)
    folders = [m.folder for m in matches]
    assert len(folders) == len(set(folders)) == 3
    assert {p.suffix for p in matches[0].masters} == {".skp", ".skb"}


def test_reindex_is_incremental_and_drops_deleted(design_root, tmp_path):
    conn = connect(tmp_path / "index.db")
    first = index_roots(conn, [design_root])
    assert first.added == 3

    (design_root / "Client B/shelf/render.png").unlink()
    save_png(design_root / "New/sofa/render.png", draw_design("table"))
    second = index_roots(conn, [design_root])
    assert (second.added, second.unchanged, second.removed) == (1, 2, 1)


def test_non_ascii_path_and_transparent_png(tmp_path):
    import numpy as np
    img = draw_design("shelf")
    rgba = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
    rgba[:20, :20, 3] = 0
    path = save_png(tmp_path / "डिज़ाइन" / "ünï.png", rgba)
    a, b = fingerprint_file(path), fingerprint_image(img)
    assert np.allclose(a.edge, b.edge) and np.allclose(a.tone, b.tone)


def test_cli_index_and_search(design_root, tmp_path, capsys):
    db = tmp_path / "cli.db"
    query = save_png(tmp_path / "query.png", draw_design("shelf", fg=(0, 0, 200)))
    assert main(["--db", str(db), "index", str(design_root)]) == 0
    assert main(["--db", str(db), "search", str(query), "--top", "1"]) == 0
    out = capsys.readouterr().out
    assert str(design_root / "Client B" / "shelf") in out
    assert "shelf.skp" in out


def test_removed_root_is_dropped_only_when_asked(design_root, tmp_path):
    conn = connect(tmp_path / "index.db")
    index_roots(conn, [design_root])
    client_a = design_root / "Client A"

    kept = index_roots(conn, [client_a])  # CLI style: other roots stay
    assert kept.removed == 0
    pruned = index_roots(conn, [str(client_a).upper()], only_these_roots=True)  # app style
    assert pruned.removed == 2
    folders = {r[0] for r in conn.execute("SELECT folder FROM images")}
    assert folders == {str(client_a / "cabinet")}
