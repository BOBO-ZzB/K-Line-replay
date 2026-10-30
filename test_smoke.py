"""无界面冒烟测试：验证模块导入、数据装载与核心交互逻辑无运行时错误。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

from PySide6 import QtWidgets
from main_window import MainWindow
from drawings import Drawing
import config


def main():
    app = QtWidgets.QApplication([])
    w = MainWindow()
    w.show()

    print("[smoke] default tf:", w.current_tf, "n =", w.n)
    assert w.n > 0, "默认周期应已装载数据"

    w.engine.step_forward()
    w.engine.step_forward()
    w.engine.step_back()
    print("[smoke] engine idx after steps:", w.engine.idx)

    # 添加水平线绘图
    ts = int(w.ts[10])
    price = float(w.c[10])
    w.manager.add(Drawing("hline", price=price, color="#d81b60"))
    w.chart.set_tool("hline")
    w.chart.render(w.engine.idx)

    # 切换周期，位置应基于时间戳保持一致
    w.tf_buttons["1D"].click()
    print("[smoke] after switch 1D -> n =", w.n, "current_ts =", w.current_ts)
    assert w.n > 0

    # 主题切换（深/浅）
    w._apply_theme("light")
    w._apply_theme("dark")
    print("[smoke] theme toggle OK")

    # 矩形 / 斐波那契
    w.manager.add(Drawing("rect", t1=int(w.ts[5]), p1=float(w.c[5]),
                          t2=int(w.ts[20]), p2=float(w.c[20]), color="#1565c0"))
    w.manager.add(Drawing("fib", t1=int(w.ts[5]), p1=float(w.c[5]),
                          t2=int(w.ts[20]), p2=float(w.c[20]),
                          levels=[0.0, 0.5, 1.0], color="#6a1b9a"))
    w.chart.render(w.engine.idx)

    # 调速 / 显示数量
    w.engine.set_cps(20)
    w.chart.set_visible_count(500)
    w.chart.render(w.engine.idx)

    print("[smoke] SMOKE TEST OK")

    # 清理测试产生的本地文件，保持交付干净
    for p in (config.DB_PATH, config.DRAWINGS_PATH):
        try:
            os.remove(p)
        except OSError:
            pass


if __name__ == "__main__":
    main()
