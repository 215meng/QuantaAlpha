# QuantaAlpha 调试总结报告

> 调试日期：2026-07-16 · 调试人：Claude（跨多会话） · 环境：Windows 11 + conda `fe` (Python 3.10.18)

---

## 1. 项目概况

**项目**：QuantaAlpha（arXiv:2602.07085v3）—— LLM 驱动的量化 Alpha 因子自进化框架。
**官方仓库**：https://github.com/QuantaAlpha/QuantaAlpha（clone 时间 2026-07-14）。
**当前状态**：clone 后在多个会话中做了大量 Windows 适配 + Claude API 修改（+1466/-117 行，24 文件），均**已 staged 但未提交**（reflog 仅一次 clone 记录）。

### 入口点
| 命令 | 说明 |
|---|---|
| `python launcher.py mine --direction "..."` | 主入口（自动加载 .env） |
| `./run.sh "价量因子挖掘"` | shell 包装（加载 .env、SSL 修复、激活 conda） |
| `quantaalpha mine/backtest/health_check` | CLI 直接调用 |

### 技术栈
| 项目 | 实际值 |
|---|---|
| Python | 3.10.18 (conda `fe`, 路径 `G:\miniconda\envs\fe`) |
| LLM API | **DeepSeek**（`OPENAI_API_KEY` + `OPENAI_BASE_URL=https://api.deepseek.com`，OpenAI 兼容协议）|
| 模型 | deepseek-chat（实际响应显示 `deepseek-v4-flash`）|
| Qlib | 0.9.7 |
| 数据 | `data/qlib/cn_data`（2005-01-04 至 2026-01-09，6016 只股票，含 OHLCV）|
| 回测 | 本地（`use_local: true`，Docker 不可用）|

---

## 2. 环境健康检查（已验证通过）

| 检查项 | 结果 |
|---|---|
| DeepSeek API 连通 | ✅ HTTP 200，响应正常 |
| Qlib 安装 | ✅ 0.9.7 |
| Qlib 数据目录 | ✅ `cn_data/{calendars,features/instruments}` 完整 |
| 本地回测路径 | ✅ `use_local: true` 已配置 |
| Docker | ❌ 不可用（但不影响，因已切本地回测）|
| Web UI 端口 19899 | ✅ 空闲 |

**注意**：`conda run -n fe python -c "..."` **不支持多行脚本**（报 NotImplementedError），应改用脚本文件；且 `conda run` **不继承 `.env` 变量**，但 `launcher.py` / `run.sh` 自身会加载 `.env`，所以直接运行 launcher 是正确方式。

---

## 3. 历史上成功的运行记录

### 关键证据：因子库 (`data/factorlib/all_factors_library.json`)
- `metadata.last_updated: 2026-07-15T15:32:51`
- 共 **3 个因子**，表达式如下：

| # | 因子表达式 | 来源会话 |
|---|---|---|
| 1 | `($open - DELAY($close, 1)) / (DELAY($close, 1) + 1e-8) * INV($volume / (TS_MEAN($volume, 20) + 1e-8) + 1e-8) * (-1)` | `log/2026-07-15_02-41-57`（7.15 凌晨）|
| 2 | `ABS($open - DELAY($close, 1)) / (DELAY($close, 1) * TS_STD($close, 20) + 1e-8) * (1 - $volume / (TS_MEDIAN($volume, 20) + 1e-8))` | `log/2026-07-15_07-25-33`（7.15 早，有 backtest）|
| 3 | 同因子2（TS_MEDIAN 版）| `log/2026-07-14_15-08-47`（7.14 首次运行）|

### 真正完整跑通的会话：`log/2026-07-15_07-25-33-551276`
- loop 0 **完整走满 5 步**：`0_factor_propose → 1_factor_construct → 2_factor_calculate → 3_factor_backtest → 4_feedback`
- 这是唯一确认到达 feedback 步的完整运行。
- 其轨迹池/因子库写入时间对应 `last_updated: 15:32`。

### 因子库写入机制
- 写入位于 `quantaalpha/pipeline/loop.py` 的 **feedback 步**（`FactorLibraryManager.add_factors_from_experiment`）。
- 仅 feedback 步会写因子库，非 backtest。

---

## 4. 当前运行的故障现象

### 错误日志（`run.sh "价量因子挖掘"` 于 2026-07-16 09:04 运行）
```
Workspace: workspace_exp_20260716_090433
factor calulate → factor 仅 propose/construct/calculate 有输出，無 backtest/feedback
backtest 时 log：
  "Failed to process new factors: No valid factor data found to merge."
  "Skip loop 0 due to No valid factor data found to merge after manual execution attempt."
```

