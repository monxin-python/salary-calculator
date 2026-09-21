# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 设置窗口模块
# @说明 : 完整负责设置窗口的所有 UI 和交互，计算逻辑委托给 calculator

import os
import sys
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFrame, QCheckBox, QFormLayout,
    QPushButton, QRadioButton, QButtonGroup,
    QScrollArea, QMessageBox, QSlider,
)
from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtGui import QFontDatabase, QKeySequence

from config import (
    CFG_PATH, save_json,
    get_display_scale, scale_value,
)
from calculator import (
    calc_hourly_rate, calc_daily_rate,
    calc_elapsed_work_minutes, calc_leave_deduction, calc_ot_pay,
    calc_auto_today_earned, calc_auto_month_earned,
)
from widgets import (
    SafeSpinBox, SafeDoubleSpinBox, SafeComboBox,
    SafeSlider, SafeTimeEdit, SafeKeySequenceEdit,
)
from styles import get_settings_style


class SettingsWindow(QWidget):
    saved = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.setObjectName("settings")
        self.setWindowTitle("⚙ 设置")
        self.setStyleSheet(get_settings_style())   # objectName 选择器对应的样式表

        # 屏幕缩放因子（仅自动检测，手动 ui_scale 不影响窗口大小）
        win_scale = self._win_scale()

        # 计算窗口大小
        w = int(cfg.get("settings_w", 600) * win_scale)
        h = int(cfg.get("settings_h", 850) * win_scale)
        self.resize(max(w, 500), max(h, 600))
        self.setMinimumSize(480, 560)

        # ── 滚动区域 ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        # 内容容器
        self._content = QWidget(objectName="content")
        self._scroll.setWidget(self._content)

        # 将滚动区域设为主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._scroll)

        self._build()
        self._load()

        sx = cfg.get("settings_x", -1)
        sy = cfg.get("settings_y", -1)
        if sx >= 0 and sy >= 0:
            self.move(sx, sy)
        else:
            geo = QApplication.primaryScreen().geometry()
            self.move((geo.width() - self.width()) // 2, (geo.height() - self.height()) // 2)

    # ── 辅助方法 ──────────────────────────────────────

    def _sep(self):
        s = QFrame()
        s.setStyleSheet("background:#e0e0e0; max-height:1px;")
        return s

    def _h_pair(self, a, b):
        r = QHBoxLayout()
        r.addWidget(a, 1)
        r.addWidget(QLabel("—", objectName="info"))
        r.addWidget(b, 1)
        return r

    # ── 构建界面 ──────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self._content)
        m_h, m_v = scale_value(20), scale_value(14)
        root.setContentsMargins(m_h, m_v, m_h, m_v)
        root.setSpacing(0)

        root.addWidget(QLabel("⚙ 设置", objectName="title", alignment=Qt.AlignCenter))
        root.addSpacing(12)

        # ── 薪资 ──
        form = QFormLayout()
        form.setSpacing(10)

        self.monthly = SafeDoubleSpinBox(prefix="¥ ", maximum=999999, decimals=2, singleStep=100)
        form.addRow(QLabel("月薪", objectName="lbl"), self.monthly)

        self.work_days = SafeSpinBox(minimum=1, maximum=7, suffix=" 天/周")
        form.addRow(QLabel("每周工作日", objectName="lbl"), self.work_days)

        self.daily_hrs = SafeDoubleSpinBox(minimum=0.5, maximum=24, decimals=1, suffix=" 小时/天")
        form.addRow(QLabel("每日工时", objectName="lbl"), self.daily_hrs)

        self.hourly_lbl = QLabel("时薪: ¥0.00", objectName="result")
        form.addRow(QLabel(""), self.hourly_lbl)
        self.monthly.valueChanged.connect(self._recalc)
        self.work_days.valueChanged.connect(self._recalc)
        self.daily_hrs.valueChanged.connect(self._recalc)

        root.addLayout(form)
        root.addSpacing(6)
        root.addWidget(self._sep())
        root.addSpacing(6)

        # ── 工作时段 ──
        root.addWidget(QLabel("⏰ 工作时段", objectName="section"))
        root.addSpacing(6)
        f2 = QFormLayout()
        f2.setSpacing(14)

        self.norm_start = SafeTimeEdit(QTime(8, 0), displayFormat="HH:mm")
        self.norm_end = SafeTimeEdit(QTime(17, 30), displayFormat="HH:mm")
        f2.addRow(QLabel("正常上班", objectName="lbl"),
                  self._h_pair(self.norm_start, self.norm_end))

        self.lunch_start = SafeTimeEdit(QTime(12, 0), displayFormat="HH:mm")
        self.lunch_end = SafeTimeEdit(QTime(13, 0), displayFormat="HH:mm")
        f2.addRow(QLabel("午休时段", objectName="lbl"),
                  self._h_pair(self.lunch_start, self.lunch_end))
        self.lunch_enabled_cb = QCheckBox("启用午休时段")
        f2.addRow(QLabel(""), self.lunch_enabled_cb)

        self.ot_start = SafeTimeEdit(QTime(18, 0), displayFormat="HH:mm")
        self.ot_end = SafeTimeEdit(QTime(21, 0), displayFormat="HH:mm")
        f2.addRow(QLabel("加班时段", objectName="lbl"),
                  self._h_pair(self.ot_start, self.ot_end))
        self.ot_enabled_cb = QCheckBox("启用加班时段")
        f2.addRow(QLabel(""), self.ot_enabled_cb)

        self.ot_mode_group = QButtonGroup(self)
        ot_row = QHBoxLayout()
        self.ot_manual_rb = QRadioButton("手动填时薪")
        self.ot_multi_rb = QRadioButton("倍率×正常时薪")
        self.ot_mode_group.addButton(self.ot_manual_rb, 0)
        self.ot_mode_group.addButton(self.ot_multi_rb, 1)
        ot_row.addWidget(self.ot_manual_rb)
        ot_row.addWidget(self.ot_multi_rb)
        f2.addRow(QLabel("加班计费", objectName="lbl"), ot_row)

        self.ot_rate = SafeDoubleSpinBox(prefix="¥ ", maximum=9999, decimals=2, singleStep=10, value=60)
        self.ot_manual_rb.toggled.connect(lambda chk: self.ot_rate.setEnabled(chk))
        f2.addRow(QLabel("加班时薪", objectName="lbl"), self.ot_rate)

        self.ot_mult = SafeDoubleSpinBox(minimum=1.0, maximum=5.0, decimals=1, singleStep=0.1, value=1.5, prefix="×")
        self.ot_multi_rb.toggled.connect(lambda chk: self.ot_mult.setEnabled(chk))
        f2.addRow(QLabel("加班倍率", objectName="lbl"), self.ot_mult)

        # 当月已加班：加班费 = 小时数 × 加班时薪，仅在启用加班时段时可填。
        # 取消勾选只让加班费归零，小时数保留，重新勾选即按原数算回来。
        self.ot_hours_month = SafeDoubleSpinBox(decimals=2, maximum=999, singleStep=0.5, suffix=" 小时")
        f2.addRow(QLabel("当月已加班", objectName="lbl"), self.ot_hours_month)
        self.ot_pay_lbl = QLabel("加班费: ¥0.00", objectName="result")
        f2.addRow(QLabel(""), self.ot_pay_lbl)
        self.ot_enabled_cb.toggled.connect(self.ot_hours_month.setEnabled)
        self.ot_enabled_cb.toggled.connect(self._recalc_ot_pay)
        self.ot_hours_month.setEnabled(self.ot_enabled_cb.isChecked())
        for w in (self.monthly, self.work_days, self.daily_hrs,
                  self.ot_hours_month, self.ot_rate, self.ot_mult):
            w.valueChanged.connect(self._recalc_ot_pay)

        root.addLayout(f2)
        root.addSpacing(6)
        root.addWidget(self._sep())
        root.addSpacing(6)

        # ── 外观 ──
        root.addWidget(QLabel("🎨 外观", objectName="section"))
        root.addSpacing(6)
        f4 = QFormLayout()
        f4.setSpacing(10)

        self.font_combo = SafeComboBox()
        for f in sorted(QFontDatabase.families()):
            self.font_combo.addItem(f)
        f4.addRow(QLabel("字体", objectName="lbl"), self.font_combo)

        self.font_size = SafeSlider(Qt.Horizontal, minimum=16, maximum=80, value=42)
        self.font_size_val = QLabel("42px", objectName="info")
        self.font_size.valueChanged.connect(self._update_font_size_label)
        self._update_font_size_label(self.font_size.value())  # 初始化时刷新一次标签
        sz = QHBoxLayout(); sz.addWidget(self.font_size); sz.addWidget(self.font_size_val)
        f4.addRow(QLabel("金额字号", objectName="lbl"), sz)

        self.money_decimals = SafeSlider(Qt.Horizontal, minimum=0, maximum=6, value=4)
        self.money_decimals.setSingleStep(1)
        self.money_decimals.setPageStep(1)
        self.money_decimals.setTickPosition(QSlider.TicksBelow)  # 7 段等距刻度
        self.money_decimals.setTickInterval(1)
        self.money_decimals_val = QLabel("4位", objectName="info")
        self.money_decimals.valueChanged.connect(
            lambda v: self.money_decimals_val.setText(f"{v}位"))
        self.money_decimals.valueChanged.emit(self.money_decimals.value())
        md = QHBoxLayout(); md.addWidget(self.money_decimals); md.addWidget(self.money_decimals_val)
        f4.addRow(QLabel("金额小数位", objectName="lbl"), md)

        self.card_alpha = SafeSlider(Qt.Horizontal, minimum=0, maximum=100, value=0)
        self.card_alpha_val = QLabel("0%", objectName="info")
        self.card_alpha.valueChanged.connect(lambda v: self.card_alpha_val.setText(f"{v}%"))
        ar = QHBoxLayout(); ar.addWidget(self.card_alpha); ar.addWidget(self.card_alpha_val)
        f4.addRow(QLabel("背景不透明度", objectName="lbl"), ar)

        self.ui_scale = SafeSlider(Qt.Horizontal, minimum=50, maximum=200, value=100, singleStep=5)
        self.ui_scale.setToolTip("整体缩放悬浮窗：低分辨率调大、高分辨率调小，100% 为跟随屏幕自动检测")
        self.ui_scale_val = QLabel("100%", objectName="info")
        self.ui_scale.valueChanged.connect(lambda v: self.ui_scale_val.setText(f"{v}%"))
        self.ui_scale_auto_btn = QPushButton("自动")
        self.ui_scale_auto_btn.setToolTip("恢复 100%（跟随屏幕分辨率自动缩放）")
        self.ui_scale_auto_btn.clicked.connect(lambda: self.ui_scale.setValue(100))
        # 按钮放滑块左侧：四个滑块的右端位置保持一致
        us = QHBoxLayout(); us.addWidget(self.ui_scale_auto_btn); us.addWidget(self.ui_scale); us.addWidget(self.ui_scale_val)
        f4.addRow(QLabel("界面缩放", objectName="lbl"), us)

        # 四个调节条的值标签统一列宽，右侧间距一致
        for lbl in (self.font_size_val, self.money_decimals_val, self.card_alpha_val, self.ui_scale_val):
            lbl.setMinimumWidth(scale_value(130))

        root.addLayout(f4)
        root.addSpacing(6)
        root.addWidget(self._sep())
        root.addSpacing(6)

        # ── 主界面显示 ──
        root.addWidget(QLabel("📺 主界面显示", objectName="section"))
        root.addSpacing(6)
        self.chk_monthly = QCheckBox("显示当月已赚工资")
        self.chk_full_month = QCheckBox("显示月薪总额（自动估算时）")
        self.chk_progress = QCheckBox("显示工作进度百分比")
        self.chk_active = QCheckBox("显示电脑活动状态")
        root.addWidget(self.chk_monthly)
        root.addSpacing(4)
        root.addWidget(self.chk_full_month)
        root.addSpacing(4)
        root.addWidget(self.chk_progress)
        root.addSpacing(4)
        root.addWidget(self.chk_active)
        root.addSpacing(6)
        root.addWidget(self._sep())
        root.addSpacing(6)

        # ── 通用 ──
        root.addWidget(QLabel("⚙ 通用", objectName="section"))
        root.addSpacing(6)
        self.chk_topmost = QCheckBox("悬浮窗始终置顶")
        self.chk_full_auto = QCheckBox("全自动运行（无论何时打开都自动计算当日/当月工资）")
        self.chk_full_auto.setToolTip(
            "开启后无需任何操作：当日工资按系统时间秒级计算、当月按日程自动估算；\n"
            "关闭后回到手动模式（右键开始/暂停计时）")
        self.chk_autostart = QCheckBox("开机自启")
        self.chk_hotkey = QCheckBox("启用全局快捷键")
        root.addWidget(self.chk_topmost)
        root.addSpacing(4)
        root.addWidget(self.chk_full_auto)
        root.addSpacing(4)
        root.addWidget(self.chk_autostart)
        root.addSpacing(4)
        root.addWidget(self.chk_hotkey)
        root.addSpacing(6)
        root.addWidget(self._sep())
        root.addSpacing(6)

        # ── 快捷键 ──
        root.addWidget(QLabel("⌨ 快捷键", objectName="section"))
        root.addSpacing(6)
        fk = QFormLayout()
        fk.setSpacing(10)
        self.hotkey_edit = SafeKeySequenceEdit()
        self.hotkey_edit.setToolTip("按下你想要的组合键，如 Ctrl+Shift+H")
        fk.addRow(QLabel("显示/隐藏悬浮窗", objectName="lbl"), self.hotkey_edit)
        root.addLayout(fk)
        root.addSpacing(6)
        root.addWidget(self._sep())
        root.addSpacing(6)

        # ── 活动检测 ──
        root.addWidget(QLabel("🖱 活动检测", objectName="section"))
        root.addSpacing(6)
        f3 = QFormLayout()
        f3.setSpacing(10)
        self.idle_timeout = SafeSpinBox(minimum=30, maximum=3600, singleStep=30,
                                        suffix=" 秒", toolTip="无操作多久后暂停计时")
        f3.addRow(QLabel("空闲超时", objectName="lbl"), self.idle_timeout)
        root.addLayout(f3)
        root.addSpacing(6)
        root.addWidget(self._sep())
        root.addSpacing(6)

        # ── 手动填写已赚 ──
        root.addWidget(QLabel("✏ 手动填写已赚", objectName="section"))
        root.addSpacing(6)
        f5 = QFormLayout()
        f5.setSpacing(10)
        self.manual_today = SafeDoubleSpinBox(prefix="¥ ", maximum=999999, decimals=2, singleStep=50)
        today_btn = QPushButton("自动计算", clicked=self._autofill_today)
        today_row = QHBoxLayout()
        today_row.addWidget(self.manual_today, 1)
        today_row.addWidget(today_btn, 0)
        f5.addRow(QLabel("当日已填", objectName="lbl"), today_row)
        self.manual_month = SafeDoubleSpinBox(prefix="¥ ", maximum=999999, decimals=2, singleStep=1000)
        month_btn = QPushButton("自动计算", clicked=self._autofill_month)
        month_row = QHBoxLayout()
        month_row.addWidget(self.manual_month, 1)
        month_row.addWidget(month_btn, 0)
        f5.addRow(QLabel("当月已填", objectName="lbl"), month_row)
        self.month_detail_lbl = QLabel("", objectName="result")
        f5.addRow(QLabel(""), self.month_detail_lbl)
        root.addLayout(f5)
        root.addSpacing(6)
        root.addWidget(self._sep())
        root.addSpacing(6)

        # ── 请假 ──
        root.addWidget(QLabel("📅 请假", objectName="section"))
        root.addSpacing(6)
        f6 = QFormLayout()
        f6.setSpacing(10)
        self._leave_unit = "day"   # 当前单位：day=天 / hour=小时
        self.leave_spin = SafeDoubleSpinBox(decimals=2, maximum=999, singleStep=0.5, suffix=" 天")
        self.leave_unit_btn = QPushButton("切换为小时")
        self.leave_unit_btn.setToolTip("点击在天/小时之间切换，数值自动换算")
        self.leave_unit_btn.clicked.connect(self._toggle_leave_unit)
        leave_row = QHBoxLayout()
        leave_row.addWidget(self.leave_spin, 1)
        leave_row.addWidget(self.leave_unit_btn, 0)
        f6.addRow(QLabel("当月已请假", objectName="lbl"), leave_row)
        self.leave_deduct_lbl = QLabel("请假扣除: ¥0.00", objectName="result")
        f6.addRow(QLabel(""), self.leave_deduct_lbl)
        for w in (self.monthly, self.work_days, self.daily_hrs, self.leave_spin):
            w.valueChanged.connect(self._recalc_leave)
        root.addLayout(f6)
        root.addSpacing(10)

        save_btn = QPushButton("💾 保存设置", objectName="gold", clicked=self._save)
        root.addWidget(save_btn)

    # ── 自动填充（委托给 calculator）──────────────────

    def _ui_work_times(self):
        """设置窗控件里的工作时段原始值，供 calculator 的自动计算函数使用"""
        return (
            self.norm_start.time().toString("HH:mm"),
            self.norm_end.time().toString("HH:mm"),
            self.lunch_start.time().toString("HH:mm"),
            self.lunch_end.time().toString("HH:mm"),
            self.lunch_enabled_cb.isChecked(),
        )

    def _autofill_today(self):
        """计算今天已赚金额并填入 —— 使用当前 UI 控件的值"""
        now = datetime.now()
        salary = self.monthly.value()
        work_days = self.work_days.value()

        if now.weekday() >= work_days:
            QMessageBox.information(self, "提示", "今天是休息日，无需计算当日工资")
            return

        if calc_daily_rate(salary, work_days) <= 0:
            QMessageBox.warning(self, "错误", "日薪计算有误，请检查月薪和每周工作日设置")
            return

        if calc_elapsed_work_minutes(now.time(), *self._ui_work_times())[1] <= 0:
            QMessageBox.warning(self, "错误", "工作时间配置有误，请检查上下班时间设置")
            return

        earned = calc_auto_today_earned(salary, work_days, *self._ui_work_times(), now)
        self.manual_today.setValue(round(earned, 2))

    def _autofill_month(self):
        """计算本月已赚金额并填入 —— 使用当前 UI 控件的值"""
        now = datetime.now()
        salary = self.monthly.value()
        work_days = self.work_days.value()

        if calc_daily_rate(salary, work_days) <= 0:
            QMessageBox.warning(self, "错误", "日薪计算有误，请检查月薪和每周工作日设置")
            return

        gross = calc_auto_month_earned(salary, work_days, *self._ui_work_times(), now)
        deduct = self._leave_deduct()
        net = round(max(0.0, gross - deduct), 2)
        self.manual_month.setValue(net)
        # 展示算式明细，避免只看到一个已扣除的数字不知所来
        if deduct > 0:
            self.month_detail_lbl.setText(
                f"当月工资 ¥{gross:.2f} − 请假 ¥{deduct:.2f} = 实际 ¥{net:.2f}")
        else:
            self.month_detail_lbl.setText(f"当月工资 ¥{gross:.2f}")

    # ── 请假单位切换 ─────────────────────────────────

    def _leave_deduct(self):
        """按当前控件值计算本月请假扣除额"""
        return calc_leave_deduction({
            "salary": self.monthly.value(),
            "work_days": self.work_days.value(),
            "daily_hours": self.daily_hrs.value(),
            "leave_value": self.leave_spin.value(),
            "leave_unit": self._leave_unit,
        })

    def _toggle_leave_unit(self):
        """天 ↔ 小时切换，数值按每日工时自动换算"""
        v = self.leave_spin.value()
        hrs = self.daily_hrs.value()
        if self._leave_unit == "day":
            self._leave_unit = "hour"
            v = v * hrs if hrs > 0 else v
        else:
            self._leave_unit = "day"
            v = v / hrs if hrs > 0 else v
        self.leave_spin.setSuffix(" 天" if self._leave_unit == "day" else " 小时")
        self.leave_unit_btn.setText("切换为小时" if self._leave_unit == "day" else "切换为天")
        self.leave_spin.setValue(round(v, 2))   # 触发 _recalc_leave

    def _recalc_leave(self):
        """实时显示请假扣除金额（使用当前控件值）"""
        self.leave_deduct_lbl.setText(f"请假扣除: ¥{self._leave_deduct():.2f}")

    # ── 加班费 ───────────────────────────────────────

    def _ot_pay(self):
        """按当前控件值计算本月加班费（未勾选加班时段时为 0）"""
        return calc_ot_pay({
            "salary": self.monthly.value(),
            "work_days": self.work_days.value(),
            "daily_hours": self.daily_hrs.value(),
            "ot_enabled": self.ot_enabled_cb.isChecked(),
            "ot_mode": "manual" if self.ot_manual_rb.isChecked() else "multiplier",
            "ot_rate": self.ot_rate.value(),
            "ot_multiplier": self.ot_mult.value(),
            "ot_hours_month": self.ot_hours_month.value(),
        })

    def _recalc_ot_pay(self):
        """实时显示加班费金额（使用当前控件值）"""
        self.ot_pay_lbl.setText(f"加班费: ¥{self._ot_pay():.2f}")

    # ── 窗口大小还原 ─────────────────────────────────

    def _win_scale(self):
        """设置窗口缩放因子：仅跟随屏幕自动检测，不受手动 ui_scale 影响。
        窗口大小是用户自己设置的，拉界面缩放不应改变它。
        """
        return max(0.82, min(get_display_scale(), 1.6))

    def _unscale(self):
        """将当前窗口尺寸还原到基准分辨率，与 __init__ 使用同一公式保证往返一致"""
        win_scale = self._win_scale()
        if win_scale > 0:
            return int(self.width() / win_scale), int(self.height() / win_scale)
        return self.width(), self.height()

    def closeEvent(self, event):
        self.cfg["settings_w"], self.cfg["settings_h"] = self._unscale()
        self.cfg["settings_x"] = self.x()
        self.cfg["settings_y"] = self.y()
        save_json(CFG_PATH, self.cfg)
        event.accept()

    # ── 开机自启 ─────────────────────────────────────

    @staticmethod
    def _set_autostart(enable):
        """写入或删除开机自启 .vbs"""
        startup_dir = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
        )
        vbs_path = os.path.join(startup_dir, "SalaryTimer.vbs")
        if enable:
            if getattr(sys, "frozen", False):
                # 打包后 __file__ 在临时解压目录，直接运行 exe 本身
                line = f'CreateObject("WScript.Shell").Run "{sys.executable}", 0, False\n'
            else:
                this_dir = os.path.dirname(os.path.abspath(__file__))
                script = os.path.join(this_dir, "main.py")
                pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                line = f'CreateObject("WScript.Shell").Run "{pythonw}" "{script}", 0, False\n'
            with open(vbs_path, "w") as f:
                f.write(line)
        else:
            try:
                os.remove(vbs_path)
            except Exception:
                pass

    # ── 时薪显示 ─────────────────────────────────────

    def _recalc(self):
        h = calc_hourly_rate(self.monthly.value(), self.work_days.value(), self.daily_hrs.value())
        if h > 0:
            self.hourly_lbl.setText(f"时薪: ¥{h:.2f}")
        else:
            self.hourly_lbl.setText("时薪: 计算错误")

    def _update_font_size_label(self, v):
        """金额字号标签只显示基准值（保持四个调节条右端对齐），实际大小放 tooltip"""
        self.font_size_val.setText(f"{v}px")
        self.font_size_val.setToolTip(f"实际显示约 {scale_value(v)}px（按屏幕缩放）")

    # ── 加载 / 保存 ──────────────────────────────────

    def _load(self):
        c = self.cfg
        self.monthly.setValue(c.get("salary", 15000))
        self.work_days.setValue(c.get("work_days", 5))
        self.daily_hrs.setValue(c.get("daily_hours", 8.0))
        for k, w, fmt in [("normal_start", self.norm_start, "08:00"),
                          ("normal_end", self.norm_end, "17:30"),
                          ("lunch_start", self.lunch_start, "12:00"),
                          ("lunch_end", self.lunch_end, "13:00"),
                          ("ot_start", self.ot_start, "18:00"),
                          ("ot_end", self.ot_end, "21:00")]:
            v = c.get(k, fmt)
            w.setTime(QTime(*map(int, v.split(":"))))
        if c.get("ot_mode", "manual") == "manual":
            self.ot_manual_rb.setChecked(True)
            self.ot_rate.setEnabled(True)
            self.ot_mult.setEnabled(False)
        else:
            self.ot_multi_rb.setChecked(True)
            self.ot_rate.setEnabled(False)
            self.ot_mult.setEnabled(True)
        self.ot_rate.setValue(c.get("ot_rate", 60))
        self.ot_mult.setValue(c.get("ot_multiplier", 1.5))
        self.ot_hours_month.setValue(c.get("ot_hours_month", 0.0))
        self.idle_timeout.setValue(c.get("idle_timeout", 300))
        idx = self.font_combo.findText(c.get("font_family", "Microsoft YaHei"))
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        self.font_size.setValue(c.get("font_size", 42))
        self.money_decimals.setValue(c.get("money_decimals", 4))
        self.card_alpha.setValue(c.get("card_alpha", 0))
        self.ui_scale.setValue(int(c.get("ui_scale", 100)))
        self.chk_monthly.setChecked(c.get("show_monthly", True))
        self.chk_full_month.setChecked(c.get("show_full_month", True))
        self.chk_progress.setChecked(c.get("show_progress", True))
        self.chk_active.setChecked(c.get("show_active", True))
        self.ot_enabled_cb.setChecked(c.get("ot_enabled", False))
        self.lunch_enabled_cb.setChecked(c.get("lunch_enabled", True))
        self.manual_today.setValue(c.get("manual_today", 0))
        self.manual_month.setValue(c.get("manual_month", 0))
        self._leave_unit = c.get("leave_unit", "day")
        self.leave_spin.setSuffix(" 天" if self._leave_unit == "day" else " 小时")
        self.leave_unit_btn.setText("切换为小时" if self._leave_unit == "day" else "切换为天")
        self.leave_spin.setValue(c.get("leave_value", 0.0))
        self._recalc_leave()
        self._recalc_ot_pay()
        self.hotkey_edit.setKeySequence(QKeySequence(c.get("hotkey_show", "Ctrl+Shift+H")))
        self.chk_hotkey.setChecked(c.get("hotkey_enabled", True))
        self.chk_autostart.setChecked(c.get("auto_start", False))
        self.chk_full_auto.setChecked(c.get("full_auto", False))
        self.chk_topmost.setChecked(c.get("always_on_top", True))
        self._recalc()

    def _save(self):
        c = self.cfg
        c["salary"] = self.monthly.value()
        c["work_days"] = self.work_days.value()
        c["daily_hours"] = self.daily_hrs.value()
        c["normal_start"] = self.norm_start.time().toString("HH:mm")
        c["normal_end"] = self.norm_end.time().toString("HH:mm")
        c["ot_start"] = self.ot_start.time().toString("HH:mm")
        c["ot_end"] = self.ot_end.time().toString("HH:mm")
        c["lunch_start"] = self.lunch_start.time().toString("HH:mm")
        c["lunch_end"] = self.lunch_end.time().toString("HH:mm")
        c["lunch_enabled"] = self.lunch_enabled_cb.isChecked()
        c["ot_mode"] = "manual" if self.ot_manual_rb.isChecked() else "multiplier"
        c["ot_rate"] = self.ot_rate.value()
        c["ot_multiplier"] = self.ot_mult.value()
        c["ot_hours_month"] = self.ot_hours_month.value()
        c["idle_timeout"] = self.idle_timeout.value()
        c["font_family"] = self.font_combo.currentText()
        c["font_size"] = self.font_size.value()
        c["money_decimals"] = self.money_decimals.value()
        c["card_alpha"] = self.card_alpha.value()
        c["show_monthly"] = self.chk_monthly.isChecked()
        c["show_full_month"] = self.chk_full_month.isChecked()
        c["show_progress"] = self.chk_progress.isChecked()
        c["show_active"] = self.chk_active.isChecked()
        c["ot_enabled"] = self.ot_enabled_cb.isChecked()
        c["manual_today"] = self.manual_today.value()
        c["manual_month"] = self.manual_month.value()
        c["leave_value"] = self.leave_spin.value()
        c["leave_unit"] = self._leave_unit
        c["hotkey_show"] = self.hotkey_edit.keySequence().toString()
        c["hotkey_enabled"] = self.chk_hotkey.isChecked()
        c["auto_start"] = self.chk_autostart.isChecked()
        c["full_auto"] = self.chk_full_auto.isChecked()
        c["always_on_top"] = self.chk_topmost.isChecked()
        c["ui_scale"] = self.ui_scale.value()
        self._set_autostart(self.chk_autostart.isChecked())
        c["settings_w"], c["settings_h"] = self._unscale()
        save_json(CFG_PATH, c)
        self.saved.emit()
        self.hide()
