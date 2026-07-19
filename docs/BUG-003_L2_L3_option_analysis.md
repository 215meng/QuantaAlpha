# BUG-003 L2/L3 修复选项分析

> 针对 `docs/CODE_PLAN_market_aware_runner.md` 确认的 BUG-003 子任务 L2（A 股数据泄漏）+ L3（factor.py 列名 bug）。

## 现状速览

- ✅ L1（runner 调度）：已修，本次 crypto mining 验证 `runner_crypto` 已启用
- ❌ L2（A 股数据泄漏）：`runner_crypto.py:59` 硬编码 `FACTOR_COSTEER_SETTINGS.data_folder` = A 股源，crypto workspace 内 h5 实际是 A 股（instrument 含 SH000300 等）
- ❌ L3（factor.py 模板列名 bug）：`template.jinjia2:19` 双重替换 + 列名重叠误匹配

## 前置决策：crypto 版 `daily_pv.h5` 从哪来

| 选项 | 动作 | 是否已有工具 |
|---|---|---|
| C（推荐） | **新增预处理脚本**，读 `others/50币/50币/前 50 种加密货币历史（2020-2025 每小时）` 50 个 CSV → 降采样到日 → 合成 1 个 crypto 版 `daily_pv.h5`，放入 `git_ignore_folder/factor_implementation_source_data_crypto/` | 有 `data_template/crypto_to_qlib_bin.py` 作参考 |

现有 crypto CSV 数量：**50 个交易对**、每小时、7 列（open/high/low/close/volume_from/volume_to）含 2020-2025。

**输出**：1 个 h5 文件，结构对齐现有 A 股 h5：
- 列：`$open` / `$close` / `$high` / `$low` / `$volume` / `$return` / `$factor`
- index：`datetime`, `instrument`（如 `BTC/USDT`, `ETH/USDT`）
- 频率：日（crypto 7×24 交易，按自然日聚合）

## 候选方案对比

| 选项 | 描述 | 优点 | 缺点 |
|---|---|---|---|
| **A. 仅修 L3** | 只修 template 列名 bug + 保留 L2 | 改动小，立即验证 L1 修复价值 | crypto 仍在 A 股数据上跑（instrument SH600000），因子看似能生成但实质是股票因子换名；"修了但白修" |
| **B. 等外部 crypto daily_pv** | L3 先修，等你捞出 crypto daily_pv 后再修 L2 | 数据你来，我管代码 | 周期长；前置阻塞；无法立即端到端验证 |
| **C. L3 +预处理脚本同步** | 修 L3 + **我写预处理脚本从 50 个 CSV 合成 crypto daily_pv.h5** + 修 L2 调度 | 完整修复；端到端验证；**改动与数据同步就绪，不阻塞**；数据完整（50 币、5 年、每小时→降采样日）| 预处理脚本需 ~50 行 Python（一次性），本周可完成 |

## 推荐方案：**C**（L3 同步）

**理由**：

1. **A 股数据同源的问题必须解决**：L1 修复已走通 runner 调度（日志 `runner_crypto.develop:134`），但因子 workspace 内装的还是 A 股数据。这意味着即使因子能生成，得到的证券代码还是 SH600000/SZ300000，与 crypto_50 数据集完全两个市场——**因子实盘价值为 0**。选项 A "只修 L3" 本质是在帮一个错误系统能跑通，没有商业价值。

2. **CSV 数据现成、50 币齐全**：原始 CSV 就在仓库 `others/50币/`，无需额外数据源。按 crypto CSV 工具（`data_template/crypto_to_qlib_bin.py`）的处理逻辑，重写一份**专门合成 factor.py 用的 daily_pv.h5** 是可行且较小的工作量。

3. **工具链已存在**：`quantaalpha/factors/data_template/crypto_to_qlib_bin.py` 已提供`crypto → qlib bin`的参考实现（含小时→日聚合、`$factor=1.0`、instrument 等逻辑）；本任务只需**改编**为 factor.py 需要的 h5 格式。

4. **L3 独立可发布**：template 列名 Crypto 修复（`expr_parser.py` + `template.jinjia2`）对 **A 股同样受益**（消除列名重叠误替换隐患），L2+L3 可以合并为 1 个 PR。

## 实施方案（选项 C）

### 步骤 1：修 L3（factor.py 列名 bug）
- 改 `quantaalpha/factors/coder/expr_parser.py:parse_symbol` 用 `\b...\b` 单词边界
- 删 `template.jinjia2` 第 18-19 行的 for 循环（parse_symbol 已单轮完成）

### 步骤 2：写预处理脚本 `scripts/build_crypto_daily_pv.py`
- 读 `others/50币/50币/前 50 种加密货币历史（2020-2025 每小时）/*.csv`
- 处理：7 列 → 6 列（drop `volume_to`，用 `volume_from` 作 `$volume`）；小时→日聚合（OHLC 标准 + 日末 close + 日 sum volume）；instrument 列加 `/USDT` 后缀；$return = close.pct_change；$factor = 1.0
- 输出：`git_ignore_folder/factor_implementation_source_data_crypto/daily_pv.h5`

### 步骤 3：修 L2（A 股数据泄漏）
- `runner_crypto._force_relink_daily_pv` 按 `MARKET_TYPE` 选数据源：crypto → `factor_implementation_source_data_crypto`；A 股 → `factor_implementation_source_data`

### 步骤 4：验证
- `python scripts/build_crypto_daily_pv.py` → h5 文件存在，instrument 为 `BTC/USDT` 等
- crypto mining 全流程：日志 `[crypto] Execute factor backtest` + crypto_50 / AAVEUSDT + **workspace daily_pv.h5 instrument 是 BTC/USDT 而非 SH000300**
- A 股全流程回归：保持原行为（默认 `factor_implementation_source_data`）

## 交付物

| 文件 | 作用 |
|---|---|
| `quantaalpha/factors/coder/expr_parser.py` | parse_symbol 改为单词边界正则 |
| `quantaalpha/factors/coder/template.jinjia2` | 删 for 循环，信任 parse_symbol 单轮结果 |
| `scripts/build_crypto_daily_pv.py` | 50 个 CSV → crypto daily_pv.h5 |
| `git_ignore_folder/factor_implementation_source_data_crypto/daily_pv.h5` | 输出（git ignore，本地唯一）|
| `quantaalpha/factors/runner_crypto.py:59` | MARKET_TYPE 感知的 data_folder 切换 |
