# providers/registry.py
"""Provider 注册表。

用法：
    from providers import register, create, list_providers

    @register("agnes")
    class AgnesAdapter(BaseProvider):
        ...

    p = create("agnes", {"api_key": "..."})
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .errors import ProviderConfigError

logger = logging.getLogger(__name__)

# name -> adapter class
_REGISTRY: dict[str, type] = {}

# name -> metadata（供 GUI 展示）
_META: dict[str, dict] = {}

_INSTANCE_CACHE: dict[str, Any] = {}  # ★ 新增：单例缓存

def register(
    name: str,
    *,
    capabilities: list[str] | None = None,
    requires_key: bool = False,
    free: bool = False,
    description: str = "",
):
    """
    装饰器：把 provider 注册进注册表。

    Args:
        name:          provider 唯一名称（与 .env 前缀一致，如 "agnes"）
        capabilities:  支持的能力列表，如 ["image", "video", "text"]
        requires_key:  是否需要 API key
        free:          是否免费
        description:   描述（GUI 显示用）
    """
    def deco(cls):
        if name in _REGISTRY:
            raise ProviderConfigError(
                f"provider '{name}' 重复注册: "
                f"{_REGISTRY[name].__name__} vs {cls.__name__}"
            )
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
    # ★ 如果已经有缓存且不需要强刷，直接返回
    if name in _INSTANCE_CACHE and not force_new:
        return _INSTANCE_CACHE[name]

    cls = _REGISTRY.get(name)
    if cls is None:
        raise ProviderConfigError(f"未知 provider: '{name}'。已注册: {list_providers()}")

    try:
        config = config or {}
        instance = cls.from_config(config) if hasattr(cls, "from_config") else cls(**config)
        _INSTANCE_CACHE[name] = instance  # ★ 写入缓存
        return instance
    except TypeError as e:
        raise ProviderConfigError(f"provider '{name}' 配置构造失败: {e}") from e


def get(name: str) -> type:
    """返回 provider 类（不实例化），GUI 用于检查能力。"""
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