# core/api_engines/__init__.py

"""API 图像生成引擎"""

from .base import BaseEngine
from .tongyi import TongyiEngine
from .yige import YigeEngine
from .hunyuan import HunyuanEngine
from .huggingface import HuggingFaceEngine
from .pollinations import PollinationsEngine      # 新增
from .agnes import AgnesEngine                    # 新增
from .freeapi import FreeAPIEngine                # 新增


def create_api_engine(provider: str, config: dict) -> BaseEngine:
    """创建 API 引擎实例（LayerForge 版本）"""
    
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
    
    # ✅ 以下为新增
    elif provider == "pollinations":
        return PollinationsEngine(
            model=config.get("POLLINATIONS_MODEL", None)  # ✅ 传递模型
        )
    
    elif provider == "agnes":
        return AgnesEngine(
            api_key=config.get("AGNES_API_KEY"),
            base_url=config.get("AGNES_BASE_URL"),
            model=config.get("AGNES_MODEL", None),
            image_model=config.get("AGNES_IMAGE_MODEL", None),
            text_model=config.get("AGNES_TEXT_MODEL", None),
            video_model=config.get("AGNES_VIDEO_MODEL", None),
            vision_model=config.get("AGNES_VISION_MODEL", None),
        )
    
    elif provider == "freeapi":
        return FreeAPIEngine(
            model=config.get("FREEAPI_MODEL", "grok-imagine-image-lite")
        )
    
    else:
        raise ValueError(f"不支持的 API 提供商: {provider}")


# 使用 LayerForge 风格的工厂（内部已包含所有增强逻辑）
def create_engine(provider: str, config: dict) -> BaseEngine:
    # 直接复用 LayerForge 的工厂代码，或者重命名
    from . import create_api_engine
    return create_api_engine(provider, config)

# 保持旧名称兼容
create_api_engine = create_engine

__all__ = [
    'BaseEngine', 
    'TongyiEngine', 
    'YigeEngine', 
    'HunyuanEngine',
    'HuggingFaceEngine', 
    'PollinationsEngine', 
    'AgnesEngine',
    'FreeAPIEngine', 
    'create_engine', 
    'create_api_engine',
]