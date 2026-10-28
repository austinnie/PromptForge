# core/backend.py
"""图像生成统一后端抽象层。

设计：
  - handlers 层只调 backend，不关心 local / api
  - 本地 = LocalBackend（diffusers）
  - API  = FallbackImageProvider（providers 层，带自动回退）
  - auto = AutoBackend（本地优先，运行期失败 → API）

历史：
  早期 ApiBackend 只是把 FallbackImageProvider 换了层皮，
  后来合并到本文件，ApiBackend 已删除。
"""

from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from PIL import Image

from providers.base import ImageRequest
from config.settings import settings

logger = logging.getLogger(__name__)


# ============================================================
# 0. 后端协议（统一签名）
# ============================================================

class BaseImageBackend(ABC):
    """图像生成后端基类。

    所有实现必须提供 text_to_image / image_to_image，
    入参统一为 providers.base.ImageRequest。
    """

    @abstractmethod
    def text_to_image(self, req: ImageRequest) -> Image.Image: ...

    @abstractmethod
    def image_to_image(self, req: ImageRequest) -> Image.Image: ...

    @abstractmethod
    def get_name(self) -> str: ...

    # ---- 可选：状态查询（供 GUI 显示）----
    def is_loaded(self) -> bool:
        return True

    def preload(self) -> None:
        """预热（本地模式加载模型；API 模式空实现）"""
        return None


# ============================================================
# 1. 本地后端（diffusers）
# ============================================================

