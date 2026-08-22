# handlers/image_to_image.py
"""图生图处理器 - 基于参考图生成新图片"""

import os
import random
import torch
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image

from .base import BaseHandler
from core.safety import SafetyChecker


class ImageToImageHandler(BaseHandler):
    """图生图处理器"""
    
    def __init__(self, app):
        super().__init__(app)
        self.is_generating = False
        self.cancel_flag = False
    
    def handle(self, intent: Dict[str, Any]) -> None:
        """处理图生图意图"""
        # 检查是否有上传的图片
        if not hasattr(self.app, 'uploaded_image') or not self.app.uploaded_image:
            self._reply("❌ 请先上传一张图片")
            self._reply("💡 点击工具栏的「📎 上传图片」按钮")
            return
        
        if not self._ensure_model_loaded():
            return
        
        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return
        
        prompt = intent.get("prompt", "")
        if not prompt:
            self._reply("❌ 请描述您想如何修改这张图片")
            return
        
        # 安全检查
        if self.app.settings.safe_mode:
            is_unsafe, _ = SafetyChecker.check(prompt)
            if is_unsafe:
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    self._reply("🛡️ 内容被安全过滤，请使用更温和的描述")
                    return
        
        # 估算参数
        params = self._estimate_params(prompt)
        strength = params.get("strength", self.app.settings.default_strength)
        
        self._update_status(f"🎨 修改中... (强度: {strength:.2f})")
        self.is_generating = True
        self.cancel_flag = False
        
        try:
            pipe = self._get_pipeline()
            if pipe is None:
                self._reply("❌ 模型未加载")
                self.is_generating = False
                return
            
            # 加载图片
            init_image = self.app.uploaded_image.copy().convert('RGB')
            w, h = init_image.size
            
            # 调整尺寸
            max_size = 1024
            if max(w, h) > max_size:
                scale = max_size / max(w, h)
                new_w = int(w * scale)
                new_h = int(h * scale)
                new_w = ((new_w + 31) // 64) * 64
                new_h = ((new_h + 31) // 64) * 64
                init_image = init_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # 设置种子
            seed = params.get("seed", random.randint(1, 2**32 - 1))
            generator = torch.Generator("cpu").manual_seed(seed)
            
            # 构建提示词
            negative = self._build_negative(prompt)
            
            self._update_status(f"🎨 修改中... 步数: {params['steps']}")
            
            # 生成
            result = pipe(
                prompt=prompt,
                negative_prompt=negative,
                image=init_image,
                strength=strength,
                num_inference_steps=params["steps"],
                guidance_scale=params["cfg"],
                generator=generator,
                num_images_per_prompt=1
            )
            
            # 保存图片
            image = result.images[0]
            filepath = self._save_image(image, prompt, "img2img")
            
            # 后处理
            filepath = self._post_process(filepath)
            
            self._reply(f"✅ 图片已修改完成！\n📁 {os.path.basename(filepath)}")
            self._update_status(f"✅ 修改完成 (种子: {seed})")
            
            # 更新上下文
            if self.context:
                self.context.update(
                    {"type": "image_to_image", "prompt": prompt},
                    {"image_path": filepath}
                )
            
        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
            else:
                self._reply(f"❌ 修改失败: {str(e)}")
                self._update_status("❌ 修改失败")
            import traceback
            traceback.print_exc()
        finally:
            self.is_generating = False
    
    def _estimate_params(self, prompt: str) -> Dict:
        """估算参数"""
        prompt_lower = prompt.lower()
        
        # 强度
        if any(k in prompt_lower for k in ['微调', '轻微', 'slight', 'minor']):
            strength = 0.25
        elif any(k in prompt_lower for k in ['大幅', '巨大', 'major', 'big']):
            strength = 0.55
        else:
            strength = self.app.settings.default_strength
        
        # 步数
        if any(k in prompt_lower for k in ['快速', 'fast', 'quick']):
            steps = 12
        elif any(k in prompt_lower for k in ['高质量', '精细', 'high quality']):
            steps = 30
        else:
            steps = self.app.settings.default_steps
        
        return {
            "strength": strength,
            "steps": steps,
            "cfg": 7.5,
            "seed": random.randint(1, 2**32 - 1),
        }
    
    def _build_negative(self, prompt: str) -> str:
        """构建负面提示词"""
        negative = "worst quality, low quality, ugly, deformed, blurry, bad anatomy, watermark, text"
        
        # 如果是人像，加强负面
        if any(k in prompt.lower() for k in ['人', 'face', 'portrait', '美女', '帅哥']):
            negative += ", bad hands, missing fingers, extra digits, bad face, deformed face"
        
        return negative
    
    def _post_process(self, filepath: str) -> str:
        """图片后处理"""
        try:
            from services.image_processor import ImageProcessor
            processor = ImageProcessor()
            return processor.process(filepath)
        except ImportError:
            return filepath
        except Exception as e:
            print(f"⚠️ 后处理失败: {e}")
            return filepath
    
    def cancel(self):
        """取消生成"""
        self.cancel_flag = True
        self.is_generating = False