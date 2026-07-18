# QuantaAlpha 项目指南

> **版本**: 2026-07-16 · **负责人**: 甘泉晔 (215meng) ·  **阶段**: 代码已对齐到官方 `windows` 分支 + 有益补丁保留，准备重新 debug

---

## 1. 项目概述

复现并改造 **QuantaAlpha**（arXiv:2602.07085v3, 2026-05）：一个通过 **轨迹级自进化（trajectory-level self-evolution）** 驱动 LLM 自动挖掘量化 Alpha 因子的框架。

**核心思想**：将每次端到端的因子挖掘运行视为一条"挖掘轨迹（mining trajectory）"，通过 **变异（mutation）** 和 **交叉（crossover）** 在轨迹层面进化因子，而非依赖带噪声的回测反馈反复重生成。

**与原论文的差异**：
| 维度 | 原论文 | 本项目 |
|---|---|---|
| LLM | GPT-5.2 | **DeepSeek API** (`deepseek-chat`，OpenAI 兼容协议) |
| 市场 | CSI 300/500, S&P 500 | CSI 300（A 股 cn_data） |
| 代码 | 官方仓库 | fork + Windows 适配 + DeepSeek 改造 |

**原论文关键指标**（复现目标）：CSI 300 上 IC=0.0472, ARR=4.68%, MDD=11.8%；跨市场迁移至 CSI 500 / S&P 500 四年累计超额收益 ~40.28% / ~19.1%。

---

## 2. 仓库信息 ★ 已 fork

| 角色 | 地址 | 说明 |
|---|---|---|
| **你的 fork（origin）** | https://github.com/215meng/QuantaAlpha | 推送改动的主仓库 |
| **官方原版（upstream）** | https://github.com/QuantaAlpha/QuantaAlpha | 上游源码，Windows 修复参考 |

**Git remote 配置**（已设置）：
```bash
origin    https://github.com/215meng/QuantaAlpha.git      ← 你的 fork（push/pull）
upstream  https://github.com/QuantaAlpha/QuantaAlpha.git  ← 官方原版（fetch/merge）
```

### 官方分支
| 分支 | 说明 |
|---|---|
| `main` | 官方主分支（Linux 原生）|
| **`windows`** | **官方 Windows 兼容版**（含 2601 行 Windows 修复 + `docs/WINDOWS_COMPAT.md`）|
| `fix_win` | 旧 Windows 修复分支（已合入 main）|
| `anonymous` | 匿名版本 |

> **代码基线**：当前工作树以 `origin/windows` 分支为准对齐，并保留了 3 处额外有益补丁（SSL 证书、embedding 降级、run.sh SSL）。详见 `docs/WINDOWS_COMPAT.md`。

---

## 3. 核心概念速查

| 概念 | 含义 |
|---|---|
| **Alpha 因子 (Alpha Factor)** | 从市场特征张量 $X \in \mathbb{R}^{N \times T \times D}$ 到 cross-sectional 收益预测 $y_{t+1}$ 的映射 $f(X_t) \sim y_{t+1}$ |
| **挖掘轨迹 (Mining Trajectory)** | 一次端到端挖掘运行的有序序列 $\tau = (s_0, a_0, s_1, a_1, \dots, s_n)$，含假设生成→因子构建→回测评估 |
| **终端奖励 (Terminal Reward)** | 轨迹质量度量 $R(\tau) = \mathcal{L}(f(X), y) - \lambda R(f)$，兼顾预测力和正则化 |
| **变异 (Mutation)** | 通过 self-reflection 定位致败步骤，**仅重写该段**，保持轨迹其余部分完整 |
| **交叉 (Crossover)** | 重组两条高奖励父代轨迹的互补片段，复用已验证的假设结构、构建模式和修复行为 |
| **多样化规划初始化 (Diversified Planning Initialization)** | 生成多个互补的研究方向，获得广泛的初始假设空间覆盖 |
| **生成门控 (Generation Gates)** | 强制语义一致性（假设/表达式/代码），约束复杂度和冗余度，防止漂移和拥挤 |
| **IC / ARR / MDD** | 因子评估三件套：信息系数、年化收益、最大回撤 |

