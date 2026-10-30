"""图表视图：基于 PySide6 + pyqtgraph，实现 K 线绘制、回放渲染、绘图交互、
主题化外观（深/浅色）、十字光标与图例浮层。"""
import os
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")
import time
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

from config import VISIBLE_DEFAULT
from drawings import Drawing
from theme import get_palette

pg.setConfigOptions(antialias=True)


def _fmt_time(ts_sec: float) -> str:
    t = time.localtime(ts_sec)
    return time.strftime("%m-%d %H:%M", t)


class TimeAxisItem(pg.AxisItem):
    """X 轴：将 K 线索引映射为时间标签。"""

    def __init__(self, orientation="bottom", get_ts=None, **kwargs):
        super().__init__(orientation, **kwargs)
        self._get_ts = get_ts

    def tickStrings(self, values, scale, spacing):
        ts = self._get_ts()
        if ts is None:
            return ["" for _ in values]
        out = []
        for v in values:
            i = int(round(v))
            if 0 <= i < len(ts):
                out.append(_fmt_time(ts[i] / 1000.0))
            else:
                out.append("")
        return out


class CandlestickItem(pg.GraphicsObject):
    """蜡烛图 item：把窗口内 K 线一次性绘制为 QPicture，性能良好。"""

    def __init__(self, up_color, down_color):
        super().__init__()
        self.up = up_color
        self.down = down_color
        self.data = []
        self._width = 0.72
        self.picture = QtGui.QPicture()

    def setData(self, data):
        self.data = data
        self._generate()
        self.informViewBoundsChanged()
        self.update()

    def _generate(self):
        pic = QtGui.QPicture()
        p = QtGui.QPainter(pic)
        w = self._width
        for (x, o, h, l, c) in self.data:
            color = self.up if c >= o else self.down
            p.setPen(pg.mkPen(color))
            p.setBrush(pg.mkBrush(color))
            p.drawLine(QtCore.QPointF(x, l), QtCore.QPointF(x, h))
            top = min(o, c)
            p.drawRect(QtCore.QRectF(x - w / 2.0, top, w, max(abs(o - c), 1e-9)))
        p.end()
        self.picture = pic

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())


class FillRectItem(pg.GraphicsObject):
    """半透明填充矩形（无边框）。用于矩形框绘图工具。

    以数据坐标 (x1,y1)-(x2,y2) 定义，填充色含 alpha，无描边。
    """

    def __init__(self, x1, y1, x2, y2, color):
        super().__init__()
        self._rect = QtCore.QRectF(
            QtCore.QPointF(min(x1, x2), min(y1, y2)),
            QtCore.QPointF(max(x1, x2), max(y1, y2)))
        self._color = color
        self._pic = QtGui.QPicture()
        self._build()

    def _build(self):
        p = QtGui.QPainter(self._pic)
        c = pg.mkColor(self._color)
        c.setAlphaF(0.40)          # 40% 透明度的红色填充
        p.setPen(QtCore.Qt.NoPen)  # 无边框
        p.setBrush(pg.mkBrush(c))
        p.drawRect(self._rect)
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self._pic)

    def boundingRect(self):
        return self._rect


