"""全局配置：交易对、时间周期、数据库路径、配色与默认值。"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "kline_data.db")
DRAWINGS_PATH = os.path.join(BASE_DIR, "drawings.json")

# OKX 交易对（BTC 现货对 BTC-USDT）
SYMBOL = "BTC-USDT"
# 默认抓取的历史长度（年）
HISTORY_YEARS = 3

# 时间周期定义：(OKX bar 参数, 周期秒数)
TIMEFRAMES = {
    "5m":  ("5m",  5 * 60),
    "15m": ("15m", 15 * 60),
    "30m": ("30m", 30 * 60),
    "1H":  ("1H",  60 * 60),
    "4H":  ("4H",  4 * 60 * 60),
    "1D":  ("1D",  24 * 60 * 60),
}
TIMEFRAME_ORDER = ["5m", "15m", "30m", "1H", "4H", "1D"]

# 技术指标
EMA_PERIOD = 20

# ---- 下载性能（OKX 公共接口 rate limit：history-candles 约 20 次/2 秒）----
DOWNLOAD_WORKERS = 12          # 并发线程数，用于隐藏 VPN/网络的往返延迟
DOWNLOAD_RATE_PER_SEC = 8.0    # 全局限速（次/秒），留出余量避免触发 429

# ---- 各周期抓取的历史长度（年）。None 表示使用上面的 HISTORY_YEARS（默认 3 年）----
# 数据量差异极大：3 年 5m ≈ 31.5 万根（≈3300 页），1 年 5m 仅 ≈1100 页。
# 默认给密集周期更短历史，下载会快数倍；想全部抓满 3 年就把对应值改成 None。
HISTORY_YEARS_PER_TF = {
    "5m":  0.5,
    "15m": 1.0,
    "30m": 2.0,
    "1H":  3.0,
    "4H":  3.0,
    "1D":  3.0,
}

# OKX 公开行情接口（无需鉴权）
OKX_CANDLES_URL = "https://www.okx.com/api/v5/market/candles"
OKX_HISTORY_URL = "https://www.okx.com/api/v5/market/history-candles"

# 配色（用户指定：绿涨红跌；EMA20 为蓝色）
UP_COLOR = "#26a69a"      # 涨：绿
DOWN_COLOR = "#ef5350"    # 跌：红
EMA_COLOR = "#2962ff"     # EMA 线（蓝）
GRID_COLOR = "#e6e6e6"
AXIS_COLOR = "#666666"
BG_COLOR = "#ffffff"

# 绘图工具默认颜色
HLINE_COLOR = "#f0b90b"   # 水平线
RECT_COLOR = "#00bcd4"    # 矩形
FIB_COLOR = "#ab47bc"     # 斐波那契

# 斐波那契默认回撤档位（可自定义）
DEFAULT_FIB_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]

# 回放默认参数
DEFAULT_CPS = 5            # 默认每秒推进的 K 线根数
VISIBLE_MIN, VISIBLE_MAX, VISIBLE_DEFAULT = 50, 2000, 300
CPS_MIN, CPS_MAX = 1, 60
