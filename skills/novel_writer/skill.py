"""
novel_writer - AI 小说生成 Skill（P2 补齐版）

功能:
  - 多章节生成（LLM 逐章创作，前后上下文连贯）
  - 支持断点续写（读取已有文件，从下一章继续）
  - 中英文双语
  - 自动生成简介和完整 Markdown 输出

依赖:
  core.llm_client（已有，Agnes 优先 / Ollama 兜底）
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


LANG_CONFIG = {
    "zh": {
        "name": "中文",
        "chapter_format": "第{n}章 {title}",
        "system_prompt": (
            "你是一位优秀的小说作家，擅长创作引人入胜的{genre}小说。"
            "请用流畅的中文写作，注重人物刻画和情节推进。"
        ),
    },
    "en": {
        "name": "English",
        "chapter_format": "Chapter {n}: {title}",
        "system_prompt": (
            "You are an excellent novelist skilled in writing {genre} fiction. "
            "Write engaging prose with strong characterization and plot development."
        ),
    },
}


class NovelWriter:
    name = "novel_writer"
    version = "1.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()

    # ---------- 初始化 ----------

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/novels",
            "default_language": "zh",
            "temperature": 0.85,
            "max_tokens_per_chapter": 4096,
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        """主流程。"""
        start = time.time()

        genre = kwargs.get("genre") or "科幻"
        title = kwargs.get("title") or f"未命名小说_{datetime.now().strftime('%Y%m%d_%H%M')}"
        outline = kwargs.get("outline") or ""
        characters = kwargs.get("characters") or "主角一人"
        chapter_count = int(kwargs.get("chapter_count", 3))
        words_per_chapter = int(kwargs.get("words_per_chapter", 800))
        language = kwargs.get("language") or self.config["default_language"]

        # 断点续写
        continue_from = kwargs.get("continue_from")
        existing = None
        if continue_from:
            existing = self._load_existing_novel(continue_from)
            if not existing:
                return {"status": "error", "error": f"续写文件加载失败: {continue_from}"}
            logger.info(f"📖 续写模式: 已有 {len(existing['chapters'])} 章")
            # 续写时覆盖标题和简介
            title = existing["title"] or title
            outline = existing["outline"] or outline
            characters = existing["characters"] or characters
            genre = existing["genre"] or genre

        if not outline:
            return {"status": "error", "error": "outline 不能为空"}

        lang_cfg = LANG_CONFIG.get(language, LANG_CONFIG["zh"])

        # ---- 检查 LLM 可用 ----
        if not self._check_llm():
            return {
                "status": "error",
                "error": "LLM 后端不可用（检查 AGNES_API_KEY 或 Ollama 服务）",
            }

        try:
            chapters: List[Dict[str, str]] = []
            start_idx = 1

            if existing:
                chapters = existing["chapters"]
                start_idx = len(chapters) + 1

            end_idx = start_idx + chapter_count - 1

            logger.info(
                f"✍️ 开始创作: 《{title}》 [{genre}] "
                f"第 {start_idx} - {end_idx} 章，共 {chapter_count} 章，"
                f"每章约 {words_per_chapter} 字"
            )

            for i in range(start_idx, end_idx + 1):
                logger.info(f"  📝 生成第 {i} 章...")
                chapter = self._generate_chapter(
                    genre=genre,
                    title=title,
                    outline=outline,
                    characters=characters,
                    chapter_index=i,
                    total_chapters=end_idx,
                    words_per_chapter=words_per_chapter,
                    lang_cfg=lang_cfg,
                    prev_chapters=chapters[-2:] if chapters else [],
                )
                if not chapter:
                    logger.warning(f"  ⚠️ 第 {i} 章生成失败，跳过")
                    continue
                chapters.append(chapter)
                logger.info(
                    f"  ✅ 第 {i} 章完成: {chapter['title']} "
                    f"({len(chapter['content'])} 字)"
                )

            if not chapters:
                return {"status": "error", "error": "所有章节都生成失败"}

            # 简介
            logger.info("  📄 生成小说简介...")
            summary = self._generate_summary(
                genre=genre,
                title=title,
                outline=outline,
                characters=characters,
                chapters=chapters,
                lang_cfg=lang_cfg,
            )

            # 保存
            filepath = self._save_novel(
                {
                    "title": title,
                    "genre": genre,
                    "outline": outline,
                    "characters": characters,
                    "language": language,
                    "summary": summary,
                    "chapters": chapters,
                },
                is_continue=bool(existing),
                original_path=continue_from if existing else None,
            )

            elapsed = f"{time.time() - start:.1f}s"
            logger.info(f"✅ 小说生成完成: {filepath} ({len(chapters)} 章, {elapsed})")

            return {
                "status": "success",
                "result": {
                    "novel_file": filepath,
                    "title": title,
                    "genre": genre,
                    "chapter_count": len(chapters),
                    "total_words": sum(len(c["content"]) for c in chapters),
                    "summary": summary,
                    "elapsed": elapsed,
                },
                "metadata": {"skill": self.name, "version": self.version},
            }

        except Exception as e:
            logger.exception("小说生成失败")
            return {"status": "error", "error": str(e)}

    # ---------- LLM ----------

    def _check_llm(self) -> bool:
        """轻量探测：至少一个 LLM 后端可用。"""
        try:
            from core.llm_client import get_default_client
            llm = get_default_client(timeout=10)
            r = llm.generate("Hi", max_tokens=5)
            return bool(r)
        except Exception as e:
            logger.warning(f"LLM 探测失败: {e}")
            return False

    def _call_llm(self, prompt: str, system: Optional[str] = None) -> str:
        from core.llm_client import get_default_client
        llm = get_default_client(
            temperature=self.config["temperature"],
            max_tokens=self.config["max_tokens_per_chapter"],
        )
        return (llm.generate(prompt, system=system) or "").strip()

    # ---------- 章节生成 ----------

    def _generate_chapter(
        self,
        genre: str,
        title: str,
        outline: str,
        characters: str,
        chapter_index: int,
        total_chapters: int,
        words_per_chapter: int,
        lang_cfg: Dict,
        prev_chapters: List[Dict[str, str]],
    ) -> Optional[Dict[str, str]]:
        """生成单章。"""
        # 上一章上下文（只取最后 500 字，节省 token）
        prev_context = ""
        if prev_chapters:
            prev = prev_chapters[-1]
            prev_context = (
                f"\n【上一章结尾参考（务必保持连贯）】\n"
                f"{prev['content'][-500:]}\n"
            )

        system = lang_cfg["system_prompt"].format(genre=genre)

        prompt = f"""【小说基本信息】
