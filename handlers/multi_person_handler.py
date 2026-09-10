# handlers/multi_person_handler.py
"""多人合成处理器 - 将多张图片（3+）合成为群像场景"""

import os
import random
import torch
from typing import Dict, Any, List
from PIL import Image

from .base import BaseHandler
from core.safety import SafetyChecker


class MultiPersonHandler(BaseHandler):
    """多人合成处理器（支持本地和 API 模式）"""

    MIN_IMAGES = 3
    MAX_IMAGES = 6

    def __init__(self, app):
        super().__init__(app)
        self.is_generating = False
        self.cancel_flag = False

    def handle(self, intent: Dict[str, Any]) -> None:
        """处理多人合成意图"""
        # 1. 检查图片数量
        uploaded = getattr(self.app, 'uploaded_images', [])
        if len(uploaded) < self.MIN_IMAGES:
            self._reply(f"❌ 多人合成至少需要上传 {self.MIN_IMAGES} 张图片")
            self._reply(f"💡 当前已上传 {len(uploaded)} 张")
            return

        # 2. 检查是否正在生成
        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return

        # 3. 提取意图参数
        prompt = intent.get("prompt", "")
        original_text = intent.get("original_text", "")
        action = intent.get("params", {}).get("action", "standing together")
        count = min(len(uploaded), self.MAX_IMAGES)

        # 4. 安全检查
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

        # 5. 根据模式选择生成方式
        if self.app.settings.generation_mode == "api":
            self._handle_api(uploaded[:count], action, count)
        else:
            self._handle_local(uploaded[:count], action, count, original_text)

    # ==================== 本地模式 ====================

    def _handle_local(self, images: List[Image.Image], action: str, count: int, original_text: str):
        """本地模式：拼接多图 → pipe 生成"""
        if not self._ensure_model_loaded():
            return

        self._update_status(f"👥 合成 {count} 人图片...")
        self.is_generating = True
        self.cancel_flag = False

        try:
            pipe = self._get_pipeline()
            if pipe is None:
                self._reply("❌ 模型未加载")
                self.is_generating = False
                return

            # 拼接 N 张图片
            combined = self._combine_images(images)

            # 构建提示词
            subjects = ", ".join([
                "1girl" if i % 2 == 0 else "1boy"
                for i in range(count)
            ])
            full_prompt = (
                f"{subjects}, group of {count} people, {action}, "
                f"masterpiece, best quality, photorealistic, 8k, "
                f"detailed faces, natural poses"
            )
            negative = (
                "worst quality, low quality, ugly, deformed, blurry, "
                "bad anatomy, watermark, text, extra limbs, missing limbs"
            )

            steps = self.app.settings.default_steps
            cfg = self.app.settings.default_cfg
            strength = 0.50

            seed = random.randint(1, 2**32 - 1)
            generator = torch.Generator("cpu").manual_seed(seed)

            self._update_status(f"👥 合成中... ({count}人, {steps}步)")

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
            filepath = self._save_image(image, f"multi_{count}_{action}", "multi")

            self._reply(f"✅ {count} 人合成完成！(本地模式)\n📁 {os.path.basename(filepath)}")
            self._update_status(f"✅ 合成完成 (种子: {seed})")

            if self.context:
                self.context.update(
                    {"type": "multi_person", "prompt": original_text, "count": count},
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

    def _handle_api(self, images: List[Image.Image], action: str, count: int):
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
                self._reply(f"❌ {engine.get_name()} 不支持图生图/多图合成")
                self.is_generating = False
                return

            # 构建提示词
            subjects = ", ".join([
                "1girl" if i % 2 == 0 else "1boy"
                for i in range(count)
            ])
            full_prompt = (
                f"{subjects}, group of {count} people, {action}, "
                f"masterpiece, best quality, photorealistic, 8k, "
                f"detailed faces, natural poses"
            )

            self._update_status(f"☁️ API 多人合成中... ({count}人)")

            # ✅ 调用 Agnes 的多图合成
            image = engine.image_to_image(
                prompt=full_prompt,
                image=images,  # ✅ 传列表
                strength=0.7,
                steps=25,
                cfg=7.5,
                seed=random.randint(1, 999),
            )

            filepath = self._save_image(image, f"multi_{count}_{action}", "multi_api")

            self._reply(f"✅ {count} 人合成完成！({engine.get_name()} API)\n📁 {os.path.basename(filepath)}")
            self._update_status("✅ API 合成完成")

            if self.context:
                self.context.update(
                    {"type": "multi_person", "prompt": full_prompt, "count": count},
                    {"image_path": filepath}
                )

        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
            else:
                self._reply(f"❌ API 多人合成失败: {str(e)}")
                self._update_status("❌ API 合成失败")
            import traceback
            traceback.print_exc()
        finally:
            self.is_generating = False

    # ==================== 工具方法 ====================

    def _combine_images(self, images: List[Image.Image]) -> Image.Image:
        """将 N 张图片横向拼接为一张图（统一高度）"""
        target_h = min(min(img.size[1] for img in images), 512)

        resized = []
        for img in images:
            img_rgb = img.copy().convert('RGB')
            w, h = img_rgb.size
            new_w = int(w * target_h / h)
            new_w = max(new_w, 1)
            resized.append(
                img_rgb.resize((new_w, target_h), Image.Resampling.LANCZOS)
            )

        total_w = sum(img.width for img in resized)
        combined = Image.new('RGB', (total_w, target_h), color=(255, 255, 255))

        x_offset = 0
        for img in resized:
            combined.paste(img, (x_offset, 0))
            x_offset += img.width

        return combined

    def _append_log(self, msg: str):
        """记录日志"""
        if hasattr(self.app, '_append_log'):
            self.app._append_log(msg)
        else:
            print(f"[LOG] {msg}")

    def cancel(self):
        """取消生成"""
        self.cancel_flag = True
        self.is_generating = False