"""
QuantaAlpha factor experiment module: Scenario and Experiment classes.
Uses project QlibFBWorkspace (no ProcessInf / pandas 1.5.x issues).
"""

from copy import deepcopy
from pathlib import Path

import yaml
from rdagent.scenarios.qlib.experiment.factor_experiment import (  # type: ignore
    QlibFactorScenario,
    FactorExperiment,
    FactorTask,
    FactorFBWorkspace,
)
from rdagent.utils.agent.tpl import T

from quantaalpha.factors.workspace import QlibFBWorkspace
from quantaalpha.factors.market_config import get_prompt_file
from rdagent.scenarios.qlib.experiment.factor_experiment import (
    QlibFactorExperiment as _OrigQlibFactorExperiment,
)


class QlibFactorExperiment(_OrigQlibFactorExperiment):
    """Override rdagent QlibFactorExperiment with project QlibFBWorkspace (correct config template)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        import rdagent.scenarios.qlib.experiment.factor_experiment as _fe_mod

        rdagent_template_path = Path(_fe_mod.__file__).parent / "factor_template"
        self.experiment_workspace = QlibFBWorkspace(
            template_folder_path=rdagent_template_path
        )


class QlibAlphaAgentScenario(QlibFactorScenario):
    """Scenario wrapper for AlphaAgent: accepts use_local; when True uses local get_data_folder_intro (no Docker).
    支持根据 MARKET_TYPE 环境变量动态切换 A 股 / crypto prompt。
    """

    def __init__(self, use_local: bool = True, *args, **kwargs):
        from rdagent.core.scenario import Scenario
        from quantaalpha.factors.qlib_utils import get_data_folder_intro as local_get_data_folder_intro

        Scenario.__init__(self)
        tpl_prefix = "scenarios.qlib.experiment.prompts"

        # 根据市场类型选择 prompt 文件
        prompt_file = get_prompt_file()
        market_prompts = self._load_prompt_file(prompt_file)

        self._background = deepcopy(
            T(f"{tpl_prefix}:qlib_factor_background").r(
                runtime_environment=self.get_runtime_environment(),
            )
        )
        # 如果 crypto，用 crypto background 覆盖（它包含 runtime_environment）
        if "qlib_factor_background" in market_prompts:
            from jinja2 import Environment, StrictUndefined
            self._background = Environment(undefined=StrictUndefined).from_string(
                market_prompts["qlib_factor_background"]
            ).render(runtime_environment=self.get_runtime_environment())

        self._source_data = deepcopy(local_get_data_folder_intro(use_local=use_local))
        self._output_format = deepcopy(
            market_prompts.get("qlib_factor_output_format", T(f"{tpl_prefix}:qlib_factor_output_format").r())
        )
        self._interface = deepcopy(
            market_prompts.get("qlib_factor_interface", T(f"{tpl_prefix}:qlib_factor_interface").r())
        )
        self._strategy = deepcopy(
            market_prompts.get("qlib_factor_strategy", T(f"{tpl_prefix}:qlib_factor_strategy").r())
        )
        self._simulator = deepcopy(
            market_prompts.get("qlib_factor_simulator", T(f"{tpl_prefix}:qlib_factor_simulator").r())
        )
        self._rich_style_description = deepcopy(
            market_prompts.get("qlib_factor_rich_style_description", T(f"{tpl_prefix}:qlib_factor_rich_style_description").r())
        )
        self._experiment_setting = deepcopy(
            market_prompts.get("qlib_factor_experiment_setting", T(f"{tpl_prefix}:qlib_factor_experiment_setting").r())
        )

    @staticmethod
    def _load_prompt_file(path: Path) -> dict:
        """加载指定 yaml 文件，返回 dict。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
