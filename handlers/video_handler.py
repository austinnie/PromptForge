# handlers/video_handler.py
"""视频生成处理器"""

import os
import random
from typing import Dict, Any
from .base import BaseHandler


class VideoHandler(BaseHandler):
    """视频生成处理器"""
    
    def __init__(self, app):
        super().__init__(app)
        self.is_generating = False
        self.cancel_flag = False
    
    def handle(self, intent: Dict[str, Any]) -> None:
        """处理视频生成意图"""
        if self.app.settings.generation_mode != "api":
            self._reply("❌ 视频生成仅支持 API 模式")
            return

        # 检查模式
        if self.app.settings.generation_mode != "api":
            self._reply("❌ 视频生成仅支持 API 模式")
            return
        
        prompt = intent.get("prompt", "")
        if not prompt:
            self._reply("❌ 请描述您想生成的视频内容")
            return
        
        # 获取 API 引擎
        from handlers.text_to_image import TextToImageHandler
        api_handler = TextToImageHandler(self.app)
        engine = api_handler._get_api_engine()
        
        if engine is None:
            self._reply("❌ API 引擎初始化失败")
            return
        
        if not hasattr(engine, 'video_generation'):
            self._reply(f"❌ {engine.get_name()} 不支持视频生成")
            return
        
        self._update_status("🎬 创建视频任务...")
        self.is_generating = True
        self.cancel_flag = False
        
        try:
            # 获取参考图（如果有上传的图片）
            init_image = None
            if hasattr(self.app, 'uploaded_images') and self.app.uploaded_images:
                init_image = self.app.uploaded_images[0].copy().convert('RGB')
                self._reply(f"📎 使用上传图片作为参考")
            
            self._update_status("🎬 提交视频生成任务...")
            
            # 调用视频生成 API
            result = engine.video_generation(
                prompt=prompt,
                image=init_image,
                duration=5,
                width=768,
                height=768
            )
            
            video_id = result.get('video_id')
            if not video_id:
                self._reply(f"❌ 未能获取视频任务ID: {result}")
                return
            
            self._reply(f"⏳ 视频生成任务已提交 (ID: {video_id})")
            self._reply(f"⏳ 预计等待 30-120 秒...")
            self._update_status(f"🎬 等待视频完成...")
            
            # 等待视频完成
            video_url = engine.wait_for_video(video_id, max_wait=300)
            
            if video_url:
                self._reply(f"✅ 视频生成完成！🎬")
                self._reply(f"📹 视频地址: {video_url}")
                
                # 下载视频到本地
                import requests
                video_response = requests.get(video_url, timeout=60)
                if video_response.status_code == 200:
                    timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
                    filename = f"{timestamp}_video_{safe_prompt}.mp4"
                    filepath = os.path.join(self.app.settings.output_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(video_response.content)
                    self._reply(f"💾 已保存到: {filepath}")
                else:
                    self._reply(f"⚠️ 无法下载视频，请点击上面的链接查看")
                
                self._update_status("✅ 视频生成完成")
            else:
                self._reply("❌ 视频生成超时或失败")
                self._update_status("❌ 视频生成失败")
            
        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
            else:
                self._reply(f"❌ 视频生成失败: {str(e)}")
                self._update_status("❌ 视频生成失败")
            import traceback
            traceback.print_exc()
        finally:
            self.is_generating = False