标题：《{title}》
题材：{genre}
主要人物：{characters}
故事大纲：{outline}
{prev_context}
【任务】
请创作第 {chapter_index} 章（共 {total_chapters} 章），要求：
1. 字数约 {words_per_chapter} 字
2. 开篇用小标题（3-6 个字，概括本章核心事件）
3. 围绕大纲推进剧情，注意前后呼应
4. 人物对话生动，场景描写细腻
5. 结尾留悬念或伏笔（最后一章除外）

【输出格式（严格遵守）】
标题：<小标题>
正文：
<正文内容>"""

        try:
            raw = self._call_llm(prompt, system=system)
            if not raw:
                return None
            return self._parse_chapter(raw, chapter_index, lang_cfg)
        except Exception as e:
            logger.warning(f"第 {chapter_index} 章生成异常: {e}")
            return None

    def _parse_chapter(
        self,
        raw: str,
        index: int,
        lang_cfg: Dict,
    ) -> Dict[str, str]:
        """从 LLM 输出解析出 {title, content}。"""
        # 尝试匹配「标题：xxx」和「正文：xxx」
        m = re.search(r"标题[:：]\s*(.+?)\n", raw)
        chapter_title = m.group(1).strip() if m else f"未命名"

        m2 = re.search(r"正文[:：]\s*\n?(.+)", raw, re.DOTALL)
        content = m2.group(1).strip() if m2 else raw.strip()

        return {
            "index": index,
            "title": chapter_title,
            "content": content,
        }

    # ---------- 简介 ----------

    def _generate_summary(
        self,
        genre: str,
        title: str,
        outline: str,
        characters: str,
        chapters: List[Dict[str, str]],
        lang_cfg: Dict,
    ) -> str:
        """生成小说简介。"""
        try:
            chapter_titles = "、".join(c["title"] for c in chapters)
            prompt = f"""请为这部小说写一段简介（150-200 字）。

