# -*- coding = utf-8 -*-
# 回归测试：加班时段不计入计时累计，加班费只由"当月已加小时"决定
import os
import re
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

import floating_window as fw
fw.save_json = lambda path, d: None   # 防止污染真实 salary_data.json

from floating_window import FloatingDisplay
from calculator import calc_ot_pay

app = QApplication(sys.argv)

CFG = {
    "salary": 15000.0,
    "work_days": 5,
    "daily_hours": 8.0,
    "normal_start": "08:00",
    "normal_end": "17:30",
    "lunch_enabled": True,
    "lunch_start": "12:00",
    "lunch_end": "13:00",
    "ot_start": "00:00",      # 全天都算加班窗口，确保当前时刻一定落在里面
    "ot_end": "23:59",
    "ot_enabled": True,
    "ot_mode": "manual",
    "ot_rate": 60.0,
    "ot_multiplier": 1.5,
    "ot_hours_month": 10.0,
    "weekday_offset": 0,
    "idle_timeout": 300,
    "full_auto": False,
    "auto_tick": False,
    "auto_monthly": False,
    "manual_today": 0.0,
    "manual_month": 0.0,
    "show_monthly": True,
    "show_full_month": False,
    "show_progress": False,
    "show_active": False,
    "always_on_top": True,
    "card_alpha": 0,
    "font_size": 42,
    "info_size": 12,
    "ui_scale": 100,
}

w = FloatingDisplay(CFG, None)

# ── 加班时段计时不打钱，但信息栏照旧报"加班中" ──
w._start()
w.t0 = time.time() - 10      # 假装已经计了 10 秒
before = w.monthly_total
w._tick()
assert abs(w.monthly_total - before) < 1e-9, "加班时段不应计入 monthly_total"
assert "加班中" in w.rate_lbl.text(), f"信息栏应显示加班中，实际: {w.rate_lbl.text()}"
print("加班时段不计费，信息栏:", w.rate_lbl.text())

# ── 当月 = 计时累计 + 手填小时数算出的加班费 ──
m = re.search(r"本月 ¥([\d.]+)", w.monthly_lbl.text())
assert m, f"当月标签格式不符: {w.monthly_lbl.text()}"
expected = w.monthly_total + calc_ot_pay(CFG)
assert abs(float(m.group(1)) - expected) < 0.01, f"显示 {m.group(1)} != 期望 {expected}"
assert abs(calc_ot_pay(CFG) - 600.0) < 1e-6
print("当月含加班费:", w.monthly_lbl.text(), "（加班费 ¥600.00）")

# ── 取消勾选 → 加班费归零，当月掉回（= 清除）──
CFG["ot_enabled"] = False
w._tick()
m2 = re.search(r"本月 ¥([\d.]+)", w.monthly_lbl.text())
assert abs(float(m2.group(1)) - w.monthly_total) < 0.01, "取消勾选后当月不应含加班费"
print("取消勾选后当月:", w.monthly_lbl.text())

print("回归测试通过")
