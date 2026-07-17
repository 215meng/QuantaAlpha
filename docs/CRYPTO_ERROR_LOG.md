# Crypto 适配错误日志

> 创建时间：2026-07-17 · 最后更新：2026-07-17 19:15
> 测试环境：Windows 11, conda fe, QuantaAlpha feature/crypto-data 分支
> 测试操作：前端选 "Top-50 Crypto" → 输入方向 "基于K线和均线构建的短期动量与长期均值回归的复合信号" → 启动挖掘
> 测试轮次：4 轮（16:35 / 18:55 / 18:55 后续重试 6 次 factor_backtest）

---

## 一、严重错误（导致回测失败）

### ERR-01：`<PRED>` 占位符无法解析（所有轮次）

- **时间**：每轮 factor_backtest 必触发
- **错误信息**：
  ```
  <PRED> lookes like a placeholder, but it can't match to any given values
  ```
- **根因**：`conf_crypto.yaml` 的 `SignalRecord` 用 `<PRED>` 占位符，依赖 runner 在回测时从上游 mining 流程注入模型预测信号。但独立回测子进程没有 mining 上游，占位符无法解析。

### ERR-02：`benchmark ['BTCUSDT'] 不存在`

- **时间**：18:59:05 起每轮触发
- **错误信息**：
  ```
  ValueError: The benchmark ['BTCUSDT'] does not exist. Please provide the right benchmark
  ```
- **日志上下文**：
  ```plaintext
  data_path={'__DEFAULT_FREQ': WindowsPath('.../data/qlib/crypto_50')}
  [140] train's l2: 0.99261 valid's l2: 0.993998
  'The following are prediction results of the LGBModel model.'
  2024-01-01 1INCHUSDT 0.039464
  ALGOUSDT 0.035268
  ValueError: The benchmark ['BTCUSDT'] does not exist.
  ```
- **根因**：Qlib 数据加载阶段能识别 50 个币（含 1INCHUSDT、ALGOUSDT 等），但 `<PRED>` 报错后 workflow 中断，benchmark 可能在另一个 instrument pool（`D.instruments('crypto_50')` vs 数据目录实际文件）中查不到 `BTCUSDT`。
- **可能原因**：
  1. `data/qlib/crypto_50/instruments/crypto_50.txt` 里 BTCUSDT 大小写不匹配
  2. Qlib backtest 模块查询 benchmark 时用的 pool 与数据池不一致
  3. `<PRED>` 报错导致 workflow 未完整初始化， BTCUSDT 在 backtest 上下文中确实不存在

---

## 二、警告（不影响流程）

| # | 内容 | 出现轮次 | 影响 |
|---|---|---|---|
| W-01 | `llama is not installed.` | 所有轮次 | 无，主流程用 DeepSeek API |
| W-02 | `No CUDA GPU detected (PyTorch).` | 所有轮次 | 无，CPU 模式跑（慢但能跑）|
| W-03 | `No valid experiment found. Create a new experiment with name workflow.` | 每轮首次 | 正常 |
| W-04 | `LiteLLM: Failed to fetch remote model cost map ... The read operation timed out.` | 16:42 / 18:55 | 无，回退本地备份 |
| W-05 | **`Request timed out. Retrying Xth time...`** | 18:59:56 连续 3 次 | DeepSeek API 不稳定，第 4 次成功（87.53s）|
| W-06 | `ModuleNotFoundError. CatBoostModel are skipped.` | 19:03 起 | 无，CatBoost 是可选依赖 |

---

## 三、因子表达式质量（跨轮次问题）

### 已生成因子汇总（4 轮共 13+ 个，全部 A 股风格）

| 因子名 | 表达式摘要 | 备注 |
|---|---|---|
| `Overnight_Intraday_Divergence_RSI_10D` | `RSI(...) * SIGN(TS_CORR(...))` | A 股隔夜/日内 |
| `MA_Slope_Body_Confidence_10D` | `SIGN(SMA(5)-SMA(20)) * (1-ABS(close-open)/(high-low))` | A 股均线 |
| `MA_Slope_Body_Ratio_Composite_10D` | `TS_MEAN((SMA(5)-DELAY(SMA(5)))-(SMA(20)-DELAY(SMA(20)))) * ...` | A 股均线 |
| `Trend_Momentum_Body_Ratio_5_20` | `TS_ZSCORE((SMA(5)-SMA(20)) * body/range)` | A 股均线 |
| `MACD_Slope_BodyShadow_Factor` | `RANK(MACD(12,26) * body/range)` | A 股 MACD |
| `Trend_Candle_Conviction_Index_15D` | `TS_MEAN/ABS/RANK` | A 股 K 线 |
| `Momentum_Conviction_Reversal_10` | `RANK(PCTCHANGE(close,10)) * RANK(body/range)` | A 股动量 |
| ...（更多类似） | ... | A 股风格 |