标题：《{title}》
题材：{genre}
主要人物：{characters}
故事大纲：{outline}
章节标题：{chapter_titles}

要求：
1. 抓住故事核心冲突和亮点
2. 吸引读者但不剧透结局
3. 只用中文，不分点，直接输出简介正文"""

            system = lang_cfg["system_prompt"].format(genre=genre)
            summary = self._call_llm(prompt, system=system)
            return summary or f"《{title}》是一部 {genre} 题材的小说。"
        except Exception as e:
            logger.warning(f"简介生成失败: {e}")
            return f"《{title}》是一部 {genre} 题材的小说。"

    # ---------- 加载 / 保存 ----------

    def _load_existing_novel(self, filepath: str) -> Optional[Dict[str, Any]]:
        """读取已有小说文件（用于续写）。"""
        p = Path(filepath)
        if not p.exists():
            return None
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"读取文件失败: {e}")
            return None

        # 解析元信息（YAML-like）
        meta: Dict[str, str] = {}
        for key in ("title", "genre", "outline", "characters", "language"):
            m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE)
            if m:
                meta[key] = m.group(1).strip()

        # 解析章节
        chapters: List[Dict[str, str]] = []
        for m in re.finditer(
            r"^## (第\s*\d+\s*章.+?|Chapter\s+\d+.+?)$\n\n(.+?)(?=^## |\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        ):
            header = m.group(1).strip()
            content = m.group(2).strip()
            # 提取标题部分（"第1章 xxx" → "xxx"）
            tm = re.search(r"章\s*(.+)$", header)
            chapter_title = tm.group(1).strip() if tm else header
            chapters.append({
                "index": len(chapters) + 1,
                "title": chapter_title,
                "content": content,
            })

        return {
            "title": meta.get("title", ""),
            "genre": meta.get("genre", ""),
            "outline": meta.get("outline", ""),
            "characters": meta.get("characters", ""),
            "language": meta.get("language", "zh"),
            "summary": "",
            "chapters": chapters,
        }

    def _save_novel(
        self,
        data: Dict[str, Any],
        is_continue: bool = False,
        original_path: Optional[str] = None,
    ) -> str:
        """保存为 Markdown。"""
        if is_continue and original_path:
            filepath = Path(original_path)
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r"[^\w\u4e00-\u9fff\-_]", "_", data["title"][:30])
            filepath = Path(self.config["output_dir"]) / f"{ts}_{safe_title}.md"

        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines: List[str] = [
            f"# {data['title']}",
            "",
            f"title: {data['title']}",
            f"genre: {data['genre']}",
            f"outline: {data['outline']}",
            f"characters: {data['characters']}",
            f"language: {data['language']}",
            f"generated_at: {datetime.now().isoformat()}",
            f"chapter_count: {len(data['chapters'])}",
            "",
        ]

        if data.get("summary"):
            lines.extend(["## 简介", "", data["summary"], ""])

        for i, ch in enumerate(data["chapters"], 1):
            chapter_format = LANG_CONFIG.get(
                data["language"], LANG_CONFIG["zh"]
            )["chapter_format"]
            lines.append(
                "## " + chapter_format.format(n=i, title=ch["title"])
            )
            lines.append("")
            lines.append(ch["content"])
            lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        return str(filepath)

    # ---------- 展示 ----------

    def get_name(self) -> str:
        return "NovelWriter"

    def __repr__(self):
        return "<NovelWriter>"