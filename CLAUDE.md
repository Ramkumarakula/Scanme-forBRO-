# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Goal

A free, fully offline Windows desktop tool for the user's brother. He gives it an image, and it checks whether that design already exists in his (already well organized) design folders. It should match even when the colors differ or the design is only nearly the same. For each match it shows the folder, because the **master file sits in the same folder as the matched photo**, and he can jump there in one click. In the end it becomes a small, lightweight window that stays on top of other apps.

`PROJECT_PLAN.md` holds the original handoff. Where it disagrees with the decisions below, the decisions below win. The plan says AutoCAD/`.dwg`, but the user has since said the masters are **SketchUp files (`.skp`) and `.skb` backups**.

## Confirmed decisions

- Target OS: Windows.
- Master files: `.skp` / `.skb` in the same folder as the matched image.
- Development and testing happen on the user's machine first, with a small sample dataset that the user will get from the brother. The brother's file count and folder locations will come later.
- Phase 1 scope: scan PNGs, search with a query image, return the matching directories (CLI only).

## Stack

Python 3.11, OpenCV + numpy (image normalization and perceptual hashing), SQLite (stdlib) for the index, pytest for tests. Later phases (pending user confirmation): Tkinter UI, Pillow `ImageGrab` for capture/clipboard, `watchdog`, PyInstaller.

## Commands

```
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

pytest                                         # all tests
pytest tests/test_search.py::test_recolored_design_matches   # single test

python -m designfinder index <root> [<root> ...]   # build/refresh index (incremental)
python -m designfinder search <image> [--top N]    # list best-matching folders
```

The index defaults to `data/index.db`; override it with `--db`.

## Architecture

The pipeline runs `scanner` → `fingerprint` → `index` (SQLite) → `search`.

- `fingerprint.py` makes matching color-independent. It converts the image to grayscale, crops away the plain background and re-pads it uniformly (so screenshot margins and scale don't matter), applies CLAHE contrast normalization, and builds a Canny edge map. For both the edge map and the gray image it keeps a **continuous** 63-value DCT signature: the 8×8 low frequencies minus DC, scaled to unit length.
  - Don't switch back to binary pHash bits. On clean line drawings many coefficients sit near zero, their bits flip on tiny noise, and a plain resize scored only about 0.65.
- `search.py` loads every signature into numpy matrices. The score is `max(edge·q, |tone·q|)`. The absolute value works because inverting an image negates its tone signature, so inverted colors still match. Results are grouped by folder (keeping each folder's best score), with the folder's master files attached.
- `index.py` keeps one row per image (path, folder, mtime, size, signatures stored as float32 BLOBs). Re-indexing skips files whose mtime and size are unchanged, and drops rows for files that have disappeared under the indexed roots.
- Synthetic-test scores: identical, recolored, or inverted copies score about 1.0, a lightly edited design about 0.88, and unrelated designs 0.05–0.3.
- Images are read with `np.fromfile` + `cv2.imdecode`, because `cv2.imread` fails on non-ASCII Windows paths.

The "same design" threshold has **not** been chosen. It has to be tuned on the brother's real example pairs, so the CLI shows ranked scores for now instead of a found/not-found verdict.

## Working rules

- Build one phase at a time, test each phase, and commit locally after each phase.
- Never invent content, features, tech choices, or numbers (such as thresholds). Ask the user instead.
- Ask the user for missing assets (sample images, example pairs, folder layouts).
- Never commit `.env`, real sample data, the index DB, or other large raw files. `data/` is gitignored for this reason.
- Don't push unless the user asks.
