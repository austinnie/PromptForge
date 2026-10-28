# providers/__init__.py
"""Provider 包入口。自动扫描并注册所有 adapters。"""

import importlib
import logging
import pkgutil

# ★ 关键：必须最先导入 registry，保证 register 定义存在
from .registry import (
    register, create, get, list_providers, get_meta, all_meta, clear_cache
)
from .base import (
    ImageRequest, VideoRequest, AudioRequest,
    ImageProvider, VideoProvider, AudioProvider, VisionProvider,
)
from .errors import (
    ProviderError, ProviderUnavailable, ProviderAuthError, ProviderConfigError
)

logger = logging.getLogger(__name__)

def _autoload_adapters():
    """自动扫描 providers/adapters/ 下的模块并导入"""
    try:
        from . import adapters
    except ImportError:
        return
    
    package = adapters
    prefix = package.__name__ + "."
    for _, module_name, _ in pkgutil.iter_modules(package.__path__, prefix):
        # 跳过下划线开头的内部模块
        if module_name.split(".")[-1].startswith("_"):
            continue
        try:
            importlib.import_module(module_name)
            logger.debug(f"✅ loaded adapter: {module_name}")
        except Exception as e:
            logger.warning(f"⚠️ adapter 加载失败 {module_name}: {e}")

_autoload_adapters()