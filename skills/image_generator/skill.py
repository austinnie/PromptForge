"""
image_generator - 图像生成 Skill

功能：
  - 文生图（text-to-image）
  - 图生图（image-to-image）
  - 多 API 提供商切换
  - 自动回退（API 失败时切换）
"""

import os
import time
import json
import logging
import random
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from PIL import Image

logger = logging.getLogger(__name__)

# ==================== 常量配置 ====================
DEFAULT_IMAGE_WIDTH = 1024
DEFAULT_IMAGE_HEIGHT = 1024
DEFAULT_STEPS = 25
DEFAULT_CFG = 7.5
DEFAULT_ENGINE = "agnes"


class ImageGenerator:
    """图像生成 Skill（文生图 / 图生图）"""

    # 可用的图像引擎
    AVAILABLE_ENGINES = [
        "agnes", "pollinations", "huggingface",
        "freeapi", "stability", "replicate",
    ]

    # 引擎自动回退顺序
    FALLBACK_ORDER = ["agnes", "pollinations", "freeapi", "huggingface"]

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = "image_generator"
        self.version = "1.0.0"
        self._setup_logging()
        self._setup_config()

        # ✅ 初始化图像引擎
        self._image_engine = None
        self._image_engine_provider = None
        self._init_image_engine()

        logger.info("ImageGenerator 初始化完成")

    def _setup_logging(self):
        log_level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/images",
            "image_width": DEFAULT_IMAGE_WIDTH,
            "image_height": DEFAULT_IMAGE_HEIGHT,
            "steps": DEFAULT_STEPS,
            "cfg": DEFAULT_CFG,
            "engine": DEFAULT_ENGINE,
            "negative_prompt": "text, watermark, signature, low quality, blurry, ugly, deformed",
            "auto_fallback": True,   # API 失败时自动切换引擎
            "engine_priority": self.FALLBACK_ORDER,  # 回退顺序
        }
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value

        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ==================== 引擎初始化 ====================

    def _init_image_engine(self):
        """初始化图像引擎（支持多个提供商）"""
        try:
            import sys
            project_root = Path(__file__).parents[2]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from api_engines import create_engine
            from config.settings import settings

            engine_name = self.config.get("engine", DEFAULT_ENGINE)
            self._image_engine = self._create_engine_by_name(engine_name, settings)
            if self._image_engine:
                self._image_engine_provider = engine_name
                logger.info(f"✅ 图像引擎已加载: {engine_name} ({self._image_engine.get_name()})")
            else:
                logger.warning(f"⚠️ 图像引擎初始化失败: {engine_name}")

        except Exception as e:
            logger.warning(f"⚠️ 图像引擎初始化异常: {e}")
            self._image_engine = None

    def _create_engine_by_name(self, engine_name: str, settings) -> Optional[Any]:
        """根据引擎名称创建引擎实例"""
        try:
            from api_engines import create_engine

            if engine_name == "agnes":
                config = {
                    "AGNES_API_KEY": settings.agnes_api_key,
                    "AGNES_BASE_URL": settings.agnes_base_url,
                    "AGNES_IMAGE_MODEL": settings.agnes_image_model,
                }
            elif engine_name == "pollinations":
                config = {"POLLINATIONS_MODEL": settings.pollinations_model}
            elif engine_name == "huggingface":
                config = {
                    "HF_API_TOKEN": settings.hf_api_token,
                    "HF_MODEL": settings.hf_model,
                }
            elif engine_name == "stability":
                config = {
                    "STABILITY_API_KEY": settings.stability_api_key,
                    "STABILITY_MODEL": settings.stability_model,
                }
            elif engine_name == "replicate":
                config = {
                    "REPLICATE_API_TOKEN": settings.replicate_api_token,
                    "REPLICATE_MODEL": settings.replicate_model,
                }
            elif engine_name == "freeapi":
                config = {"FREEAPI_MODEL": settings.freeapi_model}
            else:
                return None

            return create_engine(engine_name, config)
        except Exception as e:
            logger.warning(f"⚠️ 创建引擎 {engine_name} 失败: {e}")
            return None

    def _switch_engine(self, engine_name: str) -> bool:
        """切换到指定的引擎"""
        try:
            from config.settings import settings
            engine = self._create_engine_by_name(engine_name, settings)
            if engine:
                self._image_engine = engine
                self._image_engine_provider = engine_name
                logger.info(f"🔄 已切换到引擎: {engine_name}")
                return True
            return False
        except Exception as e:
            logger.warning(f"⚠️ 切换引擎失败: {e}")
            return False

    # ==================== 文生图 ====================

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        文生图

        Args:
            prompt: 提示词
            width: 宽度
            height: 高度
            steps: 推理步数
            cfg: 引导强度
            seed: 随机种子
            negative: 负面提示词
            engine: 指定引擎（覆盖默认）

        Returns:
            {
                "status": "success",
                "result": {
                    "image_path": "...",
                    "width": 1024,
                    "height": 1024,
                    "engine": "agnes",
                    "seed": 12345,
                    "prompt": "...",
                    "generated_at": "..."
                }
            }
        """
        start_time = time.time()
        logger.info(f"执行技能: {self.name} (v{self.version})")

        try:
            if not prompt:
                return {"status": "error", "error": "prompt 不能为空"}

            width = kwargs.get("width", self.config["image_width"])
            height = kwargs.get("height", self.config["image_height"])
            steps = kwargs.get("steps", self.config["steps"])
            cfg = kwargs.get("cfg", self.config["cfg"])
            seed = kwargs.get("seed", random.randint(1, 2**32 - 1))
            negative = kwargs.get("negative", self.config["negative_prompt"])
            engine_name = kwargs.get("engine", self.config.get("engine"))

            # ✅ 如果指定了引擎，切换
            if engine_name and engine_name != self._image_engine_provider:
                self._switch_engine(engine_name)

            # ✅ 调用引擎生成
            image = self._generate_with_fallback(
                prompt=prompt,
                negative=negative,
                width=width,
                height=height,
                steps=steps,
                cfg=cfg,
                seed=seed,
            )

            if image is None:
                return {"status": "error", "error": "图像生成失败（所有引擎均不可用）"}

            # ✅ 保存图片
            image_path = self._save_image(image, prompt, "text2img")

            return {
                "status": "success",
                "result": {
                    "image_path": image_path,
                    "width": image.size[0],
                    "height": image.size[1],
                    "engine": self._image_engine_provider,
                    "seed": seed,
                    "prompt": prompt,
                    "generated_at": datetime.now().isoformat(),
                    "elapsed": f"{time.time() - start_time:.2f}s",
                },
                "metadata": {
                    "skill": self.name,
                    "version": self.version,
                }
            }

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def _generate_with_fallback(self, prompt, negative, width, height, steps, cfg, seed) -> Optional[Image.Image]:
        """带自动回退的图像生成"""
        auto_fallback = self.config.get("auto_fallback", True)
        priority = self.config.get("engine_priority", self.FALLBACK_ORDER)

        # 首先尝试当前引擎
        engines_to_try = [self._image_engine_provider]
        if auto_fallback:
            for eng in priority:
                if eng not in engines_to_try:
                    engines_to_try.append(eng)

        for engine_name in engines_to_try:
            if not engine_name:
                continue

            # 切换引擎（如果与当前不同）
            if engine_name != self._image_engine_provider:
                if not self._switch_engine(engine_name):
                    continue

            if not self._image_engine:
                continue

            try:
                logger.info(f"🎨 使用引擎 {engine_name} 生成图片...")
                image = self._image_engine.generate_single(
                    prompt=prompt,
                    negative=negative,
                    width=width,
                    height=height,
                    steps=steps,
                    cfg=cfg,
                    seed=seed,
                )
                return image
            except Exception as e:
                logger.warning(f"⚠️ 引擎 {engine_name} 生成失败: {e}")
                continue

        return None

    # ==================== 图生图 ====================

    def generate_from_image(self, prompt: str, image: Image.Image, **kwargs) -> Dict[str, Any]:
        """
        图生图

        Args:
            prompt: 提示词
            image: 参考图（PIL Image）
            strength: 修改强度（0-1）
            width/height: 输出尺寸
            engine: 指定引擎

        Returns:
            {
                "status": "success",
                "result": {
                    "image_path": "...",
                    "engine": "agnes",
                    ...
                }
            }
        """
        start_time = time.time()
        logger.info(f"执行技能: {self.name} (v{self.version}) - 图生图")

        try:
            if not prompt:
                return {"status": "error", "error": "prompt 不能为空"}
            if image is None:
                return {"status": "error", "error": "image 不能为空"}

            width = kwargs.get("width", image.size[0])
            height = kwargs.get("height", image.size[1])
            steps = kwargs.get("steps", self.config["steps"])
            cfg = kwargs.get("cfg", self.config["cfg"])
            strength = kwargs.get("strength", 0.7)
            seed = kwargs.get("seed", random.randint(1, 2**32 - 1))
            engine_name = kwargs.get("engine", self.config.get("engine"))

            if engine_name and engine_name != self._image_engine_provider:
                self._switch_engine(engine_name)

            # ✅ 检查引擎是否支持图生图
            if not hasattr(self._image_engine, "image_to_image"):
                return {
                    "status": "error",
                    "error": f"{self._image_engine_provider} 不支持图生图",
                }

            logger.info(f"🎨 使用引擎 {self._image_engine_provider} 图生图...")

            result_image = self._image_engine.image_to_image(
                prompt=prompt,
                image=image,
                strength=strength,
                width=width,
                height=height,
                steps=steps,
                cfg=cfg,
                seed=seed,
            )

            image_path = self._save_image(result_image, prompt, "img2img")

            return {
                "status": "success",
                "result": {
                    "image_path": image_path,
                    "width": result_image.size[0],
                    "height": result_image.size[1],
                    "engine": self._image_engine_provider,
                    "strength": strength,
                    "seed": seed,
                    "prompt": prompt,
                    "generated_at": datetime.now().isoformat(),
                    "elapsed": f"{time.time() - start_time:.2f}s",
                },
                "metadata": {
                    "skill": self.name,
                    "version": self.version,
                }
            }

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    # ==================== 工具方法 ====================

    def _save_image(self, image: Image.Image, prompt: str, prefix: str = "img") -> str:
        """保存图片"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prompt = "".join(c for c in prompt[:30] if c.isalnum() or c in " _-") or "image"
        filename = f"{timestamp}_{prefix}_{safe_prompt}.png"
        output_dir = Path(self.config["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename
        image.save(filepath)
        logger.info(f"✅ 图片已保存: {filepath}")
        return str(filepath)

    def get_engine(self) -> str:
        return self._image_engine_provider

    def get_name(self) -> str:
        return f"ImageGenerator ({self._image_engine_provider})"

    def __repr__(self):
        return f"<ImageGenerator(engine={self._image_engine_provider})>"