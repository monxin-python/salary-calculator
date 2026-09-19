# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 程序入口
# @说明 : 负责 QApplication 初始化和启动

import sys

from PySide6.QtWidgets import QApplication

from config import CFG_PATH, load_json, DEFAULT_CFG
from system_utils import HotkeyFilter
from floating_window import FloatingDisplay


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)

    cfg = load_json(CFG_PATH, DEFAULT_CFG)

    hotkey_filter = HotkeyFilter()
    app.installNativeEventFilter(hotkey_filter)

    w = FloatingDisplay(cfg, hotkey_filter)
    w._apply_hotkey()  # 从配置加载快捷键
    w.show()

    hotkey_filter.triggered.connect(lambda hid: w.hide() if w.isVisible() else w.show())

    sys.exit(app.exec())
