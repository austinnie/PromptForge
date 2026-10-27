# api_engines/__init__.py

"""API 图像生成引擎"""

from .base import BaseEngine
from .tongyi import TongyiEngine
from .yige import YigeEngine
from .hunyuan import HunyuanEngine
from .huggingface import HuggingFaceEngine
from .pollinations import PollinationsEngine
from .agnes import AgnesEngine
from .freeapi import FreeAPIEngine
# ✅ 新增
from .replicate import ReplicateEngine
from .stability import StabilityEngine

# 20260915新增导入
from .free_multimodal_proxy import FreeMultimodalProxyEngine
from .freellmapi import FreeLLMAPIEngine
from .siliconflow import SiliconFlowEngine
from .openrouter import OpenRouterEngine

#def create_engine(provider: str, config: dict) -> BaseEngine:
#    """创建 API 引擎实例"""
#    
#    if provider == "tongyi":
#        return TongyiEngine(
#            api_key=config.get("TONGYI_API_KEY"),
#            model=config.get("TONGYI_MODEL", "wanx-v1")
#        )
#    
#    elif provider == "yige":
#        return YigeEngine(
#            api_key=config.get("YIGE_API_KEY"),
#            secret_key=config.get("YIGE_SECRET_KEY")
#        )
#    
#    elif provider == "hunyuan":
#        return HunyuanEngine(
#            secret_id=config.get("HUNYUAN_SECRET_ID"),
#            secret_key=config.get("HUNYUAN_SECRET_KEY")
#        )
#    
#    elif provider == "huggingface":
#        return HuggingFaceEngine(
#            api_token=config.get("HF_API_TOKEN"),
#            model=config.get("HF_MODEL", "sdxl")
#        )
#    
#    elif provider == "pollinations":
#        return PollinationsEngine(
#            api_key=config.get("POLLINATIONS_API_KEY"),
#            model=config.get("POLLINATIONS_MODEL"),
#            video_model=config.get("POLLINATIONS_VIDEO_MODEL"),
#            audio_model=config.get("POLLINATIONS_AUDIO_MODEL"),
#        )
#    
#    elif provider == "agnes":
#        return AgnesEngine(
#            api_key=config.get("AGNES_API_KEY"),
#            base_url=config.get("AGNES_BASE_URL"),
#            model=config.get("AGNES_MODEL", None),
#            image_model=config.get("AGNES_IMAGE_MODEL", None),
#            text_model=config.get("AGNES_TEXT_MODEL", None),
#            video_model=config.get("AGNES_VIDEO_MODEL", None),
#            vision_model=config.get("AGNES_VISION_MODEL", None),
#        )
#    
#    elif provider == "freeapi":
#        return FreeAPIEngine(
#            model=config.get("FREEAPI_MODEL", "grok-imagine-image-lite")
#        )
#    
#    # ✅ 新增 Replicate
#    elif provider == "replicate":
#        return ReplicateEngine(
#            api_token=config.get("REPLICATE_API_TOKEN"),
#            model=config.get("REPLICATE_MODEL", "stability-ai/stable-diffusion")
#        )
#    
#    # ✅ 新增 Stability AI
#    elif provider == "stability":
#        return StabilityEngine(
#            api_key=config.get("STABILITY_API_KEY"),
#            model=config.get("STABILITY_MODEL", "stable-diffusion-xl-1024-v1-0")
#        )
#
#    elif provider == "free_multimodal_proxy":
#        return FreeMultimodalProxyEngine(
#            base_url=config.get("FREE_MULTIMODAL_PROXY_URL"),
#            model=config.get("FREE_MULTIMODAL_PROXY_MODEL", "zimage"),
#            proxy_token=config.get("FREE_MULTIMODAL_PROXY_TOKEN"),
#        )
#
#    elif provider == "freellmapi":
#        return FreeLLMAPIEngine(
#            base_url=config.get("FREELLMAPI_URL"),
#            model=config.get("FREELLMAPI_MODEL", "auto"),
#            api_key=config.get("FREELLMAPI_KEY"),
#        )
#
#    elif provider == "siliconflow":
#        return SiliconFlowEngine(
#            api_key=config.get("SILICONFLOW_API_KEY"),
#            model=config.get("SILICONFLOW_MODEL", "sd-turbo"),
#        )
#
#    elif provider == "openrouter":
#        return OpenRouterEngine(
#            api_key=config.get("OPENROUTER_API_KEY"),
#            model=config.get("OPENROUTER_MODEL", "bytedance-seed/seedream-4.5"),
#        )
#        
#    else:
#        raise ValueError(f"不支持的 API 提供商: {provider}")
#


def create_engine(provider: str, config: dict):
    """
    兼容旧调用：内部转调 providers.create。
    
    config 里 key 命名兼容两种：
      - 短名小写（api_key）        ← 新
      - 大写全名（AGNES_API_KEY）  ← 旧
    """
    from providers import create
    return create(provider, config)
    
# 兼容旧名称
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
    'ReplicateEngine',      # ✅ 新增
    'StabilityEngine',      # ✅ 新增
    'create_engine',
    'create_api_engine',
    
    'FreeMultimodalProxyEngine',
    'FreeLLMAPIEngine',
    'SiliconFlowEngine',
    'OpenRouterEngine',    
]