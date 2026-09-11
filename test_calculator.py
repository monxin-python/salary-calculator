# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 核心计算自检
# 运行: python test_calculator.py

from datetime import datetime

from calculator import (
    calc_auto_today_seconds, calc_auto_today_earned, calc_daily_rate,
    calc_hourly_rate, calc_leave_deduction, calc_auto_monthly_full,
)

CFG = {
    "salary": 15000.0,
    "work_days": 5,
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
}


def at(h, m, s=0):
    """2026-09-07 是周一"""
    return datetime(2026, 9, 7, h, m, s)


assert calc_auto_today_seconds(CFG, at(7, 59, 59)) == 0.0            # 上班前
assert calc_auto_today_seconds(CFG, at(8, 0, 0)) == 0.0
mid = calc_auto_today_seconds(CFG, at(10, 0, 0))
ref = calc_auto_today_earned(15000, 5, "08:00", "17:30", "12:00", "13:00", True, at(10, 0, 0))
assert abs(mid - ref) < 1e-6                                          # 与分钟版口径一致
lunch_frozen = calc_auto_today_seconds(CFG, at(12, 0, 0))
assert abs(calc_auto_today_seconds(CFG, at(12, 30, 0)) - lunch_frozen) < 1e-6  # 午休中冻结
assert lunch_frozen > mid
after = calc_auto_today_seconds(CFG, at(14, 0, 0))
assert after > lunch_frozen
daily = calc_auto_today_seconds(CFG, at(17, 30, 0))
assert abs(daily - calc_daily_rate(15000, 5, at(17, 30, 0))) < 1e-6   # 满勤日=日薪
assert calc_auto_today_seconds(CFG, at(22, 0, 0)) == daily            # 下班后封顶
assert calc_auto_today_seconds(CFG, datetime(2026, 9, 12, 10, 0, 0)) == 0.0  # 周六休息

print("calc_auto_today_seconds 自检通过")

# ── 请假扣除 ──
CFG["leave_value"] = 1.0
CFG["leave_unit"] = "day"
assert abs(calc_leave_deduction(CFG, at(10, 0, 0)) - calc_daily_rate(15000, 5, at(10, 0, 0))) < 1e-6   # 1天=日薪
CFG["leave_unit"] = "hour"
assert abs(calc_leave_deduction(CFG, at(10, 0, 0)) - calc_hourly_rate(15000, 5, 8.0, at(10, 0, 0))) < 1e-6  # 1小时=时薪
CFG["leave_value"] = 999.0
CFG["leave_unit"] = "day"
assert calc_auto_monthly_full(CFG, at(10, 0, 0))[0] == 0.0   # 请假超过已赚：扣除后不为负
CFG["leave_value"] = 0.0

print("请假扣除自检通过")
