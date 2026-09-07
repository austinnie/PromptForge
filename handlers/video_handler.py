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
        # 检查模式（只保留一次）
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
        
        # 如果有系统提示，先发送
        system_hint = intent.get("system_hint", "")
        if system_hint:
            self._reply(system_hint)
            self._reply("")
        
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
                duration=self.app.settings.video_duration,
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
                
                # ✅ 流式下载视频（解决超时问题）
                import requests
                import time
                
                self._reply("⬇️ 正在下载视频文件（大文件可能需要较长时间）...")
                self._update_status("⬇️ 下载中...")
                
                # 生成文件名
                timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
                filename = f"{timestamp}_video_{safe_prompt}.mp4"
                filepath = os.path.join(self.app.settings.output_dir, filename)
                
                # 重试下载
                max_retries = 3
                download_success = False
                
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            self._reply(f"⏳ 重试下载 ({attempt + 1}/{max_retries})...")
                            time.sleep(3)
                        
                        # 流式下载，读取不超时
                        video_response = requests.get(
                            video_url,
                            stream=True,
                            timeout=(10, None)  # 连接超时 10 秒，读取不超时
                        )
                        
                        if video_response.status_code == 200:
                            total_size = int(video_response.headers.get('content-length', 0))
                            downloaded = 0
                            chunk_size = 8192
                            
                            with open(filepath, 'wb') as f:
                                for chunk in video_response.iter_content(chunk_size=chunk_size):
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        # 每 10% 显示一次进度
                                        if total_size > 0:
                                            progress = int(downloaded / total_size * 100)
                                            if progress % 10 == 0:
                                                self._update_status(f"⬇️ 下载中... {progress}%")
                            
                            self._reply(f"💾 已保存到: {filepath}")
                            self._update_status("✅ 视频下载完成")
                            download_success = True
                            break
                        else:
                            self._reply(f"⚠️ 下载失败，状态码: {video_response.status_code}")
                            
                    except requests.exceptions.Timeout:
                        if attempt == max_retries - 1:
                            self._reply("⚠️ 下载超时，请点击上面的链接直接查看视频")
                        else:
                            self._reply(f"⏳ 下载超时，重试中...")
                    except Exception as e:
                        if attempt == max_retries - 1:
                            self._reply(f"⚠️ 下载异常: {str(e)}")
                            self._reply(f"📹 请点击上面的链接直接查看视频")
                        else:
                            self._reply(f"⏳ 下载异常，重试中...")
                
                if not download_success:
                    self._reply("💡 提示：视频文件较大，建议直接点击上面的链接在浏览器中观看")
                
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