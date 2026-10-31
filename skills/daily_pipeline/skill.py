"""
daily_pipeline - PromptForge 每日自动化任务 Skill（P2 补齐版）

一键完成：
  选题 → 生成图 → AI 鉴赏写文章 → 追加二维码 → 微信排版 → 推送草稿箱

依赖：
  - skills.image_generator（文生图）
  - skills.image_curator（鉴赏 + 写文章）
  - skills.wechat_formatter（排版 + 推送）

所有阶段都可独立关闭；每阶段失败自动降级，不阻断后续。
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .topics import TOPICS_BY_STYLE, STYLE_KEYWORDS

logger = logging.getLogger(__name__)


class DailyPipeline:
    """每日自动化任务"""

    name = "daily_pipeline"
    version = "1.0.0"

    DEFAULT_TOPIC_COUNT = 1
    DEFAULT_IMAGE_COUNT = 6

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
            "output_dir": "./output/daily",
            "image_count": self.DEFAULT_IMAGE_COUNT,
            "qr_path": "assets/qr/公众号结束处.png",   # 不存在则跳过
            "wechat_theme": "newspaper",
            "wechat_publish": False,                    # 默认只排版不推送
            "open_browser": False,
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行每日任务。

        关键 kwargs：
          topic:            指定主题（不填则随机）
          preset:           指定预设（不填则按主题自动匹配）
          count:            图片数量（覆盖 config.image_count）
          preset_category:  指定预设分类（默认按主题猜）
          qr_path:          二维码路径（覆盖 config.qr_path）
          theme:            微信主题（覆盖 config.wechat_theme）
          publish:          是否推送到公众号（覆盖 config.wechat_publish）
          skip_curator:     只生成图，不做鉴赏
          skip_wechat:      不做排版
        """
        start = time.time()

        try:
            # ---- 参数解析 ----
            topic = kwargs.get("topic") or self._pick_topic()
            preset = kwargs.get("preset") or self._pick_preset_for_topic(topic)
            count = int(kwargs.get("count", self.config["image_count"]))
            qr_path = kwargs.get("qr_path", self.config["qr_path"])
            theme = kwargs.get("theme", self.config["wechat_theme"])
            publish = bool(kwargs.get("publish", self.config["wechat_publish"]))
            skip_curator = bool(kwargs.get("skip_curator", False))
            skip_wechat = bool(kwargs.get("skip_wechat", False))

            logger.info(f"🚀 每日任务开始")
            logger.info(f"   主题: {topic}")
            logger.info(f"   预设: {preset or '(无)'}")
            logger.info(f"   图片数: {count}")
            logger.info(f"   推送到公众号: {'是' if publish else '否'}")

            result: Dict[str, Any] = {
                "topic": topic,
                "preset": preset,
                "images": [],
                "article_md": None,
                "article_html": None,
                "wechat_preview": None,
                "wechat_article_dir": None,
                "published": False,
            }

            # ---- 阶段 1：生图 ----
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = "".join(c for c in topic[:20] if c.isalnum() or c in " _-") or "topic"
            images_dir = Path(self.config["output_dir"]) / f"{ts}_{safe_topic}"
            images_dir.mkdir(parents=True, exist_ok=True)

            images = self._generate_images(topic, preset, count, images_dir)
            if not images:
                return {"status": "error", "error": "图片生成失败，终止后续流程"}

            result["images"] = [str(p) for p in images]
            logger.info(f"✅ 图片生成: {len(images)} 张 → {images_dir}")

            if skip_curator:
                logger.info("⏭️ 跳过鉴赏（skip_curator=True）")
                result["output_dir"] = str(images_dir)
                result["elapsed"] = f"{time.time() - start:.1f}s"
                return {"status": "success", "result": result}

            # ---- 阶段 2：鉴赏 + 写文章 ----
            article = self._curate_article(images_dir, f"今日图鉴 · {topic}")
            if not article:
                logger.warning("⚠️ 鉴赏失败，但图片已生成，返回图片目录")
                result["output_dir"] = str(images_dir)
                result["elapsed"] = f"{time.time() - start:.1f}s"
                return {
                    "status": "partial",
                    "error": "鉴赏阶段失败",
                    "result": result,
                }

            result["article_md"] = article.get("article_md")
            result["article_html"] = article.get("article_html")
            logger.info(f"✅ 文章生成: {article.get('article_md')}")

            # ---- 阶段 3：追加二维码 ----
            qr = self._resolve_qr(qr_path)
            if qr and result["article_md"]:
                self._append_qr(result["article_md"], qr)
                logger.info(f"✅ 追加二维码: {qr}")

            if skip_wechat:
                logger.info("⏭️ 跳过排版（skip_wechat=True）")
                result["output_dir"] = article.get("output_dir") or str(images_dir)
                result["elapsed"] = f"{time.time() - start:.1f}s"
                return {"status": "success", "result": result}

            # ---- 阶段 4：微信排版 ----
            wechat = self._format_wechat(result["article_md"], theme)
            if wechat:
                result["wechat_preview"] = wechat.get("preview_path")
                result["wechat_article_dir"] = wechat.get("article_dir")
                logger.info(f"✅ 微信排版: {wechat.get('preview_path')}")

            # ---- 阶段 5：推送（可选）----
            if publish and result["wechat_article_dir"]:
                ok = self._publish_wechat(result["wechat_article_dir"])
                result["published"] = ok
                if ok:
                    logger.info("✅ 已推送到公众号草稿箱")
                else:
                    logger.warning("⚠️ 推送公众号失败")

            result["elapsed"] = f"{time.time() - start:.1f}s"
            logger.info(f"🎉 每日任务完成（耗时 {result['elapsed']}）")

            return {
                "status": "success",
                "result": result,
                "metadata": {"skill": self.name, "version": self.version},
            }

        except Exception as e:
            logger.exception("每日任务失败")
            return {"status": "error", "error": str(e)}

    # ---------- 阶段 1：生图 ----------

    def _generate_images(
        self,
        topic: str,
        preset: Optional[str],
        count: int,
        out_dir: Path,
    ) -> List[Path]:
        """生成 N 张图片。全部失败返回空列表。"""
        try:
            from skills.registry import get_meta, import_skill_class
            meta = get_meta("image_generator")
            if not meta:
                logger.error("image_generator skill 未注册")
                return []
            ImageGenerator = import_skill_class(meta)
            gen = ImageGenerator({
                "output_dir": str(out_dir),
                "log_level": "INFO",
            })
        except Exception as e:
            logger.error(f"image_generator 初始化失败: {e}")
            return []

        images: List[Path] = []
        # 多样性：每张图在 topic 后追加不同修饰
        variants = [
            "",
            ", cinematic lighting, epic scale",
            ", detailed close-up, dramatic shadows",
            ", wide establishing shot, atmosphere",
            ", golden hour, warm tones",
            ", moody blue hour, neon accents",
            ", minimalist composition, negative space",
        ]

        for i in range(count):
            variant = variants[i % len(variants)]
            full_prompt = topic + variant

            # 有预设：先用 preset_bridge 解析
            if preset:
                try:
                    from preset_bridge import preset_bridge
                    if preset_bridge.is_ready():
                        full_prompt = preset_bridge.build_prompt(
                            preset=preset,
                            subject_override=topic,
                            max_tokens=77,
                        )
                        if variant:
                            full_prompt = f"{full_prompt}{variant}"
                except Exception as e:
                    logger.warning(f"预设 {preset} 解析失败（降级为原始 topic）: {e}")

            logger.info(f"  🎨 [{i+1}/{count}] {full_prompt[:60]}...")
            try:
                r = gen.generate(full_prompt)
                if r.get("status") == "success":
                    p = Path(r["result"]["image_path"])
                    images.append(p)
                    logger.info(f"     ✅ {p.name}")
                else:
                    logger.warning(f"     ⚠️ 失败: {r.get('error', '?')}")
            except Exception as e:
                logger.warning(f"     ⚠️ 异常: {e}")

        return images

    # ---------- 阶段 2：鉴赏 ----------

    def _curate_article(self, images_dir: Path, title: str) -> Optional[Dict[str, Any]]:
        try:
            from skills.registry import get_meta, import_skill_class
            meta = get_meta("image_curator")
            if not meta:
                logger.warning("image_curator 未注册")
                return None
            ImageCurator = import_skill_class(meta)
            curator = ImageCurator({
                "output_dir": str(images_dir),
                "log_level": "INFO",
                "write_formats": ["md", "html"],
            })
            r = curator.curate(directory=str(images_dir), title=title)
            if r.get("status") != "success":
                logger.warning(f"鉴赏失败: {r.get('error')}")
                return None
            return r.get("result")
        except Exception as e:
            logger.exception(f"curator 阶段异常: {e}")
            return None

    # ---------- 阶段 3：二维码 ----------

    def _resolve_qr(self, qr_path: str) -> Optional[Path]:
        if not qr_path:
            return None
        p = Path(qr_path)
        if not p.is_absolute():
            # 相对路径：基于项目根
            project_root = Path(__file__).resolve().parents[2]
            p = project_root / qr_path
        if not p.exists():
            logger.debug(f"二维码不存在（跳过）: {p}")
            return None
        return p

    def _append_qr(self, md_path: str, qr: Path) -> None:
        """在 markdown 末尾追加二维码。"""
        try:
            p = Path(md_path)
            text = p.read_text(encoding="utf-8")
            qr_md = f"\n\n---\n\n![关注公众号]({qr.as_posix()})\n"
            if str(qr) not in text:
                p.write_text(text.rstrip() + qr_md, encoding="utf-8")
        except Exception as e:
            logger.warning(f"追加二维码失败: {e}")

    # ---------- 阶段 4：微信排版 ----------

    def _format_wechat(self, md_path: Optional[str], theme: str) -> Optional[Dict[str, Any]]:
        if not md_path:
            return None
        try:
            from skills.registry import get_meta, import_skill_class
            meta = get_meta("wechat_formatter")
            if not meta:
                return None
            WechatFormatter = import_skill_class(meta)
            fmt = WechatFormatter({
                "log_level": "INFO",
                "output_dir": str(Path(self.config["output_dir"]) / "wechat"),
            })
            r = fmt.format(md_path=md_path, theme=theme)
            if r.get("status") != "success":
                logger.warning(f"排版失败: {r.get('error')}")
                return None
            return r.get("result")
        except Exception as e:
            logger.exception(f"wechat_formatter 阶段异常: {e}")
            return None

    # ---------- 阶段 5：推送 ----------

    def _publish_wechat(self, article_dir: str) -> bool:
        try:
            from skills.registry import get_meta, import_skill_class
            meta = get_meta("wechat_formatter")
            if not meta:
                return False
            WechatFormatter = import_skill_class(meta)
            fmt = WechatFormatter({
                "log_level": "INFO",
                "output_dir": str(Path(self.config["output_dir"]) / "wechat"),
            })
            r = fmt.publish(article_dir=article_dir, dry_run=False)
            return r.get("status") == "success"
        except Exception as e:
            logger.exception(f"publish 阶段异常: {e}")
            return False

    # ---------- 选题 ----------

    def _pick_topic(self) -> str:
        # 自定义主题（scripts/topics.txt）
        custom = self._load_custom_topics()

        # 全部主题池
        all_topics = [t for ts in TOPICS_BY_STYLE.values() for t in ts]

        # 自定义主题 ×3 权重
        if custom:
            pool = all_topics + custom * 3
        else:
            pool = all_topics

        return random.choice(pool)

    def _load_custom_topics(self) -> List[str]:
        """从 scripts/topics.txt 读（每行一个主题）。"""
        try:
            project_root = Path(__file__).resolve().parents[2]
            p = project_root / "scripts" / "topics.txt"
            if not p.exists():
                return []
            return [
                line.strip() for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        except Exception:
            return []

    def _pick_preset_for_topic(self, topic: str) -> Optional[str]:
        """按主题关键词猜风格 → 从 presets_meta 里挑预设。"""
        style = self._guess_style(topic)
        if not style:
            return None

        try:
            from presets_meta import get_presets_by_category
            by_cat = get_presets_by_category()
            presets = by_cat.get(style)
            if presets:
                return random.choice(presets)
        except Exception:
            pass
        return None

    def _guess_style(self, topic: str) -> Optional[str]:
        for style, keywords in STYLE_KEYWORDS.items():
            for kw in keywords:
                if kw in topic:
                    return style
        return None

    # ---------- 展示 ----------

    def get_name(self) -> str:
        return "DailyPipeline"

    def __repr__(self):
        return "<DailyPipeline>"