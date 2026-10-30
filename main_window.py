"""主窗口：TradingView 风格 UI，集成回放、周期切换、绘图、主题与快捷键。"""
import time
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui

from config import (
    SYMBOL, TIMEFRAME_ORDER, EMA_PERIOD, HISTORY_YEARS,
    DEFAULT_CPS, VISIBLE_MIN, VISIBLE_MAX, VISIBLE_DEFAULT,
    CPS_MIN, CPS_MAX, DEFAULT_FIB_LEVELS,
)
from db import Database
from fetcher import fetch_okx, generate_sample
from indicators import ema
from drawings import DrawingManager
from chart_view import ChartView
from replay_engine import ReplayEngine
from theme import get_palette, build_qss


class DataWorker(QtCore.QThread):
    """后台数据任务：mode='download' 抓真实数据，mode='sample' 生成示例数据。"""
    progress = QtCore.Signal(str, int, int)   # tf, done, total
    finished = QtCore.Signal(bool, str)        # ok, message

    def __init__(self, db_path, mode, years, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.mode = mode
        self.years = years

    def run(self):
        # 关键：QThread 内使用独立的数据库连接，避免 SQLite 跨线程报错
        db = Database(self.db_path)
        try:
            for tf in TIMEFRAME_ORDER:
                if self.mode == "download":
                    rows = fetch_okx(tf, years=self.years,
                                    progress_cb=lambda d, t: self.progress.emit(tf, d, t))
                else:
                    rows = generate_sample(tf, years=self.years)
                db.save_batch(tf, rows)
                self.progress.emit(tf, 1, 1)
            self.finished.emit(True, "数据准备完成")
        except Exception as e:  # 网络失败等
            self.finished.emit(False, f"数据获取失败：{e}")
        finally:
            db.close()


class FibDialog(QtWidgets.QDialog):
    def __init__(self, levels, parent=None):
        super().__init__(parent)
        self.setWindowTitle("斐波那契档位设置")
        self.resize(340, 130)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("输入回撤档位（0~1，逗号分隔），可自定义："))
        self.edit = QtWidgets.QLineEdit(", ".join(f"{x:g}" for x in levels))
        layout.addWidget(self.edit)
        btns = QtWidgets.QHBoxLayout()
        ok = QtWidgets.QPushButton("确定")
        cancel = QtWidgets.QPushButton("取消")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        layout.addLayout(btns)

    def get_levels(self):
        parts = [p.strip() for p in self.edit.text().split(",") if p.strip()]
        out = []
        for p in parts:
            try:
                out.append(float(p))
            except ValueError:
                pass
        return out or list(DEFAULT_FIB_LEVELS)