---

## 4. 项目结构（已校准）

```
QuantaAlpha/                      ← 仓库根目录（git repo root）
├── configs/
│   ├── experiment.yaml           ← 主实验配置（planning/execution/evolution/quality_gate/LLM）
│   └── backtest.yaml             ← 回测配置（factor source, data, model, portfolio）
├── data/
│   ├── factorlib/                ← 因子库（all_factors_library.json）
│   ├── qlib/cn_data/             ← Qlib A 股数据（calendars/features/instruments）
│   └── results/                  ← 实验输出（workspace、backtest 结果）
├── docs/
│   └── WINDOWS_COMPAT.md         ← 官方 Windows 适配指南（必读！）
├── frontend-v2/                  ← Web UI（React + FastAPI）
├── log/                          ← 运行日志（每个会话一个时间戳目录）
├── quantaalpha/
│   ├── app/                      ← health_check、collect_info
│   ├── backtest/                 ← 独立回测模块
│   ├── compat/
│   │   └── rdagent_patches.py    ← rdagent Windows 运行时补丁（+ SSL Patch 0）
│   ├── coder/                    ← CoSTEER 代码生成 + 知识库
│   │   ├── costeer/              ← 进化 agent 框架
│   │   └── knowledge/            ← 图 + 向量知识库
│   ├── core/                     ← 共享抽象（proposal/scenario/developer/conf/evaluation）
│   ├── factors/                  ← 因子挖掘核心
│   │   ├── coder/                ← 因子代码生成（factor.py + template.jinjia2 + evaluators）
│   │   ├── runner.py             ← 回测运行器
│   │   ├── workspace.py          ← 工作区（含 Windows execute() 覆盖）
│   │   ├── feedback.py           ← 结果汇总
│   │   ├── library.py            ← 因子库管理
│   │   ├── proposal.py           ← 假设生成 & 因子表达式
│   │   ├── experiment.py         ← 场景 setup（QlibAlphaAgentScenario）
│   │   └── regulator/            ← 质量门控（consistency/complexity/redundancy）
│   ├── llm/                      ← LLM 配置 + 客户端
│   ├── pipeline/                 ← 主管线编排
│   │   ├── loop.py               ← AlphaAgentLoop（5 步循环）
│   │   ├── factor_mining.py      ← 入口 + evolution 支持
│   │   ├── factor_backtest.py     ← 回测管线
│   │   ├── planning.py           ← 并行方向生成
│   │   ├── settings.py           ← 组件 wiring（class-path）
│   │   └── evolution/            ← EvolutionController（mutation/crossover）
│   ├── utils/                    ← QlibLocalEnv（本地执行器）等
│   └── scenarios/qlib/           ← （空，逻辑已迁入 factors/）
├── launcher.py                   ← 统一入口（自动加载 .env + apply patches）
├── run.sh                        ← 主运行脚本（加载 .env + SSL + conda）
├── pyproject.toml
└── requirements.txt
```

---

## 5. 技术栈与依赖

| 项目 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.10 | conda `fe` 环境 (`G:\miniconda\envs\fe`) |
| LLM | **DeepSeek API**（OpenAI 兼容）| `OPENAI_API_KEY` + `OPENAI_BASE_URL=https://api.deepseek.com` |
| 模型 | `deepseek-chat`（实际响应 `deepseek-v4-flash`）| 通过 `CHAT_MODEL` 配置 |
| Qlib | 0.9.7 | `pyqlib`，本地回测 |
| 数据格式 | `.ipynb`（Jupyter Notebook） | 可运行代码优先用 Notebook |
| 文档/说明 | Markdown | 纯说明性内容用 `.md` |

