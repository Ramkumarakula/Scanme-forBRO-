"""Generate a mock design library and query images for testing.

    python scripts/make_mock_data.py [output_dir]      (default: mock_data)

Everything here is synthetic. The drawings are simple furniture elevations made with
OpenCV, and the .skp/.skb files are text placeholders, NOT real SketchUp models.
"""

import csv
import sys
from pathlib import Path

import cv2
import numpy as np

W, H = 800, 600

# Palettes are BGR. "Original" colors are used in the library; queries use others.
WOOD = dict(bg=(255, 255, 255), line=(30, 50, 80), panel=(140, 190, 225), accent=(40, 160, 200))
NAVY = dict(bg=(235, 235, 235), line=(90, 30, 20), panel=(150, 140, 40), accent=(255, 255, 255))
DARK = dict(bg=(25, 25, 25), line=(230, 230, 230), panel=(70, 70, 70), accent=(0, 200, 255))
PASTEL = dict(bg=(240, 250, 255), line=(80, 80, 160), panel=(200, 180, 250), accent=(120, 200, 120))


def _canvas(p):
    return np.full((H, W, 3), p["bg"], dtype=np.uint8)


def _box(img, p, x1, y1, x2, y2, fill=True, thick=4):
    if fill:
        cv2.rectangle(img, (x1, y1), (x2, y2), p["panel"], -1)
    cv2.rectangle(img, (x1, y1), (x2, y2), p["line"], thick)


def wardrobe(p, doors=3):
    img = _canvas(p)
    _box(img, p, 150, 60, 650, 540)
    cv2.line(img, (150, 150), (650, 150), p["line"], 4)  # loft
    step = 500 // doors
    for i in range(1, doors):
        cv2.line(img, (150 + i * step, 150), (150 + i * step, 540), p["line"], 4)
    for i in range(doors):
        x = 150 + i * step + step - 25
        cv2.rectangle(img, (x, 300), (x + 10, 380), p["accent"], -1)
    return img


def kitchen(p):
    img = _canvas(p)
    for i in range(5):  # wall cabinets
        _box(img, p, 80 + i * 110, 60, 180 + i * 110, 200)
    cv2.rectangle(img, (60, 330), (720, 350), p["line"], -1)  # counter
    for i in range(4):  # base cabinets
        _box(img, p, 80 + i * 140, 350, 210 + i * 140, 540)
    _box(img, p, 640, 200, 740, 540)  # tall unit
    cv2.ellipse(img, (220, 340), (60, 10), 0, 0, 360, p["accent"], -1)  # sink
    for x in (430, 490):
        cv2.circle(img, (x, 320), 18, p["accent"], 3)  # hob
    return img


def reception_desk(p):
    img = _canvas(p)
    pts = np.array([[120, 260], [680, 260], [620, 520], [180, 520]])
    cv2.fillPoly(img, [pts], p["panel"])
    cv2.polylines(img, [pts], True, p["line"], 5)
    cv2.rectangle(img, (100, 230), (700, 260), p["line"], -1)  # top
    for x in range(220, 600, 60):
        cv2.line(img, (x, 280), (x, 500), p["accent"], 6)  # slats
    return img


def tv_unit(p):
    img = _canvas(p)
    _box(img, p, 220, 90, 580, 300, fill=False, thick=8)  # TV
    _box(img, p, 80, 400, 720, 500)
    for x in (240, 400, 560):
        cv2.line(img, (x, 400), (x, 500), p["line"], 4)
    for y in (140, 220, 300):  # side shelves
        cv2.line(img, (90, y), (180, y), p["line"], 5)
        cv2.line(img, (620, y), (710, y), p["line"], 5)
    return img


def bed(p):
    img = _canvas(p)
    _box(img, p, 100, 120, 700, 300)  # headboard
    for x in (250, 400, 550):
        cv2.line(img, (x, 130), (x, 290), p["line"], 3)
    _box(img, p, 80, 300, 720, 380, fill=False)  # mattress
    _box(img, p, 80, 380, 720, 520)
    for x in (240, 560):
        cv2.line(img, (x - 40, 450), (x + 40, 450), p["accent"], 8)  # drawer handles
    return img


