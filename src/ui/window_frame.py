"""Windows가 그리는 제목 표시줄을 앱 팔레트와 맞춘다."""

import ctypes
from ctypes import wintypes
import logging
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from src.ui.theme import BORDER, CANVAS, TEXT


LOGGER = logging.getLogger("ppt_merge.window_frame")
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def _color_ref(value: str) -> int:
    color = QColor(value)
    return color.red() | (color.green() << 8) | (color.blue() << 16)


class WindowsWindowFrame:
    def __init__(self, app: QApplication) -> None:
        import pywintypes
        import win32con
        import win32gui

        self._style_hints = app.styleHints()
        self._colors = (
            (DWMWA_USE_IMMERSIVE_DARK_MODE, wintypes.BOOL(QColor(CANVAS).lightness() < 128)),
            (DWMWA_BORDER_COLOR, wintypes.DWORD(_color_ref(BORDER))),
            (DWMWA_CAPTION_COLOR, wintypes.DWORD(_color_ref(CANVAS))),
            (DWMWA_TEXT_COLOR, wintypes.DWORD(_color_ref(TEXT))),
        )
        self._win32_error = pywintypes.error
        self._win32con = win32con
        self._win32gui = win32gui

        self._set_attribute = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
        self._set_attribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        self._set_attribute.restype = ctypes.c_long

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                                          wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        # Qt 창과 Windows 파일 선택 창이 표시되는 이벤트를 현재 프로세스에서만 받는다.
        self._callback = callback_type(self._window_shown)
        set_hook = user32.SetWinEventHook
        set_hook.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, callback_type,
                             wintypes.DWORD, wintypes.DWORD, wintypes.DWORD)
        set_hook.restype = wintypes.HANDLE
        self._unhook = user32.UnhookWinEvent
        self._unhook.argtypes = (wintypes.HANDLE,)
        self._unhook.restype = wintypes.BOOL
        self._hook = set_hook(win32con.EVENT_OBJECT_SHOW, win32con.EVENT_OBJECT_SHOW, None,
                              self._callback, os.getpid(), 0, win32con.WINEVENT_OUTOFCONTEXT)
        if not self._hook:
            raise ctypes.WinError(ctypes.get_last_error())

    def _window_shown(self, _hook, _event, hwnd, object_id, child_id, _thread, _time) -> None:
        win32con = self._win32con
        if not hwnd or object_id != win32con.OBJID_WINDOW or child_id != win32con.CHILDID_SELF:
            return
        if self._style_hints.accessibility().contrastPreference() == Qt.ContrastPreference.HighContrast:
            return
        try:
            if self._win32gui.GetAncestor(hwnd, win32con.GA_ROOT) != hwnd:
                return
            style = self._win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            if style & win32con.WS_CAPTION != win32con.WS_CAPTION:
                return
        except self._win32_error:
            # 이벤트가 전달되기 전에 사라진 창은 처리할 필요가 없다.
            return
        for attribute, color in self._colors:
            self._set_attribute(hwnd, attribute, ctypes.byref(color), ctypes.sizeof(color))

    def close(self) -> None:
        if self._hook:
            self._unhook(self._hook)
            self._hook = None


def install_window_frame_theme(app: QApplication) -> WindowsWindowFrame | None:
    if sys.platform != "win32" or app.platformName() != "windows" or sys.getwindowsversion().build < 22000:
        return None
    try:
        return WindowsWindowFrame(app)
    except (ImportError, OSError):
        LOGGER.debug("Windows 제목 표시줄 색상을 적용할 수 없습니다.", exc_info=True)
        return None