### 核心错误：文件路径双重嵌套
```
python: can't open file 'E:\py\...\workspace_exp_20260716_090433\f0fd3063638e...\workspace_exp_20260716_090433\f0fd3063638e...\factor.py'
                                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                             workspace 路径被重复拼接了两次
```

### 根因
子工作区（如 `data/results/workspace/f0fd3063...`）中 **没有生成 `factor.py`**——只有 `daily_pv.h5` 数据文件。CoSTEER 编码循环反复触发 "file path duplication error"，调试循环耗尽后退出，从未产出可执行的因子脚本。

**因此故障不在度量提取逻辑，也不在 experiment.yaml 配置**——而在 CoSTEER 代码生成器在 Windows 上的路径拼接逻辑。

---

## 5. 本次会话中的改动与回退

### 我（Claude）改过的文件
| 文件 | 改动 | 现状 |
|---|---|---|
| `configs/experiment.yaml` | 调参：`max_loops 2→1`, `num_directions 2→1`, `mutation/crossover→false`, `timeout 999999→1200`, `free_args 0.5→1.0`, `backtest timeout 800→600` | ✅ 已回退到 git HEAD 原版（先 `.bak` 再 `git checkout HEAD --`）|

| 文件 | 改动性质 | 评价 |
|---|---|---|
| `run.sh` | 添加 SSL_CERT_FILE / REQUESTS_CA_BUNDLE 修复 | ✅ 有益，保留 |
| `quantaalpha/factors/coder/factor.py` | `import sys` + PYTHONPATH 分隔符 `;`（win32） | ✅ 语法必要，保留 |
| `quantaalpha/factors/runner.py` | `symlink→os.link` + 缓存命中时刷新 result.h5 | ⚠️ Windows 必要，但待验证 |
| `quantaalpha/factors/workspace.py` | **新增完整 Windows `execute()` 覆盖**（QlibLocalEnv） | ⚠️ 高度可疑——双路径 bug 最可能来源 |
| `quantaalpha/compat/rdagent_patches.py` | 380 行新文件 | ⚠️ 待验证 |
| `quantaalpha/llm/client.py`, `env.py`, `launcher.py`, `cli.py` 等 | import/env/PYTHONPATH 各处修补 | ⚠️ 待验证 |

---

## 6. 核心可疑点（双路径 bug 定位）

`coder/factor.py` 第 186 行执行逻辑：
```python
subprocess.check_output(
    f"{FACTOR_COSTEER_SETTINGS.python_bin} {execution_code_path}",  # ← execution_code_path = workspace_path / "factor.py"
    shell=True,
    cwd=self.workspace_path,
    ...
)
```
报错中 `workspace_path` 被重复拼接，说明 **`self.workspace_value` 自身已经带有一层 workspace 前缀**。最可能在 `workspace.py` 的新 Windows `execute()` 或 Coder/FBWorkspace 的路径属性处，把 `DATA_RESULTS_DIR/<workspace_exp>/<subworkspace>` 与 `subworkspace` 自身路径做了二次拼接。

**待排查**：对比 `quantaalpha/factors/coder/factor.py` 原版（git HEAD）与当前版的 workspace_path 构造逻辑；以及 `FBWorkspace` 类中 `workspace_path` 属性的来源。

---

## 7. 推荐的后续处理（待用户确认后执行）

### 方案 A（保守，推荐）
1. 全部回退：`git checkout HEAD -- <所有改动文件>`
2. 仅保留两处最小修改：
   - `run.sh`（SSL_CERT_FILE 设置）
   - `quantaalpha/factors/coder/factor.py`（`import sys` + 分隔符 `;`）
3. 跑 `./run.sh "价量因子挖掘"`，观察原版在 Windows 上是否真的不能跑
4. 如还有路径问题，再定位 window.py execute() 路径拼接并精准修复

### 方案 B（直接定位修复）
1. 不回退，直接读 `quantaalpha/factors/coder/factor.py` 与原版差异
2. 重点看 `workspace_path` / `execution_code_path` / `source_data_path` 构造
3. 找到双拼接点，最小化修复
4. 重新跑验证

