# handlers/multi_person_handler.py
"""多人合成处理器（3-6 张图，统一走 provider 链）"""

import os
import random
from typing import Dict, Any, List

from PIL import Image

from .base import BaseHandler
from core.safety import SafetyChecker
from providers.base import ImageRequest
from providers.fallback import FallbackImageProvider
from providers import list_providers, get_meta


class MultiPersonHandler(BaseHandler):
    """多人合成处理器（3-6 张）"""

    MIN_IMAGES = 3
    MAX_IMAGES = 6

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
            on_fallback=lambda frm, to, err: self._append_log(
                f"⚠️ {frm} 不可用，切到 {to}"
            ),
        )
        return self._backend

    # ---------- 主入口 ----------

    def handle(self, intent: Dict[str, Any]) -> None:
        uploaded = getattr(self.app, "uploaded_images", None) or []
        if len(uploaded) < self.MIN_IMAGES:
            self._reply(
                f"❌ 多人合成至少需要 {self.MIN_IMAGES} 张图片"
                f"（当前 {len(uploaded)} 张）"
            )
            return

        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return

        action = intent.get("params", {}).get("action", "standing together")
        count = min(len(uploaded), self.MAX_IMAGES)
        original_text = intent.get("original_text", "")

        subjects = ", ".join(["1girl" if i % 2 == 0 else "1boy" for i in range(count)])
        prompt = intent.get("prompt") or (
            f"{subjects}, group of {count} people, {action}, "
            f"masterpiece, best quality"
        )

        if getattr(self.app.settings, "safe_mode", False):
            is_safe, _ = SafetyChecker.check(prompt)
            if not is_safe:
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    self._reply("🛡️ 内容被安全过滤")
                    return

        images = [img.convert("RGB") for img in uploaded[:count]]

        self.is_generating = True
        self.cancel_flag = False

        try:
            backend = self._get_backend()
            primary = backend.primary
            self._update_status(f"🎨 多人合成中... ({count} 人, {primary})")

            if primary == "local_sd":
                reference = self._combine_images(images)
                reference_list = None
            else:
                reference = images[0]
                reference_list = images

            req = ImageRequest(
                prompt=prompt,
                negative="worst quality, low quality, blurry, deformed, bad anatomy",
                width=1024,
                height=1024,
                steps=30,
                cfg=7.5,
                seed=random.randint(1, 2**32 - 1),
                reference=reference,
                reference_list=reference_list,
                strength=0.6,
            )

            image = backend.image_to_image(req)

            tag = primary.lower()
            filepath = self._save_image(
                image, original_text or action, f"group_{count}_{tag}"
            )

            self._reply(f"✅ {count} 人合成完成！\n📁 {os.path.basename(filepath)}")
            self._update_status("✅ 多人合成完成")

            if self.context:
                self.context.update(
                    {"type": "multi_person", "prompt": prompt, "count": count},
                    {"image_path": filepath},
                )

        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
            else:
                self._reply(f"❌ 多人合成失败: {e}")
                self._update_status("❌ 多人合成失败")
                import traceback
                traceback.print_exc()
        finally:
            self.is_generating = False

    # ---------- 工具 ----------

    def _combine_images(self, images: List[Image.Image]) -> Image.Image:
        """横向拼接为一张图（保留原逻辑）"""
        h = min(img.height for img in images)
        resized = []
        for img in images:
            if img.height != h:
                w = int(img.width * h / img.height)
                resized.append(img.resize((w, h), Image.Resampling.LANCZOS))
            else:
                resized.append(img)
        total_w = sum(img.width for img in resized)
        canvas = Image.new("RGB", (total_w, h), (255, 255, 255))
        x = 0
        for img in resized:
            canvas.paste(img, (x, 0))
            x += img.width
        return canvas

    def _append_log(self, msg: str):
        if hasattr(self.app, "_append_message"):
            self.app._append_message("assistant", msg)
        else:
            print(msg)

    def cancel(self):
        self.cancel_flag = True
        self.is_generating = False