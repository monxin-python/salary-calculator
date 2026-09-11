# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 请假设置自检（离屏运行，不弹窗、不写真实配置）
# 运行: python test_settings_leave.py

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
app = QApplication([])

import settings_window as sw
sw.save_json = lambda path, d: None   # 防止覆盖真实 salary_cfg.json
sw.SettingsWindow._set_autostart = staticmethod(lambda enable: None)   # 防止动 Startup 的 VBS

from settings_window import SettingsWindow

cfg = {}
w = SettingsWindow(cfg)

assert w._leave_unit == "day"
w.leave_spin.setValue(1.0)
w._toggle_leave_unit()
assert w._leave_unit == "hour"
assert abs(w.leave_spin.value() - 8.0) < 1e-6          # 1天 -> 8小时
w._toggle_leave_unit()
assert w._leave_unit == "day"
assert abs(w.leave_spin.value() - 1.0) < 1e-6          # 8小时 -> 1天
w.daily_hrs.setValue(10.0)
w.leave_spin.setValue(2.0)
w._toggle_leave_unit()
assert abs(w.leave_spin.value() - 20.0) < 1e-6         # 2天×10小时 -> 20小时
w._save()
assert cfg["leave_value"] == 20.0 and cfg["leave_unit"] == "hour"

# 重新加载：单位与按钮文字还原
w2 = SettingsWindow(cfg)
assert w2._leave_unit == "hour"
assert abs(w2.leave_spin.value() - 20.0) < 1e-6
assert w2.leave_unit_btn.text() == "切换为天"
assert w2.leave_spin.suffix() == " 小时"

# 「自动计算」填入的当月已填必须扣除请假（与全自动口径一致）
w2.monthly.setValue(15000.0)
w2.work_days.setValue(5)
w2._leave_unit = "day"
w2.leave_spin.setValue(0.0)
w2._autofill_month()
gross = w2.manual_month.value()
assert "请假" not in w2.month_detail_lbl.text()      # 无请假只显示总额
w2.leave_spin.setValue(1.0)
w2._autofill_month()
assert abs((gross - w2.manual_month.value()) - w2._leave_deduct()) < 3.0   # 3元容差：两次调用可能跨分钟
detail = w2.month_detail_lbl.text()
assert "请假" in detail and "实际" in detail          # 有请假显示算式明细

print("请假设置切换/换算/保存/加载/自动计算扣假 自检通过")
