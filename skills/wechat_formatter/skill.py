"""
wechat_formatter - 微信公众号排版 / 推送技能

功能：
  - Markdown → 微信兼容 HTML（内联样式，兼容公众号编辑器）
  - 33 套主题 + 可视化画廊
  - AI 内容增强（可选，调用 Agnes）
  - 封面图生成（可选，复用 image_generator）
  - 一键推送公众号草稿箱（可选）
"""

import os
import re
import sys
import json
import time
import shutil
import logging
import tempfile
import subprocess
import webbrowser
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_THEME = "newspaper"


class WechatFormatter:
    """微信公众号排版技能"""

    name = "wechat_formatter"
    version = "1.0.0"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()
        self._load_engine()
        logger.info("WechatFormatter 初始化完成")

    # ---------- 初始化 ----------

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/wechat",
            "default_theme": DEFAULT_THEME,
            "auto_open_browser": True,
            "use_ai_enhance": False,   # 默认关闭，避免长文卡顿
            "use_cover_gen": False,
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)

        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    def _load_engine(self):
        try:
            project_root = Path(__file__).parents[2]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from .formatter import engine
            self._engine = engine
            logger.info(f"✅ 排版引擎已加载，主题数: {len(list(engine.THEMES_DIR.glob('*.json')))}")
        except Exception as e:
            logger.warning(f"⚠️ 排版引擎加载失败: {e}")
            self._engine = None

    # ---------- 主入口 ----------

    def format(self, md_path: str, **kwargs) -> Dict[str, Any]:
        """
        Markdown → 微信兼容 HTML

        参数（kwargs）：
          theme     主题名（默认 newspaper）
          gallery   是否打开主题画廊（默认 False）
          enhance   是否启用 AI 内容增强（默认 False）
          open      完成后是否打开浏览器
          recommend 画廊中推荐的主题 ID 列表
          footer_image 文末引导图路径（会在末尾自动插入）
          footer_alt   引导图的 alt 文字（默认 "关注"）          
        """
        start_time = time.time()
        logger.info(f"执行技能: {self.name} (v{self.version})")

        try:
            if not self._engine:
                return {"status": "error", "error": "排版引擎不可用"}

            md_path = Path(md_path).resolve()
            if not md_path.exists():
                return {"status": "error", "error": f"文件不存在: {md_path}"}

            theme_name = kwargs.get("theme") or self.config["default_theme"]
            gallery = kwargs.get("gallery", False)
            enhance = kwargs.get("enhance", self.config["use_ai_enhance"])
            should_open = kwargs.get("open", self.config["auto_open_browser"])
            recommend = kwargs.get("recommend", [])

            content = md_path.read_text(encoding="utf-8")
            logger.info(f"读取: {md_path.name} ({len(content)} 字符)")

            # ✅ 追加文末引导图
            footer_image = kwargs.get("footer_image")
            if footer_image:
                footer_path = Path(footer_image).resolve()
                if not footer_path.exists():
                    logger.warning(f"⚠️ 文末引导图不存在: {footer_path}")
                else:
                    alt_text = kwargs.get("footer_alt", "关注")
                    content = content.rstrip() + (
                        f"\n\n---\n\n![{alt_text}]({footer_path.as_posix()})\n"
                    )
                    logger.info(f"✅ 已追加文末引导图: {footer_path.name}")

            if enhance:
                content = self._ai_enhance(content)

            # 输出目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c for c in md_path.stem[:40] if c.isalnum() or c in " _-").strip() or "article"
            output_dir = Path(self.config["output_dir"]) / f"{timestamp}_{safe_name}"
            output_dir.mkdir(parents=True, exist_ok=True)

            engine = self._engine

            # ---------- 预处理 ----------
            content = engine.strip_frontmatter(content)
            content = engine.fix_cjk_spacing(content)
            content = engine.fix_cjk_bold_punctuation(content)
            content = engine.process_callouts(content)
            content = engine.process_manual_footnotes(content)
            content = engine.process_fenced_containers(content)
            content = re.sub(r"~~(.+?)~~", r"<del>\1</del>", content)

            content = engine.convert_wikilinks(content, engine.VAULT_ROOT, output_dir)
            content = engine.copy_markdown_images(content, md_path.parent, output_dir)

            html = engine.md_to_html(content)
            html, footnote_html = engine.extract_links_as_footnotes(html)

            title = engine.extract_title(md_path.read_text(encoding="utf-8"), md_path)
            word_count = engine.count_words(md_path.read_text(encoding="utf-8"))

            # ---------- 画廊模式 ----------
            if gallery:
                theme_map = {}
                for tid in engine.GALLERY_THEMES:
                    tp = engine.THEMES_DIR / f"{tid}.json"
                    if tp.exists():
                        with open(tp, encoding="utf-8") as f:
                            theme_map[tid] = json.load(f)
                theme_ids = [tid for tid in engine.GALLERY_THEMES if tid in theme_map]

                logger.info(f"画廊模式: 渲染 {len(theme_ids)} 个主题...")
                rendered_map = {}
                for tid in theme_ids:
                    rendered = engine.inject_inline_styles(html, theme_map[tid])
                    rendered = engine.convert_image_captions(rendered)
                    if footnote_html:
                        fn = engine.inject_inline_styles(footnote_html, theme_map[tid], skip_wrapper=True)
                        rendered += "\n" + fn
                    rendered_map[tid] = rendered

                gallery_path = engine.generate_gallery(
                    rendered_map, theme_map, theme_ids,
                    title, word_count, output_dir,
                    recommended=recommend,
                )
                logger.info(f"🌐 画廊: {gallery_path}")

                if should_open:
                    webbrowser.open(Path(gallery_path).resolve().as_uri())

                return {
                    "status": "success",
                    "result": {
                        "gallery_path": str(gallery_path),
                        "article_dir": str(output_dir),
                        "title": title,
                        "word_count": word_count,
                        "theme_count": len(theme_ids),
                        "elapsed": f"{time.time() - start_time:.2f}s",
                    },
                    "metadata": {"skill": self.name, "version": self.version},
                }

            # ---------- 单主题模式 ----------
            theme = engine.load_theme(theme_name)
            logger.info(f"主题: {theme.get('name')} ({theme_name})")

            html = engine.inject_inline_styles(html, theme)
            if footnote_html:
                footnote_html = engine.inject_inline_styles(footnote_html, theme, skip_wrapper=True)

            html = engine.convert_image_captions(html)
            if footnote_html:
                footnote_html = engine.convert_image_captions(footnote_html)

            full_article = html
            if footnote_html:
                full_article += "\n" + footnote_html

            article_path = output_dir / "article.html"
            article_path.write_text(full_article, encoding="utf-8")
            logger.info(f"📝 文章: {article_path}")

            preview_path = output_dir / "preview.html"
            engine.generate_preview(html, footnote_html, theme, title, word_count, preview_path)
            logger.info(f"🌐 预览: {preview_path}")

            if should_open:
                webbrowser.open(f"file://{preview_path}")

            return {
                "status": "success",
                "result": {
                    "article_path": str(article_path),
                    "preview_path": str(preview_path),
                    "article_dir": str(output_dir),
                    "title": title,
                    "word_count": word_count,
                    "theme": theme_name,
                    "theme_name": theme.get("name"),
                    "elapsed": f"{time.time() - start_time:.2f}s",
                },
                "metadata": {"skill": self.name, "version": self.version},
            }
        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    def generate_cover(self, title: str, topic: str, output_path: str = None) -> Dict[str, Any]:
        """生成公众号封面图（复用 image_generator）"""
        try:
            from .cover.cover_generator import CoverGenerator
        except Exception as e:
            return {"status": "error", "error": f"封面模块加载失败: {e}"}

        try:
            gen = CoverGenerator()
            out = gen.generate(title, topic, output_path)
            return {"status": "success", "result": {"cover_path": out}}
        except Exception as e:
            logger.error(f"封面生成失败: {e}")
            return {"status": "error", "error": str(e)}

    def publish(self, article_dir: str, cover_path: str = None, dry_run: bool = False) -> Dict[str, Any]:
        """推送文章到公众号草稿箱（subprocess 调用 publisher 脚本）"""
        try:
            project_root = Path(__file__).parents[2]
            publish_script = Path(__file__).parent / "publisher" / "wechat_publish.py"
            if not publish_script.exists():
                return {"status": "error", "error": f"未找到: {publish_script}"}

            article_dir = Path(article_dir).resolve()
            if not article_dir.exists():
                return {"status": "error", "error": f"目录不存在: {article_dir}"}

            cmd = [sys.executable, str(publish_script), "--dir", str(article_dir)]
            if cover_path:
                cmd += ["--cover", str(cover_path)]
            if dry_run:
                cmd += ["--dry-run"]

            logger.info(f"执行推送: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            if result.returncode != 0:
                return {"status": "error", "error": f"推送失败 (exit {result.returncode})"}

            return {"status": "success", "result": {"stdout": result.stdout}}
        except Exception as e:
            logger.error(f"推送异常: {e}")
            return {"status": "error", "error": str(e)}

    # ---------- 内部方法 ----------

    def _ai_enhance(self, markdown: str) -> str:
        """调用 Agnes 做内容增强（对话/画廊/callout 自动识别）"""
        try:
            import sys
            project_root = Path(__file__).parents[2]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from api_engines import create_engine
            from config.settings import settings

            engine = create_engine("agnes", {
                "AGNES_API_KEY": settings.agnes_api_key,
                "AGNES_BASE_URL": settings.agnes_base_url,
                "AGNES_VIDEO_MODEL": settings.agnes_video_model,
            })

            prompt = f"""你是微信公众号排版助手。请分析下面的 Markdown 文章，只做结构增强，不改写内容：

规则：
1. 检测到"名字：内容"交替出现的对话 → 用 :::dialogue[标题] ... ::: 包裹
2. 3 张以上连续图片 → 用 :::gallery[标题] ... ::: 包裹
3. 核心观点 → 改成 > [!important] 标题
4. 小技巧 → 改成 > [!tip] 标题
5. 章节之间确保有 --- 分隔

只输出增强后的 Markdown，不要解释。

原文：
{markdown[:6000]}"""

            logger.info("🤖 AI 内容增强中...")
            result = engine.chat_simple(prompt)
            enhanced = (result or "").strip()
            return enhanced if enhanced else markdown
        except Exception as e:
            logger.warning(f"⚠️ AI 增强失败，使用原文: {e}")
            return markdown

    # ---------- 工具 ----------

    def get_name(self) -> str:
        return f"WechatFormatter ({len(list(self._engine.THEMES_DIR.glob('*.json'))) if self._engine else 0} themes)"

    def __repr__(self):
        return f"<WechatFormatter(themes_dir={self._engine.THEMES_DIR if self._engine else None})>"