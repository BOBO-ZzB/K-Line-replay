"""绘图对象模型与持久化。

所有绘图均以「绝对时间戳 + 价格」存储，因此切换时间周期后仍能保持位置一致。
支持类型：
  - hline : 水平线（仅价格）
  - rect  : 矩形框（两个角点 ts1/p1, ts2/p2）
  - fib   : 斐波那契回撤（起止点 ts1/p1, ts2/p2 + 自定义档位）
"""
import json
import uuid
from config import DRAWINGS_PATH, DEFAULT_FIB_LEVELS, HLINE_COLOR, RECT_COLOR, FIB_COLOR


class Drawing:
    def __init__(self, dtype, **fields):
        self.id = fields.get("id") or uuid.uuid4().hex[:8]
        self.dtype = dtype
        self.fields = fields

    # 便捷属性
    @property
    def price(self):
        return self.fields.get("price")

    @property
    def t1(self):
        return self.fields.get("t1")

    @property
    def p1(self):
        return self.fields.get("p1")

    @property
    def t2(self):
        return self.fields.get("t2")

    @property
    def p2(self):
        return self.fields.get("p2")

    @property
    def levels(self):
        return self.fields.get("levels", DEFAULT_FIB_LEVELS)

    @property
    def color(self):
        return self.fields.get("color")

    def to_dict(self):
        d = {"id": self.id, "dtype": self.dtype}
        d.update(self.fields)
        return d

    @staticmethod
    def from_dict(d):
        dtype = d.pop("dtype")
        return Drawing(dtype, **d)


class DrawingManager:
    def __init__(self):
        self.drawings = []
        self.default_fib_levels = list(DEFAULT_FIB_LEVELS)
        self.load()

    def add(self, drawing: Drawing):
        self.drawings.append(drawing)
        self.save()

    def remove(self, drawing: Drawing):
        if drawing in self.drawings:
            self.drawings.remove(drawing)
            self.save()

    def clear(self):
        self.drawings.clear()
        self.save()

    def save(self):
        try:
            with open(DRAWINGS_PATH, "w", encoding="utf-8") as f:
                json.dump([d.to_dict() for d in self.drawings], f,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass

    def load(self):
        try:
            with open(DRAWINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.drawings = [Drawing.from_dict(d) for d in data]
        except (OSError, json.JSONDecodeError):
            self.drawings = []


def default_color(dtype: str) -> str:
    return {"hline": HLINE_COLOR, "rect": RECT_COLOR, "fib": FIB_COLOR}.get(dtype, "#333333")
