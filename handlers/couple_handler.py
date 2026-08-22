# handlers/couple_handler.py
"""双人合成处理器 - 将两张图片合成为双人场景"""

import os
import random
import torch
from datetime import datetime
from typing import Dict, Any
from PIL import Image

from .base import BaseHandler


class CoupleHandler(BaseHandler):
    """双人合成处理器"""
    
    def __init__(self, app):
        super().__init__(app)
        self.is_generating = False
        self.cancel_flag = False
    
    def handle(self, intent: Dict[str, Any]) -> None:
        """处理双人合成意图"""
        # 检查是否有两张图片
        if not hasattr(self.app, 'uploaded_images') or len(self.app.uploaded_images) < 2:
            self._reply("❌ 请上传两张图片（一男一女）")
            self._reply("💡 点击工具栏的「📎 上传图片」选择两张图")
            return
        
        if not self._ensure_model_loaded():
            return
        
        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return
        
        prompt = intent.get("prompt", "")
        action = intent.get("params", {}).get("action", "standing together")
        
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
            
            # 调整到相同高度
            h1, w1 = img1.size
            h2, w2 = img2.size
            target_h = min(h1, h2, 512)
            
            img1 = img1.resize((int(w1 * target_h / h1), target_h), Image.Resampling.LANCZOS)
            img2 = img2.resize((int(w2 * target_h / h2), target_h), Image.Resampling.LANCZOS)
            
            # 合并图片
            combined = Image.new('RGB', (img1.width + img2.width, target_h))
            combined.paste(img1, (0, 0))
            combined.paste(img2, (img1.width, 0))
            
            # 构建提示词
            full_prompt = f"1girl and 1boy, {action}, couple, romantic, masterpiece, best quality, photorealistic, 8k"
            negative = "worst quality, low quality, ugly, deformed, blurry, bad anatomy, watermark, text"
            
            # 参数
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
            
            # 保存图片
            image = result.images[0]
            filepath = self._save_image(image, f"couple_{action}", "couple")
            
            self._reply(f"✅ 双人合成完成！\n📁 {os.path.basename(filepath)}")
            self._update_status(f"✅ 合成完成 (种子: {seed})")
            
            # 更新上下文
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
    
    def cancel(self):
        """取消生成"""
        self.cancel_flag = True
        self.is_generating = False