def bookshelf(p, shelves=4):
    img = _canvas(p)
    _box(img, p, 200, 40, 600, 560, fill=False, thick=6)
    gap = 520 // shelves
    for i in range(1, shelves):
        cv2.line(img, (200, 40 + i * gap), (600, 40 + i * gap), p["line"], 6)
    rng = np.random.default_rng(7)
    for i in range(shelves):
        x = 215
        base = 40 + (i + 1) * gap - 4
        while x < 560:
            bw, bh = int(rng.integers(15, 35)), int(rng.integers(gap // 2, gap - 15))
            cv2.rectangle(img, (x, base - bh), (x + bw, base), p["panel"], -1)
            cv2.rectangle(img, (x, base - bh), (x + bw, base), p["line"], 2)
            x += bw + 4
    return img


def coffee_table(p):
    img = _canvas(p)
    cv2.ellipse(img, (400, 250), (260, 70), 0, 0, 360, p["panel"], -1)
    cv2.ellipse(img, (400, 250), (260, 70), 0, 0, 360, p["line"], 5)
    for x in (230, 570):
        cv2.line(img, (x, 300), (x - 20, 500), p["line"], 8)
    return img


# --- variants used for queries -------------------------------------------------------

def screenshot(img, margin=120, chrome=(200, 200, 200)):
    """Design pasted on a larger plain area, as in a loose screen capture."""
    return cv2.copyMakeBorder(img, margin, margin // 2, margin // 3, margin,
                              cv2.BORDER_CONSTANT, value=chrome)


def whatsapp(img, scale=0.6):
    """Downscaled; written as low-quality JPEG by save()."""
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def save(path: Path, img, quality=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    params = []
    if path.suffix.lower() in (".jpg", ".jpeg"):
        params = [cv2.IMWRITE_JPEG_QUALITY, quality or 90]
    elif path.suffix.lower() == ".webp":
        params = [cv2.IMWRITE_WEBP_QUALITY, quality or 90]
    ok, buf = cv2.imencode(path.suffix, img, params)
    if not ok:
        raise RuntimeError(f"encode failed: {path}")
    buf.tofile(str(path))


def placeholder_master(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"PLACEHOLDER for {path.name} - not a real SketchUp file (mock data)\n",
                    encoding="utf-8")


# folder -> (image files written in the original palette, master files)
LIBRARY = {
    "Client A/Wardrobe 3-door": (wardrobe, ["wardrobe_front.png", "IMG-20250312-WA0007.jpg"],
                                 ["wardrobe_3door.skp", "wardrobe_3door.skb"]),
    "Client A/Kitchen": (kitchen, ["kitchen_elevation.png"], ["kitchen.skp"]),
    "Client B/Reception desk": (reception_desk, ["reception.webp"],
                                ["reception_desk.skp", "reception_desk.skb"]),
    "Client B/TV unit": (tv_unit, ["IMG-20250402-WA0013.jpg"], ["tv_unit.skp"]),
    "Client C/Bed with storage": (bed, ["bed.png"], ["bed_v2.skp", "bed_v1.skp", "bed_v2.skb"]),
    "Client C/Bookshelf": (bookshelf, ["bookshelf.png"], ["bookshelf.skp"]),
}

# query file -> (image, expected folder or "" if the design should be new)
QUERIES = {
    "wardrobe_navy_colors.png": (lambda: wardrobe(NAVY), "Client A/Wardrobe 3-door"),
    "kitchen_whatsapp_pastel.jpg": (lambda: whatsapp(kitchen(PASTEL)), "Client A/Kitchen"),
    "reception_dark_mode.png": (lambda: reception_desk(DARK), "Client B/Reception desk"),
    "tv_unit_screenshot.png": (lambda: screenshot(tv_unit(NAVY)), "Client B/TV unit"),
    "bed_whatsapp_dark.jpg": (lambda: whatsapp(bed(DARK), 0.5), "Client C/Bed with storage"),
    "bookshelf_5_shelves.png": (lambda: bookshelf(PASTEL, shelves=5), "Client C/Bookshelf"),
    "wardrobe_4_doors.png": (lambda: wardrobe(WOOD, doors=4), "Client A/Wardrobe 3-door"),
    "new_coffee_table.png": (lambda: coffee_table(WOOD), ""),
}


def build(out: Path) -> None:
    for folder, (draw, images, masters) in LIBRARY.items():
        base = draw(WOOD)
        for name in images:
            img = whatsapp(base) if "-WA" in name else base
            save(out / "designs" / folder / name, img, quality=50 if "-WA" in name else None)
        for name in masters:
            placeholder_master(out / "designs" / folder / name)

    (out / "queries").mkdir(parents=True, exist_ok=True)
    with open(out / "queries" / "expected.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["query", "expected_folder"])
        for name, (make, expected) in QUERIES.items():
            save(out / "queries" / name, make(), quality=45 if name.endswith(".jpg") else None)
            writer.writerow([name, expected])


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "mock_data")
    build(target)
    print(f"Mock data written to {target.resolve()}")
