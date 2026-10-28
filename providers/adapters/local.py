# providers/adapters/local.py
"""本地模型适配器。"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from PIL import Image

from ..base import BaseProvider, ImageRequest
from ..registry import register
from ..errors import ProviderUnavailable
# 确保导入了 model_manager
from model_manager import get_checkpoint

logger = logging.getLogger(__name__)


# providers/adapters/local.py
from model_manager import list_checkpoints, get_checkpoint

# 添加一个默认配置读取逻辑
try:
    from config.settings import settings
    DEFAULT_LOCAL_MODEL_ID = getattr(settings, "default_local_model_id", None)
except ImportError:
    DEFAULT_LOCAL_MODEL_ID = None

@register("local_sd", ...)
class LocalSDAdapter(BaseProvider):
    
    @classmethod
    def from_config(cls, config: dict):
        # ★ 核心逻辑：如果传了 model_id 就用传的，没传就去配置/清单里找
        model_id = config.get("model_id")
        if not model_id:
            models = list_checkpoints()
            if not models:
                raise ProviderUnavailable("清单中无本地模型")
            
            # 尝试用默认配置，如果配置里没有或模型被删了，用第一个
            if DEFAULT_LOCAL_MODEL_ID and any(m["id"] == DEFAULT_LOCAL_MODEL_ID for m in models):
                model_id = DEFAULT_LOCAL_MODEL_ID
            else:
                model_id = models[0]["id"]
                
        return cls(
            model_id=model_id, 
            device=config.get("device", "CPU"),
            engine_type=config.get("engine_type", "auto")
        )
        
        
# ============================================================
# 本地引擎基类与实现（保持不变）
# ============================================================

class BaseLocalEngine(ABC):
    def __init__(self, model_type: str = "sd15", device: str = "CPU"):
        self.model_type = model_type
        self.device = device
        self.pipeline = None
        self.model_path: Path = None

    def load_model(self, model_path: str = None) -> "BaseLocalEngine":
        if not model_path:
            raise ValueError("必须提供模型路径")
        
        self.model_path = Path(model_path).resolve()
        if not self.model_path.exists():
            raise FileNotFoundError(f"本地模型文件不存在: {self.model_path}")

        logger.info(f"🚀 开始加载本地模型: {self.model_path.name} (设备: {self.device})")
        self._do_load(self.model_path)
        logger.info("✅ 模型加载完成！")
        return self

    @abstractmethod
    def _do_load(self, absolute_path: Path): pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs): pass


class DiffusersEngine(BaseLocalEngine):
    def _do_load(self, absolute_path: Path):
        from diffusers import StableDiffusionPipeline, StableDiffusionXLPipeline
        import torch
        
        is_sdxl = "sdxl" in str(absolute_path).lower() or "xl" in str(absolute_path).lower()
        dtype = torch.float32 if self.device == "CPU" else torch.float16
        
        if is_sdxl:
            self.pipeline = StableDiffusionXLPipeline.from_single_file(
                str(absolute_path), torch_dtype=dtype, use_safetensors=True, low_cpu_mem_usage=True
            )
        else:
            self.pipeline = StableDiffusionPipeline.from_single_file(
                str(absolute_path), torch_dtype=dtype, safety_checker=None,
                requires_safety_checker=False, use_safetensors=True, low_cpu_mem_usage=True
            )
            
        if hasattr(self.pipeline, 'enable_vae_slicing'):
            self.pipeline.enable_vae_slicing()
        if hasattr(self.pipeline, 'enable_attention_slicing'):
            self.pipeline.enable_attention_slicing()

    def generate(self, prompt: str, negative_prompt: str = "", width: int = 512, height: int = 512, 
                 num_inference_steps: int = 25, guidance_scale: float = 7.5, seed: int = None) -> Image.Image:
        if self.pipeline is None: raise RuntimeError("模型未加载")
        
        width = (width // 8) * 8
        height = (height // 8) * 8
        
        import torch
        if seed is None or seed == -1:
            seed = torch.randint(0, 2**32 - 1, (1,)).item()
        generator = torch.Generator("cpu").manual_seed(seed)
        
        result = self.pipeline(
            prompt=prompt, negative_prompt=negative_prompt,
            width=width, height=height,
            num_inference_steps=num_inference_steps, guidance_scale=guidance_scale,
            generator=generator
        )
        return result.images[0]


class OpenVINOEngine(DiffusersEngine):
    def _do_load(self, absolute_path: Path):
        try:
            from optimum.intel import OVStableDiffusionPipeline
            self.pipeline = OVStableDiffusionPipeline.from_single_file(
                str(absolute_path), export=True, compile=True
            )
            logger.info("✅ OpenVINO 编译完成。")
        except ImportError:
            logger.warning("未安装 optimum-intel，自动降级使用普通 Diffusers 引擎...")
            super()._do_load(absolute_path)


# ============================================================
# 适配器（核心修复区）
# ============================================================

@register(
    "local_sd", capabilities=["image"], requires_key=False, free=True,
    description="本地 Stable Diffusion"
)
class LocalSDAdapter(BaseProvider):
    
    @classmethod
    def from_config(cls, config: dict):
        # ★ 关键修复：确保接收并传递 model_id
        return cls(
            model_id=config.get("model_id"), 
            device=config.get("device", "CPU"),
            engine_type=config.get("engine_type", "auto")
        )

    def __init__(self, model_id: str, device: str = "CPU", engine_type: str = "auto"):
        if not model_id:
            raise ProviderUnavailable("local_sd 启动失败：必须提供 model_id")

        # ★ 核心修复：通过 model_manager 获取真实路径
        ckpt = get_checkpoint(model_id)
        if not ckpt:
            raise ProviderUnavailable(f"未找到模型 ID: {model_id}，请检查模型清单。")

        real_path = ckpt["path"]
        base_type = ckpt.get("base", "sd15")
        real_engine = ckpt.get("type", "diffusers") if engine_type == "auto" else engine_type

        logger.info(f"正在初始化本地引擎 (模型ID: {model_id}, 真实路径: {real_path})...")

        if real_engine == "openvino":
            self._engine = OpenVINOEngine(model_type=base_type, device=device)
        else:
            self._engine = DiffusersEngine(model_type=base_type, device=device)

        try:
            self._engine.load_model(model_path=real_path)
        except Exception as e:
            logger.error(f"❌ 本地模型加载失败: {e}")
            raise ProviderUnavailable(f"本地模型加载失败: {e}")

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        try:
            return self._engine.generate(
                prompt=req.prompt, negative_prompt=req.negative,
                width=req.width, height=req.height,
                num_inference_steps=req.steps, guidance_scale=req.cfg, seed=req.seed
            )
        except Exception as e:
            logger.error(f"本地推理出错: {e}")
            raise ProviderUnavailable(f"本地推理失败: {e}")

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        raise NotImplementedError("本地引擎暂未实现图生图")

    def get_name(self) -> str:
        return f"LocalSD ({self.device})"