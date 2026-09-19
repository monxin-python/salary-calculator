# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 界面样式模块
# @说明 : QSS 样式表生成，保持原视觉效果完全不变

from config import get_display_scale


def get_settings_style(scale=None):
    """生成设置窗口 QSS 样式表，字号根据屏幕缩放因子适配"""
    if scale is None:
        scale = get_display_scale()
    # 设置窗口的字号缩放更温和，不低于 82%，保证可读性
    s = max(0.82, min(scale, 1.6))

    def sz(v):
        return max(9, int(v * s))

    return f"""
    QWidget#settings {{ background: #ffffff; }}
    QWidget#content  {{ background: transparent; }}
    QLabel#title    {{ color: #2c3e50; font-size: {sz(22)}px; font-weight: bold; }}
    QLabel#lbl      {{ color: #4a5568; font-size: {sz(16)}px; font-weight: bold; }}
    QLabel#info     {{ color: #8899a6; font-size: {sz(14)}px; }}
    QLabel#result   {{ color: #b8860b; font-size: {sz(16)}px; font-weight: bold; }}
    QLabel#section  {{ color: #b8860b; font-size: {sz(16)}px; font-weight: bold; padding: 4px 0; }}

    /* ── 文本输入 & 下拉框 ── */
    QLineEdit, QComboBox {{
        background: #f7f8fa;
        border: 1px solid #d1d5db;
        border-radius: {sz(8)}px;
        padding: {sz(10)}px {sz(14)}px;
        color: #2c3e50;
        font-size: {sz(15)}px;
        min-height: {sz(36)}px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid #f0c040;
    }}
    QLineEdit {{ selection-background-color: #f0c040; selection-color: #2c3e50; }}

    /* ── 数字/时间选择框 ──
       只设字色字号与最小高度：一旦设 background/border，Qt 会用样式表接管
       子控件，上下箭头就画不出来（原生按钮被顶掉，只剩一个空框）。 */
    QSpinBox, QDoubleSpinBox, QTimeEdit, QDateTimeEdit {{
        color: #2c3e50;
        font-size: {sz(15)}px;
        min-height: {sz(36)}px;
    }}

    QComboBox QAbstractItemView {{
        background: #ffffff; color: #2c3e50; font-size: {sz(15)}px;
        selection-background-color: #f0c040; selection-color: #2c3e50;
        border: 1px solid #e0e0e0;
    }}

    QPushButton#gold {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #f0c040, stop:1 #e0a820);
        border: none; border-radius: {sz(8)}px; padding: {sz(14)}px; color: #2c3e50;
        font-size: {sz(16)}px; font-weight: bold; min-height: {sz(30)}px;
    }}
    QPushButton#gold:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #f5cc55, stop:1 #ebb830); }}

    /* 不能给勾选框设 background：会让未勾选的方框/圆点整个消失（只留勾号） */
    QCheckBox, QRadioButton {{ color: #4a5568; font-size: {sz(15)}px; padding: 4px 0; }}
    QCheckBox::indicator, QRadioButton::indicator {{ width: {sz(18)}px; height: {sz(18)}px; }}
    QSlider::groove:horizontal {{ height: {sz(6)}px; background: #e0e0e0; border-radius: 3px; }}
    QSlider::handle:horizontal {{ width: {sz(16)}px; height: {sz(16)}px; margin: -5px 0; background: #f0c040; border-radius: {sz(8)}px; }}
    QSlider::sub-page:horizontal {{ background: #f0c040; border-radius: 3px; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{
        background: #e8e8e8; width: {sz(8)}px; border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: #c0c0c0; border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #a0a0a0; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def get_floating_style(card_alpha, font_size, info_size, scale):
    """生成悬浮窗 QSS 样式表。

    Args:
        card_alpha: 背景不透明度 0-100
        font_size: 金额字号(基准值)
        info_size: 信息字号(基准值)
        scale: 屏幕缩放因子
    """
    display_fs = max(10, int(font_size * scale))
    display_infs = max(8, int(info_size * scale))
    display_monthly = max(8, int((info_size + 2) * scale))
    radius = int(12 * scale)

    # 卡片的实际透明度；低于 0.004 时 Windows 会认为该区域"没有像素"而
    # 拒绝投递鼠标事件（右键菜单无法弹出）。最低保持 0.004（1/255），肉眼完全不可见。
    card_bg = max(card_alpha / 100.0, 0.004)
    border_a = max(0.06 * card_alpha / 100.0, 0.004) if card_alpha > 0 else 0.0

    return f"""
    QWidget#main {{ background: rgba(0,0,0,0.004); }}
    QFrame#card  {{ background: rgba(20,20,40,{card_bg:.3f});
                   border: 1px solid rgba(255,255,255,{border_a:.3f});
                   border-radius: {radius}px; }}
    QLabel#money  {{ color: #f0c040; font-weight: bold; font-size: {display_fs}px; background: transparent; }}
    QLabel#monthly {{ color: #ffd700; font-size: {display_monthly}px; background: transparent; }}
    QLabel#rate   {{ color: #8892b0; font-size: {display_infs}px; background: transparent; }}
    QLabel#progress {{ color: #5ab0f0; font-size: {display_infs}px; background: transparent; }}
    QLabel#active {{ color: #5ac060; font-size: {display_infs}px; background: transparent; }}
    QLabel#idle   {{ color: #c05050; font-size: {display_infs}px; background: transparent; }}
    QLabel#weekday {{ color: #c8a8e0; font-size: {display_infs}px; background: transparent; }}
"""


def get_floating_padding(scale):
    """返回悬浮窗 card 的 (pad_h, pad_v, spacing)"""
    return int(18 * scale), int(8 * scale), max(1, int(2 * scale))


# ── 右键菜单样式 ──────────────────────────────────────

MENU_STYLE = """
    QMenu { background: #1e1e36; color: #c0c0c0; border:1px solid rgba(255,255,255,0.12);
            border-radius:6px; padding:4px; }
    QMenu::item { padding:6px 24px; border-radius:4px; }
    QMenu::item:selected { background:#f0c040; color:#1a1a2e; }
    QMenu::separator { height:1px; background:rgba(255,255,255,0.10); margin:2px 8px; }
"""
