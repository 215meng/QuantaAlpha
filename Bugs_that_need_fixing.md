# Bugs that need fixing

> 每个 bug 的状态：`待审核` → `已审核（待执行）` → `已修复（已归档）`。
> 修复执行后，bug 归档到 `log/` 文件夹，并从本文件移除（仅保留摘要）。

---

## BUG-002 | crypto 开发污染 A 股共享配置文件（A 股读到 crypto 提示）【已修复归档】

- **状态**：已修复（`b2a2d14`）→ 归档至 `log/BUG-002_配置文件按市场隔离.md`
- **日期**：2026-07-18

> 根因：提交 `5d05ebc` 把 crypto 内容写入共享的 `experiment.yaml` / `prompts.yaml` / `README.md`，A 股读到 crypto 提示。
> 修复：A 股文件 git 回退到 `5d05ebc` 之前（被污染前）；crypto 独立持有 `prompts_crypto.yaml` + `README_crypto.md`；`market_config.py` 新增 `get_prompts_file()` / `get_readme_file()`；`proposal.py` / `feedback.py` / `qlib_utils.py` 全部改为市场感知。

---

## BUG-001 | 主进程 to_parquet OOM（pyarrow malloc 1776960 failed）【已修复归档】

- **状态**：已修复（`c9bd230`）→ 归档至 `log/BUG-001_Windows_spawn_to_parquet_OOM.md`
- **日期**：2026-07-18（修复 2026-07-19）
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

### 8. 为什么原项目（upstream）没有这个问题？（2026-07-19 更新）

代码层完全对齐（runner.py / utils.py / factor_mining.py / conf.py / multi_proc_n 完全一样），**差异仅在运行环境**：

| 维度 | 上游原项目 | 本项目（当前） |
|---|---|---|
| **目标平台** | **Linux**（README 明确 "natively developed for Linux"；`docs/WINDOWS_COMPAT.md` 的 Windows 规则全部是 workaround）| Windows 11（原生） |
| **运行方式** | Docker 容器 或 Linux 主机（exec 链路走 `QlibLocalEnv` 在 **Linux 子进程**） | Windows 本地 `QlibLocalEnv`（自己就是子进程） |
| **multiprocessing 启动模式** | 默认 **fork**（共享父进程地址空间，Copy-on-Write） | 强制 **spawn**（Windows 唯一可选：重新 import 模块 + 重新初始化所有全局对象） |
| **子进程内存起点** | fork：起步小，CoW 按需复制 | spawn：每新进程重新 import → `pandarallel.initialize()`、qlib 加载、多层 DataFrame **全量重建** |
| **pyarrow 转换时的剩余余量** | 大（Linux + fork + Docker 内存上限宽） | 小（spawn 初始化吃掉大量内存 + Windows 家庭版无 pagefile 弹性） |
| **历史 Windows 文档提及** | `select.poll()` / `/bin/sh` 替代等 workaround，**从未** 提及 parquet/内存/OOM | — |

**结论：BUG-001 是 Windows + spawn-fork 差异叠加的"平台特异性 bug"，上游在 Linux+Docker+fork 下永远触发不了。** 这也解释了为什么 f488feb 修复（子进程 ARROW 节流）能保住 Linux 子进程：它只覆盖了 Linux 一侧，漏网的是 Windows 主进程侧的 to_parquet。

> 推论：修复必须落在「主进程 to_parquet 前回收 + 限制 pyarrow 线程」上（方案 A+B），而不是照搬 Linux 子进程的 env 注入——二者内存路径不同。