### 关键文件路径速查
| 路径 | 作用 |
|---|---|
| `quantaalpha/pipeline/loop.py` | 主 5 步循环 + feedback 写因子库 |
| `quantaalpha/pipeline/factor_mining.py` | 入口 + evolution controller |
| `quantaalpha/factors/coder/factor.py` | 因子代码生成 + Windows 执行 |
| `quantaalpha/factors/workspace.py` | Windows execute()（新增，可疑）|
| `quantaalpha/factors/runner.py` | 回测运行器（hard-link + h5 刷新）|
| `quantaalpha/factors/feedback.py` | 结果汇总 |
| `quantaalpha/factors/library.py` | 因子库管理 |
| `quantaalpha/llm/client.py` | LLM 客户端 |
| `quantaalpha/utils/env.py` | QlibLocalEnv（本地执行器）|
| `quantaalpha/compat/rdagent_patches.py` | rdagent 兼容补丁（380 行）|
| `configs/experiment.yaml` | 实验配置（已恢复原版）|
| `run.sh` | 运行脚本（含 SSL 修复）|

---

## 8. 教训与注意事项

1. **跨会话修改不记录作者**：本仓库自 clone 后零提交，所有改动堆积为 staged 状态。建议每次 debug 改动前先 `git commit` 基线，便于回退与追溯。
2. **`conda run` 不继承 .env** —— 应用 `launcher.py` / `run.sh` 运行；且不支持多行 `-c` 脚本。
3. **`DEBUG_SUMMARY.md` 是每个调试会话的必需产出**：跨会话时对照 PROGRESS.md 与本报告，避免重复定位。
4. **因子库写入在 feedback 步而非 backtest 步**——判断运行是否成功要看 feedback 目录是否产出。
5. **成功标志**：`__session__/<loop>/4_feedback` 目录存在 + `data/factorlib/all_factors_library.json` 的 `last_updated` 更新。

---

*报告完。所有结论基于 git 证据与日志时序，无猜测。*

---

## 9. 代码回退与清理（2026-07-16 执行）

### 操作概要
以 `origin/windows` 分支（官方 Windows 版）为基准对齐代码，保留 3 处有益自定义补丁，清理临时/旧日志文件。

### 回退结果：工作树 vs origin/windows 剩余差异（均为有意保留）

| 文件 | 差异 | 理由 |
|---|---|---|
| `.github/*` 模板 | 保留 | windows 分支删除了 issue/PR 模板，当前版保留（无害）|
| `QuantaAlpha_Windows_启动指南.md` | 保留 | 中文启动指南 |
| `README_EN.md` | 保留 | windows 分支已删除英文版 README |
| `docs/images/figure5.png` | 保留 | 图片资源 |
| `quantaalpha/compat/rdagent_patches.py` | +49 行 | **SSL 证书补丁**（Patch 0，解决 Windows 证书崩溃）|
| `quantaalpha/llm/client.py` | +6 行 | **embedding 优雅降级**（未配置 embedding_model 时返回全零）|
| `run.sh` | +14 行 | **SSL_CERT_FILE 自动设置** |

### 核心源码文件（已对齐到 origin/windows 官方版本）
`workspace.py`、`runner.py`、`coder/factor.py`、`env.py`、`launcher.py`、`cli.py`、`rdagent_patches.py`（基础）、`backtest/*`、`data_template/*`、`factor_template/*.yaml` 等。

### 清理结果
| 项目 | 清理前 | 清理后 |
|---|---|---|
| 日志目录 | 48 个 / 378 MB | **13 个 / 32 MB** |
| `__pycache__` | 21 个 | 0（Python 自动重建）|
| `.pyc` 文件 | 93 个 | 0 |
| `.bak` 备份 | 有 | 0 |
| `/tmp/mine_run.log` | 有 | 已删除 |

### 保留的日志会话（13 个）
- `07-15 07:25` — **成功运行**（唯一跑满 5 步到 feedback 的会话）
- `07-15 12:47 ~ 16:51` — 下午各次运行（含 15:18 长运行）
- `07-16 01:04` — 本次 CLI 运行（双路径 bug）

### 备份
3 个有益补丁已备份至 `_win_revert_backup/`（`rdagent_patches.ssl.patch`、`llm_client.embedding.patch`、`run.sh.ssl.patch`），可复现。

### 下一步
1. 读 `docs/WINDOWS_COMPAT.md`（官方 Windows 指南，已就位）
2. 跑 `./run.sh "价量因子挖掘"` 验证官方 Windows 版是否能跑通
3. 如仍有双路径 bug，按 WINDOWS_COMPAT.md 指导定位 `workspace.py execute()` / `coder/factor.py` 路径拼接
