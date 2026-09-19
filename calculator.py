# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 工资与时间计算模块
# @说明 : 所有纯计算逻辑，不依赖 Qt 控件，只依赖 config.parse_time

import calendar
from datetime import datetime, date

from config import parse_time

# ── 星期名称 ──────────────────────────────────────────────

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def get_effective_weekday(cfg, now=None):
    """返回 (有效星期索引, 星期名称)。

    索引: 0=周一 … 6=周日。
    受 cfg["weekday_offset"] 偏移影响，0=使用系统时间。
    """
    if now is None:
        now = datetime.now()
    sys_wd = now.weekday()  # 0=Mon … 6=Sun
    offset = cfg.get("weekday_offset", 0)
    effective = (sys_wd + offset) % 7
    return effective, WEEKDAY_NAMES[effective]


def is_workday(cfg, now=None):
    """判断今天（有效星期）是否为工作日"""
    wd, _ = get_effective_weekday(cfg, now)
    return wd < cfg["work_days"]


# ═══════════════════════════════════════════════════════════
# 基础工资计算
# ═══════════════════════════════════════════════════════════

def count_workdays_in_month(work_days, now=None):
    """当月（或 now 所在月）的实际工作日数：周一开始数前 work_days 天"""
    if now is None:
        now = datetime.now()
    total_days = calendar.monthrange(now.year, now.month)[1]
    return sum(
        1 for d in range(1, total_days + 1)
        if date(now.year, now.month, d).weekday() < work_days
    )


def count_workdays_before(work_days, now=None):
    """now 所在月、now.day 之前（不含今天）已过的工作日数"""
    if now is None:
        now = datetime.now()
    return sum(
        1 for d in range(1, now.day)
        if date(now.year, now.month, d).weekday() < work_days
    )


def calc_daily_rate(salary, work_days, now=None):
    """日薪 = 月薪 / 当月实际工作日数（随月份变化，满勤时当月工资恰等于月薪）"""
    try:
        return salary / count_workdays_in_month(work_days, now)
    except ZeroDivisionError:
        return 0.0


def calc_hourly_rate(salary, work_days, daily_hours, now=None):
    """时薪 = 当月日薪 / 每日工时"""
    try:
        return calc_daily_rate(salary, work_days, now) / daily_hours
    except ZeroDivisionError:
        return 0.0


def calc_second_rate(salary, work_days, daily_hours, now=None):
    """每秒工资 = 时薪 / 3600"""
    return calc_hourly_rate(salary, work_days, daily_hours, now) / 3600.0


# ═══════════════════════════════════════════════════════════
# 工作时间计算（午休扣除）
# ═══════════════════════════════════════════════════════════

def calc_elapsed_work_minutes(now_time, normal_start, normal_end,
                               lunch_start, lunch_end, lunch_enabled):
    """计算从上班到 now_time 已过去的工作分钟数。

    Args:
        now_time: datetime.time 对象（当前时刻）
        normal_start: "HH:MM" 上班时间字符串
        normal_end:   "HH:MM" 下班时间字符串
        lunch_start:  "HH:MM" 午休开始
        lunch_end:    "HH:MM" 午休结束
        lunch_enabled: 是否启用午休

    Returns:
        (elapsed_minutes, total_work_minutes)
        如果 total_work_minutes <= 0，返回 (0, 0)
    """
    ns = parse_time(normal_start)
    ne = parse_time(normal_end)
    start_min = ns.hour * 60 + ns.minute
    end_min = ne.hour * 60 + ne.minute
    total_work_min = end_min - start_min

    lunch_minutes = 0
    if lunch_enabled:
        ls = parse_time(lunch_start)
        le = parse_time(lunch_end)
        lunch_minutes = (le.hour * 60 + le.minute) - (ls.hour * 60 + ls.minute)
        if lunch_minutes > 0:
            total_work_min -= lunch_minutes

    if total_work_min <= 0:
        return 0, 0

    current_min = now_time.hour * 60 + now_time.minute

    if lunch_minutes > 0:
        ls = parse_time(lunch_start)
        le = parse_time(lunch_end)
        lunch_start_min = ls.hour * 60 + ls.minute
        lunch_end_min = le.hour * 60 + le.minute

        if current_min >= lunch_end_min:
            # 午休已过：总经过 - 午休时长
            elapsed = max(0, min(current_min - start_min, end_min - start_min)) - lunch_minutes
        elif current_min > lunch_start_min:
            # 正在午休：只算到午休开始
            elapsed = lunch_start_min - start_min
        else:
            # 午休还没到
            elapsed = max(0, min(current_min - start_min, lunch_start_min - start_min))
    else:
        elapsed = max(0, min(current_min - start_min, total_work_min))

    return max(0, elapsed), total_work_min


