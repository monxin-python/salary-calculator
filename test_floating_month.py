# -*- coding = utf-8 -*-
# 回归测试：全自动运行下，悬浮窗当月显示必须等于设置窗"自动计算当月"的口径
import os
import re
import sys
from datetime import datetime, date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from calculator import calc_daily_rate, calc_elapsed_work_minutes
from floating_window import FloatingDisplay

app = QApplication(sys.argv)

CFG = {
    "salary": 4500.0,
    "work_days": 6,
    "daily_hours": 8.0,
    "normal_start": "08:00",
    "normal_end": "17:30",
    "lunch_enabled": True,
    "lunch_start": "12:00",
    "lunch_end": "13:00",
    "ot_start": "18:00",
    "ot_end": "21:00",
    "ot_enabled": False,
    "ot_mode": "manual",
    "ot_rate": 60.0,
    "ot_multiplier": 1.5,
    "weekday_offset": 0,
    "idle_timeout": 300,
    "full_auto": True,
    "auto_tick": False,
    "manual_today": 0.0,
    "manual_month": 865.38,   # 残留的"当月已填"，全自动下不应再叠加
    "show_monthly": True,
    "auto_monthly": False,
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
w._tick()
shown = w.monthly_lbl.text()  # 形如 "本月 ¥1730.76"

# 设置窗 _autofill_month 的算法（用户认定的正确口径）
now = datetime.now()
daily = calc_daily_rate(CFG["salary"], CFG["work_days"], now)
past = sum(1 for d in range(1, now.day)
           if date(now.year, now.month, d).weekday() < CFG["work_days"])
t = 0.0
if now.weekday() < CFG["work_days"]:
    elapsed, total = calc_elapsed_work_minutes(
        now.time(), CFG["normal_start"], CFG["normal_end"],
        CFG["lunch_start"], CFG["lunch_end"], True)
    if total > 0:
        t = daily * max(0.0, min(elapsed / total, 1.0))
expected = daily * past + t

m = re.search(r"¥([\d.]+)", shown)
shown_val = float(m.group(1)) if m else -1.0
print(f"悬浮窗显示: {shown}  期望(设置口径): {expected:.2f}")
assert abs(shown_val - expected) < 0.01, "全自动当月显示与设置口径不一致"

# ── 金额小数位设置生效 ──
CFG2 = dict(CFG)
CFG2["money_decimals"] = 2
CFG2["weekday_offset"] = 1   # 偏移为工作日，确保当日金额非 0
w2 = FloatingDisplay(CFG2, None)
w2._tick()
m2 = re.search(r"¥ ([\d.]+)", w2.money_lbl.text())
assert m2 and len(m2.group(1).split(".")[1]) == 2, f"小数位应为2位: {w2.money_lbl.text()}"
print("小数位设置生效:", w2.money_lbl.text())

print("回归测试通过")
