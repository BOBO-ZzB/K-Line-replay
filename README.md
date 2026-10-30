# K线回放桌面程序（TradingView 风格）

基于 **Python + PySide6 + pyqtgraph + numpy + SQLite** 的 BTC/USDT 历史 K 线回放工具。

## 功能
- **数据**：从 OKX 抓取 BTC-USDT 近 3 年历史 K 线（5m / 15m / 30m / 1H / 4H / 1D 六个周期），SQLite 持久化，首次抓取后本地读取；无网络时可用「生成示例数据」离线体验。
- **回放**：逐根播放 / 暂停 / 单步前进后退 / 调速，回放中只显示当前进度之前的 K 线。
- **绘图**：水平线、矩形框、斐波那契回撤（档位可自定义），跟随回放显示、可删除、切换周期位置不变。
- **指标**：EMA20 实时计算（蓝色线）。
- **界面**：TradingView 风格，深色 / 浅色主题切换，绿涨红跌。

## 首次运行
```bat
cd kline_replay
python -m pip install -r requirements.txt
python main.py
```
首次打开本地无数据时会自动生成示例数据；点顶部「数据 ▾」→「从 OKX 下载真实数据」抓取真实 3 年数据。

## 快捷键
| 按键 | 功能 |
|---|---|
| 空格 / P / S | 播放 / 暂停 |
| ← / → | 上一根 / 下一根 |
| ↑ / ↓ | 加速 / 减速 |
| Home / End | 跳到开头 / 结尾 |
| T | 切换深色 / 浅色主题 |
| Esc | 回到光标（取消绘图） |

## 主题实现
- 调色板与 QSS 集中在 `theme.py`（`DARK` / `LIGHT` 两套）。
- 主窗口 `_apply_theme()` 设置 `setStyleSheet(build_qss(p))` 并调用 `chart.apply_theme(p)` 刷新图表背景/网格/坐标轴/蜡烛/EMA/绘图颜色。
- 默认主题为 **dark**（TradingView 默认即深色），选择通过 `QSettings("KlineReplay","UI","theme")` 持久化。

## 结构
| 文件 | 职责 |
|---|---|
| `main.py` | 入口 |
| `main_window.py` | 主窗口：顶栏 / 工具栏 / 底栏、主题、快捷键、数据任务 |
| `chart_view.py` | pyqtgraph 图表：K 线、回放渲染、绘图交互、十字光标、图例 |
| `replay_engine.py` | 回放引擎（定时器驱动） |
| `db.py` / `fetcher.py` | SQLite 持久化 / OKX 抓取与示例数据 |
| `indicators.py` / `drawings.py` | EMA 指标 / 绘图对象模型 |
| `theme.py` / `config.py` | 主题与配色 / 全局配置 |
| `test_smoke.py` / `test_worker.py` / `render_preview.py` | 无界面测试 / 后台线程测试 / 离屏截图预览 |
