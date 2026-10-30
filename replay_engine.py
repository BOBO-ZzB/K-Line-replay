"""回放引擎：以定时器驱动 K 线逐根推进，支持播放/暂停/单步/调速。"""
from PySide6 import QtCore


class ReplayEngine(QtCore.QObject):
    progress = QtCore.Signal(int, int)          # 当前索引, 总数
    playing_changed = QtCore.Signal(bool)

    def __init__(self):
        super().__init__()
        self._total = 0
        self._idx = 0
        self._cps = 5            # 每秒推进的 K 线根数
        self._playing = False
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_timeout)

    # ---------- 属性 ----------
    @property
    def idx(self):
        return self._idx

    @property
    def total(self):
        return self._total

    @property
    def playing(self):
        return self._playing

    @property
    def cps(self):
        return self._cps

    # ---------- 数据装载 ----------
    def load(self, total: int, idx: int = 0):
        self._total = max(0, total)
        self._idx = int(min(max(idx, 0), self._total - 1)) if self._total else 0
        self._emit()

    # ---------- 播放控制 ----------
    def play(self):
        if self._playing or self._total == 0:
            return
        if self._idx >= self._total - 1:
            self._idx = 0  # 已到末尾则从头重放
        self._playing = True
        self._restart_timer()
        self.playing_changed.emit(True)

    def pause(self):
        if not self._playing:
            return
        self._playing = False
        self._timer.stop()
        self.playing_changed.emit(False)

    def toggle(self):
        self.play() if not self._playing else self.pause()

    def _restart_timer(self):
        self._timer.stop()
        interval = max(1, int(1000 / self._cps))
        self._timer.start(interval)

    def set_cps(self, v: int):
        self._cps = max(1, int(v))
        if self._playing:
            self._restart_timer()

    # ---------- 单步 ----------
    def step_forward(self):
        if self._idx < self._total - 1:
            self._idx += 1
            self._emit()

    def step_back(self):
        if self._idx > 0:
            self._idx -= 1
            self._emit()

    def seek(self, idx: int):
        self._idx = int(min(max(idx, 0), self._total - 1)) if self._total else 0
        self._emit()

    # ---------- 内部 ----------
    def _on_timeout(self):
        if self._idx < self._total - 1:
            self._idx += 1
            self._emit()
        else:
            self.pause()

    def _emit(self):
        self.progress.emit(self._idx, self._total)
