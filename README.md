# Design Finder

Give it a picture of a design. It tells you which folder in your design library has the same (or nearly the same) design, even if the colors are different. It also lists the SketchUp master files (`.skp` / `.skb`) in that folder.

It is free, fully offline, and runs on Windows. Nothing is uploaded anywhere.

> **Status:** Phase 3. A small always-on-top window, plus a single `DesignFinder.exe` that needs no Python.

<img src="docs/window.png" width="360" alt="Design Finder window: a dark-mode query image at the top, matching design folders below with scores and Open folder buttons">

*(The screenshot uses the mock data. The query is a dark-mode drawing, and the top result is the light-colored original.)*

## Install on his laptop (no Python needed)

1. **Get the file.** On the development PC, run `python scripts\build_exe.py`. This creates `dist\DesignFinder.exe` (about 75 MB). Copy it to his laptop by USB stick or Google Drive. WhatsApp and e-mail often block `.exe` files.
2. **Put it in its own folder,** for example `C:\Tools\DesignFinder\`. Don't use `Program Files`. The app saves its settings and index **next to the exe**, so that folder must be writable. If it isn't, the app falls back to `%LOCALAPPDATA%\DesignFinder`.
3. **First start:** double-click `DesignFinder.exe`.
   - Windows may show *"Windows protected your PC"*, because the exe isn't code-signed. Click **More info → Run anyway**. This happens only once.
   - Some antivirus tools are suspicious of PyInstaller apps in general. If it gets quarantined, allow `DesignFinder.exe` in the antivirus.
   - Starting takes about 5 seconds, because the single-file exe unpacks itself each time.
4. **Choose the design folders.** The *Design folders* window opens on the first start. Click **Add folder…** for each top folder (sub-folders are included), then **Save and scan**. The first scan reads every image once. After that, each start re-checks only new or changed files.
5. **Optional shortcut:** right-click `DesignFinder.exe` → *Show more options* → *Send to* → *Desktop (create shortcut)*. You can also pin it to the taskbar.

**Updating:** replace `DesignFinder.exe`. His `settings.json` and `index.db` stay where they are.
**Uninstalling:** delete the folder. Nothing else is installed, and no registry entries are made.

## Using the window

- **Snip and paste:** press `Win+Shift+S`, select the design on screen, then click in Design Finder and press **Ctrl+V**. A copied image file also works.
- **Open image…:** pick any PNG, JPG or WEBP file.
- **Open with:** right-click an image → *Open with* → *Choose another app* → `DesignFinder.exe`.
- Each result shows the matching image, its **score** (1.00 = same design), the folder, and the SketchUp files there. **Open folder** opens Explorer with the newest `.skp`/`.skb` selected, ready to drag into SketchUp.
- **Keep on top** keeps the window above every other app. Untick it to turn that off. The choice is remembered.
- **Folders…** changes the design folders. **Re-scan** picks up new designs without restarting.

## How to check it works on his laptop

1. Search with an image that **is already** in his folders. Its folder should come first with a score of about 1.00.
2. Search with a **WhatsApp copy** or a **screenshot** of one of his designs. The right folder should still come first.
3. Search with a **recolored** version of a design, if he has one. Its folder should come first, with a clearly lower score for the second result.
4. Search with something he has **never** designed. All scores should be noticeably lower.
5. Click **Open folder** and check that Explorer opens with the SketchUp file selected.

Please note any wrong results (query image plus the folder that should have matched). Those examples are exactly what's needed to tune the matching and set the "found / new" cutoff.

## Command line (for development)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

python -m designfinder.app [image]          # the window, from source

# 1. Build the index once (later runs only process new/changed images)
python -m designfinder index "D:\Designs"

# 2. Search with any image
python -m designfinder search "C:\Users\me\Downloads\IMG-20250312-WA0007.jpg" --top 5
```

Example output:

```
1. 0.95  D:\Designs\Client A\Wardrobe 3-door
     image:  wardrobe_front.png
     master: wardrobe_3door.skp, wardrobe_3door.skb
2. 0.55  D:\Designs\Client C\Bookshelf
     ...
```

Each result shows a **score** (higher = more similar), the **folder**, the image in that folder that matched best, and the master files in that folder (newest first).

From source, the index is stored in `data\index.db` and the window's settings in `data\settings.json`. Use `--db <file>` to put the CLI index somewhere else. The CLI doesn't share the exe's index.

**Supported image types:** `.png`, `.jpg`, `.jpeg` (WhatsApp photos), `.webp` (WhatsApp stickers).

## How the matching works

No AI model is involved and nothing goes online. Every image goes through the same steps:

1. **Read and flatten.** The image is decoded (PNG, JPG and WEBP all end up as the same pixel grid). Transparent areas become white.
2. **Remove color.** The image is converted to **grayscale**, so a blue wardrobe and a brown wardrobe start to look alike.
3. **Crop away the margins.** Plain background around the design is trimmed. This repeats, because a screenshot has two margins: the screen around the picture, and the picture's own background. A uniform margin is then added back, and the image is resized to a standard 256 px.
4. **Even out contrast** (CLAHE). Pale and strong color schemes end up at similar contrast.
5. **Make two "views" of the design:**
   - an **edge map**: just the lines and outlines of the drawing. This view is the same whatever the colors are.
   - the **tone image**: the grayscale picture itself.
