# CODE_PLAN: 市场感知 runner 调度（修复 BUG-003）

> 目标：前端 Settings 页选 `crypto`/ `a_stock` 后，**整个 mining 流程**（prompt / 配置 / 数据集 / runner）自动切换到对应市场。
> 修复 BUG-003 根因：`settings.py` 硬编码 A 股 runner + `runner.py:198` 硬编码 A 股配置名（忽略 `QLIB_RUNNER_CONFIG`）。

---

## 1. 设计概览

### 1.1 控制变量：`MARKET_TYPE`（单一真源）

唯一的环境变量决定市场类型。前端 Settings 页 → `updateSystemConfig` → `.env` → 后端 `_run_mining` 注入子进程。

```
前端 Settings
   └─ @change defaultMarket → updateSystemConfig({ MARKET_TYPE, QLIB_RUNNER_CONFIG })
                                 ↓ 持久化
                              .env (仓库根)
                                 ↓ mining 启动时读取
                              _run_mining → env["MARKET_TYPE"] = "crypto"
                                 ↓ 子进程
                              settings.py:_select_runner_cls() 读 MARKET_TYPE
                              runner.py:198             读 QLIB_RUNNER_CONFIG
                              experiment.py:get_prompt_file() 读 MARKET_TYPE
```

### 1.2 改动点（3 处，全在后端）

| # | 文件 | 改动 | 动机 |
|---|---|---|---|
| 1 | `quantaalpha/pipeline/settings.py` | 新增 `_select_runner_cls(market_type)` 函数，按 MARKET_TYPE 返回 runner 类；替换 3 处硬编码 | 启用 `runner_crypto.py` |
| 2 | `quantaalpha/factors/runner.py:198` | `config_name = os.environ.get("QLIB_RUNNER_CONFIG") or <原硬编码默认>` | 尊重 .env 显式覆盖 |
| 3 | `frontend-v2/backend/app.py:_run_mining` | 注入 `MARKET_TYPE` + `QLIB_RUNNER_CONFIG` 到子进程 env | 让 mining 启动时 market 选择实时生效，不依赖进程继承的 .env |

### 1.3 不变

- `market_config.py`（已正确）
- `runner_crypto.py`（已正确，**仅被 settings.py 选中即可生效**）
- `experiment.py` `get_prompt_file()`（已按 MARKET_TYPE）
- `factor_template/*.yaml` 5 个 crypto 模板（已齐全）
- 前端 `InputPanel` mining start **不加** 新字段（保持 6 字段，市场配置仍走 Settings 页持久化）

---

## 2. 详细实现

### 2.1 `settings.py` —— 新增 runner 工厂

```python
# quantaalpha/pipeline/settings.py

import os
from quantaalpha.factors.market_config import get_market_type  # 复用


def _select_runner_cls(market_type: str | None = None) -> str:
    """根据 MARKET_TYPE 返回 runner 类路径。
    - crypto → QlibFactorRunnerCrypto（继承原版 + crypto 配置选择 + daily_pv re-link）
    - 其他  → QlibFactorRunner（A 股默认）
    """
    mt = (market_type or get_market_type()).lower().strip()
    if mt == "crypto":
        return "quantaalpha.factors.runner_crypto.QlibFactorRunnerCrypto"
    return "quantaalpha.factors.runner.QlibFactorRunner"
```

然后修改 3 处 `runner:` 配置：

```python
# 修改位置：FactorAgentSettings / AgentSettings / FactorFromReportSettings
runner: str = _select_runner_cls()  # 替换原来的硬编码
```

> ⚠️ 注意：settings 类定义在 import 时求值，因此 `_select_runner_cls()` 必须在**模块加载时**读取MARKET_TYPE。由于 `_run_mining` 会在 mining 注入 MARKET_TYPE env，且 `settings.py` 会在 mining 启动后被重新 import（子进程），这个时机是合理的。如果担心 import 时机问题，可以改成 lazy 属性（`@property` + 调用处修改）。

### 2.2 `runner.py:198` —— 读取 QLIB_RUNNER_CONFIG

```python
# quantaalpha/factors/runner.py

# 原：
# config_name = "conf_baseline.yaml" if len(exp.based_experiments) == 0 else "conf_combined_factors.yaml"

# 改：
_default_config = "conf_baseline.yaml" if len(exp.based_experiments) == 0 else "conf_combined_factors.yaml"
config_name = os.environ.get("QLIB_RUNNER_CONFIG") or _default_config
```

**效果**：
- 默认（A 股，.env 不设 QLIB_RUNNER_CONFIG）→ 走原路径，**零影响**
- crypto（.env `QLIB_RUNNER_CONFIG=conf_crypto.yaml`）→ 用 crypto baseline（**轮 1**）
  - 轮 2+：仍被 QLIB_RUNNER_CONFIG=conf_crypto.yaml 覆盖，**永远 crypto**（crypto 的 combined 含 crypto_50，不能再切回 A 股 combined）

