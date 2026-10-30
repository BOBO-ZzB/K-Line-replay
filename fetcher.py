"""数据获取：从 OKX 拉取历史 K 线；无网络时生成示例数据用于离线体验。"""
import time
import numpy as np
import requests
from config import (
    SYMBOL, TIMEFRAMES, HISTORY_YEARS,
    OKX_CANDLES_URL, OKX_HISTORY_URL,
)


def _fetch_page(url, bar, after, limit=100, timeout=10):
    """请求单页 K 线，返回升序/降序原始行。OKX 返回数据为降序（最新在前）。"""
    params = {"instId": SYMBOL, "bar": bar, "limit": limit, "after": after}
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json().get("data", [])
        except requests.RequestException:
            time.sleep(0.5)
    return []


def fetch_okx(tf: str, progress_cb=None, years: int = HISTORY_YEARS,
              end_ts: int = None):
    """分页抓取 OKX 历史 K 线，返回按时间升序的 (ts,o,h,l,c,v) 列表。

    progress_cb(done, total) 用于上报进度。无网络时抛出 RequestException。
    """
    bar, sec = TIMEFRAMES[tf]
    if end_ts is None:
        end_ts = int(time.time() * 1000)
    start_ts = end_ts - int(years * 365 * 24 * 3600 * 1000)
    total_est = max(1, int((end_ts - start_ts) / 1000 / sec))

    seen = set()
    rows = []
    after = end_ts
    # 先用 candles，若早期数据不足再退回 history-candles
    urls = [OKX_CANDLES_URL, OKX_HISTORY_URL]
    url_idx = 0

    while True:
        data = _fetch_page(urls[url_idx], bar, after)
        if not data and url_idx < len(urls) - 1:
            url_idx += 1
            continue
        if not data:
            break

        new_in_page = 0
        for row in data:
            ts = int(row[0])
            if ts <= start_ts:
                # 已到达目标起点，把这一根也记录后停止
                if ts not in seen:
                    seen.add(ts)
                    rows.append((ts, float(row[1]), float(row[2]),
                                 float(row[3]), float(row[4]), float(row[5])))
                break
            if ts not in seen:
                seen.add(ts)
                rows.append((ts, float(row[1]), float(row[2]),
                             float(row[3]), float(row[4]), float(row[5])))
                new_in_page += 1
        else:
            # for 循环正常结束（没有 break）才更新 after 继续翻页
            after = int(data[-1][0])
            if progress_cb:
                progress_cb(len(rows), total_est)
            if len(rows) >= total_est:
                break
            time.sleep(0.05)
            continue
        # for 循环因 break 退出：已到达起点
        if progress_cb:
            progress_cb(len(rows), total_est)
        break

    rows.sort(key=lambda x: x[0])
    return rows


def generate_sample(tf: str, years: int = 1, end_ts: int = None):
    """生成合成随机游走 K 线，用于无网络时的本地体验。"""
    _, sec = TIMEFRAMES[tf]
    n = max(50, int(years * 365 * 24 * 3600 / sec))
    if end_ts is None:
        end_ts = int(time.time() * 1000)
    start_ts = end_ts - n * sec * 1000
    ts = np.arange(start_ts, end_ts, sec * 1000).astype(np.int64)

    rng = np.random.default_rng(42)
    rets = rng.normal(0, 0.0012, len(ts))
    price = 30000.0 * np.exp(np.cumsum(rets))
    c = price
    o = np.roll(c, 1)
    o[0] = c[0]
    noise = np.abs(rng.normal(0, c * 0.0006, len(ts)))
    h = np.maximum(o, c) + noise
    l = np.minimum(o, c) - noise
    v = rng.uniform(0.5, 2.0, len(ts)) * 100.0

    return [(int(ts[i]), float(o[i]), float(h[i]), float(l[i]),
             float(c[i]), float(v[i])) for i in range(len(ts))]
