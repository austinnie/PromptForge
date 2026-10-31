# handlers/image_to_image.py
"""图生图处理器 - 走统一 provider 链（本地/API 自动 fallback）"""

import os
import random
from typing import Dict, Any

from .base import BaseHandler
from core.safety import SafetyChecker
from providers.base import ImageRequest
from providers.fallback import FallbackImageProvider
from providers import list_providers, get_meta


class ImageToImageHandler(BaseHandler):
    """图生图处理器（统一 provider 链）"""

    def __init__(self, app):
        super().__init__(app)
        self.is_generating = False
        self.cancel_flag = False
        self._backend = None

    # ---------- provider 链 ----------

    def _get_backend(self) -> FallbackImageProvider:
        if self._backend is not None:
            return self._backend

        settings = self.app.settings
        all_image = list_providers("image")
        if not all_image:
            raise RuntimeError("providers 注册表里没有 image provider")

        mode = getattr(settings, "generation_mode", "api")
        if mode == "local" and "local_sd" in all_image:
            primary = "local_sd"
        else:
            primary = getattr(settings, "api_provider", "agnes")
            if primary not in all_image:
                primary = all_image[0]

        pool = [p for p in all_image if p != primary]
        pool.sort(key=lambda p: (not get_meta(p).get("free", False), p))

        configs = {}
        for p in [primary] + pool:
            if p == "local_sd":
                configs[p] = {
                    "model_path": settings.model_path,
                    "lora_path": settings.lora_path,
                    "device": "CPU",
                }
            else:
                configs[p] = settings.get_provider_config(p)

        self._backend = FallbackImageProvider(
            primary=primary,
            fallback=pool,
            configs=configs,
            on_fallback=lambda frm, to, err: self._reply(
                f"⚠️ {frm} 不可用，自动切到 {to}"
            ),
        )
        return self._backend

    # ---------- 主入口 ----------

    def handle(self, intent: Dict[str, Any]) -> None:
        if not getattr(self.app, "uploaded_images", None):
            self._reply("❌ 请先上传一张图片")
            self._reply("💡 点击工具栏的「📎 上传图片」按钮")
            return

        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return

        prompt = intent.get("prompt", "")
        original_text = intent.get("original_text", "")
        if not prompt:
            self._reply("❌ 请描述您想如何修改这张图片")
            return

        if getattr(self.app.settings, "safe_mode", False):
            is_unsafe, _ = SafetyChecker.check(prompt)
            if is_unsafe:
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    self._reply("🛡️ 内容被安全过滤")
                    return

        init_image = self.app.uploaded_images[0].copy().convert("RGB")
        w, h = init_image.size
        max_size = 1024
        if max(w, h) > max_size:
            scale = max_size / max(w, h)
            width, height = int(w * scale), int(h * scale)
        else:
            width, height = w, h

        full_prompt = self._build_preserve_prompt(original_text or prompt)
        params = self._estimate_params(original_text or prompt)

        self.is_generating = True
        self.cancel_flag = False

        try:
            backend = self._get_backend()
            self._update_status(f"🎨 图生图中... ({backend.get_name()})")

            req = ImageRequest(
                prompt=full_prompt,
                negative=self._build_negative(original_text or prompt),
                width=width,
                height=height,
                steps=params["steps"],
                cfg=params["cfg"],
                seed=random.randint(1, 2**32 - 1),
                reference=init_image,
                strength=params["strength"],
            )

            image = backend.image_to_image(req)

            tag = backend.get_name().split()[0].lower()
            filepath = self._save_image(image, prompt[:50], f"img2img_{tag}")

            self._reply(f"✅ 图生图完成！\n📁 {os.path.basename(filepath)}")
            self._update_status("✅ 图生图完成")

            if self.context:
                self.context.update(
                    {"type": "image_to_image", "prompt": prompt},
                    {"image_path": filepath},
                )

        except NotImplementedError:
            self._reply("❌ 当前引擎不支持图生图，请切换到 agnes 等支持的提供商")
        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
            else:
                self._reply(f"❌ 图生图失败: {e}")
                self._update_status("❌ 图生图失败")
                import traceback
                traceback.print_exc()
        finally:
            self.is_generating = False

    # ---------- 以下三个方法：保留原有逻辑不变 ----------

    def _build_preserve_prompt(self, text: str) -> str:
        """构建保留原图的提示词（原逻辑保留）"""
        import re

        patterns = [
            r'(?:加上|添加|增加|放入|加个|加一只|加一个|加)\s*(.+?)(?:[，。、！？\n]|$)',
            r'add\s*(.+?)(?:[,.]|$)',
        ]
        addition = None
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                addition = m.group(1).strip()
                break

        if addition:
            addition = re.sub(r'(?:这张|原|参考|的)?图片?', '', addition).strip()
            if addition:
                return (
                    f"Add {addition} to the original image. "
                    f"Keep all existing elements, background, and style unchanged. "
                    f"Only add {addition}."
                )

        return (
            f"Edit this image: {text}. "
            f"Keep the original background and composition as much as possible."
        )

    def _build_negative(self, prompt: str) -> str:
        negative = (
            "worst quality, low quality, ugly, deformed, blurry, "
            "bad anatomy, watermark, text"
        )
        if any(k in prompt.lower() for k in ['人', 'face', 'portrait', '美女', '帅哥']):
            negative += ", bad hands, missing fingers, extra digits, bad face, deformed face"
        return negative

    def _estimate_params(self, prompt: str) -> Dict:
        prompt_lower = prompt.lower()
        if any(k in prompt_lower for k in ['微调', '轻微', 'slight', 'minor']):
            strength = 0.25
        elif any(k in prompt_lower for k in ['大幅', '巨大', 'major', 'big']):
            strength = 0.55
        else:
            strength = self.app.settings.default_strength

        if any(k in prompt_lower for k in ['快速', 'fast', 'quick']):
            steps = 12
        elif any(k in prompt_lower for k in ['高质量', '精细', 'high quality']):
            steps = 30
        else:
            steps = self.app.settings.default_steps

        return {"strength": strength, "steps": steps, "cfg": 7.5}

    def cancel(self):
        self.cancel_flag = True
        self.is_generating = False