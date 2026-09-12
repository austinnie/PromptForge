"""
image_curator - 图片鉴赏文章生成 Skill

功能：
  - 扫描目录中的图片
  - 使用多模态 AI 对每张图做高质量鉴赏
  - 生成图文混排文章：
      Markdown / HTML / Word(.docx) / PDF / 微信·知乎富文本
"""

import os
import re
import json
import time
import html
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from PIL import Image

from .writers import WordWriter, PDFWriter, ClipboardWriter, make_heading

logger = logging.getLogger(__name__)

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
DEFAULT_VISION_ENGINE = "agnes"

DEFAULT_DESCRIPTION_PROMPT = (
    "请详细描述这张图片。"
    "涵盖主体、构图、色彩、光影、风格、氛围等方面；"
    "用流畅优雅的中文写作；"
    "150 字左右。"
    "只输出描述正文，不要分点、不要标题、不要评价语。"
)


class ImageCurator:
    """图片鉴赏文章生成器"""

    AVAILABLE_ENGINES = ["agnes"]

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = "image_curator"
        self.version = "1.1.0"
        self._setup_logging()
        self._setup_config()

        self._vision_engine = None
        self._vision_engine_provider = None
        self._init_vision_engine()

        logger.info("ImageCurator 初始化完成")

    # ---------- 初始化 ----------

    def _setup_logging(self):
        log_level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/articles",
            "vision_engine": DEFAULT_VISION_ENGINE,
            "description_prompt": DEFAULT_DESCRIPTION_PROMPT,
            "article_title": None,
            "article_intro": None,
            "author": "AI 艺术评论",
            "max_images": 100,
            "generate_html": True,
            "generate_docx": True,
            "generate_pdf": True,
            "generate_clipboard": True,
            "throttle_seconds": 2,     # 图与图之间间隔，避免 API 限流
            "vision_max_size": 1280,   # 送模型前缩放
        }
        for k, v in defaults.items():
            if k not in self.config:
                self.config[k] = v
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    def _init_vision_engine(self):
        try:
            import sys
            project_root = Path(__file__).parents[2]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from api_engines import create_engine
            from config.settings import settings

            engine_name = self.config.get("vision_engine", DEFAULT_VISION_ENGINE)
            if engine_name == "agnes":
                cfg = {
                    "AGNES_API_KEY": settings.agnes_api_key,
                    "AGNES_BASE_URL": settings.agnes_base_url,
                    "AGNES_VIDEO_MODEL": settings.agnes_video_model,
                }
            else:
                logger.warning(f"⚠️ 不支持的视觉引擎: {engine_name}")
                return

            self._vision_engine = create_engine(engine_name, cfg)
            self._vision_engine_provider = engine_name
            logger.info(f"✅ 视觉引擎已加载: {engine_name}")
        except Exception as e:
            logger.warning(f"⚠️ 视觉引擎初始化失败: {e}")
            self._vision_engine = None

    # ---------- 主入口 ----------

    def curate(self, directory: str, **kwargs) -> Dict[str, Any]:
        """对目录中的图片做鉴赏，生成图文混排文章。"""
        start_time = time.time()
        logger.info(f"执行技能: {self.name} (v{self.version})")

        try:
            if not self._vision_engine:
                return {"status": "error", "error": "视觉引擎不可用"}

            dir_path = Path(directory).resolve()
            if not dir_path.exists() or not dir_path.is_dir():
                return {"status": "error", "error": f"目录不存在: {dir_path}"}

            recursive = kwargs.get("recursive", False)
            max_images = kwargs.get("max_images", self.config["max_images"])
            title = kwargs.get("title") or self.config.get("article_title") or dir_path.name
            intro = kwargs.get("intro") or self.config.get("article_intro")

            images = self._scan_images(dir_path, recursive=recursive)
            if not images:
                return {"status": "error", "error": f"目录中未找到图片: {dir_path}"}
            images = images[:max_images]
            logger.info(f"🖼️  发现 {len(images)} 张图片，开始鉴赏...")

            entries: List[Dict[str, Any]] = []
            for idx, img_path in enumerate(images, 1):
                logger.info(f"🔍 [{idx}/{len(images)}] {img_path.name}")
                entries.append(self._analyze_image(img_path, idx))
                if idx < len(images):
                    time.sleep(self.config["throttle_seconds"])

            # 输出目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(
                c for c in title if c.isalnum() or c in " _-"
            ).strip() or "gallery"
            article_dir = Path(self.config["output_dir"]) / f"{timestamp}_{safe_title}"
            article_dir.mkdir(parents=True, exist_ok=True)

            # 复制图片 → assets/
            assets_dir = article_dir / "assets"
            assets_dir.mkdir(exist_ok=True)
            for e in entries:
                src = Path(e["source_path"])
                dst = assets_dir / src.name
                try:
                    shutil.copy2(src, dst)
                except Exception as ex:
                    logger.warning(f"⚠️ 复制失败 {src.name}: {ex}")
                e["asset_path"] = f"assets/{src.name}"

            if not intro:
                intro = self._generate_intro(title, entries)

            # Markdown（总是生成）
            md_path = article_dir / "article.md"
            self._write_markdown(md_path, title, intro, entries)
            logger.info(f"📝 Markdown: {md_path}")

            # HTML
            html_path = None
            if self.config["generate_html"]:
                html_path = article_dir / "article.html"
                self._write_html(html_path, title, intro, entries)
                logger.info(f"🌐 HTML: {html_path}")

            # Word
            docx_path = None
            if self.config.get("generate_docx"):
                docx_path = article_dir / "article.docx"
                if WordWriter().write(docx_path, title, intro, entries):
                    logger.info(f"📘 Word: {docx_path}")
                else:
                    docx_path = None

            # PDF
            pdf_path = None
            if self.config.get("generate_pdf"):
                pdf_path = article_dir / "article.pdf"
                if PDFWriter().write(pdf_path, title, intro, entries, article_dir):
                    logger.info(f"📄 PDF: {pdf_path}")
                else:
                    pdf_path = None

            # 富文本（微信 / 知乎）
            clipboard_path = None
            if self.config.get("generate_clipboard"):
                clipboard_path = article_dir / "clipboard.html"
                ClipboardWriter().write(clipboard_path, title, intro, entries)
                logger.info(f"📋 富文本: {clipboard_path}")

            # metadata
            (article_dir / "metadata.json").write_text(
                json.dumps(
                    {"title": title, "intro": intro, "entries": entries},
                    ensure_ascii=False, indent=2,
                ),
                encoding="utf-8",
            )

            return {
                "status": "success",
                "result": {
                    "article_path": str(md_path),
                    "html_path": str(html_path) if html_path else None,
                    "docx_path": str(docx_path) if docx_path else None,
                    "pdf_path": str(pdf_path) if pdf_path else None,
                    "clipboard_path": str(clipboard_path) if clipboard_path else None,
                    "article_dir": str(article_dir),
                    "image_count": len(entries),
                    "title": title,
                    "elapsed": f"{time.time() - start_time:.2f}s",
                },
                "metadata": {"skill": self.name, "version": self.version},
            }
        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

    # ---------- 内部方法 ----------

    def _scan_images(self, dir_path: Path, recursive: bool = False) -> List[Path]:
        pattern = "**/*" if recursive else "*"
        return [
            p for p in sorted(dir_path.glob(pattern))
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        ]

    def _analyze_image(self, img_path: Path, index: int) -> Dict[str, Any]:
        entry = {
            "index": index,
            "filename": img_path.name,
            "source_path": str(img_path),
            "asset_path": None,
            "description": "",
            "error": None,
            "width": None,
            "height": None,
        }

        max_attempts = 3
        min_desc_len = 50   # ✅ 少于 50 字视为无效，重试

        # 兜底提示词：第 2、3 次尝试换更简短的指令，避免模型卡壳
        fallback_prompt = (
            "请用流畅的中文详细描述这张图片，150 字左右，"
            "涵盖主体、构图、色彩、风格、氛围。只输出正文。"
        )

        for attempt in range(max_attempts):
            try:
                with Image.open(img_path) as img:
                    img.load()
                    img = self._resize_for_vision(img, self.config["vision_max_size"])
                    entry["width"], entry["height"] = img.size

                    # 第 1 次用配置提示词，失败后换兜底
                    prompt = self.config["description_prompt"] if attempt == 0 else fallback_prompt

                    desc = self._vision_engine.image_to_text(img, prompt=prompt)
                    desc = (desc or "").strip()

                    if len(desc) < min_desc_len:
                        raise Exception(f"模型返回描述过短（{len(desc)} 字）")

                    entry["description"] = desc
                    entry["error"] = None
                    return entry

            except Exception as e:
                entry["error"] = str(e)
                if attempt < max_attempts - 1:
                    wait = 5 * (attempt + 1)
                    logger.warning(
                        f"⚠️ 鉴赏失败 ({attempt+1}/{max_attempts})，{wait}s 后重试: {e}"
                    )
                    time.sleep(wait)
                else:
                    logger.warning(f"⚠️ 鉴赏最终失败 {img_path.name}: {e}")
                    entry["description"] = f"（本图鉴赏失败：{e}）"

        return entry
        
    def _resize_for_vision(self, img: Image.Image, max_size: int) -> Image.Image:
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) <= max_size:
            return img
        scale = max_size / max(w, h)
        return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    def _generate_intro(self, title: str, entries: List[Dict]) -> str:
        try:
            names = "、".join(e["filename"] for e in entries[:5])
            prompt = (
                f"以下是一组关于「{title}」的图片，共 {len(entries)} 张，"
                f"部分文件名为：{names} 等。"
                "请以艺术评论家的口吻，写一段 80-120 字的引言，"
                "概括这组图片的整体气质与看点。只输出正文，不要标题。"
            )
            return self._vision_engine.chat_simple(prompt).strip()
        except Exception as e:
            logger.warning(f"⚠️ 引言生成失败: {e}")
            return f"本文收录了「{title}」主题下的 {len(entries)} 张作品。"

    # ---------- 各格式写出 ----------

    def _write_markdown(self, path: Path, title: str, intro: str, entries: List[Dict]):
        lines = [
            f"# {title}",
            "",
            f"> 共 {len(entries)} 张作品 · 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            intro,
            "",
            "---",
            "",
        ]
        for e in entries:
            heading = make_heading(e)
            lines.append(f"## {e['index']}. {heading}")
            lines.append("")
            if e.get("asset_path"):
                lines.append(f"![{heading}]({e['asset_path']})")
                lines.append("")
            lines.append(e["description"])
            lines.append("")
            lines.append("---")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_html(self, path: Path, title: str, intro: str, entries: List[Dict]):
        esc_title = html.escape(title)
        esc_intro = html.escape(intro)

        articles = []
        for e in entries:
            heading = html.escape(make_heading(e))
            asset = html.escape(e.get("asset_path") or "")
            desc = html.escape(e["description"])
            filename = html.escape(e["filename"])
            articles.append(f"""
    <article class="entry">
      <div class="entry-index">{e['index']:02d}</div>
      <h2>{heading}</h2>
      <figure><img src="{asset}" alt="{heading}" loading="lazy"></figure>
      <p class="desc">{desc}</p>
      <p class="filename">{filename}</p>
    </article>""")
        body = "\n".join(articles)

        html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc_title}</title>
