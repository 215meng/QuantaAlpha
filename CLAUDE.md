# QuantaAlpha 项目指南

> **版本**: 2026-07-20 · **负责人**: 甘泉晔 (215meng) · **阶段**: A 股基线已稳定可跑；**crypto 市场移植已完成，端到端验证通过**（feature/crypto-data 分支）

---

## 1. 项目概述

**QuantaAlpha**（arXiv:2602.07085v3, 2026-05）是一个通过 **轨迹级自进化（trajectory-level self-evolution）** 驱动 LLM 自动挖掘量化 Alpha 因子的框架。

**核心思想**：将每次端到端的因子挖掘运行视为一条"挖掘轨迹（mining trajectory）"，通过 **变异（mutation）** 和 **交叉（crossover）** 在轨迹层面进化因子，而非依赖带噪声的回测反馈反复重生成。

### 本项目当前目标 ★

在**原有 A 股因子挖掘平台（已本地适配稳定可跑）基础上，新增加密货币（Crypto）市场支持**，并通过前端可视化界面实现**市场切换**：

- **A 股市场** → 使用原有配置（A 股 prompt、A 股数据集、A 股 runner、A 股回测配置）
- **加密货币市场** → 自动调用 crypto 专属配置（crypto prompt、crypto 数据集、crypto runner、crypto 回测配置）

切换后，前端点击"因子挖掘"，平台**自动路由**到对应市场的 prompt 文件、数据集和 Python 脚本。

