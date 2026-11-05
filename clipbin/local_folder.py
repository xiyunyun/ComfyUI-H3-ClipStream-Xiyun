"""Reveal a project folder on the Windows host that runs ComfyUI.

The request comes from a browser tab, so the ComfyUI server is not the foreground
process when it hands the folder to Explorer. Windows' foreground lock therefore lets
the new Explorer window open behind the browser. The folder itself is opened by the
shell; this module only finds that window and raises it, using the documented Alt-key
release for SetForegroundWindow. Failure to raise is not an error - the folder is open
and the user can click its taskbar entry.
"""
from __future__ import annotations

import logging
import os
import platform
import time

logger = logging.getLogger(__name__)


def _explorer_windows():
    """Every visible Explorer folder window as (handle, title)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    windows = []

    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        class_name = ctypes.create_unicode_buffer(64)
        if not user32.GetClassNameW(hwnd, class_name, 64) or class_name.value != "CabinetWClass":
            return True
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, 512)
        windows.append((hwnd, title.value))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    return windows


def _raise_explorer(folder: str, previous, timeout: float = 2.0) -> bool:
    import ctypes
    from ctypes import wintypes

    name = os.path.basename(folder.rstrip("\\/"))
    deadline = time.monotonic() + timeout
    while True:
        windows = _explorer_windows()
        fresh = [hwnd for hwnd, _ in windows if hwnd not in previous]
        if fresh:
            hwnd = fresh[-1]
            break
        if name:
            matched = [hwnd for hwnd, title in windows if name in title]
            if matched:
                hwnd = matched[-1]
                break
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)

    user32 = ctypes.windll.user32
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.BringWindowToTop(hwnd)
    if user32.SetForegroundWindow(hwnd):
        return True
    user32.keybd_event(0x12, 0, 0, 0)  # VK_MENU down
    user32.keybd_event(0x12, 0, 0x0002, 0)  # VK_MENU up
    if user32.SetForegroundWindow(hwnd):
        return True
    # Last resort for a locked-down desktop: the call Alt+Tab itself uses.
    user32.SwitchToThisWindow(hwnd, True)
    return True


def open_local_folder(path: str) -> None:
    """Open one folder in Explorer and bring its window to the front."""
    if platform.system() != "Windows":
        raise RuntimeError("打开本地目录目前仅支持 Windows。")
    target = os.path.realpath(path)
    previous = set()
    try:
        previous = {hwnd for hwnd, _ in _explorer_windows()}
    except Exception:
        logger.warning("[Clip Bin] Could not list the open Explorer windows", exc_info=True)
    os.startfile(target)
    try:
        if not _raise_explorer(target, previous):
            logger.debug("[Clip Bin] Explorer window for %s was not found in time", target)
    except Exception:
        logger.warning("[Clip Bin] Could not bring the opened folder to the front", exc_info=True)


__all__ = ["open_local_folder"]
