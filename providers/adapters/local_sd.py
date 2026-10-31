# providers/adapters/local_sd.py
"""本地 Stable Diffusion 适配器。

包一层 services.pipeline_pool，把统一 ImageRequest 翻译成 diffusers pipe 调用。
注册进 providers 注册表后，本地模型自动出现在 fallback 池里，
和 agnes / pollinations 走完全相同的调度路径。
"""

from __future__ import annotations

import logging
from typing import Optional

from PIL import Image

from ..base import BaseProvider, ImageRequest
from ..errors import ProviderConfigError, ProviderUnavailable
from ..registry import register

logger = logging.getLogger(__name__)


@register(
    name="local_sd",
    capabilities=["image"],
    requires_key=False,
    free=True,
    description="本地 Stable Diffusion（OpenVINO / diffusers），基于 pipeline_pool 复用实例",
)
class LocalSDAdapter(BaseProvider):

    # ---------- 构造 ----------

    @classmethod
    def from_config(cls, config: dict):
        return cls(
            model_path=config.get("model_path") or config.get("SD_MODEL_PATH") or None,
            device=config.get("device") or config.get("SD_DEVICE") or "CPU",
            lora_path=config.get("lora_path") or config.get("LORA_PATH") or None,
            lora_weight=float(config.get("lora_weight", 1.0)),
        )

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "CPU",
        lora_path: Optional[str] = None,
        lora_weight: float = 1.0,
    ):
        self.model_path = model_path
        self.device = device
        self.lora_path = lora_path
        self.lora_weight = lora_weight
        self._pipe = None

    # ---------- 懒加载 ----------

    def _ensure_pipe(self):
        if self._pipe is not None:
            return self._pipe

        try:
            from services.pipeline_pool import pipeline_pool
        except ImportError as e:
            raise ProviderConfigError(
                f"local_sd 依赖 services.pipeline_pool 加载失败: {e}"
            )

        if not self.model_path:
            raise ProviderConfigError(
                "local_sd 需要 model_path（请设置 SD_MODEL_PATH 环境变量）"
            )

        try:
            pipe, is_new = pipeline_pool.get_pipeline(
                model_path=self.model_path,
                lora_path=self.lora_path,
                lora_weight=self.lora_weight,
            )
        except Exception as e:
            raise ProviderUnavailable(f"本地模型加载失败: {e}")

        if pipe is None:
            raise ProviderUnavailable("pipeline_pool 返回空 pipeline")

        self._pipe = pipe
        logger.info(
            f"{'✅ 首次加载' if is_new else '♻️ 复用'}本地模型: {self.model_path}"
        )
        return self._pipe

    # ---------- 生成 ----------

    def _make_generator(self, seed: Optional[int]):
        """构造确定性 generator；无 torch 就返回 None（pipe 会用默认）。"""
        try:
            import torch
        except ImportError:
            return None
        gen_device = "cuda" if self.device.lower() == "cuda" else "cpu"
        gen = torch.Generator(gen_device)
        if seed is not None:
            gen.manual_seed(int(seed))
        return gen

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        pipe = self._ensure_pipe()

        kwargs = dict(
            prompt=req.prompt,
            width=req.width,
            height=req.height,
            num_inference_steps=max(req.steps, 20),
            guidance_scale=req.cfg,
            num_images_per_prompt=1,
        )
        if req.negative:
            kwargs["negative_prompt"] = req.negative

        gen = self._make_generator(req.seed)
        if gen is not None:
            kwargs["generator"] = gen

        try:
            return pipe(**kwargs).images[0]
        except Exception as e:
            raise ProviderUnavailable(f"本地文生图失败: {e}")

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        ref = req.reference_list[0] if req.reference_list else req.reference
        if ref is None:
            raise ProviderConfigError("local_sd.image_to_image 需要 reference 图片")

        pipe = self._ensure_pipe()

        init = ref.convert("RGB")

        # 尺寸对齐到 64 的倍数，超 1024 等比缩放
        w, h = init.size
        max_size = 1024
        if max(w, h) > max_size:
            scale = max_size / max(w, h)
            w = ((int(w * scale) + 63) // 64) * 64
            h = ((int(h * scale) + 63) // 64) * 64
            init = init.resize((w, h), Image.Resampling.LANCZOS)

        kwargs = dict(
            prompt=req.prompt,
            image=init,
            strength=req.strength,
            num_inference_steps=max(req.steps, 20),
            guidance_scale=req.cfg,
            num_images_per_prompt=1,
        )
        if req.negative:
            kwargs["negative_prompt"] = req.negative

        gen = self._make_generator(req.seed)
        if gen is not None:
            kwargs["generator"] = gen

        try:
            return pipe(**kwargs).images[0]
        except Exception as e:
            raise ProviderUnavailable(f"本地图生图失败: {e}")

    # ---------- 展示 ----------

    def get_name(self) -> str:
        name = (self.model_path or "unset").split("/")[-1].split("\\")[-1]
        return f"LocalSD ({name})"