# ═══════════════════════════════════════════════════════════
# 当前费率判断
# ═══════════════════════════════════════════════════════════

def get_current_rate(cfg, now_time=None, now=None):
    """根据当前时间和配置返回 (每秒费率, 时段名称)。

    时段名称: "正常上班" | "午休中" | "加班中" | "休息时间" | "今日休息"
    加班时段工作日与休息日均计费；正常上班优先于加班窗口。
    休息日且不在加班窗口返回 (0, "今日休息")。
    """
    if now is None:
        now = datetime.now()
    if now_time is None:
        now_time = now.time()

    workday = is_workday(cfg, now)
    base_second = calc_second_rate(cfg["salary"], cfg["work_days"], cfg["daily_hours"], now)

    if workday:
        ns = parse_time(cfg["normal_start"])
        ne = parse_time(cfg["normal_end"])

        # 正常上班时段
        if ns <= now_time < ne:
            if cfg.get("lunch_enabled", True):
                ls_ = parse_time(cfg["lunch_start"])
                le = parse_time(cfg["lunch_end"])
                if ls_ <= now_time < le:
                    return 0.0, "午休中"
            return base_second, "正常上班"

    # 加班时段（休息日也计费）
    os_ = parse_time(cfg["ot_start"])
    oe = parse_time(cfg["ot_end"])
    if cfg.get("ot_enabled", False) and os_ <= now_time < oe:
        if cfg.get("ot_mode", "manual") == "manual":
            return cfg["ot_rate"] / 3600.0, "加班中"
        else:
            return base_second * cfg["ot_multiplier"], "加班中"

    return 0.0, "今日休息" if not workday else "休息时间"


# ═══════════════════════════════════════════════════════════
# 进度计算
# ═══════════════════════════════════════════════════════════

def calc_day_progress(cfg, now=None):
    """计算今日工作进度百分比（0-100）。
    只计算正常上班时段，扣除午休。
    """
    if now is None:
        now = datetime.now()

    elapsed, total = calc_elapsed_work_minutes(
        now.time(),
        cfg["normal_start"], cfg["normal_end"],
        cfg["lunch_start"], cfg["lunch_end"],
        cfg.get("lunch_enabled", True),
    )
    if total <= 0:
        return 0.0
    return elapsed / total * 100.0


def calc_month_progress(cfg, now=None):
    """计算本月工作日进度百分比（0-100）。"""
    if now is None:
        now = datetime.now()

    today_is_workday = 1 if now.weekday() < cfg["work_days"] else 0
    work_days_so_far = count_workdays_before(cfg["work_days"], now) + today_is_workday

    total_work_days = count_workdays_in_month(cfg["work_days"], now)

    if total_work_days <= 0:
        return 0.0
    return work_days_so_far / total_work_days * 100.0


# ═══════════════════════════════════════════════════════════
# 自动计算（用于自动填充和全自动月薪模式）
# ═══════════════════════════════════════════════════════════

def calc_auto_today_earned(salary, work_days, normal_start, normal_end,
                           lunch_start, lunch_end, lunch_enabled, now=None):
    """根据当前时间自动计算今日已赚金额。

    参数均为原始值（数值或字符串），方便 SettingWindow 和 FloatingDisplay 共用。
    如果今天不是工作日，返回 0。
    """
    if now is None:
        now = datetime.now()

    if now.weekday() >= work_days:
        return 0.0

    daily_rate = calc_daily_rate(salary, work_days, now)
    if daily_rate <= 0:
        return 0.0

    elapsed, total = calc_elapsed_work_minutes(
        now.time(), normal_start, normal_end,
        lunch_start, lunch_end, lunch_enabled,
    )
    if total <= 0:
        return 0.0

    day_pct = elapsed / total
    return daily_rate * max(0.0, min(day_pct, 1.0))


