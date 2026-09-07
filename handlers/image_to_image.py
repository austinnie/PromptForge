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
        if not hasattr(self.app, 'uploaded_images') or not self.app.uploaded_images:
            self._reply("❌ 请先上传一张图片")
            self._reply("💡 点击工具栏的「📎 上传图片」按钮")
            return
        
        # ✅ 根据模式决定检查方式
        if self.app.settings.generation_mode == "local":
            # 本地模式：检查本地模型
            if not self._ensure_model_loaded():
                return
        else:
            # API 模式：检查 API 引擎是否支持图生图
            from handlers.text_to_image import TextToImageHandler
            api_handler = TextToImageHandler(self.app)
            engine = api_handler._get_api_engine()
            if engine is None:
                self._reply("❌ API 引擎初始化失败，请检查 API 密钥配置")
                return
            if not hasattr(engine, 'image_to_image'):
                self._reply(f"❌ {engine.get_name()} 不支持图生图，请切换到 Agnes 等支持图生图的 API")
                return
            
            # ✅ 新增：对 Agnes 图生图行为的明确提示
            if "agnes" in str(engine).lower():
                self._reply("⚠️ 提示：Agnes 图生图是「参考原图风格重新生成」，而非「保留原图编辑」")
                self._reply("💡 如需精确保留原图编辑，请切换本地模式并加载模型")
                self._reply("   （也可继续使用 Agnes 生成，结果将参考原图风格生成新图）")
                self._reply("")
            
            # ✅ API 模式直接调用 API 图生图
            self._handle_api_img2img(intent, engine)
            return
        
        # ===== 以下是本地模式 =====
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
            init_image = self.app.uploaded_images[0].copy().convert('RGB')
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
    
    # ✅ 新增：API 图生图方法
    def _handle_api_img2img(self, intent: Dict[str, Any], engine) -> None:
        """API 图生图"""
        prompt = intent.get("prompt", "")
        original_text = intent.get("original_text", "")
        
        if not prompt:
            self._reply("❌ 请描述您想如何修改这张图片")
            return
        
        # 安全检查
        if self.app.settings.safe_mode:
            is_unsafe, _ = SafetyChecker.check(prompt)
            if is_unsafe:
                prompt = SafetyChecker.sanitize(prompt)
                if not prompt:
                    self._reply("🛡️ 内容被安全过滤")
                    return
        
        # 获取参考图尺寸
        init_image = self.app.uploaded_images[0].copy().convert('RGB')
        w, h = init_image.size
        
        # ✅ 计算合适的尺寸（保持宽高比，限制最大 1024）
        max_size = 1024
        if max(w, h) > max_size:
            scale = max_size / max(w, h)
            width = int(w * scale)
            height = int(h * scale)
        else:
            width = w
            height = h
        
        # 参数
        params = self._estimate_params(original_text or prompt)
        steps = max(params["steps"], 20)
        cfg = params["cfg"]
        
        # ✅ 根据用户输入调整 strength，但使用更保守的基础值
        user_strength = params.get("strength", 0.3)
        # 将用户强度映射到更保守的范围（0.1-0.4）
        strength = 0.1 + (user_strength * 0.3)  # 0.1 ~ 0.4
        # 如果用户明确要求"微调"，使用更小的值
        if any(k in (original_text or prompt).lower() for k in ['微调', '轻微', 'slight', 'minor']):
            strength = 0.08
        # 如果用户明确要求"大幅"，使用稍大的值
        elif any(k in (original_text or prompt).lower() for k in ['大幅', '巨大', 'major', 'big']):
            strength = 0.35
        
        # ✅ 构建详细的保留原图的 Prompt
        full_prompt = self._build_preserve_prompt(original_text)
        
        self._update_status(f"☁️ API 图生图中... (强度: {strength:.2f})")
        self.is_generating = True
        self.cancel_flag = False
            
        try:
            print(f"🔍 API 图生图参数:")
            print(f"   Prompt: {full_prompt}")
            print(f"   Width: {width}, Height: {height}")
            print(f"   Steps: {steps}, CFG: {cfg}, Strength: {strength}")
            
            image = engine.image_to_image(
                prompt=full_prompt,
                image=init_image,
                strength=strength,
                width=width,
                height=height,
                steps=steps,
                cfg=cfg,
                seed=random.randint(1, 2**32 - 1)
            )
            
            filepath = self._save_image(image, prompt[:50], "img2img_api")

            # ✅ 如果是 Agnes，说明其行为
            if "agnes" in str(engine).lower():
                self._reply("")
                self._reply("💡 提示：Agnes 图生图是「参考风格重新生成」，而非「保留原图编辑」")
                self._reply("   如需精确保留原图编辑，请切换到本地模式")
            
            self._reply(f"✅ 图生图完成（{engine.get_name()} API）！\n📁 {os.path.basename(filepath)}")
            self._update_status("✅ API 图生图完成")
            
        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
                return
            
            error_msg = str(e)
            
            # ✅ 检查是否是 Agnes 相关错误
            if "agnes" in str(engine).lower() and ("503" in error_msg or "ServiceUnavailable" in error_msg):
                self._reply("⚠️ Agnes 图生图服务暂时不可用")
                self._reply("💡 建议：")
                self._reply("   1. 稍后重试（服务可能正在恢复）")
                self._reply("   2. 切换到 本地模式（需先加载模型）")
                self._reply("   3. 使用其他 API 提供商")
                self._update_status("❌ Agnes 服务不可用")
            else:
                self._reply(f"❌ API 图生图失败: {error_msg}")
                self._update_status("❌ API 图生图失败")
            
            import traceback
            traceback.print_exc()
        finally:
            self.is_generating = False

    def _build_preserve_prompt(self, text: str) -> str:
        """构建保留原图的提示词"""
        import re
        
        # 提取用户想添加的内容
        patterns = [
            r'(?:加上|添加|增加|放入|加个|加一只|加一个|加)\s*(.+?)(?:[，。、！？\n]|$)',
            r'add\s*(.+?)(?:[,.]|$)',
        ]
        
        addition = None
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                addition = match.group(1).strip()
                break
        
        if addition:
            # 清理多余词汇
            addition = re.sub(r'(?:这张|原|参考|的)?图片?', '', addition).strip()
            if addition:
                # 英文 Prompt（Agnes 对英文理解更好）
                return f"Add {addition} to the original image. Keep all existing elements, background, and style unchanged. Only add {addition}."
        
        # 如果提取失败，使用默认描述
        return f"Edit this image: {text}. Keep the original background and composition as much as possible."
        
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