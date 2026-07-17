# Crypto 适配错误日志

> 创建时间：2026-07-17
> 测试环境：Windows 11, conda fe, QuantaAlpha feature/crypto-data 分支
> 测试操作：前端选 "Top-50 Crypto" → 输入方向 "基于隔夜收益与日内收益的背离动量" → 启动挖掘

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

---

## 四、数据加载（部分成功）

在 `<PRED>` 错误出现前，数据加载阶段正常：

| 指标 | 值 | 状态 |
|---|---|---|
| 数据路径 | `data/qlib/crypto_50` | ✅ 正确 |
| 训练 l2 | `0.992946` | ✅ LightGBM 训练完成 |
| 验证 l2 | `0.994161` | ✅ |
| Rank IC | `0.033041` | ✅ （crypto 合理范围 0.02-0.05） |
| AAVEUSDT | `0.044238` | ✅ |
| APTUSDT | `0.079290` | ✅ |
| 数据加载耗时 | 202.284s | ⚠️ 较慢（CPU 模式） |

---

## 五、根因汇总图

```
factor_propose  ──────────────────── ✅ 正常（LLM 生成假设）
factor_construct ─────────────────── ✅ 正常（LLM 构建因子）
factor_calculate ────────────────── ✅ 正常（调试 1 轮后通过）
factor_backtest  ────────────────── ❌ 失败
  ├── qrun conf_crypto.yaml
  ├── 数据加载成功（crypto_50, 50币, 2462时间步）
  ├── LightGBM 训练成功（l2≈0.993）
  └── SignalRecord: <PRED> 无法解析 → exit code 1
        ↑
        └── 根因：conf_crypto.yaml 的 task.record 用 <PRED> 占位符
            但独立回测子进程没有 mining 上游注入的信号
```

---

## 六、修复方向（待实施）

| 方案 | 改动 | 优劣 |
|---|---|---|
| **A. 让 crypto 回测走 combined_factors 路径（推荐）** | 回测时强制用 `conf_combined_factors.yaml`，让 runner 注入自定义信号 | 最小改动，复用 A 股已有逻辑 |
| **B. `conf_crypto.yaml` 显式指定信号源** | `<PRED>` → 具体信号路径 | 需了解 Qlib 信号注入机制 |
| **C. 回测前因子写入 qlib feature** | `factor_calculate` 后加一步持久化 | 最稳健，改动大 |

**推荐方案 A**：让 crypto 回测也走 `combined_factors` 路径。

---

## 七、附加观察

1. **`MARKET_TYPE=crypto` 是否真正触发了 prompt 切换？**
   - 日志里 LLM 生成的假设/direction 仍然提到"个股""隔夜收益"等 A 股术语
   - 需在日志里确认 scenario 背景是否包含 "TOP-50 CRYPTOCURRENCIES" 字样
   - 如果 prompt 切换未生效，实际生成的因子永远是 A 股风格

2. **`<PRED>` 机制理解**
   - A 股 `conf_baseline.yaml` 的 `<PRED>` 由 runner 在回测时动态替换
   - crypto 的 `conf_crypto.yaml` 应该是独立触发回测（无上游 mining），但 `<PRED>` 依赖被注入的 model/dataset，导致无法匹配
