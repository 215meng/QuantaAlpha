# Crypto 适配错误日志

> 创建时间：2026-07-17 · 最后更新：2026-07-17 19:04
> 测试环境：Windows 11, conda fe, QuantaAlpha feature/crypto-data 分支
> 测试操作：前端选 "Top-50 Crypto" → 输入方向 "基于K线和均线构建的短期动量..." → 启动挖掘

---

## 一、严重错误（导致实验失败）

### ERR-01：`<PRED>` 占位符无法解析

- **时间**：16:38:03（首次）、16:42:03（二次）
- **错误信息**：
  ```
  <PRED> lookes like a placeholder, but it can't match to any given values
  ```
- **后果**：`qrun conf_crypto.yaml` 返回 exit code 1，整个回测失败
- **日志上下文**：
  ```plaintext
  data_path={'__DEFAULT_FREQ': WindowsPath('E:/py/github_QuantaAlpha/QuantaAlpha/data/qlib/crypto_50')}
  Recorder starts running ...
  RuntimeError: Command failed with return code 1
  ```
- **根因**：`conf_crypto.yaml` 的 `task.record` 部分使用了 `<PRED>` 占位符，期望 Qlib 运行时自动填充模型预测信号。但 crypto 回测子进程是独立 workflow，没有上游 mining 步骤生成的 `<MODEL>` 和 `<DATASET>` 信号注入 → 占位符解析失败。
- **影响范围**：所有 crypto 回测都会失败（不只这一个因子）

---

### ERR-02：运行两次均失败（稳定复现）

- **时间**：16:38:04 + 16:42:04
- **错误信息**：`Task 0 failed: Command failed with return code 1`
- **根因**：同 ERR-01，稳定复现

### ERR-03：benchmark `BTCUSDT` 不存在（第二轮运行 18:55 新出现）

- **时间**：18:59:05 + 19:03:51（第二轮运行，共出现 2 次）
- **错误信息**：
  ```
  ValueError: The benchmark ['BTCUSDT'] does not exist. Please provide the right benchmark
  ```
- **日志上下文**：
  ```plaintext
  data_path={'__DEFAULT_FREQ': WindowsPath('E:/py/github_QuantaAlpha/QuantaAlpha/data/qlib/crypto_50')}
  [140] train's l2: 0.99261 valid's l2: 0.993998
  'The following are prediction results of the LGBModel model.'
  2024-01-01 1INCHUSDT 0.039464
  ALGOUSDT 0.035268
  'ICIR': 0.044374991712651524,
  ValueError: The benchmark ['BTCUSDT'] does not exist.
  ```
- **根因**：`conf_crypto.yaml` 的 `benchmark: &benchmark BTCUSDT`，但 Qlib 初始化后查询 instrument list 时找不到 `BTCUSDT`。可能原因：
  1. `data/qlib/crypto_50/instruments/crypto_50.txt` 里的 instrument 名和 Qlib 内部查询大小写不匹配
  2. `BTCTUSDT` 实际存在，但 Qlib 在 backtest 模块中查找 benchmark 时用的 instrument pool 不同
- **注**：数据加载阶段能识别 50 个币（含 AAVEUSDT, ALGOUSDT 等），说明 `BTCUSDT` 数据存在，但 benchmark 引用的 instrument pool 可能不同

---

## 二、警告（不影响主流程）

### WARN-01：llama 未安装

- **时间**：16:35:15
- **WARNING**：`llama is not installed.`
- **影响**：无，主流程用 DeepSeek API，不依赖 llama

### WARN-02：无 CUDA GPU

- **时间**：16:35:56
- **WARNING**：`No CUDA GPU detected (PyTorch).`
- **影响**：回测用 CPU，速度慢（202 秒加载数据）但能跑

### WARN-03：首次实验自动创建

- **时间**：16:38:03
- **WARNING**：`No valid experiment found. Create a new experiment with name workflow.`
- **影响**：正常，首次运行都会创建新实验

### WARN-04：LiteLLM 成本地图拉取超时

- **时间**：16:42:15
- **WARNING**：`LiteLLM: Failed to fetch remote model cost map ... The handshake operation timed out.`
- **影响**：无，回退到本地备份

---

## 二-B、第二轮运行新增警告（18:55-19:04）

