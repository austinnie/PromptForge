# providers/__init__.py
"""Provider 层对外统一入口。

import providers 时自动扫描 providers/adapters/ 下所有模块，
触发 @register 装饰器执行。
"""

from .base import (
    ImageRequest, VideoRequest, AudioRequest,
    ImageProvider, VideoProvider, AudioProvider, VisionProvider,
    BaseProvider,
)
from .registry import (
    register, create, get, list_providers, get_meta, all_meta,
)
from .errors import (
    ProviderError, ProviderUnavailable, ProviderAuthError,
    ProviderConfigError, AllProvidersFailed,
)

# 自动导入适配器 —— 触发注册
# 用 pkgutil 扫描而不是手写 import 列表，新增文件零改动
import pkgutil
import importlib
from . import adapters as _adapters_pkg

for _m in pkgutil.iter_modules(_adapters_pkg.__path__):
    if _m.name.startswith("_"):
        continue
    importlib.import_module(f"{__name__}.adapters.{_m.name}")


__all__ = [
    # 请求对象
    "ImageRequest", "VideoRequest", "AudioRequest",
    # 协议
    "ImageProvider", "VideoProvider", "AudioProvider", "VisionProvider",
    "BaseProvider",
    # 注册表
    "register", "create", "get", "list_providers", "get_meta", "all_meta",
    # 异常
    "ProviderError", "ProviderUnavailable", "ProviderAuthError",
    "ProviderConfigError", "AllProvidersFailed",
]