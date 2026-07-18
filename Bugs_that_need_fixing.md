# Bugs that need fixing

> 每个 bug 的状态：`待审核` → `已审核（待执行）` → `已修复（已归档）`。
> 修复执行后，bug 归档到 `log/` 文件夹，并从本文件移除。

---

## BUG-002 | crypto 开发污染 A 股共享配置文件（A 股读到 crypto 提示）

- **状态**：已审核（待执行）
- **日期**：2026-07-18
- **严重度**：高（A 股产出 crypto 风格因子/报错，与 crypto 报错同源）
- **模块**：`quantaalpha/factors/prompts/experiment.yaml`、`prompts.yaml`

### 1. 现象

win-debug 分支原本 A 股全链路可跑通。新增加密货币功能（`feature/crypto-data` 分支）后，A 股开始报错，且**报的错与加密货币一样**。

### 2. 根因

crypto 开发把差异内容直接写入了**共享配置文件**，未隔离到 crypto 专属文件：

| 文件 | win-debug（A 股原版） | crypto-data 后被改成 |
|---|---|---|
| `experiment.yaml` | CSI300、SH600000、Test 到 2024-12-01 | 加了 "top-50 cryptocurrencies"、BTCUSDT、Test 到 2025 |
| `prompts.yaml`（仅 `factors/prompts/`） | 11 处 "stock" 措辞 | 11 处改成 "asset" |

而加载路径 `proposal.py` / `feedback.py` 4 处全部硬编码 `prompts.yaml`，不按市场区分 → A 股直接读到了 crypto 内容。

> conf 文件（`conf_baseline.yaml` 等）反而是干净的：A 股 / crypto 已分开。

### 3. 修复方案（已审核通过）

用户明确：「每个市场拷贝一份配置文件，前端选哪个就指向哪个；A 股保持 win-debug 原样；A 股子市场（csi300/500/sp500）保持 win-debug 共用一份」。

1. `experiment.yaml` → `git checkout win-debug` 还原为纯净 A 股
2. `prompts.yaml` → 还原为 win-debug "stock" 措辞
3. 新建 `prompts_crypto.yaml`（crypto "asset" 措辞独立副本）
4. `market_config.py` 新增 `get_prompts_file()`，按 `MARKET_TYPE` 返回对应文件
5. `proposal.py`（2 处）+ `feedback.py`（2 处）共 4 个加载点改为 `get_prompts_file()`

### 4. 与 BUG-001 的关系

配置污染 ≠ OOM。但 A 股被喂了 crypto 提示后，LLM 会按 crypto 风格生成因子，可能**叠加**放大 OOM 触发概率。二者并列修复。

### 5. 关联改动

- `quantaalpha/factors/market_config.py`：+`get_prompts_file()`
- `quantaalpha/factors/proposal.py`：2 处加载点切换 + 导入
- `quantaalpha/factors/feedback.py`：2 处加载点切换 + 导入
- `quantaalpha/factors/prompts/prompts_crypto.yaml`：新建（crypto 独立副本）
- `experiment.yaml` / `prompts.yaml`：还原为 win-debug 原版

## BUG-001 | 主进程 to_parquet OOM（pyarrow malloc 1776960 failed）

- **状态**：待审核
- **日期**：2026-07-18
- **严重度**：高（阻断 evolution 全流程，0/1 任务成功）
- **模块**：`quantaalpha/factors/runner.py:168`

### 1. 现象

```
ERROR Task 0 failed: malloc of size 1776960 failed
```

回测结果**已成功算出**（IC=0.0081, l2.valid=0.9969），但在写 parquet 时崩溃，导致整轮 evolution `Top 0 trajectories`、`successful_trajectories: 0`。

### 2. 调用链

```
factor_mining.py:307  _run_tasks_parallel
factor_mining.py:212  _parallel_task_worker   ← 子进程入口（本身是 Process）
factor_mining.py:159  _run_evolution_task
workflow.py:113       model_loop.run()
loop.py:176           factor_backtest
runner.py:168         combined_factors.to_parquet(...)   ← 💥 崩溃点
  └─ pyarrow dataframe_to_arrays → pa.array(col) → malloc(1776960) FAILED
```

### 3. 崩溃点代码

