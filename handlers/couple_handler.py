# handlers/couple_handler.py
"""双人合成处理器"""

import os
import random
import torch
from typing import Dict, Any, List
from PIL import Image

from .base import BaseHandler
from core.safety import SafetyChecker


class CoupleHandler(BaseHandler):
    """双人合成处理器（支持本地和 API 模式）"""

    def __init__(self, app):
        super().__init__(app)
        self.is_generating = False
        self.cancel_flag = False

    def handle(self, intent: Dict[str, Any]) -> None:
        """处理双人合成意图"""
        if not hasattr(self.app, 'uploaded_images') or len(self.app.uploaded_images) < 2:
            self._reply("❌ 请上传两张图片（一男一女）")
            self._reply("💡 点击工具栏的「📎 上传图片」选择两张图")
            return

        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return

        prompt = intent.get("prompt", "")
        original_text = intent.get("original_text", "")
        action = intent.get("params", {}).get("action", "standing together")

        # 安全检查
        if self.app.settings.safe_mode and getattr(self.app.settings, 'enable_safety_check', True):
            is_unsafe, matched = SafetyChecker.check(original_text)
            if is_unsafe:
                self._append_log(f"⚠️ 安全拦截: {matched[:5]}")
                cleaned = SafetyChecker.sanitize(original_text)
                if not cleaned or SafetyChecker.get_score(original_text) > 30:
                    self._reply("🛡️ 检测到不安全内容，已阻止合成")
                    self._update_status("⛔ 安全拦截")
                    return
                self._reply("⚠️ 已自动过滤敏感词")
                original_text = cleaned

        # 根据模式选择
        if self.app.settings.generation_mode == "api":
            self._handle_api(action, original_text)
        else:
            self._handle_local(action, prompt)

    # ==================== 本地模式 ====================

    def _handle_local(self, action: str, prompt: str):
        """本地模式"""
        if not self._ensure_model_loaded():
            return

        self._update_status("👫 合成双人图片...")
        self.is_generating = True
        self.cancel_flag = False

        try:
            pipe = self._get_pipeline()
            if pipe is None:
                self._reply("❌ 模型未加载")
                self.is_generating = False
                return

            # 获取两张图片
            img1 = self.app.uploaded_images[0].copy().convert('RGB')
            img2 = self.app.uploaded_images[1].copy().convert('RGB')

            # 合并
            h1, w1 = img1.size
            h2, w2 = img2.size
            target_h = min(h1, h2, 512)
            img1 = img1.resize((int(w1 * target_h / h1), target_h), Image.Resampling.LANCZOS)
            img2 = img2.resize((int(w2 * target_h / h2), target_h), Image.Resampling.LANCZOS)

            combined = Image.new('RGB', (img1.width + img2.width, target_h))
            combined.paste(img1, (0, 0))
            combined.paste(img2, (img1.width, 0))

            full_prompt = f"1girl and 1boy, {action}, couple, romantic, masterpiece, best quality, photorealistic, 8k"
            negative = "worst quality, low quality, ugly, deformed, blurry, bad anatomy, watermark, text"

            steps = self.app.settings.default_steps
            cfg = self.app.settings.default_cfg
            strength = 0.50

            seed = random.randint(1, 2**32 - 1)
            generator = torch.Generator("cpu").manual_seed(seed)

            self._update_status(f"👫 合成中... 步数: {steps}")

            result = pipe(
                prompt=full_prompt,
                negative_prompt=negative,
                image=combined,
                strength=strength,
                num_inference_steps=steps,
                guidance_scale=cfg,
                generator=generator,
                num_images_per_prompt=1
            )

            image = result.images[0]
            filepath = self._save_image(image, f"couple_{action}", "couple")

            self._reply(f"✅ 双人合成完成！(本地模式)\n📁 {os.path.basename(filepath)}")
            self._update_status(f"✅ 合成完成 (种子: {seed})")

            if self.context:
                self.context.update(
                    {"type": "couple", "prompt": prompt},
                    {"image_path": filepath}
                )

        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
            else:
                self._reply(f"❌ 合成失败: {str(e)}")
                self._update_status("❌ 合成失败")
            import traceback
            traceback.print_exc()
        finally:
            self.is_generating = False

    # ==================== API 模式 ====================

    def _handle_api(self, action: str, original_text: str):
        """API 模式：使用 Agnes 的多图合成"""
        self.is_generating = True
        self.cancel_flag = False

        try:
            from handlers.text_to_image import TextToImageHandler
            api_handler = TextToImageHandler(self.app)
            engine = api_handler._get_api_engine()

            if engine is None:
                self._reply("❌ API 引擎初始化失败")
                self.is_generating = False
                return

            if not hasattr(engine, 'image_to_image'):
                self._reply(f"❌ {engine.get_name()} 不支持多图合成")
                self.is_generating = False
                return

            # 获取两张图片
            images = [
                self.app.uploaded_images[0].copy().convert('RGB'),
                self.app.uploaded_images[1].copy().convert('RGB'),
            ]

            full_prompt = f"1girl and 1boy, {action}, couple, romantic, masterpiece, best quality, photorealistic, 8k"

            self._update_status("☁️ API 双人合成中...")

            image = engine.image_to_image(
                prompt=full_prompt,
                image=images,  # ✅ 传列表
                strength=0.7,
                steps=25,
                cfg=7.5,
                seed=random.randint(1, 999),
            )

            filepath = self._save_image(image, f"couple_{action}", "couple_api")

            self._reply(f"✅ 双人合成完成！({engine.get_name()} API)\n📁 {os.path.basename(filepath)}")
            self._update_status("✅ API 合成完成")

            if self.context:
                self.context.update(
                    {"type": "couple", "prompt": full_prompt},
                    {"image_path": filepath}
                )

        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
            else:
                self._reply(f"❌ API 双人合成失败: {str(e)}")
                self._update_status("❌ API 合成失败")
            import traceback
            traceback.print_exc()
        finally:
            self.is_generating = False

    def _append_log(self, msg: str):
        if hasattr(self.app, '_append_log'):
            self.app._append_log(msg)
        else:
            print(f"[LOG] {msg}")

    def cancel(self):
        self.cancel_flag = True
        self.is_generating = False