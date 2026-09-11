# -*- coding = utf-8 -*-
# @项目 : 工资计算器 - 自定义 Qt 控件模块
# @说明 : 滚轮防误触 Mixin 及其子类

from PySide6.QtWidgets import (
    QSpinBox, QDoubleSpinBox, QComboBox, QSlider,
    QTimeEdit, QKeySequenceEdit, QScrollArea,
)
from PySide6.QtCore import Qt


class _WheelSafe:
    """Mixin：彻底防止滚轮误触。

    三个关键修正：
    1. setFocusPolicy(StrongFocus) — 禁止滚轮自动抢夺焦点
    2. delta/120 × singleStep×3 — 正确的像素级平滑滚动
    3. leaveEvent → clearFocus() — 鼠标移出即释放焦点，杜绝残留
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 修正1：强制 StrongFocus，滚轮不能自动获取焦点
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        if not self.hasFocus():
            # 沿父级链向上找到 QScrollArea
            w = self.parent()
            while w is not None:
                if isinstance(w, QScrollArea):
                    bar = w.verticalScrollBar()
                    # 修正2：delta 是 1/8 度单位（±120），换算为像素步长
                    delta = event.angleDelta().y()
                    steps = delta / 120.0
                    scroll_amount = steps * bar.singleStep() * 3
                    bar.setValue(bar.value() - int(scroll_amount))
                    event.accept()
                    return
                w = w.parent()
            event.ignore()
        else:
            super().wheelEvent(event)

    # 修正3：鼠标移出控件即刻释放焦点，防止"点过一次后路过仍然误触"
    def leaveEvent(self, event):
        self.clearFocus()
        super().leaveEvent(event)


class SafeSpinBox(_WheelSafe, QSpinBox):
    pass


class SafeDoubleSpinBox(_WheelSafe, QDoubleSpinBox):
    pass


class SafeComboBox(_WheelSafe, QComboBox):
    pass


class SafeSlider(_WheelSafe, QSlider):
    pass


class SafeTimeEdit(_WheelSafe, QTimeEdit):
    pass


class SafeKeySequenceEdit(_WheelSafe, QKeySequenceEdit):
    pass
