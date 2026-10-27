# providers/fallback.py
"""Provider 回退封装。

为什么不放在 capability 层？
  A 阶段只做"provider 注册"，回退逻辑也应该在 provider 层收口，
  这样 handlers 完全不用关心"谁失败后换谁"。

用法：
    from providers.fallback import FallbackImageProvider
    
    p = FallbackImageProvider(
        primary="freeapi",
        fallback=["pollinations", "agnes"],
        configs={"freeapi": {...}, "pollinations": {...}},
    )
    image = p.text_to_image(req)
"""

from __future__ import annotations

import logging
from typing import Optional

from PIL import Image

from .base import ImageRequest, ImageProvider
from .registry import create
from .errors import ProviderUnavailable, ProviderAuthError, ProviderConfigError

logger = logging.getLogger(__name__)


class FallbackImageProvider:
    """按顺序尝试多个 provider，直到成功。

    - ProviderUnavailable / 网络超时 / 5xx → 尝试下一个
    - ProviderAuthError / ProviderConfigError → 立刻中止（切了也没用）
    """

    def __init__(
        self,
        primary: str,
        fallback: list[str],
        configs: dict[str, dict],
        on_fallback: Optional[callable] = None,
    ):
        self.primary = primary
        self.chain = [primary] + [p for p in fallback if p != primary]
        self.configs = configs
        self.on_fallback = on_fallback  # 回调 (failed, next_provider, error)

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        return self._try(lambda p: p.text_to_image(req), "text_to_image")

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        return self._try(lambda p: p.image_to_image(req), "image_to_image")

    def _try(self, call, op_name: str):
        last_error: Exception | None = None
        for i, name in enumerate(self.chain):
            try:
                cfg = self.configs.get(name, {})
                provider = create(name, cfg)
                logger.info(f"[{op_name}] 尝试 provider: {name}")
                return call(provider)
            except (ProviderAuthError, ProviderConfigError):
                # 认证/配置错误：切下一个没意义
                raise
            except Exception as e:
                last_error = e
                if i == len(self.chain) - 1:
                    break
                next_name = self.chain[i + 1]
                logger.warning(
                    f"[{op_name}] provider {name} 失败: {e}，"
                    f"切换到 {next_name}"
                )
                if self.on_fallback:
                    try:
                        self.on_fallback(name, next_name, e)
                    except Exception:
                        pass
        raise last_error or RuntimeError(f"所有 provider 都失败: {self.chain}")