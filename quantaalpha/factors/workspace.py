"""
QuantaAlpha custom workspace.

Overrides rdagent QlibFBWorkspace:
- project-level factor_template overrides default YAML;
- base files (read_exp_res.py, etc.) still from rdagent;
- init empty git repo in workspace to suppress qlib recorder git output;
- **Windows**: override ``execute()`` to use the project's own ``QlibLocalEnv``
  (from ``quantaalpha.utils.env``) instead of rdagent's ``QlibCondaEnv``, so we
  don't depend on rdagent's ``LocalEnv._run`` / ``Env.run`` at all for the
  backtest execution path.  This follows the instructor guideline: *use your own
  LocalEnv to override, don't modify third-party packages*.
"""

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from rdagent.scenarios.qlib.experiment.workspace import QlibFBWorkspace as _RdagentQlibFBWorkspace
from rdagent.log import rdagent_logger as logger

_CUSTOM_TEMPLATE_DIR = Path(__file__).resolve().parent / "factor_template"


class QlibFBWorkspace(_RdagentQlibFBWorkspace):
    """
    Override rdagent QlibFBWorkspace: inject project factor_template/ YAML over defaults;
    init empty git repo in workspace to avoid qlib recorder git help output.

    On Windows the ``execute()`` method is overridden to use the project-owned
    ``QlibLocalEnv`` rather than rdagent's ``QlibCondaEnv``.
    """

    def __init__(self, template_folder_path: Path, *args, **kwargs) -> None:
        super().__init__(template_folder_path, *args, **kwargs)
        if _CUSTOM_TEMPLATE_DIR.exists():
            self.inject_code_from_folder(_CUSTOM_TEMPLATE_DIR)
            logger.info(f"Overrode rdagent default config with project template: {_CUSTOM_TEMPLATE_DIR}")

    def before_execute(self) -> None:
        """Init empty git repo in workspace to suppress qlib recorder git warnings."""
        super().before_execute()
        git_dir = self.workspace_path / ".git"
        if not git_dir.exists():
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=str(self.workspace_path),
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Windows-specific execute() using project's own QlibLocalEnv
    # ------------------------------------------------------------------

    def _ensure_parquet_in_workspace(self):
        """确保 combined_factors_df.parquet 对当前 workspace 可见。
        解决 ERR-03: StaticDataLoader 在子 workspace（factor 子目录）中找不到 parquet 的问题。
        """
        import shutil
        parquet_name = "combined_factors_df.parquet"
        target = self.workspace_path / parquet_name
        if target.exists():
            return  # 已存在，跳过
        # 在父 workspace 目录查找 parquet
        parent = self.workspace_path.parent
        source = parent / parquet_name
        if source.exists():
            try:
                # Windows: 复制（symlink 需要管理员特权）；Linux: 符号链接
                shutil.copy2(str(source), str(target))
                logger.info(f"[workspace] Copied {parquet_name} from parent workspace")
            except Exception as e:
                logger.warning(f"[workspace] Failed to copy {parquet_name}: {e}")

    def execute(
        self,
        qlib_config_name: str = "conf.yaml",
        run_env: dict = {},
        *args,
        **kwargs,
    ) -> str:
        """Execute qlib backtest.

        On **Linux / Docker** delegates to the parent rdagent implementation.
        On **Windows** uses the project's own ``QlibLocalEnv`` which runs commands
        via simple ``subprocess.run`` — no symlinks, no ``/bin/sh`` wrapper,
        no ``select.poll``.
        """
        if sys.platform != "win32":
            # Non-Windows: use the original rdagent execute path
            return super().execute(qlib_config_name, run_env, *args, **kwargs)

        # 确保 parquet 文件可见（ERR-03 修复）
        self._ensure_parquet_in_workspace()

        # ----- Windows path: use project's own QlibLocalEnv -----
        from quantaalpha.utils.env import QlibLocalEnv

        env = QlibLocalEnv()
        env.prepare()

        workspace_path_str = str(self.workspace_path)

        # Step 1: Run qlib backtest
        logger.info(f"[Windows] Running qrun {qlib_config_name} ...")
        execute_qlib_log = env.run(
            entry=f"qrun {qlib_config_name}",
            local_path=workspace_path_str,
            env=run_env,
        )
        logger.log_object(execute_qlib_log, tag="Qlib_execute_log")

        # Step 2: Run read_exp_res.py
        logger.info("[Windows] Running python read_exp_res.py ...")
        execute_log = env.run(
            entry="python read_exp_res.py",
            local_path=workspace_path_str,
            env=run_env,
        )

        # Step 3: Check results
        quantitative_backtesting_chart_path = self.workspace_path / "ret.pkl"
        if quantitative_backtesting_chart_path.exists():
            ret_df = pd.read_pickle(quantitative_backtesting_chart_path)
            logger.log_object(ret_df, tag="Quantitative Backtesting Chart")
        else:
            logger.error("No result file found.")
            return None, execute_qlib_log

        qlib_res_path = self.workspace_path / "qlib_res.csv"
        if qlib_res_path.exists():
            pattern = (
                r"(Epoch\d+: train -[0-9\.]+, valid -[0-9\.]+|"
                r"best score: -[0-9\.]+ @ \d+ epoch)"
            )
            matches = re.findall(pattern, execute_qlib_log)
            execute_qlib_log = "\n".join(matches)
            return pd.read_csv(qlib_res_path, index_col=0).iloc[:, 0], execute_qlib_log
        else:
            logger.error(f"File {qlib_res_path} does not exist.")
            return None, execute_qlib_log
