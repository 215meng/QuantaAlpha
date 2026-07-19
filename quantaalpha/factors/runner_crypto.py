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

import os
import shutil
import sys
from pathlib import Path

import pandas as pd

from quantaalpha.factors.runner import QlibFactorRunner
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
from quantaalpha.log import logger

# ── crypto 专属 daily_pv.h5 目录（BUG-003-L2 修复）──────────────────────
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
        # ── 0. BUG-003-L2 关键修复：re-link 必须在 process_factor_data 之前 ──
        # 原实现把 re-link 放在 process_factor_data 之后，导致 factor.py 执行时
        # daily_pv.h5 仍是 A 股版本 → result.h5 是 A 股 factor（全 NaN）。
        for ws in exp.sub_workspace_list:
            self._force_relink_daily_pv(ws.workspace_path)
        self._force_relink_daily_pv(exp.experiment_workspace.workspace_path)

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

        # ── D. MARKET_TYPE 透传 (F7) ─────────────────────────────
        # NOTE: re-link 已提前到 develop() 开头，确保 factor eval 使用正确的数据源
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
        if isinstance(exp_or_list, list):
            exp_list = exp_or_list
        else:
            exp_list = [exp_or_list]

        # 每个 exp 的 sub_workspace 都强制 re-link
        for exp in exp_list:
            if hasattr(exp, 'sub_workspace_list'):
                for ws in exp.sub_workspace_list:
                    self._force_relink_daily_pv(ws.workspace_path)

        return super().process_factor_data(exp_or_list)
