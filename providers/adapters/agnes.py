# providers/adapters/agnes.py
"""Agnes AI 适配器。

包一层现有 api_engines.agnes.AgnesEngine，
把统一 ImageRequest / VideoRequest 翻译成该引擎能吃的参数。
"""

from __future__ import annotations

from typing import Optional

from PIL import Image

from ..base import BaseProvider, ImageRequest, VideoRequest
from ..errors import ProviderAuthError, ProviderUnavailable
from ..registry import register


@register(
    "agnes",
    capabilities=["image", "video", "text", "vision"],
    requires_key=True,
    free=True,
    description="Agnes AI，注册免费，支持图像/视频/文本/视觉",
)
class AgnesAdapter(BaseProvider):

    @classmethod
    def from_config(cls, config: dict):
        # 支持两种 key 命名（向后兼容老 .env）
        api_key = config.get("api_key") or config.get("AGNES_API_KEY")
        base_url = config.get("base_url") or config.get("AGNES_BASE_URL")
        return cls(
            api_key=api_key,
            base_url=base_url,
            image_model=config.get("image_model") or config.get("AGNES_IMAGE_MODEL"),
            text_model=config.get("text_model") or config.get("AGNES_TEXT_MODEL"),
            video_model=config.get("video_model") or config.get("AGNES_VIDEO_MODEL"),
            vision_model=config.get("vision_model") or config.get("AGNES_VISION_MODEL"),
        )

    def __init__(
        self,
        api_key: Optional[str],
        base_url: Optional[str] = None,
        image_model: Optional[str] = None,
        text_model: Optional[str] = None,
        video_model: Optional[str] = None,
        vision_model: Optional[str] = None,
    ):
        if not api_key:
            from ..errors import ProviderConfigError
            raise ProviderConfigError("Agnes 需要 api_key (AGNES_API_KEY)")
        # 延迟导入，避免包加载顺序问题
        from providers._impl.agnes import AgnesEngine
        self._engine = AgnesEngine(
            api_key=api_key,
            base_url=base_url,
            image_model=image_model,
            text_model=text_model,
            video_model=video_model,
            vision_model=vision_model,
        )

    # -------- 图像 --------

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        return self._engine.generate_single(
            prompt=req.prompt,
            negative=req.negative,
            width=req.width,
            height=req.height,
            steps=req.steps,
            cfg=req.cfg,
            seed=req.seed,
        )

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        ref = req.reference_list or req.reference
        if ref is None:
            raise ValueError("image_to_image 需要 reference 或 reference_list")
        return self._engine.image_to_image(
            prompt=req.prompt,
            image=ref,
            strength=req.strength,
            width=req.width,
            height=req.height,
            steps=req.steps,
            cfg=req.cfg,
            seed=req.seed,
        )

    # -------- 视频 --------

    def video_generation(self, req: VideoRequest) -> dict:
        return self._engine.video_generation(
            prompt=req.prompt,
            image=req.image,
            duration=req.duration,
            width=req.width,
            height=req.height,
            mode=req.mode,
            first_frame_url=req.first_frame_url,
            last_frame_url=req.last_frame_url,
            callback_url=req.callback_url,
        )

    def wait_for_video(self, video_id: str, **kw) -> str:
        return self._engine.wait_for_video(video_id, **kw)

    # -------- 视觉 --------

    def image_to_text(self, image: Image.Image, prompt: str, **kw) -> str:
        return self._engine.image_to_text(image, prompt=prompt, **kw)

    # -------- 文本 --------

    def chat(self, messages, **kw) -> str:
        return self._engine.chat(messages, **kw)