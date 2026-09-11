# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 右键"修改星期"菜单自检（离屏运行，不弹窗、不写配置）
# 运行: python test_weekday_menu.py

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMenu
app = QApplication([])

import floating_window as fw
from config import DEFAULT_CFG
from calculator import get_effective_weekday

fw.save_json = lambda path, d: None          # 不写真实配置

d = fw.FloatingDisplay(dict(DEFAULT_CFG), None)
d._show_context_menu(d.rect().center())
sub = next(m for m in d.findChildren(QMenu) if "修改星期" in m.title())
acts = [a for a in sub.actions() if a.isCheckable()]
assert len(acts) == 7

acts[0].trigger()                            # 点"周一"
assert get_effective_weekday(d.cfg)[0] == 0, d.cfg["weekday_offset"]
acts[6].trigger()                            # 点"周日"
assert get_effective_weekday(d.cfg)[0] == 6, d.cfg["weekday_offset"]
acts[2].trigger()                            # 点"周三"
assert get_effective_weekday(d.cfg)[0] == 2, d.cfg["weekday_offset"]

print("右键修改星期 自检通过")
