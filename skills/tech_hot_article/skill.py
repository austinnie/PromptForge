"""
tech_hot_article - 技术热点文章生成 Skill（P2 补齐版）

功能：
  - 抓取技术热点（Hacker News / Dev.to / GitHub Trending / TechCrunch）
  - LLM 写深度技术文章（1500 字左右）
  - 自动生成配图提示词并插图（image_generator）
  - 输出 Markdown / Word / TXT

依赖：
  - requests（已有）
  - 可选：python-docx（Word 输出）
  - LLMClient（Agnes 优先 / Ollama 兜底）
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)

DEFAULT_ARTICLE_WORDS = 1500
CHARS_PER_IMAGE = 500
MAX_IMAGES_PER_ARTICLE = 4


class TechHotArticle:
    name = "tech_hot_article"
    version = "1.0.0"

    # 热点源
    HOT_SOURCES = {
        "hacker_news": "https://hnrss.org/frontpage",
        "devto":       "https://dev.to/feed",
        "techcrunch":  "https://techcrunch.com/feed/",
        "verge":       "https://www.theverge.com/rss/index.xml",
        "arstechnica": "https://arstechnica.com/feed/",
    }
    GITHUB_TRENDING = "https://github.com/trending"

    # 写作风格
    WRITING_STYLES = [
        "专业分析型",
        "通俗科普型",
        "深度技术型",
        "行业观察型",
        "趋势预测型",
    ]

    # 热点分类
    TOPICS = [
        "人工智能", "机器学习", "大语言模型", "云计算",
        "网络安全", "区块链", "Web3", "物联网", "5G",
        "量子计算", "生物科技", "新能源", "自动驾驶", "机器人",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()
        self._image_provider = None
        self._init_image_provider()

    # ---------- 初始化 ----------

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/articles",
            "article_words": DEFAULT_ARTICLE_WORDS,
            "max_images": MAX_IMAGES_PER_ARTICLE,
            "image_engine": "agnes",
            "write_formats": ["md", "docx"],
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    def _init_image_provider(self):
        """初始化图像 provider（走 registry）。"""
        try:
            from providers import list_providers, create
            from config.settings import settings

            image_providers = list_providers("image")
            if not image_providers:
                return

            engine = self.config["image_engine"]
            if engine not in image_providers:
                engine = image_providers[0]

            cfg = settings.get_provider_config(engine)
            self._image_provider = create(engine, cfg)
            self._image_engine_name = engine
            logger.info(f"✅ 图像引擎: {engine}")
        except Exception as e:
            logger.warning(f"图像引擎初始化失败: {e}")
            self._image_provider = None

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        """run_skill 走这里。

        关键 kwargs：
          topic:    指定主题（不填则自动选热点）
          style:    写作风格（默认随机）
          words:    目标字数（默认 1500）
          images:   配图数量（默认 4，0 = 不配图）
          source:   指定抓取源（hacker_news / devto / github 等）
        """
        start = time.time()

        try:
            topic_kw = kwargs.get("topic") or ""
            style = kwargs.get("style") or self._pick_style()
            words = int(kwargs.get("words", self.config["article_words"]))
            image_count = int(kwargs.get("images", self.config["max_images"]))
            source = kwargs.get("source")

            logger.info(f"📰 技术文章生成")
            logger.info(f"   主题: {topic_kw or '(自动选热点)'}")
            logger.info(f"   风格: {style}")
            logger.info(f"   字数: ~{words}")
            logger.info(f"   配图: {image_count} 张")

            # ---- 阶段 1：抓热点 ----
            hot_item = None
            if topic_kw:
                hot_item = {"title": topic_kw, "summary": "", "url": "", "source": "manual"}
            else:
                hot_topics = self.get_hot_topics(source=source)
                if not hot_topics:
                    return {"status": "error", "error": "没有抓到任何热点"}
                hot_item = hot_topics[0]
                logger.info(f"   选中热点: {hot_item['title']}")

            # ---- 阶段 2：写文章 ----
            article = self._generate_article(hot_item, style, words)
            if not article:
                return {"status": "error", "error": "文章生成失败"}

            logger.info(f"✅ 文章生成: {article['title']} ({len(article['body'])} 字)")

            # ---- 阶段 3：配图 ----
            images: List[str] = []
            if image_count > 0 and self._image_provider:
                images = self._generate_images(article, image_count)
                logger.info(f"✅ 配图生成: {len(images)} 张")

            # ---- 阶段 4：输出 ----
            article["images"] = images
            article["hot_item"] = hot_item

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r"[^\w\u4e00-\u9fff\-_]", "_", article["title"][:30])
            out_dir = Path(self.config["output_dir"]) / f"{ts}_{safe_title}"
            out_dir.mkdir(parents=True, exist_ok=True)

            md_path = self._write_markdown(article, out_dir / "article.md")
            outputs = {"article_md": str(md_path) if md_path else None}

            if "docx" in self.config["write_formats"]:
                docx_path = self._write_docx(article, out_dir / "article.docx")
                if docx_path:
                    outputs["article_docx"] = docx_path

            outputs["output_dir"] = str(out_dir)
            outputs["word_count"] = len(article["body"])
            outputs["images_count"] = len(images)
            outputs["elapsed"] = f"{time.time() - start:.1f}s"

            logger.info(f"🎉 完成: {out_dir}")
            return {
                "status": "success",
                "result": outputs,
                "metadata": {"skill": self.name, "version": self.version},
            }

        except Exception as e:
            logger.exception("技术文章生成失败")
            return {"status": "error", "error": str(e)}

    # ---------- 阶段 1：抓热点 ----------

    def get_hot_topics(self, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """抓取热点，返回按热度排序的列表。"""
        items: List[Dict[str, Any]] = []

        sources_to_fetch = [source] if source else list(self.HOT_SOURCES.keys())
        if not source or source == "github":
            sources_to_fetch = [s for s in sources_to_fetch if s != "github"]
            items.extend(self._fetch_github_trending())

        for src in sources_to_fetch:
            if src not in self.HOT_SOURCES:
                continue
            try:
                items.extend(self._fetch_rss(self.HOT_SOURCES[src], src))
            except Exception as e:
                logger.warning(f"  抓取 {src} 失败: {e}")

        if not items:
            logger.warning("⚠️ 所有源都没抓到，使用 mock 数据")
            return self._mock_hot_topics()

        # 按"有 url + summary 长度"简单排序（有内容的优先）
        items.sort(key=lambda x: (bool(x.get("url")), len(x.get("summary", ""))), reverse=True)
        return items[:20]

    def _fetch_rss(self, feed_url: str, source_name: str) -> List[Dict[str, Any]]:
        """抓取 RSS feed。"""
        try:
            r = requests.get(
                feed_url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 PromptForge/1.0"},
            )
            r.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"HTTP 失败: {e}")

        try:
            root = ET.fromstring(r.content)
        except ET.ParseError as e:
            raise RuntimeError(f"XML 解析失败: {e}")

        # RSS 2.0: <rss><channel><item>
        # Atom:   <feed><entry>
        items = root.findall(".//item") or root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )

        result: List[Dict[str, Any]] = []
        for item in items[:10]:
            title = self._text(item, "title") or self._text(
                item, "{http://www.w3.org/2005/Atom}title"
            )
            link = self._text(item, "link") or ""
            if not link:
                link_el = item.find("{http://www.w3.org/2005/Atom}link")
                if link_el is not None:
                    link = link_el.get("href", "")
            summary = (
                self._text(item, "description")
                or self._text(item, "{http://www.w3.org/2005/Atom}summary")
                or self._text(item, "{http://www.w3.org/2005/Atom}content")
                or ""
            )
            # 去 HTML 标签
            summary = re.sub(r"<[^>]+>", "", summary)[:300]

            if title:
                result.append({
                    "title": title.strip(),
                    "summary": summary.strip(),
                    "url": link.strip(),
                    "source": source_name,
                })
        return result

    def _fetch_github_trending(self) -> List[Dict[str, Any]]:
        """抓 GitHub Trending。"""
        try:
            r = requests.get(
                self.GITHUB_TRENDING,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            r.raise_for_status()
        except Exception as e:
            logger.warning(f"GitHub Trending 抓取失败: {e}")
            return []

        result: List[Dict[str, Any]] = []
        # 简单正则提取 repo 名
        for m in re.finditer(r'<h2[^>]*>.*?<a href="(/[^/]+/[^/"]+)"', r.text, re.DOTALL):
            repo = m.group(1)
            if repo.count("/") == 2:
                title = f"GitHub Trending: {repo[1:]}"
                result.append({
                    "title": title,
                    "summary": f"热门仓库 {repo[1:]}",
                    "url": f"https://github.com{repo}",
                    "source": "github",
                })
                if len(result) >= 5:
                    break
        return result

    @staticmethod
    def _text(parent, tag: str) -> str:
        el = parent.find(tag)
        return el.text.strip() if el is not None and el.text else ""

    def _mock_hot_topics(self) -> List[Dict[str, Any]]:
        return [
            {
                "title": f"{topic} 领域近期最新进展",
                "summary": f"探索 {topic} 领域的前沿技术突破与行业趋势。",
                "url": "",
                "source": "mock",
            }
            for topic in self.TOPICS[:5]
        ]

    # ---------- 阶段 2：写文章 ----------

    def _generate_article(
        self,
        hot_item: Dict[str, Any],
        style: str,
        words: int,
    ) -> Optional[Dict[str, Any]]:
        from core.llm_client import get_default_client

        title_hint = hot_item["title"]
        summary_hint = hot_item.get("summary", "")

        prompt = f"""请根据以下技术热点写一篇深度文章。

