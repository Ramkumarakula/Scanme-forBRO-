"""Build dist/DesignFinder.exe (single file, no console, no Python needed on the target).

    python scripts/build_exe.py
"""

from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]

PyInstaller.__main__.run([
    str(ROOT / "packaging" / "launcher.py"),
    "--name", "DesignFinder",
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT / "build"),
    "--paths", str(ROOT / "src"),
    # not used by the app; keeps the exe smaller
    "--exclude-module", "matplotlib",
    "--exclude-module", "pytest",
])