**LLM 配置**（`.env`）：
```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com
CHAT_MODEL=deepseek-chat
REASONING_MODEL=deepseek-chat
```

---

## 6. 构建与运行

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

# 干跑（验证因子加载）
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml --factor-source custom \
  --factor-json all_factors_library.json --dry-run -v
```

### 健康检查 & Web UI
```bash
# 健康检查
quantaalpha health_check
python launcher.py health_check  # 等效

# Web UI
cd frontend-v2 && bash start.sh   # 访问 http://localhost:3000
```

---

## 7. Windows 适配（必读 → `docs/WINDOWS_COMPAT.md`）

官方 Windows 版 = `origin/windows` 分支，含 11 项修复 + `docs/WINDOWS_COMPAT.md` 指南。当前工作树已对齐到该分支，并**额外保留** 3 处有益补丁：

| 文件 | 补丁 | 作用 |
|---|---|---|
| `quantaalpha/compat/rdagent_patches.py` | +49 行 SSL Patch 0 | 用 certifi 替代 Windows 系统证书存储（防 aiohttp 崩溃）|
| `quantaalpha/llm/client.py` | +6 行 embedding 降级 | 未配置 embedding_model 时返回全零（防 API 失败拖垮主流程）|
| `run.sh` | +14 行 SSL_CERT_FILE | 自动设置证书路径 |

> 调试时**优先参考**：`docs/WINDOWS_COMPAT.md` > `README.md` > `origin/windows` 分支。

---

## 8. Git 版本管理规范 ★ 强制

### 身份（已配置）
```bash
git config --global user.email "mengjinjiang215@gmail.com"
git config --global user.name "215meng"
```

### Remote（已配置）
| Remote | 地址 | 用途 |
|---|---|---|
| `origin` | `https://github.com/215meng/QuantaAlpha.git` | 你的 fork（推送改动）|
| `upstream` | `https://github.com/QuantaAlpha/QuantaAlpha.git` | 官方原版（合并上游更新）|

### 分支策略
| 分支 | 用途 |
|---|---|
| `main` | 主工作分支（保持可跑，作为基线）|
| `win-debug` | Windows 适配 / debug 的工作分支（改动都在此分支）|
| `feature/xxx` | 各功能/实验分支 |
| `upstream/windows` | 官方 Windows 版参考（只读，不直接改）|

### ★ 每次 Claude Code 会话的 Git 纪律

**会话开工前**：
```bash
git status                  # 看清当前状态
git log --oneline -5        # 看清最近提交
git branch                  # 确认所在分支
```

**修改代码前**：
```bash
git checkout -b win-debug               # 或 feature/xxx，不在 main 上直接改
# 若 win-debug 已存在：git checkout win-debug && git pull origin win-debug
```

**每次改动后（原子 commit）**：
```bash
git add <仅改动的文件>                   # 不要 git add -A / git add .
git commit -m "简述改了什么 + 为什么"       # 中文 message
```

**推送前**：
```bash
git push origin win-debug                # 推送到 fork
```

**合并到 main**（功能验证通过后）：
```bash
git checkout main
git merge win-debug
git push origin main
```

### Commit 规范
- **粒度**：最小化、原子化，一个 commit 只做一件事
- **Message 格式**：`[模块] 简述改动`，如 `[coder] fix: Windows 路径双拼接`、`[env] fix: SSL 证书加载`
- **中文 message**，简短说明"改了什么 + 为什么"
- **禁止**：`git add -A` 大杂烩提交、无 message 提交

### 定期同步上游
```bash
git fetch upstream                       # 拉取官方最新
git merge upstream/windows               # 合并官方 Windows 修复（如有新fix）
```

---

## 9. 编码规范

