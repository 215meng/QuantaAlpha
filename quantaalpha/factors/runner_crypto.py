"""
QuantaAlpha Crypto Factor Runner。

继承quantaalpha.factors.runner.QlibFactorRunner，仅覆盖加密货币市场差异方法。
配合 MARKET_TYPE=crypto 环境变量使用，前端选加密货币时后端启用此runner。

差异点：
1. 第一轮用 conf_crypto_baseline.yaml（QlibDataLoader，无 parquet 依赖）
   后续轮用 conf_combined_factors_crypto.yaml（NestedDataLoader + StaticDataLoader）
2. 因子数据处理前，强制 re-link daily_pv.h5 到当前源文件（修复 ERR-03）
3. MARKET_TYPE 环境变量透传给 qrun 子进程
"""

# 导入时立即打印，确认新代码被加载（诊断用，验证 backend 是否加载最新 runner_crypto.py）
print("[RUNNER_CRYPTO] module loaded - DIAG version 2026-07-20_1341")

import os
import shutil
import sys
from pathlib import Path

import pandas as pd

from quantaalpha.core.conf import RD_AGENT_SETTINGS
from quantaalpha.core.exception import FactorEmptyError
from quantaalpha.core.utils import multiprocessing_wrapper
from quantaalpha.factors.runner import QlibFactorRunner
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
from quantaalpha.factors.experiment import QlibFactorExperiment
from quantaalpha.log import logger

# ── crypto 专属 daily_pv.h5 目录（BUG-003-L2 修复）──────────────────────
# crypto mining 必须从这个目录硬链接/复制，避免读到 A 股数据。
# A 股源仍使用 FACTOR_COSTEER_SETTINGS.data_folder（= factor_implementation_source_data）。
_CRYPTO_DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "git_ignore_folder"
    / "factor_implementation_source_data_crypto"
)