`quantaalpha/factors/runner.py:166-169`

```python
parquet_path = exp.experiment_workspace.workspace_path / "combined_factors_df.parquet"
combined_factors.to_parquet(parquet_path, engine="pyarrow")   # ← 崩在这里
```

### 4. 根因

`malloc(1776960)` = **1.69 MiB** 小分配失败 → **不是分配太大，是进程堆已耗尽，连 1.7MB 都给不出**（经典 OOM）。
`1776960 = 222120 × 8 字节`，恰等于 `combined_factors` 单列大小，印证是 pyarrow 按列构建连续数组时触发。

此刻 OOM 的贡献因子（按影响排序）：

| # | 因子 | 说明 |
|---|---|---|
| ① | **pyarrow 转换瞬时尖峰** | pandas 块状内存 → pyarrow 连续数组需 **2–3×** 临时内存，并在**线程池按列并发分配**（traceback 中 `concurrent.futures.thread`），所有列同时要连续内存，瞬间顶穿 |
| ② | **`combined_factors` 的 MultiIndex 开销** | 行索引 `(datetime, instrument)` 中 `instrument` 为字符串，~222k 行 × 字符串对象开销 ≈ 数百 MB |
| ③ | **`pandarallel.initialize()`**（runner.py:13） | 模块加载时启动持久化子进程池，占用系统 RAM |
| ④ | **`multiprocessing_wrapper` n=1 内联执行**（runner.py:216-19） | 所有因子 DataFrame 全程留在主进程，不像子进程退出即释放 |

### 5. ⚠️ 历史修复未覆盖本次崩溃（关键判断）

提交 **`f488feb`**（[env] fix: Windows 子进程注入 OMP/MKL/ARROW 单线程节流变量）曾修复 OOM，但**仅作用于 `QlibLocalEnv.run()` 派生的回测子进程**。

| 维度 | 历史修复（f488feb） | 本次崩溃 |
|---|---|---|
| 崩溃进程 | 子进程（qrun / read_exp_res） | **主进程**（`_parallel_task_worker` 内） |
| 崩溃位置 | 子进程 pyarrow IO | `runner.py:168` **to_parquet** |
| 时序 | `execute()` 内部 | `execute()` **之前**（168 行 vs 180+ 行） |
| 线程控制 | ✅ OMP/MKL/ARROW=1 | ❌ 完全没有 |

全项目 grep 确认：`OMP/MKL/ARROW` **仅在 `env.py:174-176`** 设置，主进程侧（runner.py / pipeline / core）零设置。

**结论：同一根因在新位置的复现 / 漏网**——分配 size 完全一致（1776960 字节），但历史修复只堵了子进程。

> 附加细节：`OMP_NUM_THREADS` 控制 OpenMP，**pyarrow 自有线程池并不读它**，pyarrow 并行列转换需走 `pyarrow.set_cpu_count()` 才能限制。所以子进程当时能挡住主要靠 `ARROW_IO_THREADS` + 降低 MKL 峰值，对 pyarrow CPU 池的约束在主进程仍缺失。

### 6. 建议修复方向（待审核）

延续 f488feb 思路，但把「线程节流」补到**崩溃真正发生的主进程位置**（runner.py:168 `to_parquet` 前），而非照搬子进程三行：

| 方案 | 思路 | 侵入性 |
|---|---|---|
| **A. 线程节流 + 释放中间对象**（推荐） | `to_parquet` 前 `del` 中间大对象（factor_dfs、corr 结果）+ `gc.collect()`；并用 `pyarrow.set_cpu_count(1)` 限制 pyarrow CPU 池并联列转换峰值 | 小 |
| **B. index 压缩** | 把 `instrument` 字符串索引转为 category，压低 MultiIndex 与 pyarrow 转换峰值 | 小 |
| **C. 落盘子进程** | 把 `to_parquet` 这步挪到 `QlibLocalEnv` 子进程完成，写毕即释放主进程内存 | 较大 |

可组合 A + B 一起上。

### 7. 关联历史

- commit `f488feb`：子进程 OMP/MKL/ARROW 节流（quantaalpha/utils/env.py）
- 文档《因子表达式变量幻觉问题分析与修复.md》第 170 行记为「并发问题⑤」