【热点信息】
标题：{title_hint}
摘要：{summary_hint[:300] if summary_hint else '(无)'}

【写作要求】
1. 风格：{style}
2. 字数：约 {words} 字
3. 结构：
   - 吸引人的标题（30 字以内）
   - 导语（100-150 字，点明为什么值得关注）
   - 正文分 3-4 个小节（用 ## 二级标题）
   - 结语（100-150 字，展望或行动建议）
4. 面向中文技术读者，语言专业但易懂
5. 需要实际技术细节，避免空话套话
6. 输出 Markdown 格式（标题用 # / ##）

直接输出文章，不要说明你在做什么。"""

        try:
            llm = get_default_client(temperature=0.75, max_tokens=4096, timeout=180)
            raw = llm.generate(prompt)
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}")
            return None

        if not raw or len(raw) < 200:
            return None

        # 解析标题
        title = ""
        m = re.search(r"^#\s+(.+?)$", raw, re.MULTILINE)
        if m:
            title = m.group(1).strip()
            # 去掉标题行
            raw = raw[m.end():].lstrip()
        else:
            title = title_hint[:30]

        return {
            "title": title,
            "body": raw.strip(),
            "style": style,
            "source": hot_item.get("source", ""),
        }

    # ---------- 阶段 3：配图 ----------

    def _generate_images(self, article: Dict[str, Any], count: int) -> List[str]:
        """按段落均匀分配配图提示词 → 生成图片。"""
        # 提取配图提示词
        prompts = self._extract_image_prompts(article, count)
        if not prompts:
            return []

        images: List[str] = []
        for i, p in enumerate(prompts):
            logger.info(f"  🎨 [{i+1}/{len(prompts)}] {p[:50]}...")
            try:
                from providers.base import ImageRequest
                req = ImageRequest(
                    prompt=p,
                    width=1024,
                    height=576,        # 16:9 横幅
                    steps=25,
                    cfg=7.5,
                )
                img = self._image_provider.text_to_image(req)
                # 保存到文章目录
                out_dir = Path(self.config["output_dir"]) / f"tmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                out_dir.mkdir(parents=True, exist_ok=True)
                img_path = out_dir / f"img_{i+1:02d}.png"
                img.save(img_path)
                images.append(str(img_path))
                logger.info(f"     ✅ {img_path.name}")
            except Exception as e:
                logger.warning(f"     ⚠️ 失败: {e}")
        return images

    def _extract_image_prompts(self, article: Dict[str, Any], count: int) -> List[str]:
        """用 LLM 从文章提炼 N 个英文配图提示词。"""
        from core.llm_client import get_default_client

        body_snippet = article["body"][:3000]
        prompt = f"""你是 AI 画图提示词专家。请从以下技术文章中提炼 {count} 个适合 AI 画图的英文 prompt。

