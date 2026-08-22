# handlers/text_to_image.py
"""文生图处理器 - 根据文本描述生成图片"""

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
    """文生图处理器"""
    
    def __init__(self, app):
        super().__init__(app)
        self.prompt_builder = PromptBuilder()
        self.is_generating = False
        self.cancel_flag = False
    
    def handle(self, intent: Dict[str, Any]) -> None:
        """处理文生图意图"""
        if not self._ensure_model_loaded():
            return
        
        if self.is_generating:
            self._reply("⏳ 正在生成中，请稍候...")
            return
        
        # 获取提示词
        prompt = intent.get("prompt", "")
        negative = intent.get("negative", "")
        keywords = intent.get("keywords", {})
        
        # 安全检查
        if self.app.settings.safe_mode:
            is_unsafe, matched = SafetyChecker.check(prompt)
            if is_unsafe:
                self._reply(f"🛡️ 检测到不安全内容，已自动过滤")
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    alternatives = SafetyChecker.get_safe_alternatives(prompt)
                    prompt = alternatives[0] if alternatives else "a beautiful landscape, peaceful, serene"
                    self._reply(f"💡 已替换为安全提示词")
        
        # 构建完整提示词
        if not prompt:
            self._reply("❌ 请描述您想生成的图片内容")
            return
        
        # LLM增强
        if self.llm and self.app.settings.llm_enabled:
            enhanced = self._enhance_prompt(prompt)
            if enhanced:
                prompt = enhanced
                self._reply(f"🧠 已优化提示词")
        
        full_prompt = self.prompt_builder.build(
            {"prompt": prompt},
            keywords
        )
        full_negative = self.prompt_builder.build_negative(negative)
        
        # 估算参数
        params = self._estimate_params(prompt)
        
        self._update_status(f"🎨 生成中... ({params['width']}x{params['height']})")
        self.is_generating = True
        self.cancel_flag = False
        
        try:
            pipe = self._get_pipeline()
            if pipe is None:
                self._reply("❌ 模型未加载")
                self.is_generating = False
                return
            
            # 设置种子
            seed = params.get("seed", random.randint(1, 2**32 - 1))
            generator = torch.Generator("cpu").manual_seed(seed)
            
            # 生成
            self._update_status(f"🎨 生成中... 步数: {params['steps']}")
            
            result = pipe(
                prompt=full_prompt,
                negative_prompt=full_negative,
                num_inference_steps=params["steps"],
                guidance_scale=params["cfg"],
                height=params["height"],
                width=params["width"],
                generator=generator,
                num_images_per_prompt=1
            )
            
            # 保存图片
            image = result.images[0]
            filepath = self._save_image(image, prompt, "txt2img")
            
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
    
    def _enhance_prompt(self, prompt: str) -> Optional[str]:
        """使用LLM增强提示词"""
        llm_prompt = f"""请将以下描述转换为Stable Diffusion英文提示词，用逗号分隔，添加质量词：

用户需求：{prompt}

要求：
1. 使用英文
2. 添加 masterpiece, best quality, 8k, highly detailed
3. 包含主体、场景、风格、光线
4. 只输出提示词，不要解释

英文提示词："""
        
        result = self.llm.generate(llm_prompt, timeout=20, max_tokens=200)
        if result and len(result) > 10:
            # 清理结果
            result = result.strip()
            # 移除可能的引号
            result = result.strip('"\'')
            return result
        return None
    
    def _estimate_params(self, prompt: str) -> Dict:
        """估算生成参数"""
        prompt_lower = prompt.lower()
        
        # 判断类型
        is_portrait = any(k in prompt_lower for k in ['portrait', '头像', '特写', 'face', 'close-up'])
        is_full_body = any(k in prompt_lower for k in ['full body', '全身', 'standing', '站立'])
        is_landscape = any(k in prompt_lower for k in ['landscape', '风景', '山水', 'view', '景色'])
        is_couple = any(k in prompt_lower for k in ['couple', '双人', '两人', '情侣', 'together'])
        
        # 尺寸
        if is_portrait:
            width, height = 512, 640
        elif is_full_body:
            width, height = 512, 768
        elif is_landscape:
            width, height = 896, 512
        elif is_couple:
            width, height = 640, 896
        else:
            width, height = 512, 768
        
        # 步数
        if any(k in prompt_lower for k in ['快速', 'fast', 'quick']):
            steps = 12
        elif any(k in prompt_lower for k in ['高质量', 'high quality', 'masterpiece', '精细']):
            steps = 30
        else:
            steps = self.app.settings.default_steps
        
        # CFG
        if any(k in prompt_lower for k in ['写实', 'realistic', 'photorealistic']):
            cfg = 8.0
        elif any(k in prompt_lower for k in ['动漫', 'anime', '卡通']):
            cfg = 6.5
        else:
            cfg = self.app.settings.default_cfg
        
        return {
            "width": width,
            "height": height,
            "steps": steps,
            "cfg": cfg,
            "seed": random.randint(1, 2**32 - 1),
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