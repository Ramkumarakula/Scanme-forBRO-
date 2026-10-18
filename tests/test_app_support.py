"""Non-UI parts of the desktop app: settings, data folder, clipboard image conversion."""

import json
import sys

import numpy as np
from PIL import Image

from designfinder import app, settings
from designfinder.search import FolderMatch


def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    settings.Settings(roots=[r"D:\Designs", r"E:\Old"], on_top=False).save(path)
    loaded = settings.Settings.load(path)
    assert loaded.roots == [r"D:\Designs", r"E:\Old"] and loaded.on_top is False


def test_corrupt_or_hostile_settings_fall_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert settings.Settings.load(path) == settings.Settings()
    path.write_text(json.dumps({"roots": ["ok", 5, None, {"x": 1}]}), encoding="utf-8")
    assert settings.Settings.load(path).roots == ["ok"]
    path.write_text("[1, 2]", encoding="utf-8")
    assert settings.Settings.load(path) == settings.Settings()


def test_frozen_exe_keeps_data_next_to_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "DesignFinder.exe"))
    assert settings.data_dir() == tmp_path


def test_source_run_uses_repo_data_folder(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    assert settings.data_dir() == tmp_path / "data"


def test_pil_to_bgr_channel_order():
    bgr = app.bgr_from_pil(Image.new("RGB", (2, 2), (255, 0, 0)))  # pure red
    assert bgr.shape == (2, 2, 3) and tuple(bgr[0, 0]) == (0, 0, 255)


def test_open_in_explorer_selects_newest_master(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(app.subprocess, "Popen", lambda cmd: calls.append(cmd))
    master = tmp_path / "My Folder" / "chair.skp"
    master.parent.mkdir()
    master.write_text("x")
    app.open_in_explorer(FolderMatch(str(master.parent), 0.9, "x.png", [master]))
    assert calls == [f'"{app.EXPLORER}" /select,"{master}"']


def test_open_in_explorer_falls_back_to_folder_when_master_is_gone(monkeypatch, tmp_path):
    popen, started = [], []
    monkeypatch.setattr(app.subprocess, "Popen", lambda cmd: popen.append(cmd))
    monkeypatch.setattr(app.os, "startfile", lambda p: started.append(p), raising=False)
    app.open_in_explorer(FolderMatch(str(tmp_path), 0.9, "x.png", [tmp_path / "deleted.skp"]))
    assert popen == [] and started == [str(tmp_path)]
