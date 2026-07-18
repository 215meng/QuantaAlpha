"""
市场配置加载器。
根据环境变量 MARKET_TYPE 决定使用哪套 prompt 文件。

用法：
    from quantaalpha.factors.market_config import get_prompt_file, is_crypto
    prompt_path = get_prompt_file()  # 返回 Path 对象
"""
import os
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def get_market_type() -> str:
    """读取当前市场类型，默认 a_stock。"""
    return os.environ.get("MARKET_TYPE", "a_stock").lower().strip()


def get_prompt_file() -> Path:
    """
    根据 MARKET_TYPE 返回对应的 prompt yaml 文件。
    - crypto  → experiment_crypto.yaml（crypto prompt）
    - 其他    → experiment.yaml（默认 A 股 prompt）
    """
    if get_market_type() == "crypto":
        crypto_path = PROMPTS_DIR / "experiment_crypto.yaml"
        if crypto_path.exists():
            return crypto_path
    return PROMPTS_DIR / "experiment.yaml"


def get_prompts_file() -> Path:
    """
    根据 MARKET_TYPE 返回因子生成 prompts yaml 文件。
    - crypto  → prompts_crypto.yaml（crypto 变量描述用 "asset" 措辞）
    - 其他    → prompts.yaml（A 股变量描述用 "stock" 措辞）
    """
    if get_market_type() == "crypto":
        crypto_path = PROMPTS_DIR / "prompts_crypto.yaml"
        if crypto_path.exists():
            return crypto_path
    return PROMPTS_DIR / "prompts.yaml"


def get_readme_file() -> Path:
    """
    根据 MARKET_TYPE 返回数据说明 README 文件。
    - crypto  → README_crypto.md（crypto 数据描述）
    - 其他    → README.md（A 股数据描述）
    """
    if get_market_type() == "crypto":
        crypto_path = PROMPTS_DIR.parent / "data_template" / "README_crypto.md"
        if crypto_path.exists():
            return crypto_path
    return PROMPTS_DIR.parent / "data_template" / "README.md"


def is_crypto() -> bool:
    return get_market_type() == "crypto"
