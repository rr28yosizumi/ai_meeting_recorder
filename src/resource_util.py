import os
import sys
from typing import Optional


def _base_dir() -> str:
    """Return base directory where resources live.
    In PyInstaller --onefile runtime, sys._MEIPASS points to the temp extraction dir.
    In development / normal install, use the package directory (this file's directory).
    """
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir() -> str:
    """Return absolute path to bundled 'resource' directory."""
    return os.path.join(_base_dir(), 'resource')


def resource_path(*relative: str, must_exist: bool = False) -> str:
    """Build absolute path to a resource file.

    Example: resource_path('logo.png') => <base>/resource/logo.png
    Pass nested path parts separately: resource_path('images', 'icon.png')
    If must_exist and file missing, raises FileNotFoundError.
    """
    path = os.path.join(resource_dir(), *relative)
    if must_exist and not os.path.exists(path):
        raise FileNotFoundError(path)
    return path


def find_first(candidates: list[str]) -> Optional[str]:
    """Return first existing path from candidates or None."""
    for p in candidates:
        if os.path.exists(p):
            return p
    return None
