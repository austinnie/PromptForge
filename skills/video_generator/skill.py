"""
video_generator - 视频生成 Skill

功能：
  - 文生视频（text-to-video）
  - 长视频拼接（多个短视频片段拼接）
  - 多 API 提供商切换
"""

import os
import time
import uuid
import shutil
import subprocess
import socket
import urllib.request
import urllib.error
import logging
import random
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from PIL import Image

logger = logging.getLogger(__name__)

# ==================== 常量配置 ====================
DEFAULT_VIDEO_DURATION = 60         # 目标总时长（秒）
DEFAULT_SEGMENT_DURATION = 10       # 单段时长（秒）
DEFAULT_VIDEO_WIDTH = 768
DEFAULT_VIDEO_HEIGHT = 768
DEFAULT_ENGINE = "agnes"
VIDEO_DOWNLOAD_TIMEOUT = 600


class VideoGenerator:
    """视频生成 Skill"""

    AVAILABLE_ENGINES = ["agnes"]
    FALLBACK_ORDER = ["agnes"]

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = "video_generator"
        self.version = "1.0.0"
        self._setup_logging()
        self._setup_config()

        self._video_engine = None
        self._video_engine_provider = None
        self._init_video_engine()

        logger.info("VideoGenerator 初始化完成")

    def _setup_logging(self):
        log_level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/videos",
            "video_duration": DEFAULT_VIDEO_DURATION,
            "segment_duration": DEFAULT_SEGMENT_DURATION,
            "video_width": DEFAULT_VIDEO_WIDTH,
            "video_height": DEFAULT_VIDEO_HEIGHT,
            "engine": DEFAULT_ENGINE,
            "auto_merge": True,
            "auto_fallback": True,
        }
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value

        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ==================== 引擎初始化 ====================

    def _init_video_engine(self):
        try:
            import sys
            project_root = Path(__file__).parents[2]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from api_engines import create_engine
            from config.settings import settings

            engine_name = self.config.get("engine", DEFAULT_ENGINE)

            if engine_name == "agnes":
                config = {
                    "AGNES_API_KEY": settings.agnes_api_key,
                    "AGNES_BASE_URL": settings.agnes_base_url,
                    "AGNES_VIDEO_MODEL": settings.agnes_video_model,
                }
            else:
                logger.warning(f"⚠️ 不支持的视频引擎: {engine_name}")
                return

            self._video_engine = create_engine(engine_name, config)
            self._video_engine_provider = engine_name
            logger.info(f"✅ 视频引擎已加载: {engine_name} ({self._video_engine.get_name()})")
        except Exception as e:
            logger.warning(f"⚠️ 视频引擎初始化失败: {e}")
            self._video_engine = None

    # ==================== 视频生成 ====================

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        文生视频

        Args:
            prompt: 提示词
            duration: 视频时长（秒）
            width: 宽度
            height: 高度
            auto_merge: 是否自动拆分并拼接长视频
            segment_duration: 单段时长
            reference_image: 参考图（可选）

        Returns:
            {
                "status": "success",
                "result": {
                    "video_path": "...",
                    "duration": 60,
                    "segments": 6,
                    ...
                }
            }
        """
        start_time = time.time()
        logger.info(f"执行技能: {self.name} (v{self.version})")

        try:
            if not prompt:
                return {"status": "error", "error": "prompt 不能为空"}

            if not self._video_engine:
                return {"status": "error", "error": "视频引擎不可用"}

            duration = kwargs.get("duration", self.config["video_duration"])
            width = kwargs.get("width", self.config["video_width"])
            height = kwargs.get("height", self.config["video_height"])
            auto_merge = kwargs.get("auto_merge", self.config.get("auto_merge", True))
            segment_duration = kwargs.get("segment_duration", self.config["segment_duration"])
            reference_image = kwargs.get("reference_image")

            if auto_merge and duration > segment_duration:
                return self._generate_long_video(
                    prompt=prompt,
                    duration=duration,
                    segment_duration=segment_duration,
                    width=width,
                    height=height,
                    reference_image=reference_image,
                    start_time=start_time,
                )
            else:
                return self._generate_single_video(
                    prompt=prompt,
                    duration=min(duration, segment_duration),
                    width=width,
                    height=height,
                    reference_image=reference_image,
                    start_time=start_time,
                )
        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def _generate_single_video(self, prompt, duration, width, height, reference_image, start_time):
        """生成单个短视频"""
        logger.info(f"🎬 生成单个视频 ({duration}s)...")

        result = self._video_engine.video_generation(
            prompt=prompt,
            image=reference_image,
            duration=duration,
            width=width,
            height=height,
        )

        video_id = result.get("video_id")
        if not video_id:
            return {"status": "error", "error": f"未获取任务ID: {result}"}

        logger.info(f"⏳ 视频任务已提交 (ID: {video_id})，等待完成...")

        video_url = self._video_engine.wait_for_video(video_id)
        if not video_url:
            return {"status": "error", "error": "视频生成超时或失败"}

        video_path = self._download_video(video_url, prompt, "video")

        return {
            "status": "success",
            "result": {
                "video_path": video_path,
                "video_url": video_url,
                "duration": duration,
                "segments": 1,
                "prompt": prompt,
                "generated_at": datetime.now().isoformat(),
                "elapsed": f"{time.time() - start_time:.2f}s",
            },
            "metadata": {"skill": self.name, "version": self.version},
        }

    def _generate_long_video(self, prompt, duration, segment_duration, width, height, reference_image, start_time):
        """生成长视频（拆分为多个片段拼接）"""
        segment_count = duration // segment_duration
        if duration % segment_duration != 0:
            segment_count += 1

        logger.info(f"🎬 目标时长 {duration}s，拆分为 {segment_count} 段 ({segment_duration}s/段)")

        temp_dir = Path(self.config["output_dir"]) / f"temp_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        video_files = []

        try:
            for i in range(segment_count):
                logger.info(f"📹 生成第 {i+1}/{segment_count} 段...")
                segment_prompt = prompt if i == 0 else f"{prompt}，继续上一段，保持连贯"
                init_image = reference_image if i == 0 else None

                result = self._video_engine.video_generation(
                    prompt=segment_prompt,
                    image=init_image,
                    duration=segment_duration,
                    width=width,
                    height=height,
                )

                video_id = result.get("video_id")
                if not video_id:
                    logger.warning(f"⚠️ 第 {i+1} 段未获取任务ID")
                    continue

                video_url = self._video_engine.wait_for_video(video_id)
                if not video_url:
                    logger.warning(f"⚠️ 第 {i+1} 段生成失败")
                    continue

                temp_file = str(temp_dir / f"segment_{i:03d}.mp4")
                if self._download_video_file(video_url, temp_file):
                    video_files.append(temp_file)
                    logger.info(f"✅ 第 {i+1} 段完成")
                else:
                    logger.warning(f"⚠️ 第 {i+1} 段下载失败")

            if not video_files:
                return {"status": "error", "error": "未能生成任何视频片段"}

            # 合并片段
            if len(video_files) > 1:
                logger.info(f"🔄 正在合并 {len(video_files)} 个片段...")
                merged_file = self._merge_videos(video_files, str(temp_dir))
                if merged_file:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
                    final_filename = f"{timestamp}_video_{safe_prompt}_merged.mp4"
                    final_path = Path(self.config["output_dir"]) / final_filename
                    shutil.move(merged_file, str(final_path))
                    video_path = str(final_path)
                else:
                    video_path = video_files[0]
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
                final_filename = f"{timestamp}_video_{safe_prompt}.mp4"
                final_path = Path(self.config["output_dir"]) / final_filename
                shutil.move(video_files[0], str(final_path))
                video_path = str(final_path)

            return {
                "status": "success",
                "result": {
                    "video_path": video_path,
                    "duration": duration,
                    "segments": len(video_files),
                    "segment_duration": segment_duration,
                    "prompt": prompt,
                    "generated_at": datetime.now().isoformat(),
                    "elapsed": f"{time.time() - start_time:.2f}s",
                },
                "metadata": {"skill": self.name, "version": self.version},
            }
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass

    # ==================== 工具方法 ====================

    def _download_video_file(self, url: str, dest_path: str, max_retries: int = 5) -> bool:
        """下载视频文件（带重试）"""
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(VIDEO_DOWNLOAD_TIMEOUT)

        for attempt in range(max_retries):
            try:
                urllib.request.urlretrieve(url, dest_path)
                return True
            except Exception as e:
                logger.warning(f"下载失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 3)
            finally:
                socket.setdefaulttimeout(original_timeout)
        return False

    def _download_video(self, video_url: str, prompt: str, prefix: str) -> str:
        """下载视频并保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
        filename = f"{timestamp}_{prefix}_{safe_prompt}.mp4"
        filepath = str(Path(self.config["output_dir"]) / filename)
        self._download_video_file(video_url, filepath)
        return filepath

    def _merge_videos(self, video_files: List[str], temp_dir: str) -> Optional[str]:
        """使用 FFmpeg 合并视频"""
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
            if result.returncode != 0:
                logger.warning("未找到 FFmpeg")
                return None

            list_file = os.path.join(temp_dir, "file_list.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for file in video_files:
                    f.write(f"file '{os.path.abspath(file)}'\n")

            output_file = os.path.join(temp_dir, "merged.mp4")
            subprocess.run(
                ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file,
                 "-c", "copy", "-y", output_file],
                capture_output=True, timeout=120, check=True,
            )
            return output_file if os.path.exists(output_file) else None
        except Exception as e:
            logger.error(f"合并失败: {e}")
            return None

    def get_engine(self) -> str:
        return self._video_engine_provider

    def get_name(self) -> str:
        return f"VideoGenerator ({self._video_engine_provider})"

    def __repr__(self):
        return f"<VideoGenerator(engine={self._video_engine_provider})>"