class QlibFactorRunnerCrypto(QlibFactorRunner):
    """加密货币专用 runner：继承 A 股原版，覆盖 crypto-specific 方法"""

    # ── crypto 配置名 ──────────────────────────────────────────
    _CFG_ROUND1 = "conf_crypto_baseline.yaml"
    _CFG_ROUND2PLUS = "conf_combined_factors_crypto.yaml"

    # ── 1. 配置选择（F8 修复） ─────────────────────────────────
    def _select_config_name(self, exp) -> str:
        """根据实验进度选择 crypto baseline 或 combined 配置。"""
        if len(exp.based_experiments) == 0:
            return self._CFG_ROUND1
        return self._CFG_ROUND2PLUS

    # ── 2. 硬链接维护（F1 修复） ─────────────────────────────────
    def _force_relink_daily_pv(self, workspace_path: Path):
        """强制重新链接 daily_pv.h5 到当前源文件。

        旧逻辑只在文件不存在时才链接（导致残留 A 股数据）。
        本方法：无论是否存在，先删除旧链接/link，再重新硬链接/复制。
        """
        parquet_name = "daily_pv.h5"
        target = Path(workspace_path) / parquet_name

        # 确保目标目录存在（调试失败的因子可能没有目录）
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"[crypto runner] 无法创建目录 {target.parent}: {e}")
            return

        # 删除旧链接 / 文件
        if target.exists() or target.is_symlink():
            try:
                target.unlink()
                logger.debug(f"[crypto runner] 删除旧 daily_pv.h5 链接: {target}")
            except Exception as e:
                logger.warning(f"[crypto runner] 无法删除旧链接 {target}: {e}")

        # 定位源文件：crypto 用专属目录（BUG-003-L2 修复），不再读 A 股源
        data_source = _CRYPTO_DATA_DIR
        source = data_source / parquet_name

        if not source.exists():
            logger.warning(f"[crypto runner] 源文件不存在: {source}")
            return

        # 重新链接：Windows 用 shutil.copy2（无需管理员特权），Linux 用符号链接
        try:
            if sys.platform == "win32":
                shutil.copy2(str(source), str(target))
            else:
                target.symlink_to(source)
            logger.debug(f"[crypto runner] 已重新链接 daily_pv.h5 → {source}")
        except Exception as e:
            logger.warning(f"[crypto runner] 重新链接失败: {e}")

    # ── 3. 覆盖 develop（整合 F1 + F8 + 子进程 env 透传） ─────────
    def develop(self, exp, use_local=True):
        """
        覆盖原版 develop，增加：
        - crypto 专用配置选择 (F8)
        - 子 workspace 的 daily_pv.h5 强制 re-link (F1)
        - MARKET_TYPE 透传 (F7)
        """
        # ── 诊断：develop 入口的 exp 状态 ──
        _sw_count = len(exp.sub_workspace_list) if hasattr(exp, 'sub_workspace_list') else 'N/A'
        logger.info(f"[DIAG] crypto develop() entered: id(exp)={id(exp)}, sub_workspaces={_sw_count}")
        if _sw_count and _sw_count != 'N/A':
            for i, ws in enumerate(exp.sub_workspace_list):
                logger.info(f"[DIAG]   ws[{i}]: {ws.workspace_path}")
        # ── 诊断结束 ──
        # ── A. 处理 prior experiments（与原版一致） ──────────────
        if exp.based_experiments and exp.based_experiments[-1].result is None:
            exp.based_experiments[-1] = self.develop(exp.based_experiments[-1], use_local=use_local)

        # ── B. 收集 SOTA factors（与原版一致） ───────────────────
        if exp.based_experiments:
            SOTA_factor = None
            if len(exp.based_experiments) > 1:
                try:
                    SOTA_factor = self.process_factor_data(exp.based_experiments)
                except Exception as e:
                    logger.warning(f"SOTA factors processing failed: {e}")
                    SOTA_factor = None

            try:
                new_factors = self.process_factor_data(exp)
            except Exception as e:
                logger.error(f"Failed to process new factors: {e}")
                raise

            if new_factors.empty:
                raise RuntimeError("No valid factor data found to merge.")

            if SOTA_factor is not None and not SOTA_factor.empty:
                try:
                    dup = self.deduplicate_new_factors(SOTA_factor, new_factors)
                    if dup.empty:
                        raise RuntimeError("No valid factor data found after dedup.")
                    new_factors = dup
                except Exception as e:
                    logger.warning(f"Dedup failed, using new factors only: {e}")

            combined_factors = new_factors
            if len(combined_factors.columns) >= 2:
                pd.set_option('display.width', 1000)
                logger.info(f"Factor correlation: \n\n{combined_factors.corr()}\n")
            combined_factors = combined_factors.sort_index()
            combined_factors = combined_factors.loc[:, ~combined_factors.columns.duplicated(keep="last")]
            new_columns = pd.MultiIndex.from_product([["feature"], combined_factors.columns])
            combined_factors.columns = new_columns
            logger.info(f"Factor values this round: \n\n{combined_factors.tail()}\n\n")
            parquet_path = exp.experiment_workspace.workspace_path / "combined_factors_df.parquet"
            combined_factors.to_parquet(parquet_path, engine="pyarrow")
            logger.info(f"Saved combined factors to {parquet_path}")
        else:
            try:
                # 实验性修复：第一轮如果子空间为空，回退到父类 process_factor_data（含容错）
                if not exp.sub_workspace_list:
                    logger.warning("[crypto] sub_workspace_list empty in first round, falling back to parent process_factor_data")
                    new_factors = QlibFactorRunner.process_factor_data(self, exp)
                else:
                    new_factors = self.process_factor_data(exp)
            except Exception as e:
                logger.error(f"Failed to process factors: {e}")
                raise
            if new_factors.empty:
                raise RuntimeError("No valid factor data found.")
            combined_factors = new_factors
            if len(combined_factors.columns) >= 2:
                pd.set_option('display.width', 1000)
                logger.info(f"Factor correlation: \n\n{combined_factors.corr()}\n")
            combined_factors = combined_factors.sort_index()
            combined_factors = combined_factors.loc[:, ~combined_factors.columns.duplicated(keep="last")]
            new_columns = pd.MultiIndex.from_product([["feature"], combined_factors.columns])
            combined_factors.columns = new_columns
            logger.info(f"Factor values this round: \n\n{combined_factors.tail()}\n\n")
            parquet_path = exp.experiment_workspace.workspace_path / "combined_factors_df.parquet"
            combined_factors.to_parquet(parquet_path, engine="pyarrow")
            logger.info(f"Saved combined factors to {parquet_path}")

        # ── C. 选择 crypto 配置 (F8) ─────────────────────────────
        config_name = self._select_config_name(exp)
        logger.info(f"[crypto] Execute factor backtest (Use {'Local' if use_local else 'Docker container'}): {config_name}")

        # ── D. 强制 re-link 子 workspace 的 daily_pv.h5 (F1) ─────
        for ws in exp.sub_workspace_list:
            self._force_relink_daily_pv(ws.workspace_path)
        self._force_relink_daily_pv(exp.experiment_workspace.workspace_path)

        # ── E. MARKET_TYPE 透传 (F7) ─────────────────────────────
        run_env = {"MARKET_TYPE": "crypto"}

        # ── F. 执行回测（与原版相同） ────────────────────────────
        exp.experiment_workspace.before_execute()
        result_tuple = exp.experiment_workspace.execute(
            qlib_config_name=config_name,
            run_env=run_env,
        )

        result = result_tuple[0] if isinstance(result_tuple, tuple) else result_tuple
        if result is not None:
            logger.info(f"Backtesting results: \n{result.iloc[2:] if hasattr(result, 'iloc') else result}")
        else:
            logger.warning("Backtesting result is None. Check the execution logs above for errors.")
            if isinstance(result_tuple, tuple) and len(result_tuple) > 1:
                logger.info(f"Execution log: {result_tuple[1][:500]}...")

        exp.result = result
        return exp

    def process_factor_data(self, exp_or_list):
        """覆盖原版：先强制 re-link daily_pv.h5 到最新源文件，再调用 super()。"""
        logger.info("[DIAG] crypto process_factor_data override called")
        if isinstance(exp_or_list, list):
            exp_list = exp_or_list
        else:
            exp_list = [exp_or_list]

        # 每个 exp 的 sub_workspace 都强制 re-link
        for exp in exp_list:
            if hasattr(exp, 'sub_workspace_list'):
                for ws in exp.sub_workspace_list:
                    self._force_relink_daily_pv(ws.workspace_path)

        # 回退到父类通用流程（内部会再次调用 self.process_factor_data，
        # 由于多态会进入本子类版本 → 需要避免无限递归）。
        # BUG-003-L4 修复：父类 process_factor_data 在 runner.py:279 有分钟级过滤，
        # crypto 日线数据会被全部阻断。此处用"父类方法但跳过分钟级过滤"的实现。
        return self._process_factor_data_daily_safe(exp_or_list)

    def _process_factor_data_daily_safe(self, exp_or_list):
        """crypto 日线版 process_factor_data：跳过父类分钟级过滤（BUG-003-L4 修复）。

        与父类 QlibFactorRunner.process_factor_data 保持完全一致，仅把
        ``pd.Timedelta(minutes=1) not in time_diff``（分钟级硬编码）替换为
        "time_diff 非空"的一般性检查，兼容日 / 周 / 月等低频数据。
        """
        # ── 诊断：入口参数 ──
        logger.info(
            f"[DIAG] _process_factor_data_daily_safe entered: "
            f"type={type(exp_or_list).__name__}, "
            f"is_list={isinstance(exp_or_list, list)}, "
            f"len={len(exp_or_list) if hasattr(exp_or_list, '__len__') else 'N/A'}"
        )
        if isinstance(exp_or_list, list):
            for i, item in enumerate(exp_or_list):
                sw_count = len(item.sub_workspace_list) if hasattr(item, 'sub_workspace_list') else 'N/A'
                logger.info(f"[DIAG]   exp_or_list[{i}]: type={type(item).__name__}, sub_workspaces={sw_count}")
        # ── 诊断结束 ──

        if isinstance(exp_or_list, QlibFactorExperiment):
            exp_or_list = [exp_or_list]
        factor_dfs: list[pd.DataFrame] = []

        logger.info(f"[DIAG] outer loop: exp_or_list length={len(exp_or_list)}")
        for i, exp in enumerate(exp_or_list):
            sw_count = len(exp.sub_workspace_list) if hasattr(exp, 'sub_workspace_list') else 'N/A'
            logger.info(f"[DIAG]   outer loop[{i}]: type={type(exp).__name__}, sub_workspaces={sw_count}")
        # ── 诊断：确认 sub_workspace_list 内容 ──

        for exp in exp_or_list:
            message_and_df_list = multiprocessing_wrapper(
                [(implementation.execute, ("All",)) for implementation in exp.sub_workspace_list],
                n=RD_AGENT_SETTINGS.multi_proc_n,
            )
            for idx, (message, df) in enumerate(message_and_df_list):
                # ── 诊断日志：记录 execute() 返回值 ──
                if df is None:
                    logger.warning(
                        f"[DIAG] merge execute() returned df=None for sub_ws[{idx}]; "
                        f"message={message[:200]!r}"
                    )
                else:
                    logger.info(
                        f"[DIAG] merge execute() returned df: type={type(df).__name__}, "
                        f"shape={getattr(df, 'shape', None)}, index.names={getattr(df.index, 'names', None)}, "
                        f"'datetime' in index.names={'datetime' in getattr(df.index, 'names', [])}"
                    )
                # ── 诊断日志结束 ──
                if df is not None and "datetime" in df.index.names:
                    if idx < len(exp.sub_workspace_list):
                        ws = exp.sub_workspace_list[idx]
                        result_h5 = ws.workspace_path / "result.h5"
                        try:
                            df.to_hdf(str(result_h5), key="data")
                        except Exception as e:
                            logger.debug(f"Could not refresh result.h5 for {ws.workspace_path}: {e}")

                    if isinstance(df, pd.Series):
                        if idx < len(exp.sub_workspace_list):
                            factor_name = getattr(exp.sub_workspace_list[idx].target_task, "factor_name", None)
                            if factor_name:
                                df = df.to_frame(name=factor_name)
                            else:
                                df = df.to_frame(name=df.name if df.name else f"factor_{idx}")
                        else:
                            df = df.to_frame(name=df.name if df.name else f"factor_{idx}")

                    # BUG-003-L4 修复：用一般性 time_diff 检查替换分钟级硬编码
                    time_diff = df.index.get_level_values("datetime").to_series().diff().dropna().unique()
                    if len(time_diff) > 0:   # ← 原：pd.Timedelta(minutes=1) not in time_diff
                        factor_dfs.append(df)

        if factor_dfs:
            return pd.concat(factor_dfs, axis=1)
        raise FactorEmptyError("No valid factor data found to merge.")
