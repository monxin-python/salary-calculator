# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 配置与持久化模块
# @说明 : 配置常量、JSON读写、时间解析、屏幕缩放

import os
import sys
import json
import shutil
import uuid
from datetime import time as dtime

from PySide6.QtWidgets import QApplication

# ── 路径 ──────────────────────────────────────────────────

def get_app_dir():
    """返回程序所在目录（仅用于迁移旧版配置文件）。

    PyInstaller 打包后 __file__ 指向临时解压目录(_MEIxxx)，每次启动都不同
    且退出后被删除，必须改用 exe 所在目录；源码运行时保持 __file__ 目录。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_documents_dir():
    """返回用户"文档"目录，兼容被重定向（OneDrive/自定义位置）的情况"""
    try:
        import ctypes
        # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        guid = (ctypes.c_char * 16).from_buffer_copy(
            uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}").bytes_le)
        buf = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(buf)) == 0:
            path = buf.value
            ctypes.windll.ole32.CoTaskMemFree(buf)
            if path:
                return path
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


HERE = get_app_dir()
DATA_DIR = os.path.join(get_documents_dir(), "工资计算器")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = HERE  # 文档目录不可用时退回程序目录
CFG_PATH = os.path.join(DATA_DIR, "salary_cfg.json")
DATA_PATH = os.path.join(DATA_DIR, "salary_data.json")


def _migrate_legacy_files():
    """旧版配置/数据文件放在程序目录，首次启动时复制到新位置（保留原件）"""
    for name in ("salary_cfg.json", "salary_data.json"):
        old = os.path.join(HERE, name)
        new = os.path.join(DATA_DIR, name)
        if os.path.exists(old) and not os.path.exists(new):
            try:
                shutil.copy2(old, new)
            except Exception:
                pass


_migrate_legacy_files()

# ── 默认配置 ──────────────────────────────────────────────

DEFAULT_CFG = {
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
    "ot_mode": "manual",
    "ot_rate": 60.0,
    "ot_multiplier": 1.5,
    "font_family": "Microsoft YaHei",
    "font_size": 42,
    "info_size": 12,
    "money_decimals": 4,   # 主页当日已赚显示的小数位数
    "card_alpha": 0,
    "ui_scale": 100,   # 界面整体缩放百分比：100=跟随屏幕自动检测
    "hotkey_show": "Ctrl+Shift+H",
    "hotkey_enabled": True,
    "auto_start": False,
    "auto_tick": False,   # 旧配置保留：界面已不暴露，由全自动运行取代
    "full_auto": False,   # 全自动运行：按系统时间直接计算当日/当月工资，与计时器无关
    "always_on_top": True,
    "idle_timeout": 300,
    "ot_enabled": False,
    "manual_today": 0.0,
    "manual_month": 0.0,
    "show_monthly": True,
    "auto_monthly": False,
    "show_full_month": True,   # 自动估算时是否显示月薪总额（"/ ¥3500" 部分）
    "show_progress": True,
    "show_active": True,
    "settings_w": 600,
    "settings_h": 900,
    "float_x": -1,
    "float_y": -1,
    "settings_x": -1,
    "settings_y": -1,
    "weekday_offset": 0,   # 星期偏移：0=自动，正数向后偏移
    "leave_value": 0.0,    # 当月已请假
    "leave_unit": "day",   # 请假单位：day=天 / hour=小时
}


def load_json(path, default):
    """读取JSON文件，用default补充缺失字段"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {**default, **json.load(f)}
    except Exception:
        return dict(default)


def save_json(path, d):
    """写入JSON文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def parse_time(s):
    """解析 "HH:MM" → datetime.time 对象"""
    h, m = map(int, s.split(":"))
    return dtime(h, m)


# ── 屏幕缩放 ──────────────────────────────────────────────

def get_display_scale():
    """返回 UI 缩放因子（以 2K / 96DPI 为基准）。
    在 1080p 上约 0.75，在 2K 上约 1.0，在 4K 上约 1.5。
    同时考虑 Windows DPI 缩放设置，避免高 DPI 下界面过小。
    """
    try:
        screen = QApplication.primaryScreen()
        if not screen:
            return 1.0
        geo = screen.geometry()
        ref_h, ref_w = 1440, 2560
        res_scale = min(geo.height() / ref_h, geo.width() / ref_w)
        dpi_scale = screen.logicalDotsPerInch() / 96.0
        return max(0.55, min(2.5, res_scale * dpi_scale))
    except Exception:
        return 1.0


def scale_value(val):
    """将基准值按当前屏幕缩放"""
    return int(val * get_display_scale())


def get_ui_scale(manual_pct=100):
    """返回最终 UI 缩放因子 = 屏幕自动缩放 × 手动倍率。

    manual_pct 来自配置 ui_scale（百分比），默认 100 即纯自动检测。
    高分屏可调小、低分屏可调大；旧配置缺省字段时保持自动检测不变。
    """
    try:
        m = float(manual_pct) / 100.0
    except Exception:
        m = 1.0
    if m <= 0:
        m = 1.0
    return max(0.4, min(3.0, get_display_scale() * m))
