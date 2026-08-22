# handlers/text_to_image.py - 优化提示词构建和参数

import os
import random
import torch
import time
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image

from .base import BaseHandler
from core.prompt_builder import PromptBuilder
from core.safety import SafetyChecker


class TextToImageHandler(BaseHandler):
    """文生图处理器 - 优化版"""
    
    def __init__(self, app):
        super().__init__(app)
        self.prompt_builder = PromptBuilder()
        self.is_generating = False
        self.cancel_flag = False
        
        # ✅ 默认质量参数
        self.default_steps = 30
        self.default_cfg = 7.5
        self.default_width = 512
        self.default_height = 768
    
    def handle(self, intent: Dict[str, Any]) -> None:
        """处理文生图意图"""
        if not self._ensure_model_loaded():
            return
        
        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return
        
        # 获取提示词
        prompt = intent.get("prompt", "")
        original_text = intent.get("original_text", "")
        
        # ✅ 如果 LLM 没有增强，手动构建优质提示词
        if not intent.get("llm_enhanced", False):
            prompt = self._build_quality_prompt(original_text, intent.get("keywords", {}))
        else:
            # LLM 增强后的提示词，补充质量词
            prompt = self._add_quality_words(prompt)
        
        # 安全检查
        if self.app.settings.safe_mode:
            is_unsafe, matched = SafetyChecker.check(prompt)
            if is_unsafe:
                self._reply(f"🛡️ 检测到不安全内容，已自动过滤")
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    alternatives = SafetyChecker.get_safe_alternatives(original_text)
                    prompt = alternatives[0] if alternatives else "a beautiful landscape, peaceful, serene"
                    self._reply(f"💡 已替换为安全提示词")
        
        if not prompt:
            self._reply("❌ 请描述您想生成的图片内容")
            return
        
        # ✅ 优化参数
        params = self._estimate_params(original_text or prompt)
        
        # ✅ 使用更高质量参数
        steps = max(params["steps"], 25)  # 最少25步
        cfg = params["cfg"]
        width = params["width"]
        height = params["height"]
        
        self._update_status(f"🎨 生成中... ({width}x{height}, {steps}步)")
        self.is_generating = True
        self.cancel_flag = False
        
        try:
            pipe = self._get_pipeline()
            if pipe is None:
                self._reply("❌ 模型未加载")
                self.is_generating = False
                return
            
            # ✅ 使用固定种子保证可复现，但保留随机性
            seed = random.randint(1, 2**32 - 1)
            generator = torch.Generator("cpu").manual_seed(seed)
            
            # ✅ 增强负面提示词
            negative = self._build_negative(original_text or prompt)
            
            # 生成
            self._update_status(f"🎨 生成中... 步数: {steps}")
            
            result = pipe(
                prompt=prompt,
                negative_prompt=negative,
                num_inference_steps=steps,
                guidance_scale=cfg,
                height=height,
                width=width,
                generator=generator,
                num_images_per_prompt=1
            )
            
            # 保存图片
            image = result.images[0]
            filepath = self._save_image(image, prompt[:50], "chat")
            
            # 后处理
            filepath = self._post_process(filepath)
            
            self._reply(f"✅ 图片已生成！\n📁 {os.path.basename(filepath)}")
            self._update_status(f"✅ 生成完成 (种子: {seed})")
            
            # 更新上下文
            if self.context:
                self.context.update(
                    {"type": "text_to_image", "prompt": prompt},
                    {"image_path": filepath}
                )
            
        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消生成")
                self._update_status("⏹️ 已取消")
            else:
                self._reply(f"❌ 生成失败: {str(e)}")
                self._update_status("❌ 生成失败")
            import traceback
            traceback.print_exc()
        finally:
            self.is_generating = False
    
    def _build_quality_prompt(self, text: str, keywords: Dict) -> str:
        """构建高质量提示词"""
        # 基础质量词
        quality = "masterpiece, best quality, photorealistic, 8k, highly detailed, sharp focus"
        
        # 提取主体
        subject = self._extract_subject(text)
        
        # 提取场景
        scene = self._extract_scene(text, keywords)
        
        # 提取风格
        style = self._extract_style(text, keywords)
        
        # 提取光线
        lighting = self._extract_lighting(text)
        
        # 组合
        parts = [quality]
        if subject:
            parts.append(subject)
        if style:
            parts.append(style)
        if scene:
            parts.append(scene)
        if lighting:
            parts.append(lighting)
        
        # 添加细节增强
        parts.append("intricate details, professional photography, cinematic lighting")
        
        return ", ".join(parts)
    
    def _extract_subject(self, text: str) -> str:
        """提取主体描述"""
        text_lower = text.lower()
        
        # 人物
        if any(k in text_lower for k in ['美女', '女孩', '女人', '女生']):
            return "a beautiful young woman, long flowing hair, flawless skin, elegant features"
        elif any(k in text_lower for k in ['帅哥', '男孩', '男人', '男生']):
            return "a handsome young man, sharp features, well-groomed"
        
        # 风景
        if any(k in text_lower for k in ['风景', '景色', '自然']):
            return "breathtaking landscape, majestic nature scenery"
        
        # 动物
        if any(k in text_lower for k in ['猫', '狗', '动物']):
            return "a beautiful animal, detailed fur, expressive eyes"
        
        # 默认
        return "a beautiful scene, captivating subject"
    
    def _extract_scene(self, text: str, keywords: Dict) -> str:
        """提取场景"""
        scenes = keywords.get("scenes", [])
        if scenes:
            scene_map = {
                'beach': 'tropical beach, crystal clear water, palm trees',
                'forest': 'magical forest, sunlight filtering through trees',
                'city': 'modern city, urban landscape, vibrant city life',
                'garden': 'beautiful garden, blooming flowers, peaceful',
                'bedroom': 'cozy bedroom, soft warm lighting, comfortable',
                'ocean': 'ocean view, gentle waves, sea breeze',
                'sunset': 'golden sunset, dramatic sky, warm colors',
                'starry sky': 'starry night sky, milky way, cosmic beauty',
            }
            for key, desc in scene_map.items():
                if key in str(scenes):
                    return desc
        
        # 从文本中提取
        text_lower = text.lower()
        if '沙滩' in text_lower or '海边' in text_lower:
            return 'beautiful beach, golden sand, ocean waves'
        elif '森林' in text_lower:
            return 'magical forest, ancient trees, dappled sunlight'
        elif '花园' in text_lower:
            return 'beautiful garden, blooming flowers, peaceful nature'
        elif '城市' in text_lower:
            return 'modern city, urban landscape, vibrant atmosphere'
        elif '日落' in text_lower:
            return 'breathtaking sunset, golden sky, warm colors'
        elif '星空' in text_lower:
            return 'starry night sky, milky way, cosmic beauty'
        elif '卧室' in text_lower:
            return 'cozy bedroom, soft natural lighting, comfortable atmosphere'
        
        return 'beautiful setting, harmonious background'
    
    def _extract_style(self, text: str, keywords: Dict) -> str:
        """提取风格"""
        styles = keywords.get("styles", [])
        if styles:
            style_map = {
                'anime style': 'anime art style, vibrant colors, clean lines',
                'oil painting': 'oil painting style, rich colors, textured brushwork',
                'watercolor': 'watercolor painting style, soft flowing colors',
                'photorealistic': 'photorealistic, ultra detailed, lifelike',
                'cyberpunk': 'cyberpunk style, neon lights, futuristic city',
                'dark style': 'dark style, moody atmosphere, dramatic shadows',
                'traditional Chinese': 'traditional Chinese style, elegant, cultural',
                'aesthetic': 'aesthetic style, beautiful composition, artistic',
            }
            for key, desc in style_map.items():
                if key in str(styles):
                    return desc
        
        return 'elegant style, artistic composition'
    
    def _extract_lighting(self, text: str) -> str:
        """提取光线"""
        text_lower = text.lower()
        
        if any(k in text_lower for k in ['日落', '黄昏', '夕阳']):
            return 'golden hour lighting, warm golden tones'
        elif any(k in text_lower for k in ['夜晚', '晚上', '夜']):
            return 'nighttime, soft moonlight, subtle lighting'
        elif any(k in text_lower for k in ['清晨', '早晨']):
            return 'soft morning light, gentle golden glow'
        elif any(k in text_lower for k in ['阴天', '多云']):
            return 'soft diffused lighting, gentle shadows'
        
        return 'soft natural lighting, beautiful illumination'
    
    def _add_quality_words(self, prompt: str) -> str:
        """添加质量词到提示词"""
        quality_words = [
            'masterpiece', 'best quality', 'photorealistic', '8k',
            'highly detailed', 'sharp focus', 'intricate details'
        ]
        
        # 检查是否已有质量词
        prompt_lower = prompt.lower()
        for q in quality_words:
            if q in prompt_lower:
                return prompt
        
        return f"masterpiece, best quality, photorealistic, 8k, highly detailed, {prompt}"
    
    def _build_negative(self, prompt: str) -> str:
        """构建增强负面提示词"""
        base_negative = (
            "worst quality, low quality, normal quality, "
            "ugly, deformed, blurry, bad anatomy, bad proportions, "
            "disfigured, bad face, cloned face, mutated hands, "
            "extra fingers, missing fingers, fused fingers, "
            "watermark, text, signature, logo, "
            "cartoon, anime, 3d render, illustration, painting, "
            "plastic, fake, oversaturated, overexposed, "
            "poorly drawn, cropped, out of frame"
        )
        
        # 如果是人像，加强手部约束
        if any(k in prompt.lower() for k in ['woman', 'girl', 'man', 'boy', '人']):
            base_negative += ", bad hands, poorly drawn hands, missing arms, extra arms"
        
        return base_negative
    
    def _estimate_params(self, text: str) -> Dict:
        """估算参数 - 优化版"""
        text_lower = text.lower()
        
        # 人像
        if any(k in text_lower for k in ['美女', '女孩', '女人', '女生', '帅哥', '男孩', '男人', '人像', 'portrait']):
            return {
                "width": 512,
                "height": 768,
                "steps": 30,
                "cfg": 7.5,
            }
        
        # 全身照
        if any(k in text_lower for k in ['全身', '站立', 'full body']):
            return {
                "width": 512,
                "height": 896,
                "steps": 32,
                "cfg": 7.5,
            }
        
        # 风景
        if any(k in text_lower for k in ['风景', '景色', '日落', '日出', 'landscape', 'scenery']):
            return {
                "width": 896,
                "height": 512,
                "steps": 25,
                "cfg": 7.0,
            }
        
        # 动物
        if any(k in text_lower for k in ['猫', '狗', '动物', 'animal']):
            return {
                "width": 640,
                "height": 640,
                "steps": 28,
                "cfg": 7.0,
            }
        
        # 默认（高质量）
        return {
            "width": 512,
            "height": 768,
            "steps": 30,
            "cfg": 7.5,
        }
    
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