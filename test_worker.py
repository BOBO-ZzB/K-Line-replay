"""验证后台线程生成数据不再触发 SQLite 跨线程错误。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

import tempfile
from PySide6 import QtWidgets, QtCore
from db import Database
from main_window import DataWorker


def main():
    app = QtWidgets.QApplication([])
    path = os.path.join(tempfile.gettempdir(), "kline_worker_test.db")
    try:
        os.remove(path)
    except OSError:
        pass

    worker = DataWorker(path, "sample", 1)
    result = {}

    def on_finished(ok, msg):
        result["ok"], result["msg"] = ok, msg
        app.quit()

    worker.finished.connect(on_finished)
    worker.progress.connect(lambda tf, d, t: print("[worker] progress", tf))
    worker.start()
    QtCore.QTimer.singleShot(180000, app.quit)  # 安全超时
    app.exec()
    worker.wait()

    print("[worker] result:", result)
    db = Database(path)
    counts = {tf: db.count(tf) for tf in ["5m", "15m", "30m", "1H", "4H", "1D"]}
    db.close()
    print("[worker] counts:", counts)

    assert result.get("ok"), f"worker 失败: {result}"
    assert all(v > 0 for v in counts.values()), f"存在空周期: {counts}"
    print("[worker] WORKER TEST OK")


if __name__ == "__main__":
    main()
