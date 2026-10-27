# api_engines/__init__.py
"""
[DEPRECATED] 兼容层，仅保留 create_engine / create_api_engine 两个入口。

新代码请直接用：
    from providers import create, list_providers, get_meta
    from providers.base import ImageRequest
    from providers.fallback import FallbackImageProvider

本文件将在 Phase 1 完成后删除。
"""

import warnings


def create_engine(provider: str, config: dict):
    """兼容旧调用。内部转调 providers.create。"""
    warnings.warn(
        "api_engines.create_engine 已废弃，请改用 providers.create()。"
        "本函数将在下一个大版本删除。",
        DeprecationWarning,
        stacklevel=2,
    )
    from providers import create
    return create(provider, config)


# 兼容旧名称
create_api_engine = create_engine


__all__ = ["create_engine", "create_api_engine"]