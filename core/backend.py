# core/backend.py
"""⚠️ DEPRECATED

此模块已被 providers.fallback.FallbackImageProvider 取代。
保留此文件只是为了兼容旧调用（gui/app.py 的 _load_model 等处）。

新代码请直接用：
    from providers.fallback import FallbackImageProvider

build_backend() 现在返回一个 UnifiedBackend 兼容包装，
接口形状不变（text_to_image / image_to_image / preload），
但内部走 providers 链，本地模型现在是一个正式 provider（local_sd）。
"""

from __future__ import annotations

import logging
import threading
import warnings
from typing import Optional

from PIL import Image

from providers.base import ImageRequest
from providers.fallback import FallbackImageProvider
from providers import list_providers
from config.settings import settings

logger = logging.getLogger(__name__)


class UnifiedBackend:
    """Deprecated 兼容层（内部走 FallbackImageProvider）。"""

    def __init__(self):
        warnings.warn(
            "UnifiedBackend 已废弃，请改用 providers.fallback.FallbackImageProvider",
            DeprecationWarning,
            stacklevel=2,
        )
        self._provider = self._build_provider()

    def _build_provider(self) -> FallbackImageProvider:
        all_image = list_providers("image")
        if not all_image:
            raise RuntimeError("providers 注册表里没有任何 image provider")

        mode = getattr(settings, "generation_mode", "local")
        if mode == "local" and "local_sd" in all_image:
            primary = "local_sd"
        elif mode == "api":
            primary = getattr(settings, "api_provider", "agnes")
            if primary not in all_image:
                primary = all_image[0]
        else:
            primary = "local_sd" if "local_sd" in all_image else all_image[0]

        pool = [p for p in all_image if p != primary]

        configs = {}
        for p in [primary] + pool:
            if p == "local_sd":
                configs[p] = {
                    "model_path": settings.model_path,
                    "lora_path": settings.lora_path,
                    "device": "CPU",
                }
            else:
                configs[p] = settings.get_provider_config(p)

        logger.info(f"🚀 UnifiedBackend(deprecated) 初始化 primary={primary} pool={pool}")
        return FallbackImageProvider(
            primary=primary,
            fallback=pool,
            configs=configs,
            on_fallback=lambda frm, to, err: logger.warning(
                f"⚠️ 降级触发: {frm} -> {to} | {str(err).splitlines()[0][:80]}"
            ),
        )

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        return self._provider.text_to_image(req)

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        return self._provider.image_to_image(req)

    def get_name(self) -> str:
        return f"Unified ({self._provider.primary})"

    def is_loaded(self) -> bool:
        return True

    def preload(self) -> None:
        """预热本地模型（如果 primary 是 local_sd）。"""
        if self._provider.primary != "local_sd":
            return
        try:
            from providers.registry import create
            logger.info("📦 正在预热本地模型...")
            create("local_sd", {
                "model_path": settings.model_path,
                "lora_path": settings.lora_path,
                "device": "CPU",
            })
            logger.info("✅ 本地模型预热完成")
        except Exception as e:
            logger.warning(f"⚠️ 本地模型预热失败（不影响 API 降级）: {e}")


# ---------- 工厂（保留旧接口）----------

_backend_singleton: Optional[UnifiedBackend] = None
_backend_lock = threading.Lock()


def build_backend() -> UnifiedBackend:
    global _backend_singleton
    if _backend_singleton is not None:
        return _backend_singleton
    with _backend_lock:
        if _backend_singleton is not None:
            return _backend_singleton
        _backend_singleton = UnifiedBackend()
        return _backend_singleton


def reset_backend() -> None:
    global _backend_singleton
    with _backend_lock:
        _backend_singleton = None
    try:
        from providers.registry import clear_cache
        clear_cache()
    except ImportError:
        pass