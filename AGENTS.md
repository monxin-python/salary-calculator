# 工资计算器项目

## 项目概述
Windows 桌面悬浮窗，实时显示工作时段内的工资增长。基于 PySide6，支持自动计时、午休扣除、加班计费、空闲检测。

## 项目结构

```
工资计算器/
├── main.py              # 入口：QApplication + 热键 + 启动 FloatingDisplay
├── config.py            # 配置常量、JSON 读写、parse_time、屏幕缩放
├── calculator.py        # 纯计算：时薪/日薪/费率/进度/午休扣除/星期判断
├── system_utils.py      # Windows API：空闲检测(GetLastInputInfo)、全局热键
├── styles.py            # QSS 样式：设置窗样式、悬浮窗样式、右键菜单样式
├── widgets.py           # 滚轮防误触 Mixin + 5 个 Safe 控件
├── settings_window.py   # 设置窗口（SettingsWindow）：全部 UI + 保存/加载
├── floating_window.py   # 悬浮窗（FloatingDisplay）：计时器、右键菜单、拖动
├── salary_cfg.json      # 用户配置（38 项，存放于文档目录，兼容旧版格式）
└── salary_data.json     # 月度累计数据（按 YYYY-MM 分 key，存放于文档目录）
```

## 技术栈
- Python 3.11
- PySide6（Fusion 风格）
- ctypes（Windows 空闲检测、全局热键）
- 纯 JSON 持久化，无数据库

## 开发规则
- **不要随意修改现有 UI 和计算逻辑**——这是用户每日使用的工具
- 修改前先理解相关模块的全部代码
- 不要删除已有功能，只能在现有基础上扩展
- 修改后必须测试导入和核心计算
- 配置文件 `salary_cfg.json` 和 `salary_data.json` 格式必须向后兼容
- 新配置项加入 `DEFAULT_CFG`，旧配置文件缺少的字段会自动补充

## 当前功能清单

| 功能 | 说明 |
|------|------|
| 实时工资显示 | 每秒更新，4 位小数 |
| 自动计时 | 按时段自动开始/暂停（需开启 auto_tick） |
| 午休扣除 | 午休时段不计费 |
| 加班计费 | 支持手动时薪和倍率两种模式 |
| 空闲检测 | 鼠标键盘 N 秒无操作后暂停累加 |
| 当月累计 | 月薪显示可选"自动估算"或"计时累计"口径，手动已填两种口径均叠加 |
| 星期判断 | 非工作日自动休息，支持手动偏移 |
| 全局热键 | Ctrl+Shift+H 显示/隐藏悬浮窗 |
| 开机自启 | VBS 脚本写入 Startup 文件夹 |
| 悬浮置顶 | 可切换置顶/非置顶 |
| 拖动定位 | 位置自动保存 |
| 右键菜单 | 开始/暂停/清零/自动计时/月薪显示/置顶/修改星期/清除统计/设置/退出 |

## 关键状态（FloatingDisplay）

| 变量 | 说明 |
|------|------|
| `ticking` | 是否正在计时 |
| `t0` | 计时开始时刻（time.time()） |
| `accumulated` | 本次会话累计工资 |
| `monthly_total` | 当月累计（跨会话持久化到 salary_data.json） |
| `_prev_rate` | 上次 tick 时的费率，**暂停结算时使用它而非当前费率**，防止休息时段暂停导致工资丢失 |
| `cfg` | 配置字典（运行时修改会即时生效，保存时才写入文件） |

## 关键计算（calculator.py）

| 函数 | 公式 |
|------|------|
| `calc_hourly_rate` | 月薪 ÷ 当月实际工作日数 ÷ 每日工时（随月份浮动） |
| `calc_daily_rate` | 月薪 ÷ 当月实际工作日数（满勤时当月工资恒等于月薪） |
| `get_current_rate` | 按时段返回每秒费率：正常上班/午休中(0)/加班中(休息日加班窗口同样计费)/休息时间(0)/今日休息(0) |
| `count_workdays_in_month` | 当月实际工作日数（周一起数前 work_days 天） |
| `calc_elapsed_work_minutes` | 从上班到现在的净工作分钟数，扣除午休 |

## 容易踩坑的地方
1. **暂停结算**：`_pause()` 使用 `_prev_rate` 而非 `get_current_rate()`，因为暂停时刻可能已进入休息时段（费率=0），如果直接用当前费率会导致刚才的工资丢失
2. **费率切换**：`_tick()` 检测 `_prev_rate != rate` 时结算上一段的工资
3. **透明度**：card_alpha 最低 0.004（1/255），低于此值 Windows 不会投递鼠标事件
4. **星期偏移**：`weekday_offset` 影响当日是否工作日，不影响历史月份统计
5. **屏幕缩放**：`get_display_scale()` 需要 QApplication 已初始化才能调用
6. **开机自启**：VBS 路径现在指向 `main.py`，不是旧的单文件 `.py`
7. **手动已填双计**：自动估算已含今日进度，若"当月已填"由设置窗"自动计算"生成（也含今日），叠加后当日会被计入两次
