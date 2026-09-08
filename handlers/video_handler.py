# handlers/video_handler.py
"""视频生成处理器"""

import os
import time
import uuid
import shutil
import subprocess
import socket
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from PIL import Image

from .base import BaseHandler

# 视频下载超时（秒）
VIDEO_DOWNLOAD_TIMEOUT = 600  # 增加到 600 秒


class VideoHandler(BaseHandler):
    """视频生成处理器"""

    # Agnes 固定单段时长
    # SEGMENT_DURATION = 5

    def __init__(self, app):
        super().__init__(app)
        self.is_generating = False
        self.cancel_flag = False

    def handle(self, intent: Dict[str, Any]) -> None:
        """处理视频生成意图"""
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

        # 系统提示
        system_hint = intent.get("system_hint", "")
        if system_hint:
            self._reply(system_hint)
            self._reply("")

        # 检查是否启用循环拼接
        target_duration = self.app.settings.video_duration
        auto_merge = self.app.settings.video_auto_merge

        if auto_merge and target_duration > self.SEGMENT_DURATION:
            self._handle_merge_mode(engine, prompt, target_duration)
        else:
            self._handle_single_mode(engine, prompt)

    # ============================================================
    # 普通模式：生成 5 秒视频
    # ============================================================

    def _handle_single_mode(self, engine, prompt: str) -> None:
        """普通模式：生成 5 秒视频"""
        self._update_status("🎬 创建视频任务...")
        self.is_generating = True
        self.cancel_flag = False

        try:
            init_image = self._get_reference_image()

            result = engine.video_generation(
                prompt=prompt,
                image=init_image,
                duration=self.app.settings.video_segment_duration,# 修改
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

            video_url = engine.wait_for_video(video_id, max_wait=300)

            if video_url:
                self._reply(f"✅ 视频生成完成！🎬")
                self._reply(f"📹 视频地址: {video_url}")
                self._download_video(video_url, prompt, "video")
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

    # ============================================================
    # 循环拼接模式：拆分为多个 5 秒片段并合并
    # ============================================================

    def _handle_merge_mode(self, engine, prompt: str, target_duration: int) -> None:
        """循环拼接模式：生成多个 5 秒片段并合并"""
        segment_count = target_duration // self.SEGMENT_DURATION
        if target_duration % self.SEGMENT_DURATION != 0:
            segment_count += 1

        self._reply(f"🎬 目标时长 {target_duration} 秒，将生成 {segment_count} 个 {self.SEGMENT_DURATION} 秒片段")
        self._reply(f"⏳ 预计总耗时 {segment_count * 60} 秒左右，请耐心等待...")
        self._update_status(f"🎬 准备生成 {segment_count} 段视频...")

        self.is_generating = True
        self.cancel_flag = False

        temp_dir = os.path.join(self.app.settings.output_dir, f"temp_{uuid.uuid4().hex[:8]}")
        os.makedirs(temp_dir, exist_ok=True)

        video_files = []

        try:
            init_image = self._get_reference_image()

            for i in range(segment_count):
                if self.cancel_flag:
                    self._reply("⏹️ 已取消生成")
                    break

                self._reply(f"📹 生成第 {i+1}/{segment_count} 段...")
                self._update_status(f"🎬 生成第 {i+1}/{segment_count} 段...")

                segment_prompt = prompt
                if i > 0:
                    segment_prompt = f"{prompt}，继续上一段的动作，保持连贯"

                result = engine.video_generation(
                    prompt=segment_prompt,
                    image=init_image if i == 0 else None,
                    duration=self.app.settings.video_segment_duration,  # 修改
                    width=768,
                    height=768
                )

                video_id = result.get('video_id')
                if not video_id:
                    self._reply(f"❌ 第 {i+1} 段未能获取任务ID")
                    continue

                video_url = engine.wait_for_video(video_id, max_wait=300)

                if not video_url:
                    self._reply(f"❌ 第 {i+1} 段生成失败")
                    continue

                # 使用可靠的下载方法
                temp_file = os.path.join(temp_dir, f"segment_{i:03d}.mp4")
                if self._download_video_file(video_url, temp_file):
                    video_files.append(temp_file)
                    self._reply(f"✅ 第 {i+1} 段完成 ({len(video_files)}/{segment_count})")
                else:
                    self._reply(f"⚠️ 第 {i+1} 段下载失败，跳过")

            # 合并视频
            if len(video_files) > 1 and not self.cancel_flag:
                self._reply("🔄 正在合并视频...")
                self._update_status("🔄 合并中...")

                merged_file = self._merge_videos(video_files, temp_dir, prompt)

                if merged_file:
                    timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
                    final_filename = f"{timestamp}_video_{safe_prompt}_merged.mp4"
                    final_path = os.path.join(self.app.settings.output_dir, final_filename)
                    shutil.move(merged_file, final_path)

                    self._reply(f"✅ 视频合并完成！🎬")
                    self._reply(f"💾 已保存到: {final_path}")
                    self._reply(f"📊 总时长: {target_duration} 秒，由 {len(video_files)} 段拼接")
                    self._update_status("✅ 视频生成完成")
                else:
                    self._reply("❌ 视频合并失败")
                    self._update_status("❌ 合并失败")

            elif len(video_files) == 1 and not self.cancel_flag:
                timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
                final_filename = f"{timestamp}_video_{safe_prompt}.mp4"
                final_path = os.path.join(self.app.settings.output_dir, final_filename)
                shutil.move(video_files[0], final_path)
                self._reply(f"✅ 视频生成完成！🎬")
                self._reply(f"💾 已保存到: {final_path}")
                self._update_status("✅ 视频生成完成")

            elif self.cancel_flag:
                self._reply("⏹️ 已取消生成")
                self._update_status("已取消")

            else:
                self._reply("❌ 没有成功生成任何视频片段")
                self._update_status("❌ 生成失败")

        except Exception as e:
            if self.cancel_flag:
                self._reply("⏹️ 已取消")
            else:
                self._reply(f"❌ 视频生成失败: {str(e)}")
                self._update_status("❌ 视频生成失败")
            import traceback
            traceback.print_exc()
        finally:
            # 清理临时目录
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except:
                pass
            self.is_generating = False

    # ============================================================
    # 工具方法
    # ============================================================

    def _get_reference_image(self) -> Optional[Image.Image]:
        """获取上传的参考图"""
        if hasattr(self.app, 'uploaded_images') and self.app.uploaded_images:
            return self.app.uploaded_images[0].copy().convert('RGB')
        return None

    def _download_video_file(self, url: str, dest_path: str, max_retries: int = 5) -> bool:
        """
        使用 urllib 下载视频文件，带重试和超时
        """
        # 设置全局 socket 超时
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(VIDEO_DOWNLOAD_TIMEOUT)

        for attempt in range(max_retries):
            try:
                # 进度回调
                def report_progress(block_num, block_size, total_size):
                    if total_size > 0:
                        downloaded = block_num * block_size
                        progress = min(100, int(downloaded / total_size * 100))
                        if progress % 10 == 0:
                            self._update_status(f"⬇️ 下载中... {progress}%")

                self._update_status("⬇️ 开始下载...")
                urllib.request.urlretrieve(url, dest_path, reporthook=report_progress)
                self._update_status("✅ 下载完成")
                return True

            except (urllib.error.URLError, urllib.error.ContentTooShortError, socket.timeout, Exception) as e:
                print(f"下载失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 3
                    self._reply(f"⏳ 下载失败，{wait} 秒后重试...")
                    time.sleep(wait)
                else:
                    self._reply(f"❌ 下载最终失败: {str(e)}")
                    return False
            finally:
                # 恢复原始超时
                socket.setdefaulttimeout(original_timeout)

        return False

    def _merge_videos(self, video_files: List[str], temp_dir: str, prompt: str = "") -> Optional[str]:
        """使用 FFmpeg 合并多个视频"""
        try:
            # 检查 FFmpeg
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                self._reply("⚠️ 未找到 FFmpeg，请安装 FFmpeg 或使用分段视频")
                return None

            # 创建文件列表
            list_file = os.path.join(temp_dir, "file_list.txt")
            with open(list_file, 'w', encoding='utf-8') as f:
                for file in video_files:
                    abs_path = os.path.abspath(file)
                    f.write(f"file '{abs_path}'\n")

            output_file = os.path.join(temp_dir, "merged.mp4")

            subprocess.run([
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                '-y',
                output_file
            ], capture_output=True, timeout=120, check=True)

            if prompt:
                print(f"✅ 合并完成，原始提示词: {prompt[:30]}...")

            return output_file if os.path.exists(output_file) else None

        except subprocess.TimeoutExpired:
            self._reply("⚠️ FFmpeg 合并超时")
            return None
        except subprocess.CalledProcessError as e:
            self._reply(f"⚠️ FFmpeg 合并失败: {e.stderr.decode()[:200]}")
            return None
        except FileNotFoundError:
            self._reply("⚠️ 未找到 FFmpeg，请安装 FFmpeg")
            return None

    def _download_video(self, video_url: str, prompt: str, prefix: str) -> None:
        """下载单个视频（使用可靠方法）"""
        self._reply("⬇️ 正在下载视频文件...")
        self._update_status("⬇️ 下载中...")

        timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
        filename = f"{timestamp}_{prefix}_{safe_prompt}.mp4"
        filepath = os.path.join(self.app.settings.output_dir, filename)

        if self._download_video_file(video_url, filepath):
            self._reply(f"💾 已保存到: {filepath}")
            self._update_status("✅ 下载完成")
        else:
            self._reply(f"⚠️ 下载失败，请点击上面的链接直接查看")
            self._update_status("❌ 下载失败")

    # handlers/video_handler.py - 替换末尾两个方法

    def generate_video_from_prompt(self, prompt: str, duration: int = 5) -> Optional[str]:
        """
        生成单个视频片段并返回本地路径（供工作流调用）
        注意：此方法为同步等待，可能耗时较长
        """
        # 检查模式
        if self.app.settings.generation_mode != "api":
            print(f"⚠️ 视频生成仅支持 API 模式，当前为 {self.app.settings.generation_mode}")
            return None

        # 获取 API 引擎
        from handlers.text_to_image import TextToImageHandler
        api_handler = TextToImageHandler(self.app)
        engine = api_handler._get_api_engine()

        if engine is None:
            print("❌ API 引擎初始化失败")
            return None

        if not hasattr(engine, 'video_generation'):
            print(f"❌ {engine.get_name()} 不支持视频生成")
            return None

        try:
            # 获取参考图（如果有）
            init_image = self._get_reference_image()

            # 调用视频生成 API
            result = engine.video_generation(
                prompt=prompt,
                image=init_image,
                duration=self.app.settings.video_segment_duration  # 修改
                width=768,
                height=768
            )

            video_id = result.get('video_id')
            if not video_id:
                print(f"❌ 未能获取视频任务ID: {result}")
                return None

            print(f"⏳ 视频任务已提交 (ID: {video_id})，等待完成...")

            # 等待视频完成
            video_url = engine.wait_for_video(video_id, max_wait=300)

            if not video_url:
                print("❌ 视频生成超时或失败")
                return None

            # 下载到临时文件
            timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
            filename = f"{timestamp}_segment_{safe_prompt}.mp4"
            filepath = os.path.join(self.app.settings.output_dir, filename)

            if self._download_video_file(video_url, filepath):
                print(f"✅ 视频片段已保存: {filepath}")
                return filepath
            else:
                print(f"❌ 视频下载失败: {video_url}")
                return None

        except Exception as e:
            print(f"❌ 视频生成异常: {e}")
            import traceback
            traceback.print_exc()
            return None


    def generate_single_video(self, prompt: str) -> Optional[str]:
        """生成单个视频片段并返回路径（供工作流调用）"""
        return self.generate_video_from_prompt(prompt, duration=self.SEGMENT_DURATION)      