| # | 时间 | 警告 | 说明 |
|---|---|---|---|
| 5 | 18:56:05, 18:59:29 | `llama is not installed` | 同第一轮 WARN-01，无影响 |
| 6 | 18:55:55 | `No CUDA GPU detected (PyTorch)` | 同第一轮 WARN-02 |
| 7 | 18:59:05 | `No valid experiment found. Create a new experiment with name workflow.` | 正常，首次创建 |
| 8 | 18:56:05 | `LiteLLM: Failed to fetch remote model cost map ... The read operation timed out.` | 网络超时，用本地备份，无影响 |
| 9 | 18:59:05 + 19:03:51 | `<PRED> lookes like a placeholder, but it can't match to any given values` | 同 ERR-01 |
| 10 | 18:57:11 + 19:00:21 + 19:00:52 | `Request timed out. Retrying Xth time...` | DeepSeek API 首次/后续请求超时，自动重试，最终成功 |
| 11 | 19:03:51 | `ModuleNotFoundError. CatBoostModel are skipped.` | CatBoost 未安装，可选依赖，无影响 |

---

## 三、因子表达式调试（factor_calculate 阶段）

### DBG-01：LLM 混淆 `$return` 与 `$close`

- **时间**：16:36:30 - 16:37:07
- **问题**：LLM 生成的表达式用 `$return`（日收益率）代替 `$close`（收盘价）
  - 错误：`DELAY($return, 1)` ← LLM 以为这是前日收盘价
  - 正确应为：`DELAY($close, 1)`
- **评估器反馈**：`$return is not the previous close price. The expression uses $return as prev_close`
- **最终**：LLM 自我修正，重试后通过

### DBG-02：首轮 3 因子全失败

- **时间**：16:37:07
- **信息**：`Final decisions: [False, False, False] (0/3 passed)`
- **调试耗时**：53.78 秒（16:37:07 → 16:44:02）
- **最终结果**：LLM 修正后 3 因子全部通过

### DBG-03：最终生成的因子（非 crypto 特色）

| 因子名 | 表达式 | 备注 |
|---|---|---|
| `Overnight_Intraday_Divergence_RSI_10D` | `RSI((-1) * (...), 5) * SIGN(TS_CORR(...))` | A 股隔夜/日内模式 |
| `Divergence_MeanReversion_Score_20D` | `(-1) * TS_ZSCORE(...) * ABS(TS_CORR(...))` | A 股隔夜/日内模式 |
| `Volatility_Adjusted_Divergence_5D` | 含 `TS_MEAN/TS_STD/MAX/SIGN(TS_CORR)` | A 股隔夜/日内模式 |

> ⚠️ 所有因子都是 A 股风格的"隔夜-日内收益背离"类，没有 crypto 特色因子（如链上数据、持币地址变化、gas 费等）。**可能说明 prompt 切换未生效，或 LLM 仍按 A 股思维。**

### DBG-04（第二轮新增）：生成的因子（仍非 crypto 特色）

| 因子名 | 表达式 | 备注 |
|---|---|---|
| `MA_Slope_Body_Confidence_10D` | `SIGN((SMA($close,5,1)-SMA($close,20,1))/...) * (1-ABS($close-$open)/($high-$low))` | A 股均线斜率 |
| `Trend_Reversal_Body_Intensity_20D` | 同上变体 | A 股 K 线实体比例 |
| `MA_Slope_Body_Ratio_Composite_10D` | `TS_MEAN((SMA($close,5)-DELAY(SMA($close,5),1)) - ...)` | A 股均线动量 |
| `Trend_Conviction_Score_10D` | 含 `SIGN(MACD($close, 12, 26))` | A 股 MACD |
| `Momentum_Body_Disparity_10D` | 含 `TS_MEAN/ABS($close-$open)/($high-$low)` | A 股 K 线形态 |

> 结论一致：两轮均生成 A 股风格因子，prompt 切换可能**未生效**或效果弱。

---

## 四、数据加载（部分成功）

### 第一轮（16:35-16:44）

| 指标 | 值 | 状态 |
|---|---|---|
| 数据路径 | `data/qlib/crypto_50` | ✅ 正确 |
| 训练 l2 | `0.992946` | ✅ LightGBM 训练完成 |
| 验证 l2 | `0.994161` | ✅ |
| Rank IC | `0.033041` | ✅ （crypto 合理范围 0.02-0.05） |
| AAVEUSDT | `0.044238` | ✅ |
| APTUSDT | `0.079290` | ✅ |
| 数据加载耗时 | 202.284s | ⚠️ 较慢（CPU 模式） |

