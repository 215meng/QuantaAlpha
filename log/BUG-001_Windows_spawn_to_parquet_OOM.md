# BUG-001 | Windows spawn 子进程 to_parquet OOM

- **状态**：已修复（`c9bd230` 代码 + `6968f17` 文档）
- **发现日期**：2026-07-18
- **根因日期**：2026-07-19（spawn-fork 平台差异）
- **模块**：`quantaalpha/factors/runner.py:168`、`quantaalpha/core/utils.py:194`

---

## 1. 现象

因子回测**成功**，但输出阶段崩溃，整轮 evolution 最终 `Top 0 trajectories`。

```
ERROR Task 0 failed: malloc of size 1776960 failed
```

1776960 字节 = 1.69 MiB，一个极小分配却失败 → 不是容量不够，是 Windows spawn 子进程里内存碎片 / pyarrow 按列并发分配时连续块申请失败。

## 2. 调用链

```
factor_mining.py:212  _parallel_task_worker   ← 子进程
loop.py/...           factor_backtest
runner.py:168         combined_factors.to_parquet(parquet_path, engine="pyarrow")
  └─ pyarrow.lib.Table.from_pandas → _ndarray_to_array → malloc(1776960) FAILED
```

## 3. 根因

代码层与 upstream 完全对齐，差异在运行环境：

| 维度 | 上游 (Linux) | 本项目 (Windows) |
|---|---|---|
| multiprocessing 模式 | fork | spawn（强制）|
| 子进程内存起点 | 小（CoW） | 大（重走一次 pandarallel/qlib 初始化）|
| pyarrow 时余量 | 充足 | 紧张 |

## 4. 修复 diff（commit c9bd230）

```python
# runner.py: to_parquet 前三板斧
gc.collect()
pyarrow.set_cpu_count(1)
# MultiIndex object levels → category
new_levels = [idx.levels[i].astype('category') if idx.levels[i].dtype==object else idx.levels[i] ...]
combined_factors.index = combined_factors.index.set_levels(new_levels)
# MemoryError 兜底
try:
    combined_factors.to_parquet(parquet_path, engine="pyarrow")
except MemoryError:
    combined_factors.to_parquet(parquet_path, engine="pyarrow", compression="none")

# utils.py: cache pickle 静默兜底
try:
    pickle.dump(result, f)
except (MemoryError, OSError) as e:
    logger.warning(...)
```

## 5. 验证

- runner/utils import OK
- object→category 压缩：635KB → 10KB（**1.6%**）
- pyarrow 转换正常
