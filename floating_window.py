# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 悬浮显示窗口模块
# @说明 : 工资悬浮窗的全部 UI 和计时逻辑，计算委托给 calculator

import json
import os
import time
from datetime import datetime, date

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFrame, QMenu, QMessageBox,
)
from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QFont, QKeySequence

from config import (
    CFG_PATH, DATA_PATH, load_json, save_json,
    parse_time, get_ui_scale, scale_value,
)
from calculator import (
    get_current_rate, calc_day_progress, calc_month_progress,
    calc_auto_monthly_full, calc_auto_today_seconds, calc_second_rate,
    get_effective_weekday, is_workday, WEEKDAY_NAMES,
)
from system_utils import idle_seconds, parse_hotkey
from styles import get_floating_style, get_floating_padding, MENU_STYLE
from settings_window import SettingsWindow


class FloatingDisplay(QWidget):
    def __init__(self, cfg, hotkey_filter):
        super().__init__()
        self.cfg = cfg
        self.hotkey_filter = hotkey_filter
        self.drag_pos = QPoint()
        self.ticking = False
        self.t0 = time.time()
        self.accumulated = 0.0                    # 本次会话累计
        self.monthly_total = 0.0                  # 当月累计
        self._prev_rate = None                    # 上次 tick 时的费率（用于暂停结算）
        self._load_monthly()

        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.cfg.get("always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("工资计时")

        self._apply_style()
        self._build()

        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(200)

        self.adjustSize()
        fx = self.cfg.get("float_x", -1)
        fy = self.cfg.get("float_y", -1)
        if fx >= 0 and fy >= 0:
            self.move(fx, fy)
        else:
            geo = QApplication.primaryScreen().geometry()
            margin_x = scale_value(40)
            margin_y = scale_value(120)
            self.move(geo.width() - self.width() - margin_x, geo.height() - self.height() - margin_y)

        # 全窗口右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 自动开始计时
        if self.cfg.get("auto_tick", False):
            rate, _ = get_current_rate(self.cfg)
            if rate > 0:
                self._start()

    # ═══════════════════════════════════════════════════════════
    # 月度数据持久化
    # ═══════════════════════════════════════════════════════════

    def _load_monthly(self):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        key = date.today().strftime("%Y-%m")
        self.monthly_total = data.get(key, {}).get("total", 0.0)
        self.all_data = data

    def _save_monthly(self):
        key = date.today().strftime("%Y-%m")
        self.all_data[key] = {"total": round(self.monthly_total, 4)}
        save_json(DATA_PATH, self.all_data)

    def _base_monthly(self):
        """从文件重新加载月度基准"""
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(date.today().strftime("%Y-%m"), {}).get("total", 0.0)
        except Exception:
            return 0.0

    # ═══════════════════════════════════════════════════════════
    # 拖动 & 右键菜单
    # ═══════════════════════════════════════════════════════════

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.cfg["float_x"] = self.x()
            self.cfg["float_y"] = self.y()
            save_json(CFG_PATH, self.cfg)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction("▶ 开始计时", self._start)
        menu.addAction("⏸ 暂停", self._pause)
        menu.addAction("↺ 清零本次", self._reset_session)
        menu.addSeparator()

        full_auto_action = menu.addAction("⚡ 全自动运行")
        full_auto_action.setCheckable(True)
        full_auto_action.setChecked(self.cfg.get("full_auto", False))
        full_auto_action.toggled.connect(self._toggle_full_auto)

        menu.addSeparator()

        # ── 月薪显示 ──（当月口径跟随全自动运行开关，这里只留显示选项）
        monthly_menu = menu.addMenu("💵 月薪显示")
        monthly_menu.setStyleSheet(MENU_STYLE)

        hide_action = monthly_menu.addAction("隐藏月薪")
        hide_action.setCheckable(True)
        hide_action.setChecked(not self.cfg.get("show_monthly", True))
        hide_action.setEnabled(not self.cfg.get("full_auto", False))

        monthly_menu.addSeparator()

        full_action = monthly_menu.addAction("显示月薪总额")
        full_action.setCheckable(True)
        full_action.setChecked(self.cfg.get("show_full_month", True))

        hide_action.toggled.connect(self._toggle_show_monthly)
        full_action.toggled.connect(self._toggle_show_full_month)

        menu.addSeparator()

        topmost_action = menu.addAction("📌 置顶")
        topmost_action.setCheckable(True)
        topmost_action.setChecked(self.cfg.get("always_on_top", True))
        topmost_action.toggled.connect(self._toggle_topmost)

        menu.addSeparator()

        # ── 修改星期 ──
        weekday_menu = menu.addMenu("📅 修改星期")
        weekday_menu.setStyleSheet(MENU_STYLE)

        offset = self.cfg.get("weekday_offset", 0)
        sys_wd = datetime.now().weekday()
        for i, name in enumerate(WEEKDAY_NAMES):
            needed_offset = i - sys_wd
            # 标准化到 [-3, 3] 范围
            if needed_offset > 3:
                needed_offset -= 7
            elif needed_offset < -3:
                needed_offset += 7
            offset_label = f"（{'今天' if needed_offset == 0 else f'偏移 {needed_offset:+d}'}）"
            action = weekday_menu.addAction(f"{name} {offset_label}")
            action.setCheckable(True)
            action.setChecked(offset == needed_offset)
            action.triggered.connect(lambda checked, off=needed_offset: self._set_weekday_offset(off))

        menu.addSeparator()
        menu.addAction("🗑 清除所有统计", lambda: QTimer.singleShot(0, self._clear_all))
        menu.addSeparator()
        menu.addAction("⚙ 设置", self._open_settings)
        menu.addSeparator()
        menu.addAction("✕ 退出", self._quit)
        menu.popup(self.mapToGlobal(pos))

    # ═══════════════════════════════════════════════════════════
    # 样式
    # ═══════════════════════════════════════════════════════════

    def _apply_style(self):
        scale = get_ui_scale(self.cfg.get("ui_scale", 100))
        style_str = get_floating_style(
            self.cfg["card_alpha"],
            self.cfg["font_size"],
            self.cfg["info_size"],
            scale,
        )
        self.setStyleSheet(style_str)

        # 更新 card 的 padding 与行距
        if hasattr(self, 'card') and self.card.layout():
            pad_h, pad_v, spacing = get_floating_padding(scale)
            self.card.layout().setContentsMargins(pad_h, pad_v, pad_h, pad_v)
            self.card.layout().setSpacing(spacing)

    # ═══════════════════════════════════════════════════════════
    # 界面构建
    # ═══════════════════════════════════════════════════════════

    def _build(self):
        self.setObjectName("main")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(objectName="card")
        lay = QVBoxLayout(self.card)
        pad_h, pad_v, spacing = get_floating_padding(get_ui_scale(self.cfg.get("ui_scale", 100)))
        lay.setContentsMargins(pad_h, pad_v, pad_h, pad_v)
        lay.setSpacing(spacing)

        self.money_lbl = QLabel("¥ 0.00", objectName="money", alignment=Qt.AlignCenter)
        self.monthly_lbl = QLabel("", objectName="monthly", alignment=Qt.AlignCenter)
        self.rate_lbl = QLabel("右键开始 | ⚙ 设置", objectName="rate", alignment=Qt.AlignCenter)
        self.progress_lbl = QLabel("", objectName="progress", alignment=Qt.AlignCenter)
        self.active_lbl = QLabel("", objectName="active", alignment=Qt.AlignCenter)
        self.weekday_lbl = QLabel("", objectName="weekday", alignment=Qt.AlignCenter)

        lay.addWidget(self.money_lbl)
        lay.addWidget(self.monthly_lbl)
        lay.addWidget(self.rate_lbl)
        lay.addWidget(self.progress_lbl)
        lay.addWidget(self.active_lbl)
        lay.addWidget(self.weekday_lbl)

        root.addWidget(self.card)

    # ═══════════════════════════════════════════════════════════
    # 活动检测
    # ═══════════════════════════════════════════════════════════

    def _is_active(self):
        return idle_seconds() < self.cfg.get("idle_timeout", 300)

    # ═══════════════════════════════════════════════════════════
    # 计时逻辑
    # ═══════════════════════════════════════════════════════════

    def _start(self):
        self.ticking = True
        self.t0 = time.time()
        self._prev_rate = None  # 重置费率记录，避免与暂停前的旧费率比较
        # 如果之前暂停过，已累加值保留；否则从头开始
        if self.accumulated == 0:
            self.monthly_lbl.setText("")

    def _pause(self):
        if self.ticking:
            # 使用 _prev_rate（上次 tick 时的费率）而非 _current_rate()
            # 防止在非工作时段暂停时费率为 0 导致收益丢失
            rate = self._prev_rate if self._prev_rate is not None else get_current_rate(self.cfg)[0]
            elapsed = time.time() - self.t0
            self.monthly_total += elapsed * rate
            self.accumulated += elapsed * rate
        self.ticking = False
        self._prev_rate = None  # 清理费率记录
        self._save_monthly()

    def _reset_session(self):
        self.ticking = False
        self.accumulated = 0.0
        self.money_lbl.setText("¥ 0.00")
        self.rate_lbl.setText("已清零 | 右键开始")

    def _clear_all(self):
        reply = QMessageBox.question(
            self, "确认清除",
            "确定要清除所有统计数据吗？\n\n"
            "这将删除：\n"
            "• 本次会话累计金额\n"
            "• 当月累计金额\n"
            "• 所有历史数据文件\n\n"
            "此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.ticking = False
            self.accumulated = 0.0
            self.monthly_total = 0.0
            self.money_lbl.setText("¥ 0.00")
            self.monthly_lbl.setText("")
            self.rate_lbl.setText("已全部清零 | 右键开始")
            # 删除数据文件
            try:
                os.remove(DATA_PATH)
                self.all_data = {}
            except Exception:
                pass

    def _tick(self):
        rate, period = get_current_rate(self.cfg)
        active = self._is_active()
        idle_sec = idle_seconds()
        now = time.time()
        auto = self.cfg.get("auto_tick", False)
        full_auto = self.cfg.get("full_auto", False)

        # ── 自动模式：根据时段自动开始/暂停 ──
        if auto:
            if rate > 0 and active and not self.ticking:
                self._start()  # 进入工作时段 → 自动开始
            elif (rate == 0 or not active) and self.ticking:
                self._pause()  # 离开工作时段或空闲 → 自动暂停

        # ── 费率切换时结清上一段 ──
        prev = getattr(self, '_prev_rate', None)
        if prev is not None and prev != rate and self.ticking:
            elapsed = now - self.t0
            self.accumulated += elapsed * prev
            self.monthly_total += elapsed * prev
            self.t0 = now
        self._prev_rate = rate

        # 只在工作时段 + 电脑活跃时累加
        dec = int(self.cfg.get("money_decimals", 4))
        if full_auto:
            # 全自动模式：当日工资按系统时间秒级计算，与计时器/空闲状态无关
            # 不叠加"当日已填"：全自动口径纯按时间推算，避免与手动值双计
            today = calc_auto_today_seconds(self.cfg)
            self.money_lbl.setText(f"¥ {today:.{dec}f}")
        elif self.ticking and rate > 0 and active:
            current = self.accumulated + (now - self.t0) * rate
            today_total = current + self.cfg.get("manual_today", 0)
            self.money_lbl.setText(f"¥ {today_total:.{dec}f}")
        elif self.ticking and rate > 0 and not active:
            # 空闲中：暂停累加，但不停止计时状态
            elapsed = now - self.t0
            self.monthly_total += elapsed * rate
            self.accumulated += elapsed * rate
            self.t0 = now
            self._save_monthly()

        # ── 更新信息栏 ──
        if rate > 0:
            auto_tag = " [自动]" if self.cfg.get("full_auto", False) else ""
            rate_str = f"{period}{auto_tag}  ¥{rate * 3600:.2f}/时"
        else:
            rate_str = period
        self.rate_lbl.setText(rate_str)

        # 当月已赚
        if full_auto or self.cfg.get("show_monthly", True):
            if full_auto or self.cfg.get("auto_monthly", False):
                auto_total, today_earned, full_month = calc_auto_monthly_full(self.cfg)
                # 全自动运行：当月纯按日程估算，不叠加"当月已填"（与设置窗自动计算一致，避免双计）
                total = auto_total if full_auto else auto_total + self.cfg.get("manual_month", 0)
                if self.cfg.get("show_full_month", True):
                    self.monthly_lbl.setText(f"本月 ¥{total:.2f} / ¥{full_month:.0f}")
                else:
                    self.monthly_lbl.setText(f"本月 ¥{total:.2f}")
            else:
                total = self.monthly_total + self.cfg.get("manual_month", 0)
                self.monthly_lbl.setText(f"本月 ¥{total:.2f}")
            self.monthly_lbl.setVisible(True)
        else:
            self.monthly_lbl.setVisible(False)

        # 进度
        if self.cfg.get("show_progress", True):
            dp = calc_day_progress(self.cfg)
            mp = calc_month_progress(self.cfg)
            self.progress_lbl.setText(f"今日 {dp:.1f}%  |  本月 {mp:.1f}%")
            self.progress_lbl.setVisible(True)
        else:
            self.progress_lbl.setVisible(False)

        # 星期显示
        wd, wd_name = get_effective_weekday(self.cfg)
        offset = self.cfg.get("weekday_offset", 0)
        offset_str = f" (+{offset})" if offset > 0 else (f" ({offset})" if offset < 0 else "")
        is_wd = is_workday(self.cfg)
        workday_tag = "工作日" if is_wd else "休息日"
        self.weekday_lbl.setText(f"📅 {wd_name}{offset_str}  {workday_tag}")

        # 活动状态
        if self.cfg.get("show_active", True):
            if active:
                self.active_lbl.setText("🟢 活跃")
                self.active_lbl.setObjectName("active")
            else:
                self.active_lbl.setText(f"🔴 空闲 {int(idle_sec)}s")
                self.active_lbl.setObjectName("idle")

            self._apply_style()  # 刷新颜色
            self.active_lbl.setVisible(True)
        else:
            self.active_lbl.setVisible(False)

    # ═══════════════════════════════════════════════════════════
    # 设置 & 模式切换
    # ═══════════════════════════════════════════════════════════

    def _open_settings(self):
        self.settings_win = SettingsWindow(self.cfg)
        self.settings_win.saved.connect(self._on_settings_saved)
        self.settings_win.show()

    def _on_settings_saved(self):
        self._apply_style()
        self._resize_to_content()
        self._apply_hotkey()
        self._apply_topmost()

    def _resize_to_content(self):
        """缩放变化后让窗口贴合内容；保持右下角不动，避免贴边位置漂移"""
        br = self.frameGeometry().bottomRight()
        self.adjustSize()
        self.move(br.x() - self.width(), br.y() - self.height())

    def _toggle_show_monthly(self, on):
        """右键菜单切换月薪隐藏/显示（on=True 表示勾选"隐藏月薪"）"""
        self.cfg["show_monthly"] = not on
        save_json(CFG_PATH, self.cfg)

    def _toggle_full_auto(self, on):
        """右键菜单切换全自动运行；开启时月薪显示同时强制开启"""
        self.cfg["full_auto"] = on
        if on:
            self.cfg["show_monthly"] = True
        save_json(CFG_PATH, self.cfg)

    def _toggle_show_full_month(self, on):
        """切换自动估算时是否显示月薪总额"""
        self.cfg["show_full_month"] = on
        save_json(CFG_PATH, self.cfg)

    def _toggle_topmost(self, on):
        """切换悬浮窗置顶状态"""
        self.cfg["always_on_top"] = on
        self._apply_topmost()
        save_json(CFG_PATH, self.cfg)

    def _set_weekday_offset(self, offset):
        """设置星期偏移量"""
        self.cfg["weekday_offset"] = offset
        save_json(CFG_PATH, self.cfg)

    def _apply_topmost(self):
        """根据配置设置窗口置顶标志"""
        was_visible = self.isVisible()
        flags = self.windowFlags()
        if self.cfg.get("always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    def _apply_hotkey(self):
        """根据配置重新注册全局热键"""
        self.hotkey_filter.unregister(1)
        if not self.cfg.get("hotkey_enabled", True):
            return
        vk, mods = parse_hotkey(self.cfg.get("hotkey_show", "Ctrl+Shift+H"))
        if vk:
            self.hotkey_filter.register(vk, mods, 1)

    def _quit(self):
        self._pause()
        QApplication.quit()