> 注意：`runner_crypto.py` 已通过重写 `develop`() 直接自己选 `conf_crypto_baseline.yaml` / `conf_combined_factors_crypto.yaml`（见 `_select_config_name`），所以 crypto 分支下 `runner.py:198` 这条线实际不会被 `QlibFactorRunnerCrypto` 走到。但本次仍建议改 `runner.py:198`，理由是：
>  - A 股且 .env 显式设置 QLIB_RUNNER_CONFIG=... 的 Power User 也能被尊重
>  - 作为未来 crypto runner 类的 fallback（避免漏改）

### 2.3 `_run_mining` —— 注入 market env 到子进程（强制覆盖 .env 继承）

```python
# frontend-v2/backend/app.py:_run_mining

# 在 env.update(dotenv) 之后、构建 cmd 之前，加：
market_type = dotenv.get("MARKET_TYPE", "").lower().strip()
if market_type:
    env["MARKET_TYPE"] = market_type
```

**为什么不直接依赖 dotenv**：因为 `env.update(dotenv)` 已经把 `.env` MARKET_TYPE 注入，所以其实**不加这一段也能工作**。加这一段仅为**显式、醒目、防御性**——防止 `.env` 漏设或被 donenv 加载顺序覆盖。

> 建议：可以不加这一段（依赖 dotenv 注入已足够）。若加，放在 `env.update(dotenv)` 之后、`FACTOR_LIBRARY_SUFFIX` 之前。

---

## 3. 保持行为不变（向后兼容）

| 场景 | 修复前 | 修复后 |
|---|---|---|
| A 股，.env 不设 QLIB_RUNNER_CONFIG / MARKET_TYPE | A 股 runner + A 股配置 + A 股 prompt | **完全不变**（default path） |
| A 股，.env 设了 QLIB_RUNNER_CONFIG=conf_crypto.yaml | A 股 runner + A 股配置（忽略 QLIB_RUNNER_CONFIG） ← BUG-003 | A 股 runner + crypto 配置（可能非预期，但尊重 .env）|
| crypto，.env 设了 MARKET_TYPE=crypto + QLIB_RUNNER_CONFIG=conf_crypto.yaml | A 股 runner + A 股配置（忽略 QLIB_RUNNER_CONFIG） ← BUG-003 | **crypto runner（QlibFactorRunnerCrypto）+ crypto 配置 + crypto prompt ✓** |
| crypto 但 .env 漏设 QLIB_RUNNER_CONFIG | A 股 | crypto runner + **轮1 conf_baseline.yaml**（A 股 baseline，可能仍是 A 股数据）|

最后一行“crypto 但 .env 漏设 QLIB_RUNNER_CONFIG”是**未完全隔离的残余风险**，最佳实践中必须在 mining 启动前 Settings 页选 crypto。如要彻底防御，可在 `runner_crypto.py._select_config_name` 里 fallback 默认 `_CFG_ROUND1` 而非继承 runner.py 默认。

---

## 4. 验证清单（实施后勾掉）

- [ ] A 股全流程（不设 MARKET_TYPE）：行为不变（回归）
- [ ] crypto 全流程（MARKET_TYPE=crypto + QLIB_RUNNER_CONFIG=conf_crypto.yaml）：
  - [ ] 子进程实际用 `QlibFactorRunnerCrypto`（日志出现 `[crypto] Execute factor backtest...`）
  - [ ] prompt 实际读 `experiment_crypto.yaml`（prompt 内容含 "asset" / "crypto" 措辞）
  - [ ] 配置文件实际读 `conf_crypto_baseline.yaml` → `crypto_50` / `AAVEUSDT`
  - [ ] daily_pv.h5 被 force re-link 到 crypto 源文件（workspace 内 h5 存在）
  - [ ] combined_factors.parquet 写入成功（BUG-001 修复持续有效）
  - [ ] 因子**不是**股票因子（因子名、IC 值与市场一致）
- [ ] 单元测试：`_select_runner_cls("crypto")` 返回 `...runner_crypto.QlibFactorRunnerCrypto`，`_select_runner_cls("")` / `_select_runner_cls("a_stock")` 返回 `...runner.QlibFactorRunner`
- [ ] 系统测试：完整跑一轮 crypto mining，检查 `evolution_state.json`、`ret.pkl`、最终 Top N trajectories 存在

---

## 5. 回滚方案

整体改动仅 `settings.py` + `runner.py:198` + `backend/_run_mining`（3 处）。**`QlibFactorRunnerCrypto` 无改动**，完全向后兼容 A 股路径。

- 全回滚：`git revert <本次 commit>` 即可恢复 A 股硬编码。
- 最小回滚（仅 A 股 path）：不改动 settings.py；保留 BUG-001 修复。

---

## 6. 本次不做的（超出范围）

- 前端 `InputPanel` market 字段 ← 市场配置已经由 Settings 页持久化，mining start 复用 .env
- 强制 mining 启动时校验 .env 与 Settings 一致性 ← 未来增强
- A 股数据为 crypto_50 子集等共享优化 ← 与本 bug 无关
