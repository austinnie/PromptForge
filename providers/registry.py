# providers/registry.py
"""Provider 注册表。"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .errors import ProviderConfigError

logger = logging.getLogger(__name__)

# name -> adapter class
_REGISTRY: dict[str, type] = {}
# name -> metadata（供 GUI 展示）
_META: dict[str, dict] = {}
# ★ 新增：单例缓存
_INSTANCE_CACHE: dict[str, Any] = {}


def register(
    name: str,
    *,
    capabilities: list[str] | None = None,
    requires_key: bool = False,
    free: bool = False,
    description: str = "",
):
    """装饰器：把 provider 注册进注册表。"""
    def deco(cls):
        if name in _REGISTRY:
            return cls
        cls.provider_name = name
        _REGISTRY[name] = cls
        _META[name] = {
            "name": name,
            "class": cls.__name__,
            "capabilities": capabilities or [],
            "requires_key": requires_key,
            "free": free,
            "description": description,
        }
        logger.debug(f"✅ registered provider: {name} -> {cls.__name__}")
        return cls
    return deco


def create(name: str, config: dict = None, force_new: bool = False) -> Any:
    """按名称创建（或获取） provider 实例。"""
    if name in _INSTANCE_CACHE and not force_new:
        return _INSTANCE_CACHE[name]

    cls = _REGISTRY.get(name)
    if cls is None:
        raise ProviderConfigError(
            f"未知 provider: '{name}'。已注册: {list_providers()}"
        )

    try:
        config = config or {}
        instance = cls.from_config(config) if hasattr(cls, "from_config") else cls(**config)
        _INSTANCE_CACHE[name] = instance
        return instance
    except TypeError as e:
        raise ProviderConfigError(
            f"provider '{name}' 配置构造失败: {e}\n"
            f"  传入配置: {list(config.keys())}"
        ) from e


def get(name: str) -> type:
    """返回 provider 类（不实例化）"""
    return _REGISTRY[name]


def list_providers(capability: str | None = None) -> list[str]:
    """列出所有 provider，可按能力过滤。"""
    if capability is None:
        return sorted(_REGISTRY)
    return sorted(
        name for name, meta in _META.items()
        if capability in meta["capabilities"]
    )


def get_meta(name: str) -> dict:
    return dict(_META.get(name, {}))


def all_meta() -> dict[str, dict]:
    return {k: dict(v) for k, v in _META.items()}


def clear_cache():
    """清空 Provider 实例缓存"""
    global _INSTANCE_CACHE
    _INSTANCE_CACHE.clear()
    logger.info("🗑️ Provider 实例缓存已清空")