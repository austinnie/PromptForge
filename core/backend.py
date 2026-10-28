# core/backend.py
"""图像生成统一后端抽象层（Provider 驱动版）。

设计：
  - handlers 层只调 backend，不关心 local / api
  - 核心委派给 providers.FallbackImageProvider
  - 支持配置在 local 优先、api 优先、auto 三态下运行
"""

from __future__ import annotations

import logging
import threading
from typing import Optional
from PIL import Image

from providers.base import ImageRequest
from providers.fallback import FallbackImageProvider
from providers import list_providers
from config.settings import settings

logger = logging.getLogger(__name__)

# ============================================================
# 统一后端（基于 Provider 架构）
# ============================================================

class UnifiedBackend:
    """统一后端。把请求转发给 FallbackImageProvider。"""

    def __init__(self):
        self._provider = self._build_provider()

    def _build_provider(self) -> FallbackImageProvider:
        mode = getattr(settings, "generation_mode", "local")
        
        # 1. 决定 primary
        if mode == "local":
            primary = "local_sd"
        elif mode == "api":
            primary = getattr(settings, "api_provider", "agnes")
        else: # auto 模式（本地优先）
            primary = "local_sd"

        # 2. 收集所有图像 Provider，并生成 fallback 池
        all_image = list_providers("image")
        if primary not in all_image:
            primary = all_image[0] if all_image else "agnes"

        # 过滤掉 primary 后作为降级池
        pool = [p for p in all_image if p != primary]

        # 3. 组装配置
        configs = {}
        for p in [primary] + pool:
            if p == "local_sd":
                configs[p] = {
                    "device": "CPU",
                    "model_id": getattr(settings, "default_local_model_id", None)
                }
            else:
                configs[p] = settings.get_provider_config(p)

        # 4. 构建并返回 FallbackImageProvider
        logger.info(f"🚀 初始化 UnifiedBackend (primary={primary}, pool={pool})")
        return FallbackImageProvider(
            primary=primary,
            fallback=pool,
            configs=configs,
            on_fallback=lambda frm, to, err: logger.warning(
                f"⚠️ 降级触发: {frm} -> {to} | 原因: {str(err).splitlines()[0][:80]}"
            )
        )

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        return self._provider.text_to_image(req)

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        return self._provider.image_to_image(req)

    def get_name(self) -> str:
        return f"Unified ({self._provider.primary})"

    def is_loaded(self) -> bool:
        # 在新的 Provider 架构下，无需手动判断是否加载
        return True

    def preload(self) -> None:
        # 提前触发本地模型加载（如果当前 primary 是 local_sd）
        if self._provider.primary == "local_sd":
            try:
                from providers.registry import create
                logger.info("📦 正在预热本地模型...")
                create("local_sd", config={"device": "CPU"})
                logger.info("✅ 本地模型预热完成")
            except Exception as e:
                logger.warning(f"⚠️ 本地模型预热失败（不影响后续 API 降级）: {e}")


# ============================================================
# 工厂
# ============================================================

_backend_singleton: Optional[UnifiedBackend] = None
_backend_lock = threading.Lock()

def build_backend() -> UnifiedBackend:
    """进程内单例"""
    global _backend_singleton
    if _backend_singleton is not None:
        return _backend_singleton

    with _backend_lock:
        if _backend_singleton is not None:
            return _backend_singleton
        _backend_singleton = UnifiedBackend()
        return _backend_singleton

def reset_backend() -> None:
    """切换模型/模式时调用，强制重新构建"""
    global _backend_singleton
    with _backend_lock:
        _backend_singleton = None
    # 同时清空 Provider 缓存，确保下次加载新模型
    try:
        from providers.registry import clear_cache
        clear_cache()
    except ImportError:
        pass