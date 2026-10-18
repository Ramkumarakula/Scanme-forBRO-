from pathlib import Path

import cv2
import numpy as np
import pytest


def draw_design(kind: str, fg=(0, 0, 0), bg=(255, 255, 255), extra_line=False,
                scale=1.0, margin=0) -> np.ndarray:
    """Simple line drawings standing in for design renders.

    scale resizes the finished drawing; margin pads it with background (like a loose screen capture).
    """
    img = np.full((400, 600, 3), bg, dtype=np.uint8)
    if kind == "cabinet":
        cv2.rectangle(img, (60, 40), (540, 360), fg, 6)
        cv2.line(img, (300, 40), (300, 360), fg, 6)
        cv2.circle(img, (270, 200), 12, fg, -1)
        cv2.circle(img, (330, 200), 12, fg, -1)
        if extra_line:
            cv2.line(img, (60, 300), (540, 300), fg, 4)
    elif kind == "table":
        cv2.ellipse(img, (300, 120), (240, 60), 0, 0, 360, fg, 6)
        for x in (110, 490):
            cv2.line(img, (x, 140), (x, 370), fg, 8)
    elif kind == "shelf":
        for y in (60, 160, 260, 360):
            cv2.line(img, (100, y), (500, y), fg, 6)
        cv2.line(img, (100, 60), (100, 360), fg, 6)
        cv2.line(img, (500, 60), (500, 360), fg, 6)
        cv2.polylines(img, [np.array([[150, 150], [220, 80], [290, 150]])], False, fg, 5)
    else:
        raise ValueError(kind)
    if scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if margin:
        img = cv2.copyMakeBorder(img, margin, margin // 2, margin // 3, margin,
                                 cv2.BORDER_CONSTANT, value=bg)
    return img


def save_png(path: Path, img: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(path))
    return path


@pytest.fixture
def design_root(tmp_path: Path) -> Path:
    """Three project folders, each with a render and a SketchUp master file."""
    root = tmp_path / "designs"
    for folder, kind in [("Client A/cabinet", "cabinet"), ("Client B/table", "table"),
                         ("Client B/shelf", "shelf")]:
        save_png(root / folder / "render.png", draw_design(kind))
        (root / folder / f"{kind}.skp").write_bytes(b"skp")
    (root / "Client A/cabinet/cabinet.skb").write_bytes(b"skb")
    return root
