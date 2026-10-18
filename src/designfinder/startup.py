"""Optional "start with Windows" via the per-user Run registry key (no admin needed)."""

import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DesignFinder"


def supported() -> bool:
    """Only the installed .exe can auto-start; a source checkout has no stable command."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def command() -> str:
    return f'"{sys.executable}"'


def _winreg():
    import winreg
    return winreg


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    if not supported():
        return
    winreg = _winreg()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass


def repair() -> None:
    """If auto-start is on but the exe was moved, point the entry at the new location."""
    if supported() and is_enabled():
        set_enabled(True)
