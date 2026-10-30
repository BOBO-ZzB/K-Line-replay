"""主题系统：TradingView 风格的深色/浅色调色板与统一 QSS。

用法：
    from theme import get_palette, build_qss
    p = get_palette("dark")          # 或 "light"
    window.setStyleSheet(build_qss(p))
    chart.apply_theme(p)

配色约定：绿涨红跌（上涨 #26a69a 绿，下跌 #ef5350 红），EMA20 为蓝色。
默认主题为 dark（TradingView 默认即深色）。
"""

DARK = {
    "name": "dark",
    "is_dark": True,
    "bg": "#131722",
    "panel": "#1e222d",
    "panel2": "#2a2e39",
    "border": "#2a2e39",
    "text": "#d1d4dc",
    "muted": "#787b86",
    "hover": "#2a2e39",
    "active_bg": "#233150",
    "accent": "#2962ff",
    "accent_hover": "#1e53e5",
    "chart_bg": "#131722",
    "grid": "#1f2430",
    "up": "#26a69a",
    "down": "#ef5350",
    "ema": "#2962ff",
    "hline": "#f0b90b",
    "rect": "#00bcd4",
    "fib": "#ab47bc",
}

LIGHT = {
    "name": "light",
    "is_dark": False,
    "bg": "#f5f1e8",
    "panel": "#efe9dc",
    "panel2": "#e8e1d3",
    "border": "#ddd5c4",
    "text": "#1a1a1a",
    "muted": "#8a8478",
    "hover": "#e8e1d3",
    "active_bg": "#e3eaf3",
    "accent": "#2962ff",
    "accent_hover": "#1e53e5",
    "chart_bg": "#f5f1e8",
    "grid": "#e3dbc9",
    "up": "#26a69a",
    "down": "#ef5350",
    "ema": "#1565c0",
    "hline": "#d99a00",
    "rect": "#ef5350",
    "fib": "#8e24aa",
}

PALETTES = {"dark": DARK, "light": LIGHT}


def get_palette(name: str):
    return PALETTES.get(name, DARK)


_QSS = """
* {
    font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
    color: $TEXT$;
    outline: 0;
}
QMainWindow, QWidget#Root { background: $BG$; }
QWidget#TopBar { background: $PANEL$; border-bottom: 1px solid $BORDER$; }
QWidget#ToolRail { background: $PANEL$; border-right: 1px solid $BORDER$; }
QWidget#BottomBar { background: $PANEL$; border-top: 1px solid $BORDER$; }

QLabel { background: transparent; }
QLabel#Symbol { font-size: 17px; font-weight: 700; color: $TEXT$; }
QLabel#SymbolExchange { font-size: 11px; color: $MUTED$; }
QLabel#Muted { color: $MUTED$; }
QLabel#BottomText { color: $MUTED$; font-size: 12px; }
QLabel#Legend { background: transparent; }

QPushButton {
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    color: $TEXT$;
}
QPushButton:hover { background: $HOVER$; }
QPushButton:pressed { background: $PANEL2$; }

QPushButton#TfBtn {
    padding: 4px 10px;
    border-radius: 4px;
    color: $MUTED$;
    font-weight: 600;
}
QPushButton#TfBtn:hover { color: $TEXT$; background: $HOVER$; }
QPushButton#TfBtn:checked { color: $ACCENT$; background: $ACTIVE_BG$; }

QPushButton#PlayBtn {
    background: $ACCENT$;
    color: #ffffff;
    font-weight: 600;
    padding: 6px 16px;
    border-radius: 4px;
}
QPushButton#PlayBtn:hover { background: $ACCENT_HOVER$; }

QPushButton#ToolBtn {
    padding: 0px;
    border-radius: 6px;
    color: $MUTED$;
    font-size: 15px;
}
QPushButton#ToolBtn:hover { background: $HOVER$; color: $TEXT$; }
QPushButton#ToolBtn:checked { background: $ACTIVE_BG$; color: $ACCENT$; }

QPushButton#MenuBtn {
    color: $MUTED$;
    font-weight: 600;
    padding: 4px 8px;
}
QPushButton#MenuBtn:hover { color: $TEXT$; background: $HOVER$; }

QPushButton#ThemeBtn {
    border: 1px solid $BORDER$;
    border-radius: 4px;
    padding: 4px 10px;
    color: $TEXT$;
}
QPushButton#ThemeBtn:hover { background: $HOVER$; }

QSlider::groove:horizontal { height: 3px; background: $BORDER$; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $ACCENT$; border-radius: 2px; }
QSlider::handle:horizontal {
    background: $ACCENT$; width: 12px; height: 12px; margin: -5px 0; border-radius: 6px;
}

QCheckBox { color: $MUTED$; spacing: 5px; }
QCheckBox::indicator {
    width: 14px; height: 14px; border: 1px solid $BORDER$; border-radius: 3px;
    background: $PANEL2$;
}
QCheckBox::indicator:checked { background: $ACCENT$; border-color: $ACCENT$; }

QComboBox {
    background: $PANEL2$; border: 1px solid $BORDER$; border-radius: 4px;
    padding: 4px 8px; color: $TEXT$;
}
QComboBox QAbstractItemView {
    background: $PANEL$; border: 1px solid $BORDER$;
    selection-background-color: $ACTIVE_BG$;
}

QLineEdit {
    background: $PANEL2$; border: 1px solid $BORDER$; border-radius: 4px;
    padding: 6px; color: $TEXT$;
}
QDialog { background: $PANEL$; }
QMenuBar { background: $PANEL$; color: $TEXT$; }
QMenuBar::item { padding: 4px 10px; background: transparent; }
QMenuBar::item:selected { background: $HOVER$; }
QMenu { background: $PANEL$; border: 1px solid $BORDER$; color: $TEXT$; }
QMenu::item { padding: 6px 24px; }
QMenu::item:selected { background: $ACTIVE_BG$; }

QMessageBox, QProgressDialog { background: $PANEL$; }
QProgressBar {
    background: $PANEL2$; border: 1px solid $BORDER$; border-radius: 4px;
    text-align: center; color: $TEXT$;
}
QProgressBar::chunk { background: $ACCENT$; border-radius: 3px; }
QToolTip { background: $PANEL2$; color: $TEXT$; border: 1px solid $BORDER$; }
"""


def build_qss(p) -> str:
    qss = _QSS
    for key, val in p.items():
        if isinstance(val, str):
            qss = qss.replace(f"${key.upper()}$", val)
    return qss
