# providers/adapters/pollinations.py
"""Pollinations AI 适配器。

包一层 api_engines.pollinations.PollinationsEngine，
把统一 ImageRequest / VideoRequest / AudioRequest 翻译成该引擎能吃的参数。

设计：
  - 有 key → 走旧引擎（完整流程，含 LLM 翻译）
  - 无 key → 独立走匿名 HTTP（旧引擎的匿名路径已被官方禁用）

错误语义（决定 FallbackImageProvider 是否切换）：
  - 402 余额不足     → ProviderConfigError（切也没用）
  - 401/403 认证失败 → ProviderAuthError（切也没用）
  - 429 限流         → ProviderUnavailable（可切下一个）
  - 5xx / 超时       → ProviderUnavailable（可切下一个）
"""

from __future__ import annotations

import io
import logging
import random
import time
import urllib.parse
from typing import Optional

import requests
from PIL import Image

from ..base import (
    BaseProvider,
    ImageRequest,
    VideoRequest,
    AudioRequest,
)
from ..errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderUnavailable,
    ProviderError,
)
from ..registry import register

logger = logging.getLogger(__name__)


_ANON_BASE = "https://gen.pollinations.ai"

_QUALITY_PREFIX = "masterpiece, best quality, highly detailed, sharp focus"
_QUALITY_SUFFIX = "professional photography, cinematic lighting, 8k uhd, intricate details"

_QUALITY_MARKERS = (
    "masterpiece", "best quality", "highly detailed",
    "8k", "ultra detailed", "professional photography",
)