**与原论文的差异**：
| 维度 | 原论文 | 本项目 |
|---|---|---|
| LLM | GPT-5.2 | **DeepSeek API** (`deepseek-chat`，OpenAI 兼容协议）|
| 市场 | CSI 300/500, S&P 500 | **A 股（CSI -series）+ 加密货币（Top-50 BTC/ETH/...）**|
| 代码 | 官方仓库 | fork + Windows 适配 + DeepSeek 改造 + crypto 移植 |

---

## 2. 仓库信息

| 角色 | 地址 | 说明 |
|---|---|---|
| **你的 fork（origin）** | https://github.com/215meng/QuantaAlpha | 推送改动的主仓库 |
| **官方原版（upstream）** | https://github.com/QuantaAlpha/QuantaAlpha | 上游源码 |

### 关键分支
| 分支 | 说明 | 状态 |
|---|---|---|
| **`main`** | 主工作分支（保持可跑，A 股基线）| ★ 基线 |
| **`win-debug`** | 官方 Windows 兼容版已合并于此，**A 股本地适配已完成** | ★ 稳定 |
| **`feature/crypto-data`** | **当前工作分支** — crypto 市场移植 + 市场切换功能 | 当前 |
| `upstream/windows` | 官方 Windows 版参考（只读）| 参考 |

```bash
origin    https://github.com/215meng/QuantaAlpha.git      ← 你的 fork（push/pull）
upstream  https://github.com/QuantaAlpha/QuantaAlpha.git  ← 官方原版（fetch/merge）
```

---

## 3. 市场切换架构 ★ 核心

### 3.1 全链路：前端 → 后端 → 子进程 → 配置路由

```
前端 SettingsPage
  └─ 用户选择 "defaultMarket=crypto"
  └─ handleSave() 写入 .env：
        MARKET_TYPE=crypto
        QLIB_RUNNER_CONFIG=conf_crypto.yaml
  └─ PUT /api/v1/system config → backend/app.py 写 .env 文件

前端 Mining Dashboard → 点击"开始挖掘"
  └─ POST /api/v1/mining/start（注意：不再传 market 参数，市场由 .env 决定）
  └─ backend/app.py:_run_mining()
        └─ 加载 .env 到子进程 env（含 MARKET_TYPE）
        └─ 启动子进程: python -m quantaalpha.cli mine

子进程启动
  └─ cli.py → factor_mining.py:main()
  └─ pipeline/settings.py:_select_runner_cls()
        └─ 读 MARKET_TYPE → crypto ? QlibFactorRunnerCrypto : QlibFactorRunner
  └─ factors/market_config.py
        └─ get_prompt_file()  → experiment_crypto.yaml / experiment.yaml
        └─ get_prompts_file() → prompts_crypto.yaml / prompts.yaml
        └─ get_readme_file()  → README_crypto.md / README.md
  └─ factors/runner_crypto.py (crypto 时)
        └─ 选 conf_crypto_baseline.yaml（第1轮）/ conf_crypto.yaml（后续轮）
        └─ 强制 re-link daily_pv.h5 → crypto 数据源
        └─ 跳过分钟级过滤（crypto 是日线）
```

### 3.2 市场切换三件套（.env 中的变量）

| 变量 | A 股 | crypto | 作用 |
|---|---|---|---|
| `MARKET_TYPE` | `a_stock`（或不设） | `crypto` | routing 主开关，被 settings.py / market_config.py 读取 |
| `QLIB_RUNNER_CONFIG` | 空（默认 conf_baseline.yaml） | `conf_crypto.yaml` | runner 选择回测配置 |
| `QLIB_DATA_DIR` | `data/qlib/cn_data` | **不变**（crypto_50 路径硬编码在 conf_crypto.yaml 中）| qlib 数据根目录 |

### 3.3 Crypto 专属文件清单（已创建）

| 类别 | 文件 | 说明 |
|---|---|---|
| **Runner** | `quantaalpha/factors/runner_crypto.py` | crypto 专用 runner，继承 A 股原版，覆盖 crypto 差异 |
| **市场路由** | `quantaalpha/factors/market_config.py` | 根据 MARKET_TYPE 选择 prompt/README 文件 |
| **实验 prompt** | `quantaalpha/factors/prompts/experiment_crypto.yaml` | crypto 场景 prompt（含 crypto 数据描述）|
| **因子 prompt** | `quantaalpha/factors/prompts/prompts_crypto.yaml` | crypto 因子生成 prompt（变量名用 "asset" 措辞）|
| **数据说明** | `quantaalpha/factors/data_template/README_crypto.md` | crypto 数据结构说明 |
| **回测配置** | `quantaalpha/factors/factor_template/conf_crypto.yaml` | crypto 后续轮（含自定义因子注入）|
| **Baseline 配置** | `quantaalpha/factors/factor_template/conf_crypto_baseline.yaml` | crypto 第1轮（无自定义因子）|
| **合并配置** | `quantaalpha/factors/factor_template/conf_combined_factors_crypto.yaml` | crypto combined（备用）|
| **数据生成** | `quantaalpha/factors/data_template/generate_crypto.py` | crypto 数据生成脚本 |
| **Bin 转换** | `quantaalpha/factors/data_template/crypto_to_qlib_bin.py` | crypto → qlib bin 格式 |
| **Qlib bin 数据** | `data/qlib/crypto_50/`（calendars/features/instruments）| crypto 50 币 Qlib 数据集 |
| **源数据** | `data/git_ignore_folder/factor_implementation_source_data_crypto/daily_pv.h5` | crypto 因子实现源数据 |

### 3.4 Crypto 仍缺的专属文件（待补充）

| 缺失 | 说明 |
|---|---|
| **crypto 版 planning_prompts** | 当前 crypto 的"规划方向"复用了 A 股的 `planning_prompts.yaml`，需要新建 crypto 专属挖掘方向（`planning_prompts_crypto.yaml`）|
| **前端 InputPanel 市场选择接通** | `InputPanel.tsx` 的市场下拉框是僵尸功能（只有 csi500/sp500，未传到后端），与 SettingsPage 重复，建议统一或移除 |

---

## 4. 核心概念速查

| 概念 | 含义 |
|---|---|
| **Alpha 因子 (Alpha Factor)** | 从市场特征张量 $X \in \mathbb{R}^{N \times T \times D}$ 到 cross-sectional 收益预测 $y_{t+1}$ 的映射 $f(X_t) \sim y_{t+1}$ |
| **挖掘轨迹 (Mining Trajectory)** | 一次端到端挖掘运行的有序序列 $\tau = (s_0, a_0, s_1, a_1, \dots, s_n)$ |
| **终端奖励 (Terminal Reward)** | 轨迹质量度量 $R(\tau) = \mathcal{L}(f(X), y) - \lambda R(f)$ |
| **多样化规划初始化** | 生成多个互补的研究方向，获得广泛的初始假设空间覆盖 |
| **IC / ARR / MDD** | 因子评估三件套：信息系数、年化收益、最大回撤 |
| **Crypto 24/7 特性** | 加密货币无周末/节假日休市，日线连续；无涨跌停（limit_threshold=1.0）；高频波动 |

---

## 5. 项目结构（已校准）

```
QuantaAlpha/                      ← 仓库根目录（git repo root）
├── configs/
│   ├── experiment.yaml           ← 主实验配置（planning/execution/evolution/quality_gate/LLM）
│   └── backtest.yaml             ← 回测配置
├── data/
│   ├── factorlib/                ← 因子库（all_factors_library.json）
│   ├── qlib/
│   │   ├── cn_data/              ← A 股 Qlib bin 数据（calendars/features/instruments）
│   │   └── crypto_50/            ← crypto 50 币 Qlib bin 数据
│   ├── results/                  ← 实验输出
│   └── git_ignore_folder/
│       ├── factor_implementation_source_data/       ← A 股源数据
│       └── factor_implementation_source_data_crypto/ ← crypto 源数据（daily_pv.h5）
├── docs/
├── frontend-v2/                  ← Web 全栈（React 前端 + FastAPI 后端）
│   ├── backend/app.py            ← 后端入口（运行 mining/backtest 子进程）
│   ├── src/
│   │   ├── pages/
│   │   │   ├── SettingsPage.tsx  ← ★ 市场切换入口（defaultMarket 选择 + 写 .env）
│   │   │   ├── HomePage.tsx       ← 主页（含 InputPanel）
│   │   │   └── MiningDashboardPage.tsx
│   │   ├── components/
│   │   │   └── InputPanel.tsx    ← 挖掘输入面板（市场选择目前是僵尸功能）
│   │   └── services/api.ts       ← 前端 API 封装
│   └── start.sh                  ← 前端启动脚本
├── log/                          ← 运行日志（每个会话一个时间戳目录）+ bug 归档
├── quantaalpha/
│   ├── cli.py                    ← CLI 入口（mine/backtest/health_check）
│   ├── compat/
│   │   └── rdagent_patches.py    ← rdagent Windows 运行时补丁（+ SSL Patch）
│   ├── factors/
│   │   ├── market_config.py      ← ★ 市场路由（按 MARKET_TYPE 选 prompt/README）
│   │   ├── experiment.py         ← 场景 setup（QlibAlphaAgentScenario 读 get_prompt_file）
│   │   ├── runner.py             ← A 股原版 runner（含分钟级过滤 runner.py:279）
│   │   ├── runner_crypto.py      ← ★ crypto 专用 runner（覆盖 crypto 差异）
│   │   ├── coder/
│   │   │   ├── expr_parser.py    ← 因子表达式解析（parse_expression/parse_symbol）
│   │   │   └── template.jinjia2  ← 因子代码模板
│   │   ├── prompts/
│   │   │   ├── experiment.yaml          ← A 股场景 prompt
│   │   │   ├── experiment_crypto.yaml   ← ★ crypto 场景 prompt
│   │   │   ├── prompts.yaml             ← A 股因子 prompt
│   │   │   └── prompts_crypto.yaml      ← ★ crypto 因子 prompt
│   │   ├── factor_template/
│   │   │   ├── conf_baseline.yaml / conf_combined_factors.yaml  ← A 股回测配置
│   │   │   ├── conf_crypto.yaml         ← ★ crypto 回测配置
│   │   │   └── conf_crypto_baseline.yaml← ★ crypto baseline 配置
│   │   ├── data_template/
│   │   │   ├── README.md                ← A 股数据说明
│   │   │   ├── README_crypto.md         ← ★ crypto 数据说明
│   │   │   ├── generate_crypto.py       ← crypto 数据生成
│   │   │   └── crypto_to_qlib_bin.py    ← crypto → qlib bin 转换
│   │   ├── proposal.py         ← 假设生成
│   │   ├── feedback.py         ← 结果汇总
│   │   ├── library.py          ← 因子库管理
│   │   ├── workspace.py        ← 工作区
│   │   └── regulator/          ← 质量门控
│   ├── llm/                     ← LLM 配置 + 客户端（含 embedding 降级补丁）
│   ├── pipeline/
│   │   ├── settings.py         ← ★ 组件 wiring（_select_runner_cls 工厂）
│   │   ├── factor_mining.py    ← 主管线入口 + evolution
│   │   ├── factor_backtest.py  ← 回测管线
│   │   ├── loop.py             ← AlphaAgentLoop（5 步循环）
│   │   ├── evolution/          ← EvolutionController（mutation/crossover）
│   │   └── prompts/
│   │       ├── planning_prompts.yaml      ← A 股挖掘方向（crypto 复用中）
│   │       └── planning_prompts_crypto.yaml ← ★ crypto 专属挖掘方向（待确认是否需要）
│   └── utils/                   ← QlibLocalEnv 等
├── launcher.py                   ← 统一入口（自动加载 .env + apply patches）
├── run.sh                        ← 主运行脚本（加载 .env + SSL + conda）
└── .env                          ← ★ 市场切换持久化位置（MARKET_TYPE + QLIB_RUNNER_CONFIG）
```

---

## 6. 技术栈与依赖

| 项目 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.10 | conda `fe` 环境 (`G:\miniconda\envs\fe`) |
| LLM | **DeepSeek API**（OpenAI 兼容）| `OPENAI_API_KEY` + `OPENAI_BASE_URL=https://api.deepseek.com` |
| 模型 | `deepseek-chat` | 通过 `CHAT_MODEL` 配置 |
| Qlib | 0.9.7 | `pyqlib`，本地回测 |
| 前端 | React + TypeScript + Vite | `frontend-v2/src/` |
| 后端 | FastAPI + WebSocket | `frontend-v2/backend/app.py`（端口 8000）|
| 数据格式 | `.ipynb`（Jupyter Notebook） | 可运行代码优先用 Notebook |
| 文档/说明 | Markdown | 纯说明性内容用 `.md` |

---

## 7. 构建与运行

### 入口命令
```bash
# 主运行脚本（推荐，自动加载 .env + SSL + conda）
./run.sh "价量因子挖掘"
./run.sh "momentum reversal factors" "exp_suffix"

# CLI 直接调用
quantaalpha mine --direction "Price-Volume Factor Mining" --config_path configs/experiment.yaml
quantaalpha mine --direction "Microstructure Factors" --step_n 10

# Launcher（自动加载 .env）
python launcher.py mine --direction "factor mining direction"
```

### Web UI（含市场切换）
```bash
cd frontend-v2 && bash start.sh
# 前端: http://localhost:3000  →  Settings 页选择市场
# 后端: http://localhost:8000
```

### 回测
```bash
# 仅自定义因子
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml --factor-source custom \
  --factor-json all_factors_library.json

# 与 Alpha158(20) 基线合并
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml --factor-source combined \
  --factor-json all_factors_library.json
```

---

## 8. Windows 适配（必读 → `docs/WINDOWS_COMPAT.md`）

| 文件 | 补丁 | 作用 |
|---|---|---|
| `quantaalpha/compat/rdagent_patches.py` | SSL Patch | 用 certifi 替代 Windows 系统证书存储（防 aiohttp 崩溃）|
| `quantaalpha/llm/client.py` | embedding 降级 | 未配置 embedding_model 时返回全零（防 API 失败拖垮主流程）|
| `run.sh` | SSL_CERT_FILE | 自动设置证书路径 |

**multiprocessing 启动模式**：Windows 强制 **spawn**（非 Linux 的 fork），这是 OOM 和子进程内存问题的根因之一。conda run 不支持多行脚本、不继承 .env 变量，用 launcher.py / run.sh 运行。

---

## 9. Git 版本管理规范 ★ 强制

### 身份（已配置）
```bash
git config --global user.email "mengjinjiang215@gmail.com"
git config --global user.name "215meng"
```

### ★ 版本标记纪律（基本成功/完全成功）

debug 过程中遇到难以解决的问题或"屎山"时，能**快速回退到相对成功的版本**是救命稻草。因此：

**每次 mining 运行结束后**，评估结果并在 commit message 或 tag 中标记：

| 标记 | commit message 前缀 | 含义 | 触发条件 |
|---|---|---|---|
| 🟢 **完全成功** | `[success]` | 全流程跑通：因子生成 + 回测 + 结果输出 | exit 0，结果可解析，关键指标有值 |
| 🟡 **基本成功** | `[partial]` | 核心流程跑通但最终结果缺失/异常 | 因子生成成功、回测执行，但结果未输出或有小问题 |
| 🔴 **失败** | `[fail]` | 核心流程中断 | exit != 0，或关键步骤失败 |

**标记方式**：
1. **commit message** 加前缀（如 `[partial] crypto mining: 生成 3 个因子但回测 NaN`）
2. **重要锚点打 tag**（推荐，最便于回退）：
   ```bash
   git tag -a v0.5-crypto-mining-works -m "[success] crypto 端到端成功，Rank IC=0.033"
   git tag -a v0.2-a-stock-baseline -m "[success] A 股基线稳定可跑"
   git push origin --tags
   ```

**当前已知锚点**：
| Tag | 分支 | 状态 | 说明 |
|---|---|---|---|
| `v0.5-crypto-mining-works` | feature/crypto-data | 🟢 完全成功 | crypto 端到端通过，3 因子入库 |
| `v0.4-crypto-data-path-fixed` | feature/crypto-data | 🟡 部分成功 | 数据路径修复，但 merge 仍失败 |
| `v0.2-a-stock-baseline` | win-debug | 🟢 完全成功 | A 股基线稳定 |
| `v0.1.0-crypto-data-isolation` | feature/crypto-data | 🟡 部分成功 | L2+L3 修复，端到端验证通过 |

**回退锚点**：
```bash
# 查看成功锚点
git tag -l | grep -E "success|partial|works|baseline"

# 回退到某个成功版本（创建新分支保留现场）
git checkout -b crypto-fix-attempt3 v0.5-crypto-mining-works
```

### 分支策略
| 分支 | 用途 |
|---|---|
| `main` | 主工作分支（保持可跑，作为基线）|
| `win-debug` | Windows 适配 / debug 工作分支（**A 股基线稳定**）|
| **`feature/crypto-data`** | **当前工作分支** — crypto 移植 |
| `feature/xxx` | 各功能/实验分支 |

### 每次 Claude Code 会话的 Git 纪律

**会话开工前**（强制）：
```bash
git status                  # 看清当前状态
git log --oneline -5        # 看清最近提交
git branch                  # 确认所在分支
```

**修改代码前**：
```bash
git checkout feature/crypto-data    # 或当前工作分支
```

**每次改动后（原子 commit）**：
```bash
git add <仅改动的文件>                   # 不要 git add -A / git add .
git commit -m "[模块] 简述改了什么 + 为什么"  # 中文 message
```

**推送前**：
```bash
git push origin feature/crypto-data
```

### Commit 规范
- **粒度**：最小化、原子化，一个 commit 只做一件事
- **Message 格式**：`[success|partial|fail] [模块] 简述`（运行结果标记 + 改动描述）
- **运行结果标记**是必须的：每次 mining/backtest 运行后的提交必须带 `[success]`/`[partial]`/`[fail]`
- **中文 message**，简短说明"改了什么 + 为什么 + 运行结果"
- **禁止**：`git add -A` 大杂烩提交、无 message 提交

---

## 10. Debug 工作流纪律 ★ 强制

### 10.1 角色分工

| 角色 | 谁 | 职责 |
|---|---|---|
| **报错报告人** | 用户（你）| 发送前端日志截图/文件，描述现象 |
| **分析者** | Claude（我）| 结合本地 log + 代码定位根因，报告并建议方案 |
| **审批者** | 用户（你）| 审核方案并批准是否执行修改 |
| **执行者** | Claude（我）| 在批准后执行最小化修改 |

### 10.2 Debug 流程

```
用户发送前端日志/报错
       ↓
① Claude 分析：结合本地 log/ 目录 + 代码，定位根因
       ↓
② Claude 报告：【现象】【根因】【建议方案 + 侵入性】【受影响文件】
       ↓
③ 用户审批：确认方案 / 修改方案 / 拒绝
       ↓
④ Claude 执行：最小化修改（只改指定文件）
       ↓
⑤ Claude 验证：运行测试 / mining / backtest 验证
       ↓
  ┌─── 成功 ─────────────────────────────────────┐
  │ ⑥ 归档 bug + 修复方法到 log/BUG-xxx.md       │
  │ ⑦ commit 带 [success]/[partial] 标记         │
  │ ⑧ 若是重要锚点，打 tag                        │
  │ ⑨ 从 Bugs_that_need_fixing.md 移除该 bug     │
  └───────────────────────────────────────────────┘
  ┌─── 失败 ─────────────────────────────────────┐
  │ ⑥ 立即回退本次修复（git revert / checkout）   │
  │ ⑦ 保留现场分支（git checkout -b debug/xxx）   │
  │ ⑧ 重新分析，寻找新修复方法                     │
  └───────────────────────────────────────────────┘
```

### 10.3 关键原则

- **分析时不动手**：定位和报告阶段**禁止直接改代码**，先给方案等你审批
- **最小化改动**：每次只改任务明确指定的文件，不顺手重构、不格式化无关代码
- **验证后再声明完成**：改完必须跑实际运行验证，验证通过才能说"完成"
- **修复必须记录**：成功修复后，bug 的现象 + 根因 + 修复方法必须归档到 `log/BUG-xxx.md`
- **失败必须回退**：修复失败，**立即回退**到修复前状态（不能带着破损代码继续），并开新分支保留调试现场
- **不确定就说不确定**：禁止编造理由或含糊其辞

### 10.4 运行后的评估与标记（每次必做）

每次 mining / backtest 运行结束后，执行以下评估：

1. **查看结果**：
   ```bash
   ls -lt log/ | head -5          # 最新日志目录
   cat log/<最新>/mining.log | tail -30   # 查看尾部结果
   ```
2. **判断等级**：完全成功 / 基本成功 / 失败（见第 9 节定义）
3. **commit 并标记**：带 `[success]`/`[partial]`/`[fail]` 前缀
4. **若是重要锚点 → 打 tag**

---

## 11. Bug 跟踪与归档

### 11.1 活跃 bug 登记（`Bugs_that_need_fixing.md`）

每个未修复 bug 必须登记，包含：状态（`待审核`）、现象、位置（文件:行号）、根因分析、建议修复方向（方案 + 侵入性）、关联历史。

### 11.2 状态流转

```
待审核 ──用户审核──▶ 已审核（待执行）──修复+验证──▶ 已修复（已归档至 log/）
                                         │
                                    失败 ──▶ 回退 + 新分支保留现场 + 重找方案
```

### 11.3 归档格式（log/BUG-xxx_简短描述.md）

修复成功后归档，包含：现象、根因、修复 diff、验证结果。便于后续出现同样问题时参照。

### 11.4 清理原则

`Bugs_that_need_fixing.md` 只放**未修复的 bug**；修复即归档、归档即清理，保持活跃列表干净。

### 11.5 已修复 Bug 记录

| Bug | 修复 commit | 验证 |
|---|---|---|
| BUG-001 to_parquet OOM | `c9bd230` | ✅ 已归档 |
| BUG-002 配置文件污染 | `b2a2d14` | ✅ 已归档 |
| BUG-003 crypto 市场隔离 | `b456daa` | ✅ **端到端验证通过**（Rank IC=0.033，3 个 crypto 因子入库） |

---

## 12. 编码规范

- **改动范围最小化**：每次只改任务明确指定的文件，不顺手重构、不格式化无关代码
- **改前先 Read**：修改任何文件前必须 Read 当前内容，禁止凭记忆改写
- **验证后再声明完成**：改完必须跑实际运行验证，验证通过才能说"完成"
- **报错立刻说**：遇到报错或无法达成的指令，第一时间告知，不静默跳过
- **不确定就说不确定**：禁止编造理由或含糊其辞
- **中文交流**：所有输出、注释、文档用中文，技术术语保留英文
- **遇到报错先报告，不要直接修改代码**：先停止、向用户报告、确认后再改（参见第 10 节 Debug 流程）
- **寻找解决方案优先参考原项目指导文件**：`docs/WINDOWS_COMPAT.md` > `README.md` > `origin/windows` 分支

---

## 13. 环境备忘录

| 项目 | 值 |
|---|---|
| conda 根目录 | `G:\miniconda` |
| 默认环境 | `fe`（Python 3.10.18，路径 `G:\miniconda\envs\fe`）|
| Python 直接路径 | `G:\miniconda\envs\fe\python.exe` |
| 日志目录 | `log/<启动时间戳>/`（如 `log/2026-07-19_15-41-31-738300/`）|
| 因子库 | `data/factorlib/all_factors_library.json` |
| A 股 Qlib 数据 | `data/qlib/cn_data/` |
| crypto Qlib 数据 | `data/qlib/crypto_50/` |
| crypto 源数据 | `data/git_ignore_folder/factor_implementation_source_data_crypto/daily_pv.h5` |

**注意**：`conda run -n fe python -c "..."` **不支持多行脚本**（报 NotImplementedError），应改用脚本文件；且 `conda run` **不继承 `.env` 变量**，用 `launcher.py` / `run.sh` 运行。

---

## 14. 资源链接

- **你的 fork**: https://github.com/215meng/QuantaAlpha
- **官方 GitHub**: https://github.com/QuantaAlpha/QuantaAlpha
- **论文 arXiv**: https://arxiv.org/abs/2602.07085
- **DeepSeek API 文档**: https://platform.deepseek.com/
- **BigAlpha 比赛**: https://bigalpha.com/

---

## 附录 A：市场切换快速检查清单

切换市场后，按以下清单验证路由正确：

- [ ] `.env` 中 `MARKET_TYPE` 正确（`a_stock` 或 `crypto`）
- [ ] `.env` 中 `QLIB_RUNNER_CONFIG` 正确（A 股空 / crypto 为 `conf_crypto.yaml`）
- [ ] 子进程日志出现 `[crypto] Execute factor backtest`（crypto 时）
- [ ] workspace 内 `daily_pv.h5` 的 instrument 是 crypto（BTC/ETH）而非 A 股（SH000300）
- [ ] mining 全流程无 `FactorEmptyError` / `No valid factor data found`
- [ ] 回测结果输出不是股票因子（看因子名、instrument 类型）