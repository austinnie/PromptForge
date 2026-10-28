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

from .base import ImageRequest, ImageProvider, VideoRequest
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

# providers/fallback.py

    def _try(self, call, op_name: str):
        last_error: Exception | None = None
        for i, name in enumerate(self.chain):
            try:
                cfg = self.configs.get(name, {})
                # ★ 这里 create 会自动走缓存，不会重复加载本地模型
                provider = create(name, cfg) 
                logger.info(f"[{op_name}] 尝试 provider: {name}")
                return call(provider)
            except ProviderAuthError:
                raise
            except Exception as e:
                last_error = e
                if i == len(self.chain) - 1:
                    break
                next_name = self.chain[i + 1]
                logger.warning(f"[{op_name}] provider {name} 失败: {e}，切换到 {next_name}")
                if self.on_fallback:
                    try: self.on_fallback(name, next_name, e)
                    except Exception: pass
        raise last_error or RuntimeError(f"所有 provider 都失败: {self.chain}")

    def get_name(self) -> str:
        """用于上层回显当前引擎名称"""
        return f"Fallback ({self.primary})"

    # 如果你在 GUI 里也想展示当前真实的引擎（比如降级后），可以再补个属性
    @property
    def current_provider(self):
        return self.primary
        
class FallbackVideoProvider:
    """按顺序尝试多个 provider，直到视频任务创建成功。

    跟 FallbackImageProvider 同构，但只覆盖视频能力。
    注意：wait_for_video 只在"创建成功"的那个 provider 上调用，
    所以必须记住上次成功的 provider 名。
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
        self.on_fallback = on_fallback  # (failed, next, error)
        # 记录成功创建视频任务的 provider（wait_for_video 用）
        self._last_provider_name: Optional[str] = None

    def video_generation(self, req: VideoRequest) -> dict:
        last_error: Optional[Exception] = None
        for i, name in enumerate(self.chain):
            try:
                cfg = self.configs.get(name, {})
                provider = create(name, cfg)
                logger.info(f"[video_generation] 尝试 provider: {name}")
                result = provider.video_generation(req)
                self._last_provider_name = name
                return result
            except (ProviderAuthError, ProviderConfigError):
                # 认证 / 配置错误，切下一个没意义
                raise
            except Exception as e:
                last_error = e
                if i == len(self.chain) - 1:
                    break
                next_name = self.chain[i + 1]
                logger.warning(
                    f"[video_generation] {name} 失败: {e}，切换到 {next_name}"
                )
                if self.on_fallback:
                    try:
                        self.on_fallback(name, next_name, e)
                    except Exception:
                        pass
        raise last_error or RuntimeError(f"所有 provider 都失败: {self.chain}")

    def wait_for_video(self, video_id: str, **kw) -> str:
        """用"创建成功"的那个 provider 等结果。"""
        name = self._last_provider_name or self.primary
        cfg = self.configs.get(name, {})
        provider = create(name, cfg)
        return provider.wait_for_video(video_id, **kw)

    def get_name(self) -> str:
        return f"FallbackVideoProvider({self.chain})"        