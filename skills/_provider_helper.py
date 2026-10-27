# skills/_provider_helper.py
"""给 skills 层用的 provider 快捷构造器。

统一走 FallbackImageProvider，享受 providers 层的自动回退。
"""

from __future__ import annotations

import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


def build_image_provider(
    primary: Optional[str] = None,
    fallback: Optional[list[str]] = None,
    on_fallback: Optional[Callable[[str, str, Exception], None]] = None,
):
    """构造一个带 fallback 的图像 provider 链。

    Args:
        primary:     首选 provider 名（默认取 settings.api_provider）
        fallback:    备选 provider 列表（默认：其它所有 image provider，free 优先）
        on_fallback: 回调 (failed_name, next_name, error)，可选

    Returns:
        FallbackImageProvider 实例
    """
    from config.settings import settings
    from providers import list_providers, get_meta
    from providers.fallback import FallbackImageProvider

    primary = primary or settings.api_provider

    image_providers = list_providers("image")
    if not image_providers:
        raise RuntimeError("providers 注册表里没有任何 image provider")

    if primary not in image_providers:
        fallback_primary = "agnes" if "agnes" in image_providers else image_providers[0]
        logger.warning(
            f"⚠️ provider '{primary}' 不支持图像，回退到 {fallback_primary}"
        )
        primary = fallback_primary

    if fallback is None:
        fallback = [p for p in image_providers if p != primary]
        fallback.sort(key=lambda p: (not get_meta(p).get("free", False), p))

    pool = [primary] + [p for p in fallback if p != primary]

    # settings.get_provider_config 会自动扫 .env 里 {NAME}_* 变量
    configs = {p: settings.get_provider_config(p) for p in pool}

    return FallbackImageProvider(
        primary=primary,
        fallback=[p for p in pool if p != primary],
        configs=configs,
        on_fallback=on_fallback,
    )


def get_provider_capabilities(provider_name: str) -> list[str]:
    """拿某个 provider 的能力列表（image / video / text / vision ...）。"""
    from providers import get_meta
    return list(get_meta(provider_name).get("capabilities", []))


def list_image_providers() -> list[str]:
    """列出所有支持 image 的 provider（free 优先）。"""
    from providers import list_providers, get_meta
    names = list_providers("image")
    names.sort(key=lambda p: (not get_meta(p).get("free", False), p))
    return names