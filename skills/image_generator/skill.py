"""
image_generator - 图像生成 Skill

功能：
  - 文生图（text-to-image）
  - 图生图（image-to-image）
  - 多 API 提供商切换
  - 自动回退（API 失败时切换）

数据流：
  ImageGenerator → FallbackImageProvider → providers/adapters/*

不再直接依赖 api_engines。
"""

import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

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

    # 可用的图像引擎（保留给 GUI / CLI --engines 用，真实来源是 providers 注册表）
    AVAILABLE_ENGINES = [
        "agnes", "pollinations", "huggingface",
        "freeapi", "stability", "replicate",
    ]

    # 引擎自动回退顺序（保留向后兼容；真实 fallback 由 FallbackImageProvider 决定）
    FALLBACK_ORDER = ["agnes", "pollinations", "freeapi", "huggingface"]

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = "image_generator"
        self.version = "1.1.0"  # 走 providers 版
        self._setup_logging()
        self._setup_config()

        # ✅ 初始化图像 provider 链
        self._provider = None
        self._image_engine_provider = None
        self._init_image_engine()

        logger.info("ImageGenerator 初始化完成")

    # ==================== 配置 / 日志 ====================

    def _setup_logging(self):
        log_level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/images",
            "image_width": DEFAULT_IMAGE_WIDTH,
            "image_height": DEFAULT_IMAGE_HEIGHT,
            "steps": DEFAULT_STEPS,
            "cfg": DEFAULT_CFG,
            # engine=None → 用 settings.api_provider
            "engine": None,
            "negative_prompt": (
                "text, watermark, signature, low quality, blurry, ugly, deformed"
            ),
        }
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value

        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ==================== Provider 初始化 ====================

    def _init_image_engine(self):
        """初始化图像 provider 链（带 fallback）。"""
        try:
            import sys
            project_root = Path(__file__).parents[2]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from skills._provider_helper import build_image_provider

            engine_name = self.config.get("engine")  # None 就让 helper 用默认

            def _on_fallback(frm: str, to: str, err: Exception):
                logger.warning(
                    f"⚠️ provider {frm} 失败（{str(err).splitlines()[0][:80]}），"
                    f"切换到 {to}"
                )

            self._provider = build_image_provider(
                primary=engine_name,
                on_fallback=_on_fallback,
            )
            self._image_engine_provider = self._provider.primary

            logger.info(
                f"✅ 图像 provider 链: {self._provider.chain} "
                f"(primary={self._image_engine_provider})"
            )
        except Exception as e:
            logger.warning(f"⚠️ 图像 provider 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            self._provider = None
            self._image_engine_provider = None

    # ==================== 文生图 ====================

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        文生图

        Args:
            prompt:   提示词
            width:    宽度
            height:   高度
            steps:    推理步数
            cfg:      引导强度
            seed:     随机种子
            negative: 负面提示词
            engine:   指定首选引擎（覆盖本次调用的 primary）

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

            if self._provider is None:
                return {
                    "status": "error",
                    "error": "图像 provider 不可用（检查 .env 里的 API key）",
                }

            width = kwargs.get("width", self.config["image_width"])
            height = kwargs.get("height", self.config["image_height"])
            steps = kwargs.get("steps", self.config["steps"])
            cfg = kwargs.get("cfg", self.config["cfg"])
            seed = kwargs.get("seed", random.randint(1, 2**32 - 1))
            negative = kwargs.get("negative", self.config["negative_prompt"])
            engine_name = kwargs.get("engine")  # 单次调用覆盖 primary

            # ✅ 若指定了 engine 且与当前 primary 不同，临时换 primary
            #    （不重建整个链，只是临时切换一次）
            provider = self._provider
            effective_engine = self._image_engine_provider
            if engine_name and engine_name != self._image_engine_provider:
                from skills._provider_helper import build_image_provider

                try:
                    provider = build_image_provider(
                        primary=engine_name,
                        on_fallback=lambda f, t, e: logger.warning(
                            f"⚠️ {f} 失败，切到 {t}: {str(e)[:80]}"
                        ),
                    )
                    effective_engine = provider.primary
                    logger.info(f"🔄 本次调用使用 provider: {effective_engine}")
                except Exception as e:
                    logger.warning(f"⚠️ 指定 provider {engine_name} 失败，用默认: {e}")
                    provider = self._provider
                    effective_engine = self._image_engine_provider

            # ✅ 构造统一请求
            from providers.base import ImageRequest

            req = ImageRequest(
                prompt=prompt,
                negative=negative,
                width=width,
                height=height,
                steps=steps,
                cfg=cfg,
                seed=seed,
            )

            image = provider.text_to_image(req)

            if image is None:
                return {
                    "status": "error",
                    "error": "图像生成失败（所有 provider 均不可用）",
                }

            image_path = self._save_image(image, prompt, "text2img")

            return {
                "status": "success",
                "result": {
                    "image_path": image_path,
                    "width": image.size[0],
                    "height": image.size[1],
                    "engine": effective_engine,
                    "seed": seed,
                    "prompt": prompt,
                    "generated_at": datetime.now().isoformat(),
                    "elapsed": f"{time.time() - start_time:.2f}s",
                },
                "metadata": {
                    "skill": self.name,
                    "version": self.version,
                },
            }

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    # ==================== 图生图 ====================

    def generate_from_image(
        self, prompt: str, image: Image.Image, **kwargs
    ) -> Dict[str, Any]:
        """
        图生图

        Args:
            prompt:   提示词
            image:    参考图（PIL Image）
            strength: 修改强度（0-1）
            width/height: 输出尺寸（默认参考图尺寸）
            engine:   指定首选引擎

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

            if self._provider is None:
                return {
                    "status": "error",
                    "error": "图像 provider 不可用（检查 .env 里的 API key）",
                }

            width = kwargs.get("width", image.size[0])
            height = kwargs.get("height", image.size[1])
            steps = kwargs.get("steps", self.config["steps"])
            cfg = kwargs.get("cfg", self.config["cfg"])
            strength = kwargs.get("strength", 0.7)
            seed = kwargs.get("seed", random.randint(1, 2**32 - 1))
            negative = kwargs.get("negative", self.config["negative_prompt"])
            engine_name = kwargs.get("engine")

            # ✅ 临时切换 primary（同 generate）
            provider = self._provider
            effective_engine = self._image_engine_provider
            if engine_name and engine_name != self._image_engine_provider:
                from skills._provider_helper import build_image_provider

                try:
                    provider = build_image_provider(
                        primary=engine_name,
                        on_fallback=lambda f, t, e: logger.warning(
                            f"⚠️ {f} 失败，切到 {t}: {str(e)[:80]}"
                        ),
                    )
                    effective_engine = provider.primary
                    logger.info(f"🔄 本次调用使用 provider: {effective_engine}")
                except Exception as e:
                    logger.warning(f"⚠️ 指定 provider {engine_name} 失败，用默认: {e}")

            # ✅ 检查 provider 是否支持图生图
            #    adapter 里如果没有 image_to_image 方法，调用会 AttributeError
            if not hasattr(provider, "image_to_image"):
                return {
                    "status": "error",
                    "error": f"{effective_engine} 不支持图生图",
                }

            from providers.base import ImageRequest

            req = ImageRequest(
                prompt=prompt,
                negative=negative,
                width=width,
                height=height,
                steps=steps,
                cfg=cfg,
                seed=seed,
                reference=image,
                strength=strength,
            )

            result_image = provider.image_to_image(req)

            image_path = self._save_image(result_image, prompt, "img2img")

            return {
                "status": "success",
                "result": {
                    "image_path": image_path,
                    "width": result_image.size[0],
                    "height": result_image.size[1],
                    "engine": effective_engine,
                    "strength": strength,
                    "seed": seed,
                    "prompt": prompt,
                    "generated_at": datetime.now().isoformat(),
                    "elapsed": f"{time.time() - start_time:.2f}s",
                },
                "metadata": {
                    "skill": self.name,
                    "version": self.version,
                },
            }

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    # ==================== 工具方法 ====================

    def _save_image(self, image: Image.Image, prompt: str, prefix: str = "img") -> str:
        """保存图片。

        命名规则：{prefix}_{序号:02d}_{时间戳}.png
        不再把 prompt 拼进文件名（避免 AI 痕迹 + 中文乱码）。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(self.config["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        # 找下一个可用序号
        existing = sorted(output_dir.glob(f"{prefix}_*.png"))
        next_idx = len(existing) + 1

        filename = f"{prefix}_{next_idx:02d}_{timestamp}.png"
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