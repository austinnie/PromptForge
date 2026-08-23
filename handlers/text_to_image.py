# handlers/text_to_image.py
"""文生图处理器 - 支持本地和 API 两种模式"""

import os
import random
import torch
from typing import Dict, Any, Optional
from PIL import Image

from .base import BaseHandler
from core.prompt_builder import PromptBuilder
from core.safety import SafetyChecker
from api_engines import create_engine


class TextToImageHandler(BaseHandler):
    """文生图处理器"""
    
    def __init__(self, app):
        super().__init__(app)
        self.prompt_builder = PromptBuilder()
        self.is_generating = False
        self.cancel_flag = False
        
        # API 引擎（延迟初始化）
        self._api_engine = None
    
    def _get_api_engine(self):
        """获取 API 引擎（单例）"""
        if self._api_engine is None:
            settings = self.app.settings
            provider = settings.api_provider
            config = settings.get_api_config().get(provider, {})
            
            try:
                self._api_engine = create_engine(provider, config)
                print(f"✅ API 引擎初始化: {provider}")
            except Exception as e:
                print(f"❌ API 引擎初始化失败: {e}")
                return None
        
        return self._api_engine
    
    def handle(self, intent: Dict[str, Any]) -> None:
        """处理文生图意图"""
        settings = self.app.settings
        
        # 根据模式选择生成方式
        if settings.generation_mode == "api":
            self._handle_api(intent)
        else:
            self._handle_local(intent)
    
    def _handle_local(self, intent: Dict[str, Any]) -> None:
        """本地模式生成"""
        if not self._ensure_model_loaded():
            return
        
        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return
        
        prompt = intent.get("prompt", "")
        original_text = intent.get("original_text", "")
        
        if not prompt:
            self._reply("❌ 请描述您想生成的图片内容")
            return
        
        # 安全检查
        if self.app.settings.safe_mode:
            is_unsafe, _ = SafetyChecker.check(prompt)
            if is_unsafe:
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    self._reply("🛡️ 内容被安全过滤")
                    return
        
        params = self._estimate_params(original_text or prompt)
        steps = max(params["steps"], 25)
        cfg = params["cfg"]
        width = params["width"]
        height = params["height"]
        
        self._update_status(f"🎨 本地生成中... ({width}x{height}, {steps}步)")
        self.is_generating = True
        self.cancel_flag = False
        
        try:
            pipe = self._get_pipeline()
            if pipe is None:
                self._reply("❌ 模型未加载")
                self.is_generating = False
                return
            
            seed = random.randint(1, 2**32 - 1)
            generator = torch.Generator("cpu").manual_seed(seed)
            negative = self._build_negative(original_text or prompt)
            
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
            
            image = result.images[0]
            filepath = self._save_image(image, prompt[:50], "local")
            
            self._reply(f"✅ 图片已生成！\n📁 {os.path.basename(filepath)}")
            self._update_status(f"✅ 本地生成完成 (种子: {seed})")
            
            if self.context:
                self.context.update(
                    {"type": "text_to_image", "prompt": prompt},
                    {"image_path": filepath}
                )
            
        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消生成")
            else:
                self._reply(f"❌ 生成失败: {str(e)}")
                self._update_status("❌ 生成失败")
            import traceback
            traceback.print_exc()
        finally:
            self.is_generating = False    


    def _handle_api(self, intent: Dict[str, Any]) -> None:
        """API 模式生成"""
        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return
        
        prompt = intent.get("prompt", "")
        original_text = intent.get("original_text", "")
        
        if not prompt:
            self._reply("❌ 请描述您想生成的图片内容")
            return
        
        # 安全检查
        if self.app.settings.safe_mode:
            is_unsafe, _ = SafetyChecker.check(prompt)
            if is_unsafe:
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    self._reply("🛡️ 内容被安全过滤")
                    return
        
        # 获取 API 引擎
        engine = self._get_api_engine()
        if engine is None:
            self._reply("❌ API 引擎初始化失败，请检查 API 密钥配置")
            return
        
        params = self._estimate_params(original_text or prompt)
        width = min(params["width"] * 2, 1024)
        height = min(params["height"] * 2, 1024)
        steps = max(params["steps"], 20)
        cfg = params["cfg"]
        
        self._update_status(f"☁️ API 生成中... (宽度: {width}, 高度: {height})")
        self.is_generating = True
        self.cancel_flag = False
        
        try:
            # 构建提示词
            if self.app.settings.api_provider == "pollinations":
                simple_prompt = intent.get("original_text", prompt)
                for word in ["生成", "画", "帮我画", "create", "generate"]:
                    simple_prompt = simple_prompt.replace(word, "")
                full_prompt = simple_prompt.strip().strip('，').strip(',')
                print(f"🔍 Pollinations 使用简化 Prompt: {full_prompt}")
            else:
                full_prompt = self._build_quality_prompt(original_text, intent.get("keywords", {}))
            
            negative = self._build_negative(original_text)
            
            self._update_status(f"☁️ 调用 {engine.get_name()} API...")
            
            image = engine.generate_single(
                prompt=full_prompt,
                negative=negative,
                width=width,
                height=height,
                steps=steps,
                cfg=cfg,
                seed=random.randint(1, 2**32 - 1)
            )
            
            filepath = self._save_image(image, prompt[:50], "api")
            
            self._reply(f"✅ 图片已生成（{engine.get_name()} API）！\n📁 {os.path.basename(filepath)}")
            self._update_status("✅ API 生成完成")
            
            if self.context:
                self.context.update(
                    {"type": "text_to_image", "prompt": prompt},
                    {"image_path": filepath}
                )
            
        except Exception as e:
            error_msg = str(e)
            
            # ✅ 如果 Free API 失败，自动切换到 Pollinations
            if self.app.settings.api_provider == "freeapi" and "不可用" in error_msg:
                print(f"⚠️ Free API 不可用，自动切换到 Pollinations")
                self._reply("⚠️ Free API 暂时不可用，自动切换到 Pollinations...")
                
                # 切换提供商
                self.app.settings.api_provider = "pollinations"
                self._api_engine = None
                engine = self._get_api_engine()
                
                if engine:
                    try:
                        # 重新生成
                        self._update_status("☁️ 切换到 Pollinations 重新生成...")
                        
                        # 简化 prompt
                        simple_prompt = intent.get("original_text", prompt)
                        for word in ["生成", "画", "帮我画", "create", "generate"]:
                            simple_prompt = simple_prompt.replace(word, "")
                        full_prompt = simple_prompt.strip().strip('，').strip(',')
                        
                        image = engine.generate_single(
                            prompt=full_prompt,
                            negative="ugly, blurry",
                            width=width,
                            height=height,
                            steps=steps,
                            cfg=cfg,
                            seed=random.randint(1, 2**32 - 1)
                        )
                        
                        filepath = self._save_image(image, prompt[:50], "api")
                        self._reply(f"✅ 图片已生成（Pollinations AI）！\n📁 {os.path.basename(filepath)}")
                        self._update_status("✅ Pollinations 生成完成")
                        
                        if self.context:
                            self.context.update(
                                {"type": "text_to_image", "prompt": prompt},
                                {"image_path": filepath}
                            )
                        return
                        
                    except Exception as e2:
                        print(f"❌ Pollinations 也失败了: {e2}")
                        self._reply(f"❌ 所有 API 都失败了，请稍后重试或使用本地模式")
                        self._update_status("❌ 所有 API 失败")
                        return
            
            # 原有错误处理
            if self.cancel_flag:
                self._reply("⏹️ 已取消生成")
            else:
                self._reply(f"❌ API 生成失败: {error_msg}")
                self._update_status("❌ API 生成失败")
            import traceback
            traceback.print_exc()
        finally:
            self.is_generating = False
        
    def _build_quality_prompt(self, text: str, keywords: Dict) -> str:
        """构建高质量提示词"""
        quality = "masterpiece, best quality, photorealistic, 8k, highly detailed"
        subject = self._extract_subject(text)
        scene = self._extract_scene(text, keywords)
        style = self._extract_style(text, keywords)
        lighting = self._extract_lighting(text)
        
        parts = [quality]
        if subject:
            parts.append(subject)
        if style:
            parts.append(style)
        if scene:
            parts.append(scene)
        if lighting:
            parts.append(lighting)
        parts.append("intricate details, professional photography")
        
        return ", ".join(parts)
    
    def _extract_subject(self, text: str) -> str:
        """提取主体"""
        text_lower = text.lower()
        if any(k in text_lower for k in ['美女', '女孩', '女人']):
            return "a beautiful young woman, flawless skin, elegant features"
        if any(k in text_lower for k in ['帅哥', '男孩', '男人']):
            return "a handsome young man, sharp features"
        if any(k in text_lower for k in ['风景', '景色']):
            return "breathtaking landscape, majestic nature"
        return "a beautiful scene"
    
    def _extract_scene(self, text: str, keywords: Dict) -> str:
        """提取场景"""
        scenes = keywords.get("scenes", [])
        scene_map = {
            'beach': 'tropical beach, crystal clear water',
            'forest': 'magical forest, ancient trees',
            'city': 'modern city, vibrant urban landscape',
            'garden': 'beautiful garden, blooming flowers',
            'ocean': 'ocean view, gentle waves',
            'sunset': 'golden sunset, warm colors',
            'starry sky': 'starry night, milky way',
        }
        for key, desc in scene_map.items():
            if key in str(scenes):
                return desc
        
        text_lower = text.lower()
        if '沙滩' in text_lower or '海边' in text_lower:
            return 'beautiful beach, ocean waves'
        if '森林' in text_lower:
            return 'magical forest, dappled sunlight'
        if '日落' in text_lower:
            return 'breathtaking sunset, golden sky'
        return 'beautiful setting'
    
    def _extract_style(self, text: str, keywords: Dict) -> str:
        """提取风格"""
        styles = keywords.get("styles", [])
        style_map = {
            'anime style': 'anime art style, vibrant colors',
            'oil painting': 'oil painting, rich textures',
            'watercolor': 'watercolor, soft flowing colors',
            'photorealistic': 'photorealistic, ultra detailed',
            'cyberpunk': 'cyberpunk style, neon lights',
            'traditional Chinese': 'traditional Chinese style, elegant',
        }
        for key, desc in style_map.items():
            if key in str(styles):
                return desc
        return 'elegant style, artistic composition'
    
    def _extract_lighting(self, text: str) -> str:
        """提取光线"""
        text_lower = text.lower()
        if any(k in text_lower for k in ['日落', '黄昏']):
            return 'golden hour, warm golden tones'
        if '夜晚' in text_lower:
            return 'nighttime, soft moonlight'
        if '清晨' in text_lower:
            return 'soft morning light, gentle glow'
        return 'soft natural lighting, beautiful illumination'
    
    def _build_negative(self, prompt: str) -> str:
        """构建负面提示词"""
        base = (
            "worst quality, low quality, ugly, deformed, blurry, "
            "bad anatomy, disfigured, bad face, cloned face, "
            "mutated hands, extra fingers, missing fingers, "
            "watermark, text, signature, "
            "cartoon, anime, 3d render, illustration, painting, "
            "plastic, fake, oversaturated, overexposed"
        )
        if any(k in prompt.lower() for k in ['woman', 'girl', 'man', 'boy']):
            base += ", bad hands, poorly drawn hands"
        return base
    
    def _estimate_params(self, text: str) -> Dict:
        """估算参数"""
        text_lower = text.lower()
        
        # ✅ 使用新模型支持的尺寸 (宽*高)
        if any(k in text_lower for k in ['美女', '女孩', '女人', '人像']):
            return {"width": 1104, "height": 1472, "steps": 30, "cfg": 7.5}
        if any(k in text_lower for k in ['全身', '站立']):
            return {"width": 928, "height": 1664, "steps": 32, "cfg": 7.5}
        if any(k in text_lower for k in ['风景', '景色', '日落']):
            return {"width": 1664, "height": 928, "steps": 25, "cfg": 7.0}
        if any(k in text_lower for k in ['正方形', '头像']):
            return {"width": 1328, "height": 1328, "steps": 30, "cfg": 7.5}
        
        # 默认 1:1
        return {"width": 1328, "height": 1328, "steps": 30, "cfg": 7.5}
    
    def cancel(self):
        self.cancel_flag = True
        self.is_generating = False