要求：
1. 每个 prompt 描述一个抽象概念的具体视觉表达
2. 风格：futuristic tech illustration, clean composition, professional
3. 输出格式：每行一个 prompt，不要编号、不要解释、不要 markdown

文章：
{body_snippet}

直接输出 {count} 行英文 prompt："""

        try:
            llm = get_default_client(temperature=0.7, max_tokens=500, timeout=60)
            raw = llm.generate(prompt) or ""
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            # 过滤太短的
            prompts = [l for l in lines if len(l) > 20][:count]

            # 追加统一风格词
            suffix = ", futuristic tech illustration, clean composition, professional, 16:9"
            return [p + suffix for p in prompts] if prompts else []
        except Exception as e:
            logger.warning(f"配图提示词生成失败: {e}")
            # 降级：用文章标题直接生成
            return [f"{article['title']}, tech concept art, futuristic, 16:9"] * min(count, 1)

    # ---------- 输出 ----------

    def _write_markdown(self, article: Dict[str, Any], path: Path) -> Optional[Path]:
        try:
            lines = [f"# {article['title']}", ""]

            # 插入导语（body 的前 3 行或前 200 字）
            body = article["body"]
            body_lines = body.split("\n")

            # 简单策略：每 3 个段落插一张图
            images = article.get("images", [])
            img_idx = 0
            chars_since_img = 0
            chars_per_img = max(CHARS_PER_IMAGE, len(body) // (len(images) + 1)) if images else 999999

            for line in body_lines:
                lines.append(line)
                chars_since_img += len(line)

                # 到达配图阈值，且有图未用
                if images and img_idx < len(images) and chars_since_img >= chars_per_img:
                    lines.append("")
                    lines.append(f"![配图]({Path(images[img_idx]).as_posix()})")
                    lines.append("")
                    img_idx += 1
                    chars_since_img = 0

            # 剩余图片追加到末尾
            while img_idx < len(images):
                lines.append("")
                lines.append(f"![配图]({Path(images[img_idx]).as_posix()})")
                img_idx += 1

            path.write_text("\n".join(lines), encoding="utf-8")
            return path
        except Exception as e:
            logger.warning(f"Markdown 输出失败: {e}")
            return None

    def _write_docx(self, article: Dict[str, Any], path: Path) -> Optional[str]:
        try:
            import docx
        except ImportError:
            logger.info("python-docx 未安装，跳过 Word 输出")
            return None

        try:
            doc = docx.Document()
            doc.add_heading(article["title"], level=0)

            for line in article["body"].split("\n"):
                if line.startswith("## "):
                    doc.add_heading(line[3:].strip(), level=1)
                elif line.startswith("# "):
                    doc.add_heading(line[2:].strip(), level=1)
                elif line.strip():
                    doc.add_paragraph(line)

            for img_path in article.get("images", []):
                try:
                    doc.add_picture(str(img_path), width=docx.shared.Inches(5.5))
                except Exception as e:
                    logger.warning(f"插入图片失败: {e}")

            doc.save(str(path))
            return str(path)
        except Exception as e:
            logger.warning(f"Word 输出失败: {e}")
            return None

    # ---------- 工具 ----------

    def _pick_style(self) -> str:
        import random
        return random.choice(self.WRITING_STYLES)

    def get_name(self) -> str:
        return "TechHotArticle"

    def __repr__(self):
        return "<TechHotArticle>"