class LocalBackend(BaseImageBackend):
    """本地 SD/SDXL 后端。

    关键改进：
      - 懒加载：__init__ 不加载模型，首次推理时才加载
      - 走 PipelinePool 复用（避免多次 LocalBackend() 各加载一份）
      - 路径自适应（D盘/E盘）
    """

    def __init__(self, model_path: str = None):
        self.model_path = self._resolve_model_path(model_path)
        self.pipeline = None
        self._load_lock = threading.Lock()

    def _resolve_model_path(self, raw_path: str) -> str:
        """智能解析模型路径（适配不同电脑 D盘/E盘）"""
        if raw_path and Path(raw_path).exists():
            return str(Path(raw_path).resolve())

        env_path = settings.model_path
        if env_path and Path(env_path).exists():
            return str(Path(env_path).resolve())

        # .env 里配的是 D:\，但家里是 E:\ → 换盘符试试
        if env_path:
            original = Path(env_path)
            tail = Path(*original.parts[1:]) if len(original.parts) > 1 else Path("")
            for drive in ["E:/", "D:/", "C:/"]:
                test_path = Path(drive) / tail
                if test_path.exists():
                    logger.info(f"🔄 路径自适应: {env_path} → {test_path}")
                    return str(test_path.resolve())

        raise FileNotFoundError(
            f"找不到本地模型文件。\n"
            f"  配置的路径: {env_path or '(未配置)'}\n"
            f"  已尝试盘符: E:/, D:/, C:/\n"
            f"  请检查 .env 里的 SD_MODEL_PATH"
        )

    def _ensure_loaded(self):
        """懒加载：首次调用时加载模型（走 PipelinePool 复用）。"""
        if self.pipeline is not None:
            return self.pipeline

        with self._load_lock:
            if self.pipeline is not None:
                return self.pipeline
            self._init_pipeline()
        return self.pipeline

    def _init_pipeline(self):
        # ✅ 优先走 PipelinePool（复用已加载的模型）
        try:
            from services.pipeline_pool import pipeline_pool
            pipe, newly_loaded = pipeline_pool.get_pipeline(self.model_path)
            if pipe is not None:
                self.pipeline = pipe
                if newly_loaded:
                    logger.info(f"✅ 本地模型加载完成: {self.model_path}")
                else:
                    logger.info(f"♻️ 复用已有 Pipeline: {self.model_path}")
                return
        except Exception as e:
            logger.warning(f"⚠️ PipelinePool 不可用，回退直接加载: {e}")

        # 兜底：直接加载
        self._load_direct()

    def _load_direct(self):
        import torch
        from diffusers import StableDiffusionPipeline, StableDiffusionXLPipeline

        logger.info(f"📦 正在加载本地模型: {self.model_path}")
        is_sdxl = "sdxl" in self.model_path.lower() or "xl" in self.model_path.lower()
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        cls = StableDiffusionXLPipeline if is_sdxl else StableDiffusionPipeline
        kwargs = dict(
            torch_dtype=dtype,
            use_safetensors=True,
            low_cpu_mem_usage=True,
        )
        if not is_sdxl:
            kwargs.update(safety_checker=None, requires_safety_checker=False)

        self.pipeline = cls.from_single_file(self.model_path, **kwargs)
        self.pipeline.to("cuda" if torch.cuda.is_available() else "cpu")

        if hasattr(self.pipeline, "enable_vae_slicing"):
            self.pipeline.enable_vae_slicing()
        if hasattr(self.pipeline, "enable_attention_slicing"):
            self.pipeline.enable_attention_slicing()

        logger.info("✅ 本地模型加载完成")

    def preload(self) -> None:
        self._ensure_loaded()

    def is_loaded(self) -> bool:
        return self.pipeline is not None

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        import torch
        self._ensure_loaded()

        width = max((req.width // 8) * 8, 64)
        height = max((req.height // 8) * 8, 64)
        seed = req.seed or torch.randint(0, 2**32 - 1, (1,)).item()
        generator = torch.Generator("cpu").manual_seed(seed)

        logger.info(f"🎨 本地推理: {req.prompt[:40]}... (步数: {req.steps})")
        result = self.pipeline(
            prompt=req.prompt,
            negative_prompt=req.negative,
            width=width,
            height=height,
            num_inference_steps=req.steps,
            guidance_scale=req.cfg,
            generator=generator,
        )
        return result.images[0]

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        import torch
        self._ensure_loaded()
        if not req.reference:
            raise ValueError("本地图生图需要 reference 图片")

        width = max((req.width // 8) * 8, 64)
        height = max((req.height // 8) * 8, 64)
        seed = req.seed or torch.randint(0, 2**32 - 1, (1,)).item()
        generator = torch.Generator("cpu").manual_seed(seed)

        logger.info(f"🎨 本地图生图: {req.prompt[:40]}... (强度: {req.strength})")
        result = self.pipeline(
            prompt=req.prompt,
            negative_prompt=req.negative,
            image=req.reference,
            strength=req.strength,
            width=width,
            height=height,
            num_inference_steps=req.steps,
            guidance_scale=req.cfg,
            generator=generator,
        )
        return result.images[0]

    def get_name(self) -> str:
        return f"Local ({Path(self.model_path).stem})"


# ============================================================
# 2. API 后端（直接包 FallbackImageProvider）
# ============================================================

class ApiBackend(BaseImageBackend):
    """API 后端 - 就是 FallbackImageProvider 的别名。

    保留此类是为了：
      1. build_backend() 的语义清晰（local/api/auto 三态）
      2. 未来如需在 API 前后加预热 / 缓存，有个挂点
    """

    def __init__(self):
        from skills._provider_helper import build_image_provider
        self._provider = build_image_provider(
            on_fallback=lambda f, t, e: logger.warning(
                f"⚠️ API {f} 失败，切到 {t}: {str(e).splitlines()[0][:80]}"
            )
        )

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        return self._provider.text_to_image(req)

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        # provider 可能不支持图生图（AttributeError）
        if not hasattr(self._provider, "image_to_image"):
            raise RuntimeError(
                f"{self._provider.primary} 及其 fallback 都不支持图生图"
            )
        return self._provider.image_to_image(req)

    def get_name(self) -> str:
        return f"API ({self._provider.primary})"


# ============================================================
# 3. AutoBackend：本地优先，运行期失败降级 API
# ============================================================

class AutoBackend(BaseImageBackend):
    """自动模式：先本地，失败/未加载 → API。

    与旧实现的区别：
      旧: build_backend() 时如果本地加载失败，整个走 API（构建期降级）
      新: 构建期都建好，运行期首次推理时才决定（避免"配了本地但暂时不可用"就永久退化）
    """

    def __init__(self):
        self._local = None
        self._api = None
        self._local_unavailable = False

    def _get_local(self) -> Optional[LocalBackend]:
        if self._local_unavailable:
            return None
        if self._local is None:
            try:
                self._local = LocalBackend()
            except Exception as e:
                logger.warning(f"⚠️ 本地后端不可用，永久降级 API: {e}")
                self._local_unavailable = True
                return None
        return self._local

    def _get_api(self) -> ApiBackend:
        if self._api is None:
            self._api = ApiBackend()
        return self._api

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        local = self._get_local()
        if local is not None:
            try:
                return local.text_to_image(req)
            except Exception as e:
                logger.warning(f"⚠️ 本地推理失败，本次降级 API: {e}")
        return self._get_api().text_to_image(req)

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        local = self._get_local()
        if local is not None:
            try:
                return local.image_to_image(req)
            except Exception as e:
                logger.warning(f"⚠️ 本地图生图失败，本次降级 API: {e}")
        return self._get_api().image_to_image(req)

    def get_name(self) -> str:
        if self._local and self._local.is_loaded():
            return f"Auto (local: {self._local.get_name()})"
        return "Auto (api)"

    def is_loaded(self) -> bool:
        return self._local is not None and self._local.is_loaded()

    def preload(self) -> None:
        local = self._get_local()
        if local:
            local.preload()


# ============================================================
# 4. 工厂
# ============================================================

_backend_singleton: Optional[BaseImageBackend] = None
_backend_lock = threading.Lock()


def build_backend() -> BaseImageBackend:
    """按 settings.generation_mode 返回 backend。

    - local : LocalBackend
    - api   : ApiBackend
    - auto  : AutoBackend（本地优先，失败降级）

    进程内单例：同一 mode 只建一份，避免多次 build_backend() 各建一份 LocalBackend。
    切换模式请重启进程，或调用 reset_backend()。
    """
    global _backend_singleton
    if _backend_singleton is not None:
        return _backend_singleton

    with _backend_lock:
        if _backend_singleton is not None:
            return _backend_singleton

        mode = (settings.generation_mode or "local").lower()
        if mode == "local":
            _backend_singleton = LocalBackend()
        elif mode == "api":
            _backend_singleton = ApiBackend()
        elif mode == "auto":
            _backend_singleton = AutoBackend()
        else:
            raise ValueError(f"未知的 GENERATION_MODE: {mode}")

        logger.info(f"✅ Backend 已创建: {_backend_singleton.get_name()}")
        return _backend_singleton


def reset_backend() -> None:
    """清空单例（切换 generation_mode 时调用）"""
    global _backend_singleton
    with _backend_lock:
        _backend_singleton = None