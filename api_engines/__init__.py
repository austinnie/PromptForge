# api_engines/__init__.py
"""API 图像生成引擎"""

from .base import BaseEngine
from .tongyi import TongyiEngine
from .yige import YigeEngine
from .hunyuan import HunyuanEngine
from .huggingface import HuggingFaceEngine


def create_engine(provider: str, config: dict) -> BaseEngine:
    """创建 API 引擎实例"""
    
    if provider == "tongyi":
        return TongyiEngine(
            api_key=config.get("TONGYI_API_KEY"),
            model=config.get("TONGYI_MODEL", "wanx-v1")
        )
    
    elif provider == "yige":
        return YigeEngine(
            api_key=config.get("YIGE_API_KEY"),
            secret_key=config.get("YIGE_SECRET_KEY")
        )
    
    elif provider == "hunyuan":
        return HunyuanEngine(
            secret_id=config.get("HUNYUAN_SECRET_ID"),
            secret_key=config.get("HUNYUAN_SECRET_KEY")
        )
    
    elif provider == "huggingface":
        return HuggingFaceEngine(
            api_token=config.get("HF_API_TOKEN"),
            model=config.get("HF_MODEL", "sdxl")
        )
    
    else:
        raise ValueError(f"不支持的 API 提供商: {provider}")


__all__ = [
    'BaseEngine',
    'TongyiEngine',
    'YigeEngine',
    'HunyuanEngine',
    'HuggingFaceEngine',
    'create_engine',
]