class MainWindow(QtWidgets.QMainWindow):
    SHORTCUTS = [
        ("空格", "播放 / 暂停"),
        ("P / S", "播放 / 暂停"),
        ("← / →", "上一根 / 下一根"),
        ("↑ / ↓", "加速 / 减速"),
        ("Home / End", "跳到开头 / 结尾"),
        ("T", "切换深色 / 浅色主题"),
        ("Esc", "回到光标（取消绘制）"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Kline Replay · {SYMBOL}")
        self.resize(1360, 840)
        self.setMinimumSize(1000, 620)

        self.settings = QtCore.QSettings("KlineReplay", "UI")
        self.theme_name = self.settings.value("theme", "dark")
        self.palette = get_palette(self.theme_name)

        self.db = Database()
        self.manager = DrawingManager()
        self.engine = ReplayEngine()

        self.current_tf = "1H"
        self.current_ts = None
        self.ts = self.o = self.h = self.l = self.c = self.v = None
        self.n = 0
        self._progress = None

        self._build_ui()
        self._apply_theme(self.theme_name)
        self._connect_signals()
        self._no_focus_controls()
        self._setup_shortcuts()
        self._load_timeframe(self.current_tf, keep_position=False)

    # ================= UI 构建 =================
    def _build_ui(self):
        root = QtWidgets.QWidget()
        root.setObjectName("Root")
        v = QtWidgets.QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._build_topbar())
        v.addWidget(self._build_body(), 1)
        v.addWidget(self._build_bottombar())
        self.setCentralWidget(root)

    def _nav_button(self, text, tip=""):
        b = QtWidgets.QPushButton(text)
        b.setFixedSize(34, 28)
        b.setToolTip(tip)
        b.setCursor(QtCore.Qt.PointingHandCursor)
        b.setFocusPolicy(QtCore.Qt.NoFocus)
        return b

    def _build_topbar(self):
        bar = QtWidgets.QWidget()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(52)
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(6)

        # 数据菜单
        self.menu_btn = QtWidgets.QPushButton("数据 ▾")
        self.menu_btn.setObjectName("MenuBtn")
        self.menu_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.menu_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        menu = QtWidgets.QMenu(self)
        menu.addAction("从 OKX 下载真实数据", self._download)
        menu.addAction("生成示例数据（离线体验）", self._generate_sample)
        menu.addSeparator()
        menu.addAction("清空数据库", self._clear_db)
        self.menu_btn.setMenu(menu)
        h.addWidget(self.menu_btn)

        h.addSpacing(8)

        # 交易对
        sym_w = QtWidgets.QWidget()
        sv = QtWidgets.QVBoxLayout(sym_w)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)
        lbl1 = QtWidgets.QLabel(SYMBOL.replace("-", ""))
        lbl1.setObjectName("Symbol")
        lbl2 = QtWidgets.QLabel("OKX · 现货")
        lbl2.setObjectName("SymbolExchange")
        sv.addWidget(lbl1)
        sv.addWidget(lbl2)
        h.addWidget(sym_w)

        h.addSpacing(14)

        # 周期按钮组
        self.tf_group = QtWidgets.QButtonGroup(self)
        self.tf_group.setExclusive(True)
        self.tf_buttons = {}
        for tf in TIMEFRAME_ORDER:
            b = QtWidgets.QPushButton(tf)
            b.setObjectName("TfBtn")
            b.setCheckable(True)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setFocusPolicy(QtCore.Qt.NoFocus)
            self.tf_group.addButton(b)
            self.tf_buttons[tf] = b
            h.addWidget(b)
        self.tf_buttons[self.current_tf].setChecked(True)

        h.addSpacing(14)

        # 回放控制
        self.btn_back = self._nav_button("⏮", "上一根 (←)")
        self.btn_play = QtWidgets.QPushButton("▶ 播放")
        self.btn_play.setObjectName("PlayBtn")
        self.btn_play.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_play.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_play.setToolTip("播放 / 暂停 (空格)")
        self.btn_fwd = self._nav_button("⏭", "下一根 (→)")
        h.addWidget(self.btn_back)
        h.addWidget(self.btn_play)
        h.addWidget(self.btn_fwd)

        h.addSpacing(10)

        # 速度
        sp_lbl = QtWidgets.QLabel("速度")
        sp_lbl.setObjectName("Muted")
        h.addWidget(sp_lbl)
        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.speed_slider.setRange(CPS_MIN, CPS_MAX)
        self.speed_slider.setValue(DEFAULT_CPS)
        self.speed_slider.setFixedWidth(110)
        self.speed_slider.setFocusPolicy(QtCore.Qt.NoFocus)
        h.addWidget(self.speed_slider)
        self.speed_label = QtWidgets.QLabel(f"{DEFAULT_CPS} 根/秒")
        self.speed_label.setObjectName("Muted")
        h.addWidget(self.speed_label)

        h.addStretch(1)

        # 帮助 + 主题
        self.help_btn = QtWidgets.QPushButton("⌨")
        self.help_btn.setObjectName("ThemeBtn")
        self.help_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.help_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.help_btn.setToolTip("快捷键帮助")
        self.help_btn.clicked.connect(self._show_shortcuts)
        h.addWidget(self.help_btn)

        self.theme_btn = QtWidgets.QPushButton("☀ 亮色")
        self.theme_btn.setObjectName("ThemeBtn")
        self.theme_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.theme_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.theme_btn.setToolTip("切换主题 (T)")
        self.theme_btn.clicked.connect(self._toggle_theme)
        h.addWidget(self.theme_btn)

        return bar

    def _build_body(self):
        body = QtWidgets.QWidget()
        bh = QtWidgets.QHBoxLayout(body)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)

        # 左侧工具栏
        rail = QtWidgets.QWidget()
        rail.setObjectName("ToolRail")
        rail.setFixedWidth(48)
        rv = QtWidgets.QVBoxLayout(rail)
        rv.setContentsMargins(6, 10, 6, 10)
        rv.setSpacing(6)

        self.tool_group = QtWidgets.QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons = {}
        tools = [
            ("cursor", "↖", "光标 / 选择 (Esc)"),
            ("hline", "—", "水平线"),
            ("rect", "▭", "矩形框"),
            ("fib", "F", "斐波那契回撤"),
            ("delete", "✕", "删除图形（点击图形）"),
        ]
        for tool, text, tip in tools:
            b = QtWidgets.QPushButton(text)
            b.setObjectName("ToolBtn")
            b.setCheckable(True)
            b.setFixedSize(36, 36)
            b.setToolTip(tip)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setFocusPolicy(QtCore.Qt.NoFocus)
            b.setProperty("tool", tool)
            self.tool_group.addButton(b)
            self.tool_buttons[tool] = b
            rv.addWidget(b)
        rv.addSpacing(8)

        self.btn_clear = QtWidgets.QPushButton("⌫")
        self.btn_clear.setObjectName("ToolBtn")
        self.btn_clear.setFixedSize(36, 36)
        self.btn_clear.setToolTip("清空全部绘图")
        self.btn_clear.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_clear.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_clear.clicked.connect(self._clear_drawings)
        rv.addWidget(self.btn_clear)

        self.btn_fib_set = QtWidgets.QPushButton("⚙")
        self.btn_fib_set.setObjectName("ToolBtn")
        self.btn_fib_set.setFixedSize(36, 36)
        self.btn_fib_set.setToolTip("斐波那契档位设置")
        self.btn_fib_set.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_fib_set.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_fib_set.clicked.connect(self._fib_settings)
        rv.addWidget(self.btn_fib_set)
        rv.addStretch(1)

        bh.addWidget(rail)

        self.chart = ChartView(self.manager)
        bh.addWidget(self.chart, 1)
        return body

    def _build_bottombar(self):
        bar = QtWidgets.QWidget()
        bar.setObjectName("BottomBar")
        bar.setFixedHeight(30)
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(14, 0, 14, 0)
        h.setSpacing(10)

        self.info_label = QtWidgets.QLabel("")
        self.info_label.setObjectName("BottomText")
        h.addWidget(self.info_label)
        h.addStretch(1)

        self.follow_chk = QtWidgets.QCheckBox("跟随")
        self.follow_chk.setChecked(True)
        self.follow_chk.setFocusPolicy(QtCore.Qt.NoFocus)
        h.addWidget(self.follow_chk)

        vis_lbl = QtWidgets.QLabel("显示")
        vis_lbl.setObjectName("Muted")
        h.addWidget(vis_lbl)
        self.vis_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.vis_slider.setRange(VISIBLE_MIN, VISIBLE_MAX)
        self.vis_slider.setValue(VISIBLE_DEFAULT)
        self.vis_slider.setFixedWidth(100)
        self.vis_slider.setFocusPolicy(QtCore.Qt.NoFocus)
        h.addWidget(self.vis_slider)
        self.vis_label = QtWidgets.QLabel(f"{VISIBLE_DEFAULT}")
        self.vis_label.setObjectName("BottomText")
        h.addWidget(self.vis_label)

        self.progress_label = QtWidgets.QLabel("0 / 0")
        self.progress_label.setObjectName("BottomText")
        h.addWidget(self.progress_label)
        return bar

    # ================= 主题 =================
    def _apply_theme(self, name):
        p = get_palette(name)
        self.palette = p
        self.theme_name = p["name"]
        self.setStyleSheet(build_qss(p))
        if hasattr(self, "chart"):
            self.chart.apply_theme(p)
        if hasattr(self, "theme_btn"):
            self.theme_btn.setText("☀ 亮色" if p["is_dark"] else "🌙 深色")
        self.settings.setValue("theme", p["name"])
        self._update_status(self.engine.idx)

    def _toggle_theme(self):
        self._apply_theme("light" if self.theme_name == "dark" else "dark")

    # ================= 信号 =================
    def _connect_signals(self):
        self.engine.progress.connect(self._on_progress)
        self.engine.playing_changed.connect(self._on_playing_changed)
        self.btn_play.clicked.connect(self.engine.toggle)
        self.btn_back.clicked.connect(self.engine.step_back)
        self.btn_fwd.clicked.connect(self.engine.step_forward)
        self.tf_group.buttonClicked.connect(self._on_tf_button)
        self.tool_group.buttonClicked.connect(self._on_tool_button)
        self.speed_slider.valueChanged.connect(self._on_speed)
        self.vis_slider.valueChanged.connect(self._on_visible)
        self.follow_chk.toggled.connect(self.chart.set_follow)
        self.chart.follow_changed.connect(self.follow_chk.setChecked)
        self._set_tool("cursor")

    def _no_focus_controls(self):
        widgets = (self.findChildren(QtWidgets.QPushButton)
                   + self.findChildren(QtWidgets.QSlider))
        for w in widgets:
            w.setFocusPolicy(QtCore.Qt.NoFocus)

    def _setup_shortcuts(self):
        def sc(key, fn):
            s = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            s.setContext(QtCore.Qt.ApplicationShortcut)
            s.activated.connect(fn)
            return s

        sc("Space", self.engine.toggle)
        sc("P", self.engine.play)
        sc("S", self.engine.pause)
        sc("Left", self.engine.step_back)
        sc("Right", self.engine.step_forward)
        sc("Up", lambda: self._bump_speed(+5))
        sc("Down", lambda: self._bump_speed(-5))
        sc("Home", lambda: self.engine.seek(0))
        sc("End", lambda: self.engine.seek(self.n - 1))
        sc("T", self._toggle_theme)
        sc("Esc", lambda: self._set_tool("cursor"))

    def _bump_speed(self, delta):
        v = int(min(max(self.speed_slider.value() + delta, CPS_MIN), CPS_MAX))
        self.speed_slider.setValue(v)

    def _show_shortcuts(self):
        rows = "".join(
            f"<tr><td style='padding:3px 14px 3px 0;color:{self.palette['accent']};"
            f"font-weight:600'>{k}</td><td style='padding:3px 0'>{d}</td></tr>"
            for k, d in self.SHORTCUTS)
        QtWidgets.QMessageBox.information(
            self, "快捷键", f"<table>{rows}</table>")

    # ================= 数据 =================
    def _ensure_data(self, tf):
        arr = self.db.load(tf)
        if arr is None or arr["n"] == 0:
            rows = generate_sample(tf, years=1)
            self.db.save_batch(tf, rows)
            arr = self.db.load(tf)
        return arr

    def _load_timeframe(self, tf, keep_position=True):
        arr = self._ensure_data(tf)
        self.ts = arr["ts"]
        self.o, self.h, self.l, self.c, self.v = arr["o"], arr["h"], arr["l"], arr["c"], arr["v"]
        self.n = arr["n"]
        ema_arr = ema(self.c, EMA_PERIOD)
        self.chart.set_data(self.ts, self.o, self.h, self.l, self.c, self.v, ema_arr)

        if keep_position and self.current_ts is not None and self.n > 0:
            idx = int(min(max(np.searchsorted(self.ts, self.current_ts), 0), self.n - 1))
            self.current_ts = self.ts[idx]
        else:
            idx = 0
            self.current_ts = self.ts[0] if self.n > 0 else None
        self.engine.load(self.n, idx)

    def _on_tf_button(self, btn):
        tf = btn.text()
        if tf == self.current_tf and self.n > 0:
            return
        self.current_tf = tf
        self._load_timeframe(tf, keep_position=True)

    # ================= 回放回调 =================
    def _on_progress(self, idx, total):
        if self.n > 0:
            self.current_ts = int(self.ts[idx])
        self.chart.render(idx)
        self._update_status(idx)

    def _on_playing_changed(self, playing):
        self.btn_play.setText("⏸ 暂停" if playing else "▶ 播放")

    def _on_speed(self, v):
        self.engine.set_cps(v)
        self.speed_label.setText(f"{v} 根/秒")

    def _on_visible(self, v):
        self.chart.set_visible_count(v)
        self.vis_label.setText(str(v))
        self.chart.render(self.engine.idx)

    # ================= 绘图工具 =================
    def _on_tool_button(self, btn):
        self._set_tool(btn.property("tool"))

    def _set_tool(self, tool):
        self.chart.set_tool(tool)
        b = self.tool_buttons.get(tool)
        if b:
            b.setChecked(True)

    def _clear_drawings(self):
        self.manager.clear()
        self.chart.render(self.engine.idx)

    def _fib_settings(self):
        dlg = FibDialog(self.manager.default_fib_levels, self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.manager.default_fib_levels = dlg.get_levels()

    # ================= 数据任务 =================
    def _start_worker(self, mode):
        for tf in TIMEFRAME_ORDER:
            self.db.clear(tf)
        self.worker = DataWorker(self.db.path, mode, HISTORY_YEARS)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self._progress = QtWidgets.QProgressDialog("正在准备数据…", "取消", 0, 100, self)
        self._progress.setWindowModality(QtCore.Qt.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.show()
        self.worker.start()

    def _on_worker_progress(self, tf, done, total):
        if self._progress:
            self._progress.setLabelText(f"周期 {tf}")
            pct = max(1, min(100, int(100 * done / max(total, 1))))
            self._progress.setValue(pct)

    def _on_worker_finished(self, ok, msg):
        if self._progress:
            self._progress.close()
        if ok:
            self._load_timeframe(self.current_tf, keep_position=False)
            QtWidgets.QMessageBox.information(self, "完成", msg)
        else:
            QtWidgets.QMessageBox.warning(self, "失败", msg + "\n可改用「生成示例数据」离线体验。")
        self.worker = None

    def _download(self):
        self._start_worker("download")

    def _generate_sample(self):
        self._start_worker("sample")

    def _clear_db(self):
        r = QtWidgets.QMessageBox.question(self, "确认", "确定清空本地数据库？")
        if r == QtWidgets.QMessageBox.Yes:
            self.db.clear()
            self._load_timeframe(self.current_tf, keep_position=False)

    # ================= 状态 =================
    def _update_status(self, idx):
        p = self.palette
        if self.n == 0:
            self.info_label.setText("无数据")
            self.progress_label.setText("0 / 0")
            self.chart.set_legend_text("")
            return
        idx = int(min(max(idx, 0), self.n - 1))
        o, h, l, c, v = self.o[idx], self.h[idx], self.l[idx], self.c[idx], self.v[idx]
        chg = (c - o) / o * 100 if o else 0
        color = p["up"] if c >= o else p["down"]
        t = time.strftime("%Y-%m-%d %H:%M", time.localtime(self.ts[idx] / 1000.0))

        sym = SYMBOL.replace("-", "")
        legend = (
            f'<span style="color:{p["text"]};font-weight:700;font-size:14px">{sym}</span>'
            f' <span style="color:{p["muted"]}">{self.current_tf}</span>'
            f'&nbsp;&nbsp;<span style="color:{p["muted"]}">开</span>'
            f' <span style="color:{color}">{o:,.1f}</span>'
            f' <span style="color:{p["muted"]}">高</span>'
            f' <span style="color:{color}">{h:,.1f}</span>'
            f' <span style="color:{p["muted"]}">低</span>'
            f' <span style="color:{color}">{l:,.1f}</span>'
            f' <span style="color:{p["muted"]}">收</span>'
            f' <span style="color:{color}">{c:,.1f}</span>'
            f'&nbsp;&nbsp;<span style="color:{p["ema"]};font-weight:600">EMA 20</span>'
        )
        self.chart.set_legend_text(legend)

        sign = "+" if chg >= 0 else ""
        self.info_label.setText(
            f"{t}　<b style='color:{color}'>{sign}{chg:.2f}%</b>　量 {v:,.2f}")
        self.progress_label.setText(f"{idx + 1} / {self.n}")

    # ================= 快捷键（备用） =================
    def keyPressEvent(self, event):
        super().keyPressEvent(event)