@register(
    "pollinations",
    capabilities=["image", "audio", "video", "text"],
    requires_key=True,     # 图像必须 key + pollen 余额
    free=False,            # 图像不免费了（chat 免费）
    description="Pollinations AI（图像需 pollen 余额，chat 免费）",
)
class PollinationsAdapter(BaseProvider):

    # ============================================================
    # 构造
    # ============================================================

    @classmethod
    def from_config(cls, config: dict):
        return cls(
            api_key=(
                config.get("api_key")
                or config.get("POLLINATIONS_API_KEY")
                or None
            ),
            image_model=(
                config.get("image_model")
                or config.get("model")
                or config.get("POLLINATIONS_MODEL")
            ),
            video_model=(
                config.get("video_model")
                or config.get("POLLINATIONS_VIDEO_MODEL")
            ),
            audio_model=(
                config.get("audio_model")
                or config.get("POLLINATIONS_AUDIO_MODEL")
            ),
        )

    def __init__(
        self,
        api_key: Optional[str] = None,
        image_model: Optional[str] = None,
        video_model: Optional[str] = None,
        audio_model: Optional[str] = None,
    ):
        self.api_key = api_key or None
        self.image_model = image_model or "flux"
        self.video_model = video_model
        self.audio_model = audio_model

        # 有 key 才创建旧引擎；无 key 完全走匿名 HTTP
        self._engine = None
        if self.api_key:
            from api_engines.pollinations import PollinationsEngine
            self._engine = PollinationsEngine(
                api_key=self.api_key,
                image_model=image_model,
                video_model=video_model,
                audio_model=audio_model,
            )

        logger.info(
            f"PollinationsAdapter 初始化: "
            f"image={self.image_model}, "
            f"key={'有' if self.api_key else '无（匿名）'}"
        )

    # ============================================================
    # Prompt 工具
    # ============================================================

    @staticmethod
    def _simplify_prompt(prompt: str) -> str:
        if not prompt:
            return prompt
        for word in [
            "生成图片", "生成一张", "生成",
            "帮我画", "画一张", "画",
            "create an image of", "generate an image of",
            "create", "generate",
        ]:
            prompt = prompt.replace(word, "")
        return prompt.strip().strip("，,。.：: ")

    @staticmethod
    def _ensure_quality(prompt: str) -> str:
        lower = prompt.lower()
        if any(q in lower for q in _QUALITY_MARKERS):
            return prompt
        return f"{_QUALITY_PREFIX}, {prompt}, {_QUALITY_SUFFIX}"

    # ============================================================
    # 错误分类（统一入口）
    # ============================================================

    def _classify_http_error(self, response: requests.Response):
        """根据状态码和响应体抛对应异常，用于 fallback 判断。"""
        status = response.status_code
        try:
            detail = response.json()
            err = detail.get("error", {})
            code = err.get("code", "") if isinstance(err, dict) else ""
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
        except Exception:
            code, msg = "", response.text[:200]

        if status == 402 or code == "INSUFFICIENT_BALANCE":
            raise ProviderUnavailable(
                f"Pollinations 余额不足（402）\n"
                f"  充余额: https://enter.pollinations.ai/top-up\n"
                f"  原始错误: {msg[:150]}"
            )

        if status in (401, 403):
            raise ProviderAuthError(
                f"Pollinations 认证失败（{status}）: {msg[:150]}"
            )

        if status == 429:
            raise ProviderUnavailable(f"Pollinations 限流（429）: {msg[:100]}")

        if status >= 500:
            raise ProviderUnavailable(
                f"Pollinations 服务端错误（{status}）: {msg[:100]}"
            )

        raise ProviderError(
            f"Pollinations 调用失败（{status}）: {msg[:150]}"
        )

    # ============================================================
    # 匿名 HTTP（无 key 路径）
    # ============================================================

    def _anon_request(
        self, method: str, endpoint: str, *,
        params=None, data=None, timeout=180, max_retries=3,
    ) -> requests.Response:
        url = f"{_ANON_BASE}/{endpoint.lstrip('/')}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        for attempt in range(max_retries):
            try:
                r = requests.request(
                    method=method, url=url, headers=headers,
                    params=params, json=data, timeout=timeout,
                )
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ 请求超时，重试 ({attempt+1}/{max_retries})")
                    time.sleep(2)
                    continue
                raise ProviderUnavailable("Pollinations 请求超时")
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ 连接失败，重试 ({attempt+1}/{max_retries})")
                    time.sleep(2)
                    continue
                raise ProviderUnavailable(f"Pollinations 连接失败: {e}")

            if r.status_code == 200:
                return r

            # 429 → 退避重试（不立即抛，因为限流是临时的）
            if r.status_code == 429 and attempt < max_retries - 1:
                wait = 2 * (attempt + 1)
                logger.warning(f"⚠️ Pollinations 限流，{wait}s 后重试")
                time.sleep(wait)
                continue

            # 其他错误 → 走统一分类
            self._classify_http_error(r)

        raise ProviderUnavailable("Pollinations 匿名请求重试耗尽")

    # ============================================================
    # 图像
    # ============================================================

    def text_to_image(self, req: ImageRequest) -> Image.Image:
        clean = self._simplify_prompt(req.prompt)
        if not clean:
            raise ValueError("Pollinations: 简化后 prompt 为空")

        width = min(req.width, 2048)
        height = min(req.height, 2048)

        # ---- 有 key：走旧引擎 ----
        if self._engine is not None:
            try:
                return self._engine.text_to_image(
                    prompt=clean,
                    negative=req.negative,
                    width=width,
                    height=height,
                    steps=req.steps,
                    cfg=req.cfg,
                    seed=req.seed,
                )
            except Exception as e:
                err = str(e)
                # 旧引擎把 402/401 都包装成 Exception，这里按文本判断
                err = str(e)
                if "402" in err or "Insufficient" in err or "balance" in err.lower():
                    raise ProviderUnavailable(
                        f"Pollinations 余额不足（402）\n"
                        f"  充余额: https://enter.pollinations.ai/top-up\n"
                        f"  原始错误: {err[:150]}"
                    ) from e
                if "401" in err or "403" in err:
                    raise ProviderAuthError(f"Pollinations 认证失败: {err[:150]}") from e
                if "429" in err or "rate" in err.lower():
                    raise ProviderUnavailable(f"Pollinations 限流: {err[:100]}") from e
                raise

        # ---- 无 key：匿名 HTTP ----
        final_prompt = self._ensure_quality(clean)
        encoded = urllib.parse.quote(final_prompt, safe="")
        endpoint = f"/image/{encoded}"

        seed = req.seed if req.seed is not None else random.randint(1, 2**31 - 1)

        params = {
            "model": self.image_model,
            "width": width,
            "height": height,
            "seed": seed,
            "nologo": "true",
        }
        if req.negative and len(req.negative) < 200:
            params["negative"] = req.negative

        logger.info(
            f"Pollinations 匿名文生图: model={self.image_model}, "
            f"size={width}x{height}, seed={seed}"
        )

        r = self._anon_request("GET", endpoint, params=params, timeout=180)
        return Image.open(io.BytesIO(r.content))

    def image_to_image(self, req: ImageRequest) -> Image.Image:
        ref = req.reference_list or req.reference
        if ref is None:
            raise ValueError("Pollinations image_to_image 需要 reference 或 reference_list")

        clean = self._simplify_prompt(req.prompt)
        if not clean:
            raise ValueError("Pollinations: 简化后 prompt 为空")

        if self._engine is None:
            raise ProviderConfigError(
                "Pollinations 图生图需要 API key（匿名模式不支持 /v1/images/edits）。"
            )

        try:
            return self._engine.image_to_image(
                prompt=clean,
                image=ref,
                strength=req.strength,
                width=req.width,
                height=req.height,
                seed=req.seed,
            )
        except Exception as e:
            err = str(e)
            if "402" in err or "Insufficient" in err or "balance" in err.lower():
                raise ProviderUnavailable(
                    f"Pollinations 余额不足（402）\n"
                    f"  充余额: https://enter.pollinations.ai/top-up\n"
                    f"  原始错误: {err[:150]}"
                ) from e
            if "401" in err or "403" in err:
                raise ProviderAuthError(f"Pollinations 认证失败: {err[:150]}") from e
            raise

    # ============================================================
    # 视频
    # ============================================================

    def video_generation(self, req: VideoRequest) -> dict:
        clean = self._simplify_prompt(req.prompt)
        if not clean:
            raise ValueError("Pollinations: 简化后 prompt 为空")

        if self._engine is None:
            raise ProviderConfigError("Pollinations 视频生成需要 API key")

        return self._engine.video_generation(
            prompt=clean,
            image=req.image,
            duration=req.duration,
            width=req.width,
            height=req.height,
            model=(
                req.mode
                if req.mode and req.mode not in ("text", "keyframe", "reference")
                else None
            ),
            callback_url=req.callback_url,
        )

    def video_status(self, video_id: str) -> dict:
        if self._engine is None:
            raise ProviderConfigError("Pollinations 视频需要 API key")
        return self._engine.video_status(video_id)

    def wait_for_video(self, video_id: str, **kw) -> str:
        if self._engine is None:
            raise ProviderConfigError("Pollinations 视频需要 API key")
        return self._engine.wait_for_video(video_id, **kw)

    # ============================================================
    # 音频
    # ============================================================

    def generate_audio(self, req: AudioRequest) -> bytes:
        if self._engine is None:
            raise ProviderConfigError(
                "Pollinations 音频生成需要 API key（/v1/audio/speech 不支持匿名）。"
            )
        return self._engine.generate_audio(
            text=req.text,
            voice=req.voice,
            output_format=req.output_format,
            duration=req.duration,
        )

    # ============================================================
    # 文本 / 视觉
    # ============================================================

    def chat(self, messages, **kw) -> str:
        if self._engine is None:
            raise ProviderConfigError(
                "Pollinations 对话需要 API key（/v1/chat/completions 不支持匿名）。"
            )
        return self._engine.chat(messages, **kw)

    def image_to_text(self, image: Image.Image, prompt: str, **kw) -> str:
        if self._engine is None:
            raise ProviderConfigError("Pollinations 视觉理解需要 API key")
        return self._engine.image_to_text(image, prompt=prompt, **kw)

    # ============================================================
    # 展示
    # ============================================================

    def get_name(self) -> str:
        tag = "匿名" if not self.api_key else "已认证"
        return f"Pollinations ({tag})"