6. **Make a fingerprint of each view.** The view is shrunk to 32×32 and its **DCT** (the same math JPEG uses) is computed. The 16×16 lowest-frequency values (the overall layout, ignoring tiny details) are kept and scaled to length 1. That gives 255 numbers per view.
7. **Compare.** Two images are compared with **cosine similarity** of their fingerprints, giving 1.0 for identical and about 0 for unrelated. The final score is the average of the edge similarity and the tone similarity. For tone, the sign is ignored, so a design with **inverted colors** (dark mode, white lines on black) still matches.

So images are **not** converted to another file format. Each one is reduced to two short lists of numbers (fingerprints), which are stored in a small SQLite database. A search fingerprints the query image the same way and compares it against all stored fingerprints at once. Results are grouped by folder, and each folder keeps its best-matching image.

### Why not normal "perceptual hashes" (pHash)?

That was the first approach. On clean line drawings it turned bits on and off almost randomly, and a plain resize of the same drawing scored barely above an unrelated one. Keeping the actual numbers and using cosine similarity fixed this.

## Test with mock data

There is no real data from the designer yet, so `mock_data/` holds a **synthetic** library. It contains six furniture drawings across three "clients". Some are PNG, some are WhatsApp-style JPEG (`IMG-…-WA….jpg`), and one is WEBP. Each folder has **placeholder** `.skp`/`.skb` files. These are text files, not real SketchUp models.

`mock_data/queries/` contains search images that differ from the library: recolored, dark mode (inverted), WhatsApp-compressed, screenshot with margins, an extra shelf, an extra door, and one design that is **not** in the library.

```powershell
python scripts\make_mock_data.py        # regenerate mock_data\
python scripts\eval_queries.py          # index mock_data\designs and score every query
```

Current result:

| Query | Expected folder | Score | 2nd best | Result |
|---|---|---|---|---|
| wardrobe, navy colors | Wardrobe 3-door | 0.95 | 0.55 | OK |
| kitchen, WhatsApp JPEG + pastel | Kitchen | 0.63 | 0.54 | OK |
| reception desk, dark mode | Reception desk | 0.78 | 0.69 | OK |
| TV unit, screenshot with margins | TV unit | 0.95 | 0.54 | OK |
| bed, WhatsApp JPEG + dark | Bed with storage | 0.93 | 0.57 | OK |
| bookshelf with 5 shelves (library has 4) | Bookshelf | 0.90 | 0.63 | OK |
| wardrobe with 4 doors (library has 3) | Wardrobe 3-door | 0.64 | 0.58 | OK |
| coffee table (new design) | — | 0.38 | | not in library |

**7/7 found correctly.** Every correct match scores at least 0.63, and the new design scores 0.38.

**Known limits:**
- Some correct matches beat the second-best folder by only about 0.06–0.09 (the edited wardrobe, the pastel kitchen). Boxy furniture drawings look alike at this level of detail.
- The cutoff between "found" and "this looks new" is **not set yet**. It has to be picked from real example pairs, so for now the tool shows ranked scores.
- If real data shows confusion, the next improvement is to re-check the top results with feature-point matching (ORB).

The same evaluation works on real samples. Put them in `data\` (gitignored) with the same `designs\` + `queries\expected.csv` layout and run `python scripts\eval_queries.py data`.

## Development

```powershell
pytest                                                  # all tests
pytest tests/test_search.py::test_recolored_design_matches   # one test
python scriptsuild_exe.py                             # build dist\DesignFinder.exe
pip-audit --skip-editable                               # known-vulnerability check of dependencies
bandit -q -r src scripts packaging                      # static security scan
```

| Path | What it does |
|---|---|
| `src/designfinder/fingerprint.py` | Image → fingerprints (steps 1–6 above) |
| `src/designfinder/index.py` | SQLite index: incremental re-scan, drops removed folders, auto-rebuild when the fingerprint format changes |
| `src/designfinder/search.py` | In-memory comparison (step 7), grouping by folder |
| `src/designfinder/scanner.py` | Finds image files and master files |
| `src/designfinder/app.py` | The always-on-top window (Tkinter) |
| `src/designfinder/settings.py` | Where settings/index live, and the chosen design folders |
| `src/designfinder/__main__.py` | Command line |
| `packaging/launcher.py`, `scripts/build_exe.py` | Single-file exe (PyInstaller) |
| `scripts/` | Mock data generator, evaluation, exe build |
| `tests/` | Unit tests plus an end-to-end test on the mock data |

## Security

- **Fully offline.** There is no network code, no `eval` and no `pickle`. Fingerprints are stored as raw float arrays.
- The only external program it starts is Windows' own `explorer.exe`. It's called by full path (no PATH lookup) with no shell, and only for files that exist in the index and contain no quote character.
- All SQL uses parameters, so file names can't inject SQL.
- `settings.json` is validated on load. A corrupt or tampered file falls back to defaults instead of crashing.
- Folder scanning doesn't follow symbolic links, so it can't loop or escape the chosen folders.
- Images are decoded by OpenCV and Pillow. Keep dependencies up to date, re-run `pip-audit`, and rebuild the exe. Real design files, `.env` files, the index database and built exes are gitignored and never committed.
- The exe is **not code-signed**, so Windows SmartScreen warns on first run (see the install steps above).
- At the time of this phase, `pip-audit` reports no known vulnerabilities and `bandit` reports no issues.

## Roadmap

1. ~~Phase 1: index PNGs, search, return folder~~
2. ~~Phase 2: JPG/WEBP support, mock data, evaluation, docs, security checks~~
3. ~~Phase 3: always-on-top window (open / paste / Open folder), single `.exe`, install guide~~
4. Next: tune on real samples and set the "found / new" cutoff (needs the designer's files)
5. Later, still to be confirmed: screen-capture hotkey, tray icon, watching folders for changes, auto-start with Windows
