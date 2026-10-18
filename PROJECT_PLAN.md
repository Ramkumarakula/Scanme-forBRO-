# Handoff: Design photo finder for brother's AutoCAD workflow

## 1. Project goal and who it is for

**For:** the user's brother, who works with design files on his laptop (files in File Explorer, imported into AutoCAD for design).

**Problem (user's words):** "my brother have files in his file explorer in laptop some time he need to go through the photos to check whether he did it before and file will be little different so if he find he will find the master file which is in the same folder so he can grab it and import in the autocad for the design"

**Goal:** when he gives an image, the tool checks whether it is already there or not, and brings up the most related photos.

## 2. Overall concept and the scroll experience

Not applicable: no website or scroll experience was discussed. The project is a lightweight desktop search tool.

## 3. Pages/sections

Not applicable: no pages or sections were discussed.

## 4. Visual style

Not discussed: no colors, fonts, mood or references were given.

---

## DECIDED (confirmed by the user)

- Match images even when they are in different colors and the design is almost similar: "we will do this" ("make it recognise even they are in different colors and the design is almost similar").
- A fixed window: "we will give a fixed window where this can be there in the application".
- Search efficiency over re-organizing: "not every time he searches for some thing he organised them very well we just need to make search efficient". The files are already well organised.
- Result should "give the directory of the file and make him move there in one click".
- Completely free, with no hosting: "i dont want to host it somewhere".
- Easily accessible, lightweight, "maybe sits on top of all aplication light weight when asked".
- Input is "maybe capturing screen or giving it the photo".
- The master file is in the same folder as the matched photo.

## SUGGESTED BUT NOT CONFIRMED (proposed by Claude, no clear agreement from the user)

**Matching**
- Perceptual hashing (pHash/dHash) as the first approach, with a small CLIP embedding model (CPU, offline) added only if there are too many misses.
- To ignore color: grayscale, contrast normalization, edge/line map, and fingerprinting both the edge map and its inverted version.
- Two-stage matching: fast shortlist, then re-rank the top ~20 with ORB/SIFT feature matching or CLIP.
- Tune the "same design" score threshold using 10-20 real example pairs from his folders.

**Index and search**
- Index only his design root folders; one record per image (fingerprint, folder path, master file).
- Store the index in a SQLite file; process only new or changed files after the first run.
- Keep fingerprints in memory at startup for fast comparison.
- Group results by folder, showing each folder once with its best score.
- Watch folders for changes with the `watchdog` library.
- Master file detection: the .dwg in the matched folder, or the newest one if there are several.
- If no score passes the threshold, show "Not found, this looks new."

**Application and UI**
- Python app, with Tkinter for a small always-on-top window.
- Global hotkey (example given: Ctrl+Alt+F) to open it; system tray icon.
- Saved capture region, so one hotkey captures that exact area and searches instantly.
- Drag and drop and clipboard paste (Win+Shift+S then Ctrl+V) as backup inputs.
- Each result shows the folder path and master file name, with two buttons: "Open folder" (Explorer with the master file highlighted) and "Open in AutoCAD" (default app).

**Packaging and placement**
- Package as a single .exe with PyInstaller, kept in a folder such as `C:\Tools\DesignFinder`, with the index file next to it.
- First launch asks him to pick the design root folders.
- Auto-start via a shortcut in `shell:startup`.
- Fully offline; internet needed only for the one-time library/model download.
- Libraries named: Python, OpenCV, Pillow, SQLite, Tkinter, watchdog, PyInstaller, optional CLIP model.
- Existing tools (Awesome Duplicate Photo Finder, VisiPics) mentioned as not covering this flow.

## OPEN QUESTIONS

1. Is his laptop Windows? (asked twice, not answered; the plan above assumes Windows)
2. Roughly how many images are in his folders (hundreds, thousands, tens of thousands)? (asked, not answered)
3. Which file types are the "photos" (JPG, PNG, other), and is the master file always a .dwg? Only .dwg was mentioned, as an example.
4. How should the master file be chosen when a folder has more than one candidate? "Newest" was only a suggestion.
5. Should the first version use hashing only, or include the CLIP model? The user has not chosen.
6. Hotkey, tray icon, auto-start at login and the saved capture region were suggested, but the user said only "maybe" for capture and on-top behavior.
7. Which input methods are required in version 1: screen capture, giving the photo, both?
8. The user's list ended at "5." and no further section was specified. Which sections should the handoff include beyond 1-4?
9. Sections 2-4 as worded (scroll experience, pages, visual style) don't match this project. Should they be dropped, or was this meant to be a different project (for example a website)?
10. What similarity threshold counts as "same design"? It needs real example files from the brother.

## Constraints for Claude Code

- Build only from the DECIDED list. Treat the SUGGESTED list as proposals to confirm with the user before implementing.
- Do not add features, tech choices or numbers that are not listed above.
- Resolve the OPEN QUESTIONS with the user before building.