<style>
  :root {{
    --bg: #fafaf7; --fg: #2a2a2a; --muted: #888; --accent: #c25b3b;
    --rule: #e8e4dc;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 48px 24px 96px;
    background: var(--bg); color: var(--fg);
    font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
    line-height: 1.8;
  }}
  .container {{ max-width: 820px; margin: 0 auto; }}
  header {{ text-align: center; margin-bottom: 64px; }}
  header h1 {{
    font-size: 2.4em; letter-spacing: .08em; margin: 0 0 16px; font-weight: 700;
  }}
  header .meta {{ color: var(--muted); font-size: .9em; }}
  header .intro {{
    margin-top: 32px; color: #555; font-style: italic;
    border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule);
    padding: 24px 8px;
  }}
  .entry {{ margin-bottom: 72px; position: relative; }}
  .entry-index {{
    font-size: 3em; color: #e0dbd2;
    position: absolute; left: -60px; top: -10px;
    font-family: Georgia, serif; font-style: italic;
  }}
  .entry h2 {{
    font-size: 1.5em; margin: 0 0 24px; letter-spacing: .02em;
    border-left: 3px solid var(--accent); padding-left: 16px;
  }}
  .entry figure {{
    margin: 0 0 24px; background: #f0ede6; border-radius: 4px;
    overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.04);
  }}
  .entry figure img {{ display: block; width: 100%; height: auto; }}
  .entry .desc {{ font-size: 1.02em; color: #333; text-align: justify; }}
  .entry .filename {{
    color: var(--muted); font-size: .78em;
    font-family: ui-monospace, Consolas, monospace;
    margin-top: 16px; word-break: break-all;
  }}
  @media (max-width: 640px) {{
    body {{ padding: 24px 16px 64px; }}
    .entry-index {{ position: static; margin-bottom: 8px; }}
  }}
</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>{esc_title}</h1>
      <div class="meta">共 {len(entries)} 张作品 · {datetime.now().strftime('%Y-%m-%d')}</div>
      <div class="intro">{esc_intro}</div>
    </header>
{body}
  </div>
</body>
</html>
"""
        path.write_text(html_doc, encoding="utf-8")

    # ---------- 杂项 ----------

    def get_name(self) -> str:
        return f"ImageCurator ({self._vision_engine_provider})"

    def __repr__(self):
        return f"<ImageCurator(engine={self._vision_engine_provider})>"