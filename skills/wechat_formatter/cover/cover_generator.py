"""
封面图生成器

复用 PromptForge 的 image_generator 技能，为公众号生成 2.35:1 封面图。
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

COVER_PROMPT_TEMPLATE = """请创建一张吸引眼球的公众号封面图，遵循以下规范：

视觉风格
- Notion 插画风格，比例为 2.35:1（公众号封面标准尺寸）
- 色彩鲜明、对比强烈，确保在小尺寸预览时依然醒目
- 风格统一，避免写实元素，保持整体手绘质感

构图要求
- 主视觉元素居中或偏左（右侧预留标题区域）
- 添加 1-2 个简洁的卡通形象、图标或人物剪影，增强记忆点
- 大量留白，突出核心信息，避免画面拥挤

文字处理
- 标题文字大而醒目，控制在 8 字以内
- 可添加 1 行副标题或关键词标签
- 字体风格与手绘插画协调统一

语言
- 默认使用中文
- 画面内所有可读文字必须使用简体中文

内容主题：{topic}
封面标题：{title}"""


class CoverGenerator:
    """公众号封面图生成器"""

    def __init__(self, engine: str = "agnes"):
        self.engine = engine
        self._generator = None
        self._init_generator()

    def _init_generator(self):
        try:
            import sys
            project_root = Path(__file__).parents[3]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from skills.image_generator import ImageGenerator
            self._generator = ImageGenerator({"engine": self.engine})
            logger.info(f"✅ 封面生图引擎已加载: {self.engine}")
        except Exception as e:
            logger.warning(f"⚠️ 封面引擎加载失败: {e}")
            self._generator = None

    def generate(
        self,
        title: str,
        topic: str,
        output_path: Optional[str] = None,
    ) -> str:
        """生成封面图，返回图片路径"""
        if not self._generator:
            raise Exception("封面引擎不可用，请检查 image_generator 技能")

        prompt = COVER_PROMPT_TEMPLATE.format(title=title, topic=topic)

        # 尽量接近 2.35:1（1280x544），但 Agnes 支持 1280x720（16:9）
        result = self._generator.generate(
            prompt=prompt,
            width=1280,
            height=720,
        )

        if result.get("status") != "success":
            raise Exception(f"生图失败: {result.get('error')}")

        src = Path(result["result"]["image_path"])
        if not src.exists():
            raise Exception(f"生图返回路径不存在: {src}")

        # 若未指定输出路径，则放在 src 同级
        if output_path:
            dst = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = "".join(c for c in title[:20] if c.isalnum() or c in " _-").strip() or "cover"
            dst = src.parent / f"{timestamp}_cover_{safe}{src.suffix}"

        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst != src:
            import shutil
            shutil.copy2(src, dst)

        logger.info(f"🎨 封面: {dst}")
        return str(dst)