### 第二轮（18:55-19:04）

| 指标 | 值 | 状态 |
|---|---|---|
| 数据路径 | `data/qlib/crypto_50` | ✅ 正确 |
| 训练 l2 | `0.993326` | ✅ |
| 验证 l2 | `0.994370` | ✅ |
| ICIR | `0.04437` | ✅ |
| 1INCHUSDT | `0.039464` | ✅ |
| ALGOUSDT | `0.035268` | ✅ |
| 数据加载耗时 | ~85-97s | ✅ 正常（CPU） |
| ⚠️ benchmark | `BTCUSDT` | ❌ 不存在 |

---

## 五、根因汇总图

### 第一轮错误链

```
factor_propose  ──────────────────── ✅ 正常
factor_construct ─────────────────── ✅ 正常
factor_calculate ────────────────── ✅ 正常（调试 1 轮后通过）
factor_backtest  ────────────────── ❌ 失败
  ├── qrun conf_crypto.yaml
  ├── 数据加载成功（crypto_50, 50币）
  ├── LightGBM 训练成功（l2≈0.993）
  ├── IC=0.033, ICIR=0.044 （指标正常）
  └── 失败点: <PRED> 无法解析 + benchmark BTCUSDT 不存在 → exit code 1
        ↑
        └── 根因 1：conf_crypto.yaml 的 SignalRecord 用 <PRED> 占位符，独立回测子进程无信号注入
            根因 2：benchmark BTCUSDT 在 Qlib instrument pool 中查不到
```

### 第二轮重复第一轮场景（0/1 succeeded），且 LLM 生成因子仍为 A 股风格
> **关键疑虑**：prompt 切换是否真正生效？（LLM 似乎仍按 A 股语义工作）

---

## 六、修复方向（待实施）

| 方案 | 改动 | 优劣 |
|---|---|---|
| **A. 让 crypto 回测走 combined_factors 路径（推荐）** | 回测时强制用 `conf_combined_factors.yaml`，让 runner 注入自定义信号 | 最小改动，复用 A 股已有逻辑 |
| **B. `conf_crypto.yaml` 显式指定信号源 + 修复 benchmark** | `<PRED>` → 具体信号路径；benchmark 改为存在的 instrument 或自建指数 | 需了解 Qlib 信号注入 + benchmark 机制 |
| **C. 回测前因子写入 qlib feature** | `factor_calculate` 后加一步持久化 | 最稳健，改动大 |

**推荐方案 A + B 组合**：
1. 回测阶段复用 `conf_combined_factors.yaml` 走信号注入路径（解决 `<PRED>` 问题）
2. `conf_crypto.yaml` 的 `benchmark` 改为 crypto 池中确定存在的 instrument（如 `BTCUSDT`）或自建等权指数
3. 检查 `data/qlib/crypto_50/instruments/crypto_50.txt` 里是否真的有 `BTCUSDT`（大小写敏感）

---

## 七、附加观察

1. **`MARKET_TYPE=crypto` 是否真正触发了 prompt 切换？**
   - 两轮日志里 LLM 生成的假设/direction 仍然提到"个股""隔夜收益"等 A 股术语
   - 需在日志里确认 scenario 背景是否包含 "TOP-50 CRYPTOCURRENCIES" 字样
   - 如果 prompt 切换未生效，实际生成的因子永远是 A 股风格

2. **benchmark 不存在但数据有该 instrument？**
   - 日志显示数据有 `AAVEUSDT`, `ALGOUSDT`, `1INCHUSDT` 等 50 个币
   - 但 `benchmark: BTCUSDT` 却说 "does not exist"
   - 可能是 Qlib 在 `backtest` 模块查询时用的 `instrument pool` 和 `data pool` 不一致
   - 需确认 `crypto_50.txt` 第一行是不是 `BTCUSDT`

2. **`<PRED>` 机制理解**
   - A 股 `conf_baseline.yaml` 的 `<PRED>` 由 runner 在回测时动态替换
   - crypto 的 `conf_crypto.yaml` 应该是独立触发回测（无上游 mining），但 `<PRED>` 依赖被注入的 model/dataset，导致无法匹配
