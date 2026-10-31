# providers/registry.py
"""Provider 注册表。"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .errors import ProviderConfigError
import os

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
    config_schema: dict[str, dict] | None = None,   # ← 新增
):
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
            "config_schema": config_schema or {},    # ← 新增
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
    
# ============================================================
# 配置自动加载（P3 新增）
# ============================================================

def load_config(name: str) -> dict:
    """按 config_schema 从环境变量加载 provider 配置。"""
    meta = _META.get(name)
    if not meta:
        return {}

    schema = meta.get("config_schema", {})
    cfg: dict = {}

    if not schema:
        prefix = f"{name.upper()}_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                short = key[len(prefix):].lower()
                cfg[short] = value
                cfg[key] = value
        return cfg

    for key, spec in schema.items():
        env_key = spec.get("env") or f"{name.upper()}_{key.upper()}"
        val = os.getenv(env_key)

        if val is None or val == "":
            val = spec.get("default")

        if (val is None or val == "") and spec.get("required"):
            raise ProviderConfigError(f"{name} 缺少必填配置: {env_key}")

        type_ = spec.get("type", "str")
        if val is not None and val != "":
            try:
                if type_ == "int":
                    val = int(val)
                elif type_ == "float":
                    val = float(val)
                elif type_ == "bool":
                    val = str(val).lower() in ("1", "true", "yes", "on")
            except (ValueError, TypeError):
                pass

        cfg[key] = val
        cfg[env_key] = val

    return cfg


def validate_config(name: str) -> list[str]:
    """检查 provider 配置是否齐全，返回缺失的 env 变量名。"""
    meta = _META.get(name, {})
    schema = meta.get("config_schema", {})
    missing = []
    for key, spec in schema.items():
        if not spec.get("required"):
            continue
        env_key = spec.get("env") or f"{name.upper()}_{key.upper()}"
        if not os.getenv(env_key):
            missing.append(env_key)
    return missing


def validate_all() -> dict[str, list[str]]:
    """检查所有 provider，返回 {name: [缺失 env]}。"""
    result = {}
    for name in _META:
        missing = validate_config(name)
        if missing:
            result[name] = missing
    return result    