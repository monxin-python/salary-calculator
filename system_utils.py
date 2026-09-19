# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - Windows 系统功能模块
# @说明 : 空闲检测、全局热键

import ctypes
import ctypes.wintypes
from ctypes import Structure, wintypes, byref

from PySide6.QtCore import (
    Qt, QAbstractNativeEventFilter, Signal, QObject,
)
from PySide6.QtGui import QKeySequence


# ═══════════════════════════════════════════════════════════
# Windows 空闲检测 — GetLastInputInfo
# ═══════════════════════════════════════════════════════════

class LASTINPUTINFO(Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def idle_seconds():
    """返回自上次用户输入(键盘/鼠标)以来的秒数"""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(byref(lii)):
        return 0
    return (kernel32.GetTickCount() - lii.dwTime) / 1000.0


# ═══════════════════════════════════════════════════════════
# 全局热键
# ═══════════════════════════════════════════════════════════

WM_HOTKEY = 0x0312
MOD_MAP = {
    Qt.ControlModifier: 0x0002,
    Qt.AltModifier: 0x0001,
    Qt.ShiftModifier: 0x0004,
    Qt.MetaModifier: 0x0008,
}


class HotkeyFilter(QObject, QAbstractNativeEventFilter):
    triggered = Signal(int)

    def __init__(self):
        QObject.__init__(self)
        QAbstractNativeEventFilter.__init__(self)

    def register(self, key, modifiers, hid):
        mod = sum(v for k, v in MOD_MAP.items() if modifiers & k)
        return bool(user32.RegisterHotKey(None, hid, mod, key))

    def unregister(self, hid):
        user32.UnregisterHotKey(None, hid)

    def nativeEventFilter(self, event_type, message):
        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            self.triggered.emit(int(msg.wParam))
            return True, 0
        return False, 0


# ── 快捷键转换工具 ──────────────────────────────────────

def qt_key_to_vk(qt_key):
    """Qt.Key → Windows VK 码"""
    if Qt.Key_A <= qt_key <= Qt.Key_Z:
        return qt_key
    if Qt.Key_0 <= qt_key <= Qt.Key_9:
        return qt_key
    if Qt.Key_F1 <= qt_key <= Qt.Key_F24:
        return 0x70 + (qt_key - Qt.Key_F1)
    return ord(QKeySequence(qt_key).toString()[0]) if QKeySequence(qt_key).toString() else 0


def parse_hotkey(hotkey_str):
    """解析 "Ctrl+Shift+H" → (vk, qt_mods)"""
    seq = QKeySequence(hotkey_str)
    if seq.isEmpty():
        return 0, Qt.NoModifier
    kc = seq[0]
    return qt_key_to_vk(kc.key()), kc.keyboardModifiers()
