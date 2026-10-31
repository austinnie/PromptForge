"""
image_curator - 图片鉴赏文章生成 Skill（P2 补齐版）

功能:
  - 扫描目录中的图片
  - 用 vision 模型（agnes）逐张生成鉴赏描述
  - 生成图文混排文章（Markdown + HTML）
  - 可选输出 Word / PDF / 复制到剪贴板

依赖:
  - 必需: Pillow, requests（已有）
  - 可选: python-docx（Word）, reportlab（PDF）, pyperclip（剪贴板）
"""

from __future__ import annotations

import html as html_mod
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from .writers import WordWriter, PDFWriter, ClipboardWriter, make_heading

logger = logging.getLogger(__name__)

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
DEFAULT_VISION_ENGINE = "agnes"

DEFAULT_DESCRIPTION_PROMPT = (
    "请详细描述这张图片。涵盖主体、构图、色彩、光影、风格、氛围等方面；"
    "用流畅优雅的中文写作；150 字左右。只输出描述正文，不要分点、不要标题、不要评价语。"
)


class ImageCurator:
    """图片鉴赏文章生成器"""

    name = "image_curator"
    version = "1.0.0"

    AVAILABLE_ENGINES = ["agnes"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()
        self._vision_provider = None
        self._init_vision_engine()

    # ---------- 初始化 ----------

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/curator",
            "vision_engine": DEFAULT_VISION_ENGINE,
            "max_image_size": 1024,        # 送 vision 前的最长边
            "max_images": 30,              # 一次最多处理多少张
            "recursive": False,            # 是否递归子目录
            "write_formats": ["md", "html"],  # "md"/"html"/"docx"/"pdf"/"clipboard"
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    def _init_vision_engine(self):
        """初始化 vision provider（走 providers 注册表）。"""
        engine_name = self.config["vision_engine"]
        try:
            from providers import list_providers, create
            from config.settings import settings

            vision_providers = list_providers("vision")
            if not vision_providers:
                logger.warning("⚠️ 没有支持 vision 的 provider，无法鉴赏图片")
                return

            if engine_name not in vision_providers:
                engine_name = vision_providers[0]
                logger.warning(f"⚠️ 视觉引擎 {self.config['vision_engine']} 不存在，使用 {engine_name}")

            cfg = settings.get_provider_config(engine_name)
            self._vision_provider = create(engine_name, cfg)
            logger.info(f"✅ 视觉引擎: {engine_name}")
        except Exception as e:
            logger.warning(f"⚠️ 视觉引擎初始化失败: {e}")
            self._vision_provider = None

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        """run_skill 走这里。"""
        directory = kwargs.get("directory") or kwargs.get("folder") or self.config["output_dir"]
        title = kwargs.get("title") or f"图片鉴赏 · {datetime.now().strftime('%Y-%m-%d')}"
        return self.curate(directory, title, **kwargs)

    def curate(
        self,
        directory: str,
        title: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """对目录中的图片做鉴赏，生成图文混排文章。

        Args:
            directory: 图片目录
            title:     文章标题（默认用时间）
            max_images:  覆盖默认上限
            recursive:   覆盖默认递归
        """
        start = time.time()

        try:
            dir_path = Path(directory).resolve()
            if not dir_path.exists() or not dir_path.is_dir():
                return {"status": "error", "error": f"目录不存在: {dir_path}"}

            max_images = int(kwargs.get("max_images", self.config["max_images"]))
            recursive = bool(kwargs.get("recursive", self.config["recursive"]))

            images = self._scan_images(dir_path, recursive=recursive)[:max_images]
            if not images:
                return {"status": "error", "error": f"目录中没有图片: {dir_path}"}

            if self._vision_provider is None:
                return {"status": "error", "error": "视觉引擎未初始化（检查 AGNES_API_KEY）"}

            logger.info(f"🖼️ 鉴赏开始: {len(images)} 张 (目录: {dir_path.name})")

            # 逐张分析
            entries: List[Dict[str, Any]] = []
            for i, img_path in enumerate(images, 1):
                logger.info(f"  [{i}/{len(images)}] {img_path.name}")
                entry = self._analyze_image(img_path, index=i)
                if entry:
                    entries.append(entry)
                else:
                    logger.warning(f"  ⚠️ 跳过: {img_path.name}")

            if not entries:
                return {"status": "error", "error": "所有图片都鉴赏失败"}

            # 生成导言
            title = title or f"图片鉴赏 · {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            intro = self._generate_intro(title, entries)

            # 输出
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in title[:20] if c.isalnum() or c in " _-").strip() or "curator"
            out_dir = Path(self.config["output_dir"]) / f"{ts}_{safe_title}"
            out_dir.mkdir(parents=True, exist_ok=True)

            md_path = self._write_markdown(out_dir / "article.md", title, intro, entries)
            html_path = self._write_html(out_dir / "article.html", title, intro, entries)

            outputs = {
                "article_md": str(md_path) if md_path else None,
                "article_html": str(html_path) if html_path else None,
                "image_count": len(entries),
            }

            # 可选：Word / PDF / 剪贴板
            formats = self.config["write_formats"]
            if "docx" in formats:
                w = WordWriter()
                if w.available:
                    p = w.write(entries, out_dir / "article.docx", title=title)
                    if p:
                        outputs["article_docx"] = p

            if "pdf" in formats:
                p = PDFWriter()
                if p.available:
                    r = p.write(entries, out_dir / "article.pdf", title=title)
                    if r:
                        outputs["article_pdf"] = r

            if "clipboard" in formats and md_path:
                c = ClipboardWriter()
                if c.available:
                    c.write(md_path.read_text(encoding="utf-8"))
                    outputs["copied_to_clipboard"] = True

            outputs["output_dir"] = str(out_dir)
            outputs["elapsed"] = f"{time.time() - start:.1f}s"

            logger.info(f"✅ 鉴赏完成: {out_dir}")
            return {
                "status": "success",
                "result": outputs,
                "metadata": {"skill": self.name, "version": self.version},
            }

        except Exception as e:
            logger.exception("图片鉴赏失败")
            return {"status": "error", "error": str(e)}

    # ---------- 内部 ----------

    def _scan_images(self, dir_path: Path, recursive: bool = False) -> List[Path]:
        pattern = "**/*" if recursive else "*"
        files = [
            p for p in dir_path.glob(pattern)
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        ]
        # 按修改时间倒序（最新的在前）
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    def _analyze_image(self, img_path: Path, index: int) -> Optional[Dict[str, Any]]:
        """对单张图片调用 vision，返回 {image_path, description, index}。"""
        try:
            img = Image.open(img_path).convert("RGB")
            img = self._resize_for_vision(img, self.config["max_image_size"])

            desc = self._vision_provider.image_to_text(
                img,
                prompt=DEFAULT_DESCRIPTION_PROMPT,
            )
            if not desc or not desc.strip():
                return None

            return {
                "image_path": str(img_path),
                "description": desc.strip(),
                "index": index,
            }
        except Exception as e:
            logger.warning(f"分析 {img_path.name} 失败: {e}")
            return None

    @staticmethod
    def _resize_for_vision(img: Image.Image, max_size: int) -> Image.Image:
        w, h = img.size
        if max(w, h) <= max_size:
            return img
        scale = max_size / max(w, h)
        return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    def _generate_intro(self, title: str, entries: List[Dict[str, Any]]) -> str:
        """用 LLM 生成导言（失败则用简单文案）。"""
        try:
            from core.llm_client import get_default_client
            llm = get_default_client(temperature=0.7, max_tokens=300, timeout=60)
            prompt = (
                f"你是一位优雅的图片鉴赏主笔。请为下面这篇「{title}」写一段导言。\n\n"
                f"共 {len(entries)} 张图片，各图的简要描述如下：\n"
                + "\n".join(f"- {e['description'][:60]}" for e in entries[:5])
                + "\n\n要求：150 字以内，中文，流畅优美，只输出正文，不要标题。"
            )
            intro = llm.generate(prompt)
            return (intro or "").strip()
        except Exception as e:
            logger.warning(f"导言生成失败: {e}")
            return f"本期共收录 {len(entries)} 张图片。"

    def _write_markdown(
        self,
        path: Path,
        title: str,
        intro: str,
        entries: List[Dict[str, Any]],
    ) -> Optional[Path]:
        try:
            lines: List[str] = []
            lines.append(make_heading(title, 1))
            if intro:
                lines.append(intro + "\n")

            for e in entries:
                img_path = Path(e["image_path"])
                # 复制图片到输出目录（相对引用）
                local_img = path.parent / "images" / img_path.name
                local_img.parent.mkdir(parents=True, exist_ok=True)
                if not local_img.exists():
                    import shutil
                    shutil.copy2(img_path, local_img)
                lines.append(f"\n![{img_path.stem}](images/{img_path.name})\n")
                lines.append(e["description"] + "\n")

            path.write_text("\n".join(lines), encoding="utf-8")
            return path
        except Exception as e:
            logger.warning(f"写 Markdown 失败: {e}")
            return None

    def _write_html(
        self,
        path: Path,
        title: str,
        intro: str,
        entries: List[Dict[str, Any]],
    ) -> Optional[Path]:
        try:
            def esc(s: str) -> str:
                return html_mod.escape(str(s))

            parts: List[str] = [
                "<!DOCTYPE html>",
                "<html lang='zh-CN'><head><meta charset='utf-8'>",
                f"<title>{esc(title)}</title>",
                "<style>",
                "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;"
                "max-width:780px;margin:0 auto;padding:32px 24px;color:#222;line-height:1.75;background:#fff;}",
                "h1{font-size:26px;border-bottom:2px solid #222;padding-bottom:10px;margin-bottom:24px;}",
                ".intro{color:#555;font-style:italic;margin-bottom:32px;padding-left:14px;"
                "border-left:3px solid #999;}",
                ".entry{margin:36px 0;text-align:center;}",
                ".entry img{max-width:100%;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.08);}",
                ".entry p{text-align:left;color:#333;margin-top:14px;font-size:15px;}",
                ".footer{margin-top:60px;padding-top:20px;border-top:1px solid #eee;"
                "color:#999;font-size:12px;text-align:center;}",
                "</style></head><body>",
                f"<h1>{esc(title)}</h1>",
            ]
            if intro:
                parts.append(f"<p class='intro'>{esc(intro)}</p>")

            for e in entries:
                img_path = Path(e["image_path"])
                parts.append("<div class='entry'>")
                parts.append(f"<img src='images/{esc(img_path.name)}' alt='{esc(img_path.stem)}'>")
                parts.append(f"<p>{esc(e['description'])}</p>")
                parts.append("</div>")

            parts.append(
                f"<div class='footer'>Generated by PromptForge · "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>"
            )
            parts.append("</body></html>")
            path.write_text("\n".join(parts), encoding="utf-8")
            return path
        except Exception as e:
            logger.warning(f"写 HTML 失败: {e}")
            return None

    def get_name(self) -> str:
        return f"ImageCurator ({self.config['vision_engine']})"

    def __repr__(self):
        return f"<ImageCurator(vision={self.config['vision_engine']})>"