- **改动范围最小化**：每次只改任务明确指定的文件，不顺手重构、不格式化无关代码
- **改前先 Read**：修改任何文件前必须 Read 当前内容，禁止凭记忆改写
- **验证后再声明完成**：改完跑测试/编译/实际执行，验证通过才能说"完成"
- **报错立刻说**：遇到报错或无法达成的指令，第一时间告知，不静默跳过
- **不确定就说不确定**：禁止编造理由或含糊其辞
- **中文交流**：所有输出、注释、文档用中文，技术术语保留英文
- **遇到报错先报告，不要直接修改代码**：先停止、向用户报告、确认后再改
- **寻找解决方案优先参考原项目指导文件**：`docs/WINDOWS_COMPAT.md` > `README.md` > `origin/windows` 分支

---

## 10. 环境备忘录

| 项目 | 值 |
|---|---|
| conda 根目录 | `G:\miniconda` |
| 默认环境 | `fe`（Python 3.10.18，路径 `G:\miniconda\envs\fe`）|
| Python 直接路径 | `G:\miniconda\envs\fe\python.exe` |
| 日志目录 | `log/<启动时间戳>/`（如 `log/2026-07-16_09-08-12-773731/`）|
| 因子库 | `data/factorlib/all_factors_library.json` |

**注意**：`conda run -n fe python -c "..."` **不支持多行脚本**（报 NotImplementedError），应改用脚本文件；且 `conda run` **不继承 `.env` 变量**，用 `launcher.py` / `run.sh` 运行。

---

## 11. 资源链接

- **你的 fork**: https://github.com/215meng/QuantaAlpha
- **官方 GitHub**: https://github.com/QuantaAlpha/QuantaAlpha
- **官方 Windows 分支**: `origin/windows`（含 `docs/WINDOWS_COMPAT.md`）
- **论文 arXiv**: https://arxiv.org/abs/2602.07085
- **论文 PDF（本地）**: `others/2602.07085v3.pdf`
- **DeepSeek API 文档**: https://platform.deepseek.com/

---

## 12. 调试产出

| 文件 | 说明 |
|---|---|
| `DEBUG_SUMMARY.md` | 完整调试总结报告（220 行，含环境/成功记录/故障定位/git状态）|
| `docs/WINDOWS_COMPAT.md` | 官方 Windows 适配指南 |
| `_win_revert_backup/` | 3 个有益补丁备份（SSL、embedding、run.sh）|

---

## 13. Bug 跟踪流程（强制）

每次遇到 bug，**必须**按以下流程处理，**禁止**跳过等待直接修复：

### 13.1 登记（发现 bug 后立即执行）

将 bug 完整写入 **`Bugs_that_need_fixing.md`**，包含：
- 状态标记为 `待审核`
- 现象、位置（文件:行号）、调用链
- 根因分析
- **建议修复方向（方案 + 侵入性）**
- 关联历史（相关 commit / 文档）

### 13.2 等待统一审核

- **不立即动手修复**，先停止、向用户报告根因与候选方案
- 等待用户**统一审核** `Bugs_that_need_fixing.md` 中所有待审核 bug
- 用户确认方案后，状态改为 `已审核（待执行）`

### 13.3 执行修复

- 按审核通过的方案修改代码
- 最小化改动，只改任务明确指定的文件

### 13.4 归档与清理（修复验证通过后）

1. **归档到 `log/`**：将该 bug 的完整记录（现象 + 根因 + 修复 diff）写成 `log/BUG-<编号>_<简短描述>.md`
2. **从 `Bugs_that_need_fixing.md` 移除**该 bug 条目（已修复的不留在活跃列表）
3. 原子 commit，message 格式：`[bug fix] BUG-<编号>: <简述>`

### 13.5 状态流转

```
待审核 ──用户审核──▶ 已审核（待执行）──修复+验证──▶ 已修复（已归档）
```

> **原则**：Bugs_that_need_fixing.md 只放**未修复的 bug**；修复即归档、归档即清理，保持活跃列表干净。
