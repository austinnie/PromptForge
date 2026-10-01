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

from .prompt_rules import apply_rules

logger = logging.getLogger(__name__)

# ==================== 常量配置 ====================
DEFAULT_VIDEO_DURATION = 60         # 目标总时长（秒）
DEFAULT_SEGMENT_DURATION = 10       # 单段时长（秒）
DEFAULT_VIDEO_WIDTH = 768
DEFAULT_VIDEO_HEIGHT = 768
DEFAULT_ENGINE = "agnes"
VIDEO_DOWNLOAD_TIMEOUT = 600

# ✅ 段间冷却范围（秒），避免触发 Agnes 创建任务接口限流
SEGMENT_COOLDOWN_MIN = 10
SEGMENT_COOLDOWN_MAX = 15


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
            # 提示词规则（见 prompt_rules.py）；设 False 可整体关闭，做 A/B 对照
            "apply_prompt_rules": True,
            "style_lock": None,
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
        """文生视频"""
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

            # ---- 提示词规则 ----
            dialogue = kwargs.get("dialogue")
            is_long = bool(auto_merge and duration > segment_duration)
            if dialogue and is_long:
                return {"status": "error",
                        "error": "dialogue 目前只支持单段视频（duration <= segment_duration）；"
                                 "长视频的每段台词需要分镜，请用逐镜方案"}
            rules = None
            if kwargs.get("apply_prompt_rules", self.config.get("apply_prompt_rules", True)):
                rules = {
                    "dialogue": dialogue,
                    "speaker": kwargs.get("speaker"),
                    "voice": kwargs.get("voice"),
                    "style_lock": kwargs.get("style_lock", self.config.get("style_lock")),
                    # 场景语言默认 en；只有显式传 prompt_lang="zh" 时才用中文块。
                    # 绝不因为台词里有汉字就把整块切成中文（见 prompt_rules.py 顶部说明）。
                    "lang": kwargs.get("prompt_lang", "en"),
                    # 当前引擎带图走 reference 模式（图只是风格参考，不是首帧），
                    # 所以始终用「不提首帧」的版本；等接入 keyframe 模式后再改为 True
                    "has_first_frame": False,
                }

            if is_long:
                return self._generate_long_video(
                    prompt=prompt,
                    duration=duration,
                    segment_duration=segment_duration,
                    width=width,
                    height=height,
                    reference_image=reference_image,
                    start_time=start_time,
                    rules=rules,
                )
            else:
                return self._generate_single_video(
                    prompt=prompt,
                    duration=min(duration, segment_duration),
                    width=width,
                    height=height,
                    reference_image=reference_image,
                    start_time=start_time,
                    rules=rules,
                )
        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def _generate_single_video(self, prompt, duration, width, height, reference_image, start_time, rules=None):
        """生成单个短视频"""
        logger.info(f"🎬 生成单个视频 ({duration}s)...")

        final_prompt = self._compose_prompt(prompt, rules)
        result = self._video_generation_with_queue_retry(
            prompt=final_prompt,
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
                "final_prompt": final_prompt,
                "generated_at": datetime.now().isoformat(),
                "elapsed": f"{time.time() - start_time:.2f}s",
            },
            "metadata": {"skill": self.name, "version": self.version},
        }

    def _generate_long_video(self, prompt, duration, segment_duration, width, height, reference_image, start_time, rules=None):
        """生成长视频（拆分为多个片段拼接）"""
        segment_count = duration // segment_duration
        if duration % segment_duration != 0:
            segment_count += 1

        logger.info(f"🎬 目标时长 {duration}s，拆分为 {segment_count} 段 ({segment_duration}s/段)")

        temp_dir = Path(self.config["output_dir"]) / f"temp_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        video_files = []
        success = False   # ✅ 只有完全成功才清理临时目录

        try:
            for i in range(segment_count):
                logger.info(f"📹 生成第 {i+1}/{segment_count} 段...")
                segment_prompt = prompt if i == 0 else f"{prompt}，继续上一段，保持连贯"
                init_image = reference_image if i == 0 else None

                result = self._video_generation_with_queue_retry(
                    prompt=self._compose_prompt(segment_prompt, rules),
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

                # ✅ 段间冷却：降低创建任务的 RPM，避免 Agnes 限流
                if i < segment_count - 1:
                    cooldown = SEGMENT_COOLDOWN_MIN + random.randint(
                        0, SEGMENT_COOLDOWN_MAX - SEGMENT_COOLDOWN_MIN
                    )
                    logger.info(f"😴 段间冷却 {cooldown}s...")
                    time.sleep(cooldown)

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

            success = True
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
            if success:
                # ✅ 成功后清理临时目录
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
            else:
                # ✅ 失败时保留已生成的片段，便于人工/续传使用
                logger.warning(f"⚠️ 任务未完成，临时文件保留在: {temp_dir}")

    def _video_generation_with_queue_retry(self, **kwargs) -> Dict[str, Any]:
        from api_engines.agnes import VideoQueueFullError   # ← 这里导入
        """调用 video_generation；遇到视频队列满时按指数退避重试。

        节奏：60s → 120s → 300s → 600s → 900s → 1800s
        累计等待约 63 分钟；超过上限则抛出。
        可通过 config 覆盖：
          - queue_max_retries: 最大重试次数（默认 6）
          - queue_first_wait:  首次等待秒数（默认 60）
        """
        max_retries = int(self.config.get("queue_max_retries", 6))
        wait = int(self.config.get("queue_first_wait", 60))

        last_err: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                return self._video_engine.video_generation(**kwargs)
            except VideoQueueFullError as e:
                last_err = e
                if attempt >= max_retries:
                    logger.error(f"❌ 队列持续满，{max_retries} 次重试后放弃: {e}")
                    raise
                logger.warning(
                    f"⏳ 视频队列满（第 {attempt}/{max_retries} 次），"
                    f"{wait}s 后重试... ({e})"
                )
                time.sleep(wait)
                wait = min(wait * 2, 1800)

        # 理论不可达，防御性抛出
        raise last_err if last_err else RuntimeError("队列重试异常")
        
    # ==================== 工具方法 ====================

    def _compose_prompt(self, prompt: str, rules: Optional[Dict[str, Any]]) -> str:
        """套用 prompt_rules 的固定块；rules 为 None 表示关闭，原样返回。
        最终提示词写进日志，方便事后核对到底发了什么。"""
        if not rules:
            return prompt
        final = apply_rules(prompt, **rules)
        logger.info("📝 最终提示词:\n%s", final)
        return final

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