> ⚠️ **关键问题**：4 轮测试，LLM 生成的因子全部是 A 股风格（均线、MACD、K 线形态），没有任何 crypto 特色因子。
> **可能原因**：
> 1. `MARKET_TYPE=crypto` 环境变量未传递到子进程（runner 子进程是独立 Python 进程，需显式 env 传递）
> 2. 或 prompt 差异不够强（LLM 训练数据中 A 股语义太强，轻微提示无法覆盖）
>
> **验证方式**：在 `get_prompt_file()` 里临时打印路径，或检查 `experiment.py` 渲染后的 background 是否含 "TOP-50 CRYPTOCURRENCIES"。

---

## 四、数据加载表现（正常）

每轮 factor_backtest 数据加载均成功：

| 指标 | 值 | 状态 |
|---|---|---|
| 数据路径 | `data/qlib/crypto_50` | ✅ |
| 训练 l2 | `0.993 ~ 0.994` | ✅ LightGBM 训练完成 |
| 验证 l2 | `0.994` | ✅ |
| IC | `0.0088 ~ 0.033` | ✅ crypto 合理范围 0.02-0.05 |
| ICIR | `0.044` | ✅ |
| 预测值（1INCHUSDT 等）| 有输出 | ✅ 50 币全部就绪 |

> **结论**：数据层已打通（CSV → Qlib bin → 训练 → 预测全流程 OK），问题**完全集中在回测配置层**（`<PRED>` + benchmark）。

---

## 五、根因汇总图

```
factor_propose  ──── ✅ 正常（5-6s；API 不稳定时 87s+）
factor_construct ─── ✅ 正常（10-16s）
factor_calculate ─── ✅ 正常（21-54s，首轮调试后通过）
factor_backtest  ──── ❌ 失败（10/10 次）
  ├── qrun conf_crypto.yaml
  ├── Qlib 初始化成功 → data_path 指向 crypto_50 ✅
  ├── 数据加载: Loading data Done (85-202s) ✅
  ├── ProcessInf / CSRankNorm / FillnaLabel 全部 Done ✅
  ├── LightGBM 训练完成 (l2≈0.993) ✅
  ├── 预测输出 (1INCHUSDT/ALGOUSDT 等有值) ✅
  └── 崩溃点:
        ├── <PRED> 占位符无法解析 (ERROR)
        ├── benchmark ['BTCUSDT'] 不存在 (ERROR)
        └── exit code 1 (RuntimeError)

=== 两层独立问题 ===
  问题 A: <PRED> 占位符 ← conf_crypto.yaml 依赖 runner 注入 mining 信号，独立回测子进程无信号
  问题 B: benchmark BTCUSDT ← Qlib crypto_50 pool 中查不到该 instrument
```

---

## 六、修复方案（待统一实施）

| 优先级 | 方案 | 改动文件 | 说明 |
|---|---|---|---|
| **P0** | 修复 `<PRED>`：让 crypto 回测走 `conf_combined_factors.yaml` | `runner.py` + `conf_crypto.yaml` | A 股 A 路径成熟，复用即可解决占位符注入问题 |
| **P0** | 修复 `benchmark`：改为确定存在的 instrument 或自建等权指数 | `conf_crypto.yaml`（benchmark 字段）| 候选：`1INCHUSDT`、`AAVEUSDT`（验证存在后替换），或自建等权指数 |
| **P1** | 验证 `MARKET_TYPE` 子进程传递 | `runner.py`（子进程 env）、`experiment.py`（日志打出来）| 若子进程未读到 `MARKET_TYPE=crypto`，需显式 env 传入 |
| **P2** | 强化 crypto prompt（如 P1 修复后因子仍是 A 股风格）| `experiment_crypto.yaml` | 在 background 加入更明确的市场特征描述，强制 LLM crypto 语义 |

**推荐执行顺序**：P0（两个一起改） → 跑通回测（拿到第一个完整结果） → P1 → P2

---

## 七、待用户确认

- [ ] `data/qlib/crypto_50/instruments/crypto_50.txt` 第一行是否是 `BTCUSDT`？（大小写）
- [ ] 是否同意先实施方案 A+B（让 crypto 回测走 combined_factors + 换 benchmark 为 `AAVEUSDT`）
- [ ] `MARKET_TYPE=crypto` 是否应作为子进程 env 显式传入（推荐是）
