"""SQLite 持久化层：按 (周期, 时间戳) 存储 / 读取 K 线。"""
import sqlite3
import numpy as np
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS klines (
    tf TEXT    NOT NULL,
    ts INTEGER NOT NULL,
    o  REAL,
    h  REAL,
    l  REAL,
    c  REAL,
    v  REAL,
    PRIMARY KEY (tf, ts)
);
CREATE INDEX IF NOT EXISTS idx_klines_tf_ts ON klines(tf, ts);
"""


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        # WAL 提升多连接并发读写能力；NORMAL 兼顾写入速度与安全
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.commit()

    def count(self, tf: str) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM klines WHERE tf=?", (tf,))
        return cur.fetchone()[0]

    def latest_ts(self, tf: str):
        cur = self.conn.execute(
            "SELECT MAX(ts) FROM klines WHERE tf=?", (tf,))
        return cur.fetchone()[0]

    def save_batch(self, tf: str, rows):
        """rows: iterable of (ts, o, h, l, c, v)。使用 INSERT OR REPLACE 增量写入。"""
        data = [(tf, int(r[0]), float(r[1]), float(r[2]),
                 float(r[3]), float(r[4]), float(r[5])) for r in rows]
        self.conn.executemany(
            "INSERT OR REPLACE INTO klines(tf, ts, o, h, l, c, v) "
            "VALUES (?,?,?,?,?,?,?)", data)
        self.conn.commit()

    def load(self, tf: str):
        """读取某周期全部 K 线，返回按时间升序的 numpy 数组字典。无数据返回 None。"""
        cur = self.conn.execute(
            "SELECT ts, o, h, l, c, v FROM klines WHERE tf=? ORDER BY ts ASC", (tf,))
        rows = cur.fetchall()
        if not rows:
            return None
        arr = np.asarray(rows, dtype=float)  # 列: ts,o,h,l,c,v
        return {
            "ts": arr[:, 0].astype(np.int64),
            "o": arr[:, 1],
            "h": arr[:, 2],
            "l": arr[:, 3],
            "c": arr[:, 4],
            "v": arr[:, 5],
            "n": len(arr),
        }

    def clear(self, tf: str = None):
        if tf:
            self.conn.execute("DELETE FROM klines WHERE tf=?", (tf,))
        else:
            self.conn.execute("DELETE FROM klines")
        self.conn.commit()

    def close(self):
        self.conn.close()
