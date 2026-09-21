# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 加班费设置自检（离屏运行，不弹窗、不写真实配置）
# 运行: python test_settings_ot.py

import os
import re
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
app = QApplication([])

import settings_window as sw
sw.save_json = lambda path, d: None   # 防止覆盖真实 salary_cfg.json
sw.SettingsWindow._set_autostart = staticmethod(lambda enable: None)   # 防止动 Startup 的 VBS

from settings_window import SettingsWindow
from calculator import calc_hourly_rate

cfg = {}
w = SettingsWindow(cfg)

# ── 未勾选加班时段：输入框禁用、加班费为 0 ──
assert not w.ot_enabled_cb.isChecked()
assert not w.ot_hours_month.isEnabled()
w.ot_hours_month.setValue(10.0)
assert w._ot_pay() == 0.0

# ── 勾选后输入框启用，10h × ¥60 = ¥600，明细标签同步 ──
w.ot_manual_rb.setChecked(True)
w.ot_rate.setValue(60.0)
w.ot_enabled_cb.setChecked(True)
assert w.ot_hours_month.isEnabled()
assert abs(w._ot_pay() - 600.0) < 1e-6
assert "¥600.00" in w.ot_pay_lbl.text()

# ── 取消勾选：加班费归零（当月清除），但小时数保留 ──
w.ot_enabled_cb.setChecked(False)
assert w._ot_pay() == 0.0
assert "¥0.00" in w.ot_pay_lbl.text()
assert abs(w.ot_hours_month.value() - 10.0) < 1e-6

# ── 重新勾选：按原小时数算回来 ──
w.ot_enabled_cb.setChecked(True)
assert abs(w._ot_pay() - 600.0) < 1e-6

# ── 倍率模式：时薪 × 倍率 ──
w.monthly.setValue(15000.0)
w.work_days.setValue(5)
w.daily_hrs.setValue(8.0)
w.ot_multi_rb.setChecked(True)
w.ot_mult.setValue(1.5)
assert abs(w._ot_pay() - 10 * calc_hourly_rate(15000.0, 5, 8.0) * 1.5) < 1e-6

# ── 保存 / 重新加载：勾选态还原，输入框可用 ──
w.ot_manual_rb.setChecked(True)
w._save()
assert cfg["ot_enabled"] is True
assert abs(cfg["ot_hours_month"] - 10.0) < 1e-6
w2 = SettingsWindow(cfg)
assert abs(w2.ot_hours_month.value() - 10.0) < 1e-6
assert w2.ot_hours_month.isEnabled()

# ── 未勾选态重新加载：值还在，但输入框禁用、加班费为 0 ──
cfg["ot_enabled"] = False
w3 = SettingsWindow(cfg)
assert abs(w3.ot_hours_month.value() - 10.0) < 1e-6
assert not w3.ot_hours_month.isEnabled()
assert w3._ot_pay() == 0.0

# ── 「自动计算」明细：启用加班才显示加班费，且「当月已填」不含它（防悬浮窗双计）──
w4 = SettingsWindow({})
w4.monthly.setValue(15000.0)
w4.work_days.setValue(5)
w4.daily_hrs.setValue(8.0)
w4.ot_hours_month.setValue(10.0)
w4.ot_rate.setValue(60.0)
w4.ot_manual_rb.setChecked(True)

w4.ot_enabled_cb.setChecked(False)
w4._autofill_month()
assert "加班" not in w4.month_detail_lbl.text(), w4.month_detail_lbl.text()
filled_no_ot = w4.manual_month.value()

w4.ot_enabled_cb.setChecked(True)
w4._autofill_month()
detail = w4.month_detail_lbl.text()
assert "加班费 ¥600.00" in detail and "实际" in detail, detail
# 「当月已填」不含加班费，否则悬浮窗会再加一遍
assert abs(w4.manual_month.value() - filled_no_ot) < 3.0, "「当月已填」不应含加班费"
m = re.search(r"实际 ¥([\d.]+)", detail)
assert m, detail
assert abs(float(m.group(1)) - (w4.manual_month.value() + 600.0)) < 3.0, detail
print("自动计算明细:", detail)

print("加班费设置 启用联动/归零/还原/保存/加载/自动计算明细 自检通过")
