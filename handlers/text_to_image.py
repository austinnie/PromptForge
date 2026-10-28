# handlers/text_to_image.py
"""文生图处理器 - 统一的本地/API 双路调度 (基于 Provider 架构)"""

import os
import random
from typing import Dict, Any

from .base import BaseHandler
from core.prompt_builder import PromptBuilder
from core.safety import SafetyChecker

from providers import list_providers, get_meta
from providers.base import ImageRequest
from providers.fallback import FallbackImageProvider
from providers.errors import ProviderUnavailable, ProviderAuthError


class TextToImageHandler(BaseHandler):
    """文生图处理器"""

    def __init__(self, app):
        super().__init__(app)
        self.prompt_builder = PromptBuilder()
        self.is_generating = False
        self.cancel_flag = False
        self._backend = None

    def _get_backend(self) -> FallbackImageProvider:
        """构建并返回统一的后台调度器（带单例缓存）"""
        if self._backend is not None:
            return self._backend

        settings = self.app.settings
        primary = getattr(settings, "api_provider", "local_sd")

        # 1. 验证 primary 是否存在
        all_image_providers = list_providers("image")
        if primary not in all_image_providers:
            print(f"⚠️ Provider '{primary}' 不存在或不支持图像，自动选择第一个可用的。")
            primary = all_image_providers[0] if all_image_providers else "agnes"

        # 2. 构建 Fallback 候选池（排除 primary，免费优先）
        pool = [p for p in all_image_providers if p != primary]
        pool.sort(key=lambda p: (not get_meta(p).get("free", False), p))

        # 3. 读取所有 Provider 的配置
        configs = {p: settings.get_provider_config(p) for p in [primary] + pool}

        def _format_error(err: Exception) -> str:
            if isinstance(err, ProviderUnavailable):
                return str(err).split("\n")[0]
            if isinstance(err, ProviderAuthError):
                return "认证失败"
            return str(err)[:80]

        self._backend = FallbackImageProvider(
            primary=primary,
            fallback=pool,
            configs=configs,
            on_fallback=lambda frm, to, err: self._reply(
                f"⚠️ {frm} 不可用（{_format_error(err)}），自动切换到 {to}..."
            ),
        )
        print(f"✅ 后台引擎链: {[primary] + pool}")
        return self._backend

    def handle(self, intent: Dict[str, Any]) -> None:
        """统一的文生图处理入口（自动适配本地/API）"""
        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return

        prompt = intent.get("prompt", "")
        original_text = intent.get("original_text", "")
        
        if not prompt:
            self._reply("❌ 请描述您想生成的图片内容")
            return

        # 1. 安全检查
        if getattr(self.app.settings, "safe_mode", False):
            is_safe, _ = SafetyChecker.check(prompt)
            if not is_safe:
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    self._reply("🛡️ 检测到不安全内容，已阻止生成")
                    return

        # 2. 自动估算参数 (尺寸统一拉满，具体由底层 Engine 去截断/适配)
        params = self._estimate_params(original_text or prompt)
        width = params["width"]
        height = params["height"]
        steps = max(params["steps"], 20)
        cfg = params["cfg"]

        self.is_generating = True
        self.cancel_flag = False

        try:
            backend = self._get_backend()
            self._update_status(f"🎨 使用 {backend.get_name()} 生成中...")
            
            req = ImageRequest(
                prompt=prompt,
                negative=self._build_negative(original_text),
                width=width,
                height=height,
                steps=steps,
                cfg=cfg,
                seed=random.randint(1, 2**32 - 1),
            )
            
            image = backend.text_to_image(req)
            
            # 保存（生成来源标签自动从 backend 名字提取）
            tag = backend.get_name().split()[0].lower()
            filepath = self._save_image(image, prompt[:50], tag)
            
            self._reply(f"✅ 图片已生成！\n📁 {os.path.basename(filepath)}")
            self._update_status("✅ 生成完成")

            if self.context:
                self.context.update(
                    {"type": "text_to_image", "prompt": prompt},
                    {"image_path": filepath},
                )

        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
            else:
                self._reply(f"❌ 生成失败: {e}")
                self._update_status("❌ 生成失败")
                import traceback
                traceback.print_exc()
        finally:
            self.is_generating = False


    # ==================== 图生图（统一入口） ====================

    def handle_image_to_image(self, intent: Dict[str, Any]) -> None:
        """图生图统一处理入口"""
        if not getattr(self.app, "uploaded_images", None):
            self._reply("❌ 图生图需要上传一张参考图片")
            return

        prompt = intent.get("prompt", "")
        original_text = intent.get("original_text", "")
        if not prompt:
            self._reply("❌ 请描述您想如何修改这张图片")
            return

        # 安全检查
        if getattr(self.app.settings, "safe_mode", False):
            is_safe, _ = SafetyChecker.check(prompt)
            if not is_safe:
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    self._reply("🛡️ 内容被安全过滤")
                    return

        params = self._estimate_params(original_text or prompt)
        width = min(params["width"], 1024)
        height = min(params["height"], 1024)
        
        self._update_status("🎨 图生图中...")
        self.is_generating = True
        self.cancel_flag = False

        try:
            backend = self._get_backend()
            init_image = self.app.uploaded_images[0].copy().convert("RGB")
            
            # 复用你的高质量提示词构建逻辑
            full_prompt = self._build_quality_prompt(original_text, intent.get("keywords", {}))

            req = ImageRequest(
                prompt=full_prompt,
                negative=self._build_negative(original_text),
                width=width,
                height=height,
                steps=params["steps"],
                cfg=params["cfg"],
                seed=random.randint(1, 2**32 - 1),
                reference=init_image,
                strength=0.7,
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
            self._reply("❌ 当前引擎不支持图生图，请切换到云端 API 提供商。")
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

    # ==================== 提示词工程辅助工具 ====================
    
    def _build_quality_prompt(self, text: str, keywords: Dict) -> str:
        """构建高质量提示词 - 以用户描述为核心"""
        quality = "masterpiece, best quality, 8k, highly detailed"
        
        subject = self._extract_subject(text)
        scene = self._extract_scene(text, keywords)
        style = self._extract_style(text, keywords)
        lighting = self._extract_lighting(text)
        
        parts = [quality]
        
        # ✅ 用户原始描述必须包含（核心依据）
        if text:
            parts.append(text)
        
        # ✅ 只有检测到明确主体时才添加（避免臆测）
        if subject:
            parts.append(subject)
        
        if scene:
            parts.append(scene)
        if style:
            parts.append(style)
        if lighting:
            parts.append(lighting)
        
        # ✅ 如果检测到景观场景但无人物，显式添加 "no humans" 约束
        text_lower = text.lower()
        has_landscape = any(k in text_lower for k in [
            '风景', '景色', '日出', '日落', '夕阳', '旭日', '朝阳',
            '云海', '山川', '河流', '湖泊', '大海', '沙漠', '草原',
            '森林', '田园', '天空', '星空', '极光'
        ])
        has_person = any(k in text_lower for k in ['美女', '女孩', '女人', '人', '少女', '帅哥', '男孩', '男人', '少年'])
        if has_landscape and not has_person:
            parts.append("landscape, nature, no humans, no people")
        
        parts.append("intricate details, professional photography")
        
        return ", ".join(parts)
    
    def _extract_subject(self, text: str) -> str:
        """提取主体描述 - 如果没有明确主体，返回空字符串"""
        text_lower = text.lower()
        
        # ----- 人物 -----
        if any(k in text_lower for k in ['美女', '女孩', '女人', '少女']):
            return "a beautiful young woman, flawless skin, elegant features"
        if any(k in text_lower for k in ['帅哥', '男孩', '男人', '少年']):
            return "a handsome young man, sharp features"
        
        # ----- 动物 -----
        animals = ['猫', '狗', '鸟', '马', '老虎', '狮子', '龙', '鹰', '鹿']
        if any(k in text_lower for k in animals):
            return "a magnificent animal, detailed fur and features"
        
        # ----- 风景/自然（明确景观词） -----
        landscape_words = [
            '风景', '景色', '山水', '日出', '日落', '夕阳', '旭日', '朝阳',
            '云海', '山川', '河流', '湖泊', '大海', '沙漠', '草原', '森林',
            '田园', '乡村', '天空', '星空', '极光', '彩虹', '樱花', '枫叶',
            '雪景', '瀑布', '峡谷', '海岸'
        ]
        if any(k in text_lower for k in landscape_words):
            return "breathtaking landscape, majestic nature, stunning scenery"
        
        # ----- 默认：不添加任何主体，让模型根据用户描述自由发挥 -----
        return ""
    
    def _extract_scene(self, text: str, keywords: Dict) -> str:
        """提取场景描述"""
        scenes = keywords.get("scenes", [])
        scene_map = {
            'beach': 'tropical beach, crystal clear water',
            'forest': 'magical forest, ancient trees',
            'city': 'modern city, vibrant urban landscape',
            'garden': 'beautiful garden, blooming flowers',
            'ocean': 'ocean view, gentle waves',
            'sunset': 'breathtaking sunset, golden sky',
            'starry sky': 'starry night, milky way',
        }
        for key, desc in scene_map.items():
            if key in str(scenes):
                return desc
        
        text_lower = text.lower()
        
        # ✅ 扩展自然景观识别（包括日出、旭日等）
        if '日出' in text_lower or '旭日' in text_lower or '朝阳' in text_lower:
            return 'sunrise over the horizon, golden morning light, warm orange and red sky, glowing sun'
        if '日落' in text_lower or '夕阳' in text_lower:
            return 'breathtaking sunset, golden hour, warm colors, dramatic sky'
        if '沙滩' in text_lower or '海边' in text_lower:
            return 'beautiful beach, ocean waves, coastal scenery'
        if '森林' in text_lower:
            return 'magical forest, dappled sunlight, towering trees'
        if '星空' in text_lower:
            return 'starry night sky, milky way, twinkling stars'
        if '云海' in text_lower:
            return 'sea of clouds, mountain peaks, ethereal mist'
        if '瀑布' in text_lower:
            return 'majestic waterfall, cascading water, misty spray'
        if '雪景' in text_lower:
            return 'snowy landscape, pristine white, winter wonderland'
        
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