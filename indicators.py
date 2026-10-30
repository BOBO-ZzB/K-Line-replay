"""技术指标计算（基于 numpy，便于大批量数据）。"""
import numpy as np


def ema(values: np.ndarray, period: int) -> np.ndarray:
    """指数移动平均。返回与输入等长的数组，前 period-1 个为 NaN。"""
    n = len(values)
    out = np.full(n, np.nan, dtype=float)
    if n < period or period <= 0:
        return out
    alpha = 2.0 / (period + 1)
    out[period - 1] = float(np.mean(values[:period]))
    prev = out[period - 1]
    for i in range(period, n):
        prev = alpha * values[i] + (1 - alpha) * prev
        out[i] = prev
    return out
