# handlers/multi_person_handler.py
"""多人合成处理器 - 将多张图片合成为群像场景"""

import os
import random
import torch
from typing import Dict, Any
from PIL import Image

from .base import BaseHandler
from core.safety import SafetyChecker


class MultiPersonHandler(BaseHandler):
    """多人合成处理器"""
    
    def __init__(self, app):
        super().__init__(app)
        self.is_generating = False
        self.cancel_flag = False
    
    def handle(self, intent: Dict[str, Any]) -> None:
        """处理多人合成意图"""
        if not hasattr(self.app, 'uploaded_images') or len(self.app.uploaded_images) < 3:
            self._reply("❌ 多人合成至少需要上传 3 张图片")
            return
        
        if not self._ensure_model_loaded():
            return
        
        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return
        
        original_text = intent.get("original_text", "")
        action = intent.get("params", {}).get("action", "standing together")
        count = intent.get("params", {}).get("count", len(self.app.uploaded_images))
        
        # ✅ 安全检查
        if self.app.settings.safe_mode and self.app.settings.enable_safety_check:
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
        
        self._update_status(f"👥 合成 {count} 人图片...")
        self.is_generating = True
        self.cancel_flag = False
        
        try:
            pipe = self._get_pipeline()
            if pipe is None:
                self._reply("❌ 模型未加载")
                self.is_generating = False
                return
            
            # ✅ 合并 N 张图片（横向拼接）
            images = []
            for img in self.app.uploaded_images[:count]:
                img_rgb = img.copy().convert('RGB')
                images.append(img_rgb)
            
            # 统一高度
            target_h = min(min(img.size[1] for img in images), 512)
            resized = []
            for img in images:
                w, h = img.size
                new_w = int(w * target_h / h)
                resized.append(img.resize((new_w, target_h), Image.Resampling.LANCZOS))
            
            total_w = sum(img.width for img in resized)
            combined = Image.new('RGB', (total_w, target_h))
            x_offset = 0
            for img in resized:
                combined.paste(img, (x_offset, 0))
                x_offset += img.width
            
            # 构建提示词
            subjects = ", ".join(["1girl" if i % 2 == 0 else "1boy" for i in range(count)])
            full_prompt = f"{subjects}, group of {count} people, {action}, masterpiece, best quality, photorealistic, 8k"
            negative = "worst quality, low quality, ugly, deformed, blurry, bad anatomy, watermark, text"
            
            steps = self.app.settings.default_steps
            cfg = self.app.settings.default_cfg
            strength = 0.50
            
            seed = random.randint(1, 2**32 - 1)
            generator = torch.Generator("cpu").manual_seed(seed)
            
            self._update_status(f"👥 合成中... 步数: {steps}")
            
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
            
            self._reply(f"✅ {count} 人合成完成！\n📁 {os.path.basename(filepath)}")
            self._update_status(f"✅ 合成完成 (种子: {seed})")
            
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
    
    def _append_log(self, msg: str):
        if hasattr(self.app, '_append_log'):
            self.app._append_log(msg)
        else:
            print(f"[LOG] {msg}")
    
    def cancel(self):
        self.cancel_flag = True
        self.is_generating = False