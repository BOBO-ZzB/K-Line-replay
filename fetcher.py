"""数据获取：从 OKX 拉取历史 K 线；无网络时生成示例数据用于离线体验。

性能优化（相比早期逐页串行版本）：
- 用 requests.Session 复用 TCP/TLS 连接（走 VPN 时省去每页重复握手，明显更快）
- 预计算分页边界，用线程池并发抓取（把网络往返延迟重叠起来）
- 全局限速 + 429 退避，既跑得快又不触发 OKX 限流
"""
import math
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests
from requests.adapters import HTTPAdapter

from config import (
    SYMBOL, TIMEFRAMES, HISTORY_YEARS,
    OKX_HISTORY_URL,
    DOWNLOAD_WORKERS, DOWNLOAD_RATE_PER_SEC, HISTORY_YEARS_PER_TF,
)

_PAGE_LIMIT = 100      # OKX 单页上限
_OVERLAP_BARS = 4      # 相邻页重叠若干根，避免分页边界丢数据（按 ts 去重）
_TIMEOUT = 12
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _make_session():
    """带连接池的共享 Session：复用连接，避免每请求重新握手。"""
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32, max_retries=0)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": _UA, "Accept": "application/json"})
    return s


class _RateLimiter:
    """全局限速器：匀速发牌，多线程共享也不会超过设定速率。"""

    def __init__(self, rate_per_sec: float):
        self._interval = 1.0 / max(rate_per_sec, 0.1)
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next)
            self._next = slot + self._interval
        delay = slot - time.monotonic()
        if delay > 0:
            time.sleep(delay)


def _fetch_one(session, limiter, bar, after,
               limit=_PAGE_LIMIT, timeout=_TIMEOUT):
    """抓取单页，返回原始行列表（OKX 为降序）。429/异常做退避重试。"""
    params = {"instId": SYMBOL, "bar": bar, "limit": limit, "after": after}
    for attempt in range(4):
        limiter.wait()
        try:
            r = session.get(OKX_HISTORY_URL, params=params, timeout=timeout)
            if r.status_code == 200:
                js = r.json()
                if str(js.get("code", "0")) == "0":
                    return js.get("data", [])
                # 业务错误（常见为限流）→ 退避后重试
                time.sleep(0.4 * (attempt + 1))
            elif r.status_code == 429:
                time.sleep(0.6 * (attempt + 1))
            else:
                time.sleep(0.3 * (attempt + 1))
        except requests.RequestException:
            time.sleep(0.4 * (attempt + 1))
    return []


def _years_for_tf(tf: str) -> float:
    y = HISTORY_YEARS_PER_TF.get(tf)
    return float(y) if y else float(HISTORY_YEARS)


def fetch_okx(tf: str, progress_cb=None, years: float = None,
              end_ts: int = None, max_workers: int = None,
              rate_per_sec: float = None):
    """并发分页抓取 OKX 历史 K 线，返回按时间升序的 (ts,o,h,l,c,v) 列表。

    progress_cb(done_pages, total_pages) 上报页级进度。无网络时返回空列表。
    """
    bar, sec = TIMEFRAMES[tf]
    if years is None:
        years = _years_for_tf(tf)
    if max_workers is None:
        max_workers = DOWNLOAD_WORKERS
    if rate_per_sec is None:
        rate_per_sec = DOWNLOAD_RATE_PER_SEC
    if end_ts is None:
        end_ts = int(time.time() * 1000)

    sec_ms = sec * 1000
    start_ts = end_ts - int(years * 365 * 24 * 3600 * 1000)
    span_ms = end_ts - start_ts
    step_bars = max(1, _PAGE_LIMIT - _OVERLAP_BARS)   # 每页实际推进的根数
    step_ms = step_bars * sec_ms
    n_pages = max(1, int(math.ceil(span_ms / step_ms)))

    # 从新到旧的每页 after 边界（after=X 返回 ts<X 的数据）
    afters = [end_ts - i * step_ms for i in range(n_pages)]

    session = _make_session()
    limiter = _RateLimiter(rate_per_sec)
    seen = set()
    rows = []
    done = 0
    total = len(afters)

    def _task(after):
        return _fetch_one(session, limiter, bar, after)

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_task, a) for a in afters]
            for fut in as_completed(futures):
                data = fut.result()
                for row in data:
                    ts = int(row[0])
                    if ts < start_ts or ts > end_ts:
                        continue
                    if ts not in seen:
                        seen.add(ts)
                        rows.append((ts, float(row[1]), float(row[2]),
                                     float(row[3]), float(row[4]), float(row[5])))
                done += 1
                if progress_cb:
                    progress_cb(done, total)
    finally:
        session.close()

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