class ChartView(QtWidgets.QWidget):
    follow_changed = QtCore.Signal(bool)   # 用户手动缩放/平移后自动关闭跟随

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._palette = get_palette("dark")
        self.ts = None
        self.o = self.h = self.l = self.c = self.v = None
        self.n = 0
        self.ema = None
        self.visible_count = VISIBLE_DEFAULT
        self.follow = True
        self.tool = "cursor"
        self._pending = None
        self._current_idx = 0
        self._draw_items = []
        self._init_ui()

    # ---------- UI ----------
    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.plot = pg.PlotWidget(
            axisItems={"bottom": TimeAxisItem(get_ts=self._get_ts, orientation="bottom")})
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        # 网格线：X/Y 双向，alpha 适度，主题切换时同步颜色
        self.plot.showGrid(x=True, y=True, alpha=0.18)

        self.candle_item = CandlestickItem(self._palette["up"], self._palette["down"])
        self.candle_item.setZValue(10)
        self.plot.addItem(self.candle_item)
        self.ema_item = pg.PlotDataItem(pen=pg.mkPen(self._palette["ema"], width=2))
        self.ema_item.setZValue(20)
        self.plot.addItem(self.ema_item)

        self._preview = pg.PlotDataItem(
            pen=pg.mkPen(self._palette["muted"], width=1, style=QtCore.Qt.DashLine))
        self.plot.addItem(self._preview)

        # 十字光标
        ch_pen = pg.mkPen(self._palette["muted"], width=1, style=QtCore.Qt.DotLine)
        self._ch_v = pg.InfiniteLine(angle=90, movable=False, pen=ch_pen)
        self._ch_h = pg.InfiniteLine(angle=0, movable=False, pen=ch_pen)
        self.plot.addItem(self._ch_v, ignoreBounds=True)
        self.plot.addItem(self._ch_h, ignoreBounds=True)
        self._ch_v.hide()
        self._ch_h.hide()

        # 鼠标跟随价格标签（贴在 Y 轴上，随光标上下移动）
        self.price_tag = pg.TextItem(color=self._palette["text"], anchor=(0, 0.5))
        self.price_tag.setZValue(100)
        self.price_tag.hide()
        self.plot.addItem(self.price_tag, ignoreBounds=True)

        layout.addWidget(self.plot)

        # 图表左上角图例（TradingView 风格）
        self.legend = QtWidgets.QLabel(self)
        self.legend.setObjectName("Legend")
        self.legend.setTextFormat(QtCore.Qt.RichText)
        self.legend.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.legend.move(14, 10)
        self.legend.raise_()

        self.plot.scene().sigMouseClicked.connect(self._on_click)
        self.plot.scene().sigMouseMoved.connect(self._on_move)

        # 鼠标移出图表时隐藏光标与价格标签
        self._viewport = self.plot.getPlotItem().getViewBox()
        self._viewport.sigRangeChangedManually.connect(self._on_user_zoom)

    def leaveEvent(self, event):
        self._on_leave(event)
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "legend"):
            self.legend.raise_()

    def _get_ts(self):
        return self.ts

    # ---------- 主题 ----------
    def apply_theme(self, p):
        self._palette = p
        self.plot.setBackground(p["chart_bg"])
        for name in ("left", "bottom"):
            ax = self.plot.getAxis(name)
            ax.setPen(pg.mkPen(p["grid"]))
            if hasattr(ax, "setTextPen"):
                ax.setTextPen(pg.mkPen(p["muted"]))
        self.candle_item.up = p["up"]
        self.candle_item.down = p["down"]
        self.ema_item.setPen(pg.mkPen(p["ema"], width=2))
        self._preview.setPen(pg.mkPen(p["muted"], width=1, style=QtCore.Qt.DashLine))
        for ln in (self._ch_v, self._ch_h):
            ln.setPen(pg.mkPen(p["muted"], width=1, style=QtCore.Qt.DotLine))
        self.price_tag.setColor(p["text"])
        self.render(self._current_idx)

    def set_legend_text(self, html: str):
        self.legend.setText(html)
        self.legend.adjustSize()
        self.legend.raise_()

    # ---------- 数据 ----------
    def set_data(self, ts, o, h, l, c, v, ema):
        self.ts, self.o, self.h, self.l, self.c, self.v = ts, o, h, l, c, v
        self.n = len(ts)
        self.ema = ema

    # ---------- 渲染 ----------
    def render(self, idx):
        if self.n == 0 or self.ts is None:
            self.candle_item.setData([])
            self.ema_item.setData([], [])
            return
        idx = int(min(max(idx, 0), self.n - 1))
        self._current_idx = idx
        vc = self.visible_count
        start = max(0, idx - vc + 1)
        end = idx + 1
        xs = np.arange(start, end)
        win = [(int(x), self.o[x], self.h[x], self.l[x], self.c[x])
               for x in range(start, end)]
        self.candle_item.setData(win)
        if self.ema is not None:
            self.ema_item.setData(xs, self.ema[start:end])
        else:
            self.ema_item.setData([], [])
        # 智能跟随：保持用户当前缩放级别，仅当光标接近右边界时平移窗口；
        # 绝不触碰 Y 轴，用户对价格轴的缩放始终被保留。
        if self.follow:
            self._smart_follow_x(end)
        self._render_drawings(idx, start, end)

    def _smart_follow_x(self, end):
        """保持当前 X 轴缩放宽度不变，仅平移到能容纳最新 K 线的位置。

        - 首次渲染（X 范围仍是 pyqtgraph 默认的 [0,1] 或异常窄）时按可见根数设定初始范围。
        - 若用户已缩放，保持该宽度，只做平移。
        """
        vb = self.plot.getViewBox()
        xr, _ = vb.viewRange()
        cur_width = xr[1] - xr[0]
        # 尚未初始化有效视图（默认 [0,1] 宽度 1，或非有限值）
        if (not np.isfinite(cur_width)) or cur_width <= 1.5:
            self.plot.setXRange(end - self.visible_count + 1, end, padding=0.02)
            return
        # 用户手动的"当前缩放级别"：窗口宽度就是用户的缩放级别，保持它
        if end > xr[1] - 0.5:
            # 最新 K 线即将超出右边界 → 平移窗口，宽度不变
            new_right = end + max(0.5, cur_width * 0.02)
            new_left = new_right - cur_width
            vb.setXRange(new_left, new_right, padding=0)

    def _render_drawings(self, idx, start, end):
        for it in self._draw_items:
            self.plot.removeItem(it)
        self._draw_items = []
        if self.ts is None:
            return
        for d in self.manager.drawings:
            if d.dtype == "hline":
                line = pg.InfiniteLine(
                    pos=d.price, angle=0,
                    pen=pg.mkPen(d.color, width=1.3), movable=False)
                line.setZValue(5)
                self.plot.addItem(line)
                self._draw_items.append(line)
                ti = pg.TextItem(text=f"{d.price:,.1f}", color=d.color, anchor=(0, 1))
                ti.setZValue(30)
                ti.setPos(end, d.price)
                self.plot.addItem(ti)
                self._draw_items.append(ti)
            elif d.dtype == "rect":
                i1o = self._ts_to_idx(d.t1)
                i2o = self._ts_to_idx(d.t2)
                if max(i1o, i2o) > idx:
                    continue
                i1 = self._clamp_idx(i1o, start, end)
                i2 = self._clamp_idx(i2o, start, end)
                # 半透明红色填充矩形，无边框，置于蜡烛后方
                item = FillRectItem(i1, d.p1, i2, d.p2, "#ef5350")
                item.setZValue(0)
                self.plot.addItem(item)
                self._draw_items.append(item)
            elif d.dtype == "fib":
                i1o = self._ts_to_idx(d.t1)
                i2o = self._ts_to_idx(d.t2)
                if max(i1o, i2o) > idx:
                    continue
                i1 = self._clamp_idx(i1o, start, end)
                i2 = self._clamp_idx(i2o, start, end)
                for lvl in d.levels:
                    price = d.p1 + (d.p2 - d.p1) * lvl
                    # 横向参考线（InfiniteLine 横跨可见区域，可靠渲染）
                    line = pg.InfiniteLine(
                        pos=price, angle=0,
                        pen=pg.mkPen(d.color, width=1.1, style=QtCore.Qt.DashLine),
                        movable=False)
                    line.setZValue(5)
                    self.plot.addItem(line)
                    self._draw_items.append(line)
                    # 数字标签（百分比 + 价格）
                    ti = pg.TextItem(
                        text=f"{lvl * 100:.1f}%  {price:,.1f}",
                        color=d.color, anchor=(1, 0.5))
                    ti.setZValue(30)
                    ti.setPos(i1, price)
                    self.plot.addItem(ti)
                    self._draw_items.append(ti)

    # ---------- 工具 / 交互 ----------
    def set_tool(self, tool: str):
        self.tool = tool
        self._pending = None
        self._clear_preview()

    def set_visible_count(self, n: int):
        self.visible_count = n

    def set_follow(self, follow: bool):
        self.follow = follow

    def _ts_to_idx(self, ts):
        if self.n == 0:
            return 0
        i = int(np.searchsorted(self.ts, ts))
        return int(min(max(i, 0), self.n - 1))

    def _clamp_idx(self, i, start, end):
        return int(min(max(i, start), end))

    def _clear_preview(self):
        self._preview.setData([], [])

    def _data_pos(self, evt):
        vb = self.plot.getViewBox()
        pos = vb.mapSceneToView(evt)
        return pos.x(), pos.y()

    def _on_click(self, evt):
        if evt.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        if self.tool == "cursor" or self.n == 0:
            return
        xf, yf = self._data_pos(evt.scenePos())
        idxc = int(min(max(round(xf), 0), self.n - 1))
        ts = int(self.ts[idxc])
        price = float(yf)

        if self.tool == "hline":
            self.manager.add(Drawing("hline", price=price,
                                     color=self._palette["hline"]))
            self.render(self._current_idx)
        elif self.tool in ("rect", "fib"):
            if self._pending is None:
                self._pending = {"t1": ts, "p1": price}
            else:
                t1, p1 = self._pending["t1"], self._pending["p1"]
                if self.tool == "rect":
                    self.manager.add(Drawing(
                        "rect", t1=t1, p1=p1, t2=ts, p2=price,
                        color=self._palette["rect"]))
                else:
                    self.manager.add(Drawing(
                        "fib", t1=t1, p1=p1, t2=ts, p2=price,
                        levels=list(self.manager.default_fib_levels),
                        color=self._palette["fib"]))
                self._pending = None
                self._clear_preview()
                self.render(self._current_idx)
        elif self.tool == "delete":
            self._delete_nearest(xf, yf)

    def _on_move(self, evt):
        if self.n == 0:
            return
        xf, yf = self._data_pos(evt)
        self._ch_v.setPos(xf)
        self._ch_h.setPos(yf)
        self._ch_v.show()
        self._ch_h.show()
        # 价格标签实时显示在 Y 轴附近
        self.price_tag.setText(f"{yf:,.1f}")
        xr, yr = self.plot.getViewBox().viewRange()
        tag_x = xr[0] + (xr[1] - xr[0]) * 0.03
        self.price_tag.setPos(tag_x, yf)
        self.price_tag.show()
        if self._pending is None:
            return
        i1 = self._clamp_idx(self._ts_to_idx(self._pending["t1"]), 0, self.n - 1)
        i2 = int(min(max(round(xf), 0), self.n - 1))
        p1 = self._pending["p1"]
        xs = [i1, i2, i2, i1, i1]
        ys = [p1, p1, yf, yf, p1]
        self._preview.setData(xs, ys)

    def _on_leave(self, evt):
        """鼠标离开图表时隐藏十字光标与价格标签。"""
        self._ch_v.hide()
        self._ch_h.hide()
        self.price_tag.hide()

    def _on_user_zoom(self, *args):
        """用户手动滚轮缩放或拖拽平移时，关闭自动跟随，尊重用户视图。"""
        self.follow = False
        self.follow_changed.emit(False)

    def _delete_nearest(self, xf, yf):
        xr, yr = self.plot.getViewBox().viewRange()
        span_x = max(xr[1] - xr[0], 1e-9)
        span_y = max(yr[1] - yr[0], 1e-9)
        best, best_d = None, 1e18
        for d in self.manager.drawings:
            if d.dtype == "hline":
                dist = abs(yf - d.price) / span_y
            else:
                i1 = self._ts_to_idx(d.t1)
                i2 = self._ts_to_idx(d.t2)
                y1 = min(d.p1, d.p2)
                y2 = max(d.p1, d.p2)
                ex = max(i1 - xf, 0.0, xf - i2)
                ey = max(y1 - yf, 0.0, yf - y2)
                dist = ((ex / span_x) ** 2 + (ey / span_y) ** 2) ** 0.5
            if dist < best_d:
                best_d, best = dist, d
        if best is not None and best_d < 0.05:
            self.manager.remove(best)
            self.render(self._current_idx)
