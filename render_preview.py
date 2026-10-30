"""离屏渲染预览：生成深色/浅色两张界面截图，便于目视检查。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

from PySide6 import QtWidgets
from PySide6.QtTest import QTest
from main_window import MainWindow


def main():
    app = QtWidgets.QApplication([])
    w = MainWindow()
    w.resize(1400, 860)
    w.show()
    QTest.qWait(400)

    # 跳到数据中部并加一个斐波那契，画面更接近真实使用
    w.engine.seek(max(0, w.n // 2))
    QTest.qWait(200)

    for theme in ("dark", "light"):
        w._apply_theme(theme)
        QTest.qWait(350)
        pm = w.grab()
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"preview_{theme}.png")
        pm.save(path)
        print("saved", path, pm.width(), "x", pm.height())


if __name__ == "__main__":
    main()