def calc_auto_month_earned(salary, work_days, normal_start, normal_end,
                            lunch_start, lunch_end, lunch_enabled, now=None):
    """自动计算本月已赚金额（含今日进度）。"""
    if now is None:
        now = datetime.now()

    daily_rate = calc_daily_rate(salary, work_days, now)
    if daily_rate <= 0:
        return 0.0

    # 本月已过去的完整工作日（不含今天）
    past_work_days = count_workdays_before(work_days, now)

    # 今天如果是工作日，计算今日进度
    today_earned = 0.0
    if now.weekday() < work_days:
        today_earned = calc_auto_today_earned(
            salary, work_days, normal_start, normal_end,
            lunch_start, lunch_end, lunch_enabled, now,
        )

    return daily_rate * past_work_days + today_earned


def calc_auto_today_seconds(cfg, now=None):
    """全自动模式：按系统时间秒级计算今日已赚金额（仅正常上班时段，扣除午休）。

    与 calc_auto_today_earned 口径一致（后者按分钟），本函数秒级精度供悬浮窗
    每秒刷新。不依赖计时器累加，任何时刻调用结果相同。非工作日返回 0。
    """
    if now is None:
        now = datetime.now()

    if not is_workday(cfg, now):
        return 0.0

    daily_rate = calc_daily_rate(cfg["salary"], cfg["work_days"], now)
    if daily_rate <= 0:
        return 0.0

    ns = parse_time(cfg["normal_start"])
    ne = parse_time(cfg["normal_end"])
    start_s = ns.hour * 3600 + ns.minute * 60
    end_s = ne.hour * 3600 + ne.minute * 60
    now_s = now.hour * 3600 + now.minute * 60 + now.second
    total_s = end_s - start_s

    lunch_s = 0
    if cfg.get("lunch_enabled", True):
        ls = parse_time(cfg["lunch_start"])
        le = parse_time(cfg["lunch_end"])
        l_start_s = ls.hour * 3600 + ls.minute * 60
        l_end_s = le.hour * 3600 + le.minute * 60
        lunch_s = l_end_s - l_start_s
        if lunch_s > 0:
            total_s -= lunch_s

    if total_s <= 0:
        return 0.0

    elapsed = now_s - start_s
    if lunch_s > 0:
        elapsed -= max(0, min(now_s, l_end_s) - l_start_s)
    elapsed = max(0.0, min(elapsed, total_s))
    return daily_rate * elapsed / total_s


def calc_leave_deduction(cfg, now=None):
    """本月请假扣除金额：请假天数×日薪 或 请假小时×时薪（按当月费率）"""
    value = cfg.get("leave_value", 0.0)
    if value <= 0:
        return 0.0
    if cfg.get("leave_unit", "day") == "day":
        return value * calc_daily_rate(cfg["salary"], cfg["work_days"], now)
    return value * calc_hourly_rate(cfg["salary"], cfg["work_days"], cfg["daily_hours"], now)


def calc_auto_monthly_full(cfg, now=None):
    """自动估算本月工资（按日程推算，不依赖计时器）。

    Returns:
        (auto_total, today_earned, full_month_salary)
        - auto_total: 本月至今应得工资（含今日进度）
        - today_earned: 今日已得
        - full_month_salary: 本月满勤工资（恒等于月薪）
    """
    if now is None:
        now = datetime.now()

    daily_rate = calc_daily_rate(cfg["salary"], cfg["work_days"], now)
    if daily_rate <= 0:
        return 0.0, 0.0, 0.0

    # 本月已过去的完整工作日（不含今天）
    past_work_days = count_workdays_before(cfg["work_days"], now)

    # 今天如果是工作日（使用有效星期），计算今日进度
    today_earned = 0.0
    if is_workday(cfg, now):
        dp = calc_day_progress(cfg, now)
        today_earned = daily_rate * max(0.0, min(dp, 100.0)) / 100.0

    full_month_earned = daily_rate * past_work_days
    auto_total = full_month_earned + today_earned
    # 扣除本月请假（天×日薪 / 小时×时薪），不为负
    auto_total = max(0.0, auto_total - calc_leave_deduction(cfg, now))

    # 满勤工资 = 日薪 × 当月实际工作日数（恒等于月薪），取分位消除浮点尾差
    full_month_salary = round(daily_rate * count_workdays_in_month(cfg["work_days"], now), 2)

    return auto_total, today_earned, full_month_salary
