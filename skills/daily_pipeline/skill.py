#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
daily_pipeline - PromptForge 每日自动化任务 Skill

一键完成：生成图片 → AI 鉴赏写文章 → 追加二维码 → 微信排版 → 推送草稿箱

作为 Skill 使用：
    from skills.daily_pipeline import DailyPipeline
    pipe = DailyPipeline({"output_root": "output/daily"})
    result = pipe.execute(topic="月下松林", count=6)
    print(result["result"]["article_dir"])

作为 CLI 使用：
    python -m skills.daily_pipeline.skill --topic "月下松林" --count 6
    # 或走 scripts/daily_task.py（薄包装，功能等价）
"""

from __future__ import annotations

import logging
import random
import sys
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# 主题库：按风格分类
# ============================================================

TOPICS_BY_STYLE: Dict[str, List[str]] = {

    "mecha": [
        "赛博朋克机甲少女", "未来都市夜景", "机械与花的结合", "赛博武士",
        "机械天使", "科幻太空舱内部", "巨型机甲战士", "无人机与霓虹城市",
        "赛博朋克街头", "机甲少女立绘", "未来科技实验室", "蒸汽朋克机械生物",
        "机械昆虫微观", "钢铁巨兽", "人形机器人肖像", "量子计算机内部",
        "未来战士肖像", "太空战舰舰桥", "机械之心", "赛博朋克雨夜",
    ],

    "chinese": [
        "水墨山水意境", "古风仕女图", "东方龙纹图腾", "竹韵与清风",
        "梅花傲雪", "水墨荷花", "工笔牡丹", "书法与印章",
        "国风建筑", "仙鹤祥云", "水墨猫戏", "山水长卷",
        "月下松林", "古寺钟声", "书房清供", "清明上河图意象",
        "青绿山水", "江南水乡", "茶室一隅", "宋韵雅集",
    ],

    "portrait": [
        "优雅人像摄影", "都市女孩日常", "海滩度假写真", "职场精英肖像",
        "画廊里的女孩", "清纯少女特写", "夏日晚风人像", "秋日街拍",
        "冬日暖阳肖像", "雨天窗边女孩", "咖啡馆里的她", "樱花树下的少女",
        "职业女性写真", "时尚街头人像", "黑白人像摄影", "海边少女剪影",
        "图书馆里的安静时光", "窗前阅读的下午", "复古胶片人像", "星夜下的她",
    ],

    "anime": [
        "日系动漫少女", "秋日动漫人像", "二次元校园少女", "魔法少女变身",
        "赛博朋克动漫角色", "机娘立绘", "动漫手办展示", "动漫婚礼场景",
        "夏日祭典动漫", "烟花下的少女", "动漫风景插图", "日常系动漫生活",
        "少女与猫", "和风动漫少女", "动漫男孩肖像",
    ],

    "landscape": [
        "治愈系风景", "星空银河下的湖泊", "晨雾弥漫的山谷", "夕阳下的海面",
        "雪山日出", "秋日枫林", "春日樱花小径", "夏日草原",
        "冬日雪村", "雨后的森林", "沙漠日落", "瀑布与彩虹",
        "悬崖上的灯塔", "云海翻涌", "极光之夜", "薰衣草花田",
        "梯田晨雾", "湖畔黄昏", "秘境温泉", "无人海岸线",
    ],

    "animal": [
        "雪豹特写", "仙鹤独立", "锦鲤戏水", "森林小鹿",
        "草原奔马", "北极狐", "猫科动物剪影", "凤凰涅槃",
        "东方龙", "凤凰与花", "猫咪午睡", "柴犬日常",
        "小鸟与枝头", "蜜蜂采蜜", "蝴蝶与花",
    ],

    "design": [
        "珠宝设计", "腕表机械美学", "极简家具", "工业设计概念",
        "未来交通工具", "飞行器设计", "智能家居概念", "首饰盒静物",
        "古典乐器特写", "书籍封面设计", "徽章与图腾", "字体设计",
        "包装设计概念", "家具草图",
    ],
}

ALL_TOPICS = [t for topics in TOPICS_BY_STYLE.values() for t in topics]


# ============================================================
# 变体模板
# ============================================================

VARIANT_TEMPLATES = [
    "{topic}, wide cinematic establishing shot, epic scale",
    "{topic}, close-up detail shot, shallow depth of field",
    "{topic}, low angle dramatic perspective, imposing presence",
    "{topic}, aerial bird's-eye view, sweeping panorama",
    "{topic}, symmetrical centered composition, elegant balance",
    "{topic}, dynamic diagonal composition, sense of motion",
    "{topic}, golden hour warm tones, romantic atmosphere",
    "{topic}, blue hour cool tones, moody cinematic lighting",
    "{topic}, minimalist composition, generous negative space",
    "{topic}, rule of thirds framing, natural candid feel",
    "{topic}, three-quarter view, soft diffused studio lighting",
    "{topic}, striking silhouette against bright backdrop",
    "{topic}, macro detail focus, extremely fine texture",
    "{topic}, environmental portrait, subject in context",
    "{topic}, back view, mysterious and contemplative",
    "{topic}, top-down flat lay composition, artistic arrangement",
]


# ============================================================
# 预设分类 ↔ 主题风格映射
# ============================================================

PRESET_CAT_TO_STYLES: Dict[str, List[str]] = {
    "机甲": ["mecha"],
    "国风": ["chinese"],
    "人像": ["portrait"],
    "动漫": ["anime"],
    "素描": ["portrait", "animal", "mecha"],
    "动物": ["animal"],
    "设计": ["design"],
    "风景": ["landscape"],
}

STYLE_TO_PRESET_CATS: Dict[str, List[str]] = {
    "mecha":     ["机甲"],
    "chinese":   ["国风"],
    "portrait":  ["人像", "素描"],
    "anime":     ["动漫"],
    "animal":    ["动物", "素描"],
    "design":    ["设计"],
    "landscape": ["风景"],
}

STYLE_KEYWORDS: Dict[str, List[str]] = {
    "mecha": ["机甲", "赛博", "机器人", "机械", "未来", "太空", "战舰", "科幻",
              "量子", "钢铁", "人形机", "无人机", "霓虹", "蒸汽朋克"],
    "chinese": ["水墨", "古风", "国风", "东方", "书法", "宋韵", "江南", "工笔",
                "祥云", "竹", "梅", "松", "茶", "月下", "清明", "青绿", "印章"],
    "anime": ["动漫", "二次元", "日系", "手办", "校园", "魔法少女", "机娘", "和风", "祭典"],
    "animal": ["猫", "狗", "鸟", "龙", "凤", "鹤", "鹿", "马", "虎", "狮",
               "鲸", "蝶", "豹", "狐", "兔", "熊", "鱼", "锦鲤", "柴犬", "蜜蜂", "蝴蝶"],
    "design": ["珠宝", "腕表", "家具", "设计", "包装", "字体", "徽章",
               "飞行器", "乐器", "书籍", "首饰", "智能家居", "工业"],
    "landscape": ["风景", "山", "湖", "海", "星", "雪", "日落", "日出", "森",
                  "草原", "沙漠", "梯田", "瀑布", "温泉", "海岸", "极光", "云海",
                  "灯塔", "花田", "枫", "樱花"],
    "portrait": ["人像", "少女", "女孩", "男孩", "美女", "写真", "肖像",
                 "职场", "她", "摄影", "街拍", "咖啡馆", "图书馆"],
}

VALID_PRESET_CATEGORIES = ["机甲", "国风", "人像", "动漫", "素描", "动物", "设计", "风景"]


# ============================================================
# 核心类
# ============================================================

class DailyPipeline:
    """每日自动化任务（生成 → 鉴赏 → 排版 → 发布）"""

    name = "daily_pipeline"
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
            "output_root": "output/daily",
            "qr": "assets/qr/公众号结束处.png",
            "theme": "newspaper",
            "count": 6,
            "engine": "agnes",
            "topics_file": "scripts/topics.txt",   # 跟 daily_task.py 放一起
            "auto_publish": True,
            "auto_open": False,
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)

    # ---------- 公开 API ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行每日任务。

        支持三种发布模式（article_type 控制）：
          - "news"     只发文章（生成 → 鉴赏 → 排版 → 推送）
          - "newspic"  只发贴图（生成 → 直接推送图片消息，跳过鉴赏/排版）
          - "both"     文章 + 贴图，两条流程共用同一批图

        kwargs:
          topic           str   主题（默认随机）
          preset          str   预设（默认随机）
          preset_category str   限定预设分类
          vary_preset     bool  每张图换预设
          count           int   张数
          theme           str   排版主题
          output_root     str   生图输出根目录
          qr              str   文末二维码路径
          publish         bool  是否推送草稿箱（默认取 config["auto_publish"]）
          open_browser    bool  完成后打开浏览器（默认取 config["auto_open"]）
          skip_curate     bool  跳过鉴赏/文章流程（仅对 news / both 生效）
          skip_generate   bool  跳过生图（需同时提供 image_dir）
          image_dir       str   已有图片目录（skip_generate=True 时必填）
          article_type    str   发布类型："news"（默认）| "newspic" | "both"

        返回:
          {
            "status": "success" | "error",
            "result": {
              # ---- 主题 / 素材 ----
              "topic":             str,          # 实际使用的主题
              "preset":            str | None,   # 实际使用的预设
              "image_dir":         str,          # 图片目录（文章与贴图共用）
              "title":             str | None,   # 仅 newspic 模式：贴图标题

              # ---- 文章流程产物（news / both，且未 skip_curate 时才非空）----
              "md_path":           str | None,   # 鉴赏产出的 Markdown
              "article_dir":       str | None,   # 排版输出目录
              "preview_path":      str | None,   # preview.html
              "clipboard_path":    str | None,   # clipboard.html

              # ---- 推送状态（按渠道拆分）----
              "news_published":    bool | None,  # None = 该渠道未执行
              "news_error":        str  | None,  # 该渠道失败原因 / 提示
              "newspic_published": bool | None,
              "newspic_error":     str  | None,

              # ---- 兼容旧字段 ----
              "published":         bool,         # 任一渠道成功即 True
              "publish_error":     str  | None,  # 全部失败时的原因摘要
            },
            "metadata": {
              "skill":   str,   # "daily_pipeline"
              "version": str,
              "elapsed": str,   # 形如 "0:00:12.345678"
            },
            "error": str (仅 status="error" 时),
          }

        示例:
            # 每天文章 + 贴图，共用一批图
            pipe.execute(topic="月下松林", count=6, article_type="both")

            # 复用昨天生成好的图，只发贴图
            pipe.execute(article_type="newspic",
                         skip_generate=True,
                         image_dir="output/daily/20250621_093000_images")
        """
        start_time = datetime.now()

        try:
            # ---- 参数归一化 ----
            topic = kwargs.get("topic") or None
            preset = kwargs.get("preset") or None
            preset_category = kwargs.get("preset_category") or None
            vary_preset = bool(kwargs.get("vary_preset", False))
            count = int(kwargs.get("count", self.config["count"]))
            theme = kwargs.get("theme", self.config["theme"])
            output_root = kwargs.get("output_root", self.config["output_root"])
            qr = kwargs.get("qr", self.config["qr"])
            publish = kwargs.get("publish", self.config["auto_publish"])
            open_browser = kwargs.get("open_browser", self.config["auto_open"])
            skip_curate = bool(kwargs.get("skip_curate", False))
            skip_generate = bool(kwargs.get("skip_generate", False))
            image_dir_arg = kwargs.get("image_dir")
            article_type = kwargs.get("article_type", "news")

            if article_type not in ("news", "newspic", "both"):
                return self._err(f"article_type 无效: {article_type}")

            # ---- 选主题 + 预设 ----
            topic, preset = self.pick_topic_and_preset(
                topic=topic, preset=preset, preset_category=preset_category,
            )
            logger.info(f"🎯 主题: {topic}")
            logger.info(f"🎨 预设: {preset or '（无）'}")
            logger.info(f"📦 发布类型: {article_type}")

            date_str = start_time.strftime("%Y-%m-%d")
            today_ts = start_time.strftime("%Y%m%d_%H%M%S")

            # ---- 确定图片目录 ----
            if skip_generate:
                if not image_dir_arg:
                    return self._err("skip_generate=True 必须提供 image_dir")
                image_dir = Path(image_dir_arg)
                if not image_dir.is_absolute():
                    image_dir = (PROJECT_ROOT / image_dir).resolve()
                if not image_dir.exists():
                    return self._err(f"图片目录不存在: {image_dir}")
            else:
                image_dir = (PROJECT_ROOT / output_root / f"{today_ts}_images").resolve()
                image_dir.mkdir(parents=True, exist_ok=True)

            result: Dict[str, Any] = {
                "topic": topic,
                "preset": preset,
                "image_dir": str(image_dir),
                "md_path": None,
                "article_dir": None,
                "preview_path": None,
                "clipboard_path": None,
                # 分渠道状态（推荐用法）
                "news_published": None,
                "news_error": None,
                "newspic_published": None,
                "newspic_error": None,
                # 兼容旧字段：任一渠道成功即 True
                "published": False,
                "publish_error": None,
            }

            # ---- 步骤 1：生图（文章 + 贴图共享这一批图）----
            if not skip_generate:
                paths = self.generate_images(topic, count, image_dir, preset, vary_preset)
                if not paths:
                    return self._err("未生成任何图片")
                logger.info(f"✅ 生成 {len(paths)} 张 → {image_dir}")

            # 收集图片列表（贴图会用到，也包括 skip_generate 时传入的现成目录）
            images: List[Path] = sorted([
                p for p in image_dir.iterdir()
                if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            ])

            need_news = article_type in ("news", "both")
            need_newspic = article_type in ("newspic", "both")

            # ============================================================
            # 步骤 2：文章流程（news / both）
            # ============================================================
            if need_news:
                if skip_curate:
                    result["news_error"] = "skip_curate=True，跳过文章流程"
                    logger.info("⏭️  skip_curate=True，跳过文章流程")
                else:
                    title = f"{topic} {date_str}"
                    md_path = self.curate_article(image_dir, title)
                    if not md_path:
                        result["news_error"] = "鉴赏/文章生成失败"
                        logger.error("❌ 鉴赏/文章生成失败")
                        if article_type == "news":
                            return self._err("鉴赏/文章生成失败")
                    else:
                        result["md_path"] = str(md_path)

                        qr_path = (PROJECT_ROOT / qr).resolve()
                        if not qr_path.exists():
                            logger.warning(f"⚠️ 二维码不存在，跳过: {qr_path}")
                            qr_path = None

                        article_dir = self.format_wechat(md_path, theme, qr_path)
                        if not article_dir:
                            result["news_error"] = "排版失败"
                            if article_type == "news":
                                return self._err("排版失败")
                        else:
                            result["article_dir"] = str(article_dir)
                            result["preview_path"] = str(article_dir / "preview.html")
                            result["clipboard_path"] = str(article_dir / "clipboard.html")

                            if publish:
                                pub = self.publish_wechat(article_dir)
                                result["news_published"] = pub.get("published", False)
                                result["news_error"] = pub.get("error")
                            else:
                                result["news_published"] = False
                                result["news_error"] = "未启用推送"

            # ============================================================
            # 步骤 3：贴图流程（newspic / both），复用同一批图
            # ============================================================
            if need_newspic:
                if not images:
                    result["newspic_error"] = "没有可用的图片"
                    logger.error("❌ 贴图模式未找到任何图片")
                    if article_type == "newspic":
                        return self._err("贴图模式未找到任何图片")
                else:
                    np_title = topic[:20]
                    logger.info(f"🖼️  贴图模式，共 {len(images)} 张 → 标题「{np_title}」")
                    if publish:
                        pub_np = self.publish_wechat_newspic(
                            article_dir=image_dir,   # 签名保留，实际未使用
                            images=images,
                            title=np_title,
                            content=f"{topic}\n\n每日 AI 生图 · {date_str}",
                        )
                        result["newspic_published"] = pub_np.get("published", False)
                        result["newspic_error"] = pub_np.get("error")
                    else:
                        result["newspic_published"] = False
                        result["newspic_error"] = "未启用推送"

            # ---- 兼容字段 ----
            result["published"] = bool(
                (result["news_published"] is True) or (result["newspic_published"] is True)
            )
            if not result["published"]:
                result["publish_error"] = (
                    result["news_error"] or result["newspic_error"] or "未启用推送"
                )

            # ---- 打开浏览器 ----
            if open_browser and result["article_dir"]:
                preview = (Path(result["article_dir"]) / "preview.html").resolve()
                if preview.exists():
                    webbrowser.open(preview.as_uri())

            return {
                "status": "success",
                "result": result,
                "metadata": {
                    "skill": self.name,
                    "version": self.version,
                    "elapsed": str(datetime.now() - start_time),
                },
            }

        except Exception as e:
            logger.error(f"执行失败: {e}")
            traceback.print_exc()
            return self._err(str(e))
            
    # ---------- 子步骤 ----------

    def generate_images(
        self,
        topic: str,
        count: int,
        out_dir: Path,
        preset: Optional[str],
        vary_preset: bool = False,
    ) -> List[Path]:
        """生成图片 + 统一重命名"""
        from skills.image_generator import ImageGenerator

        out_dir = out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        gen = ImageGenerator({
            "engine": self.config["engine"],
            "output_dir": str(out_dir),
        })

        # 预设构造器
        prompt_builder = None
        if preset:
            try:
                from preset_bridge import preset_bridge
                if preset_bridge.is_ready():
                    prompt_builder = preset_bridge
                    logger.info(f"🎯 使用预设: {preset}")
            except Exception as e:
                logger.warning(f"⚠️ 预设加载失败: {e}")

        # 收集同分类的其他预设
        preset_pool: List[str] = []
        if vary_preset and preset:
            try:
                from presets_meta import PRESET_META
                meta = PRESET_META.get(preset)
                if meta and len(meta) >= 2:
                    cat = meta[1]
                    preset_pool = [
                        n for n, m in PRESET_META.items()
                        if isinstance(m, (list, tuple)) and len(m) >= 2
                        and m[1] == cat and n != preset
                    ]
                    logger.info(f"🎲 vary-preset: 池中 {len(preset_pool)} 个同分类预设")
            except Exception:
                pass

        # 打乱变体
        variants = VARIANT_TEMPLATES.copy()
        random.shuffle(variants)

        raw_paths: List[Path] = []
        for i in range(count):
            variant_tpl = variants[i % len(variants)]
            varied_subject = variant_tpl.format(topic=topic)

            current_preset = preset
            if preset_pool and i > 0:
                current_preset = random.choice(preset_pool)

            if prompt_builder:
                prompt, _ = prompt_builder.build_prompt(
                    preset=current_preset,
                    mode="random",
                    subject_override=varied_subject,
                    max_tokens=77,
                    return_detail=True,
                )
            else:
                prompt = (
                    f"{varied_subject}, masterpiece, best quality, 8k, "
                    f"highly detailed, cinematic lighting, professional photography"
                )

            logger.info(f"🎨 [{i+1}/{count}] {variant_tpl[:55]}...")
            if preset_pool:
                logger.info(f"   预设: {current_preset}")

            try:
                r = gen.generate(prompt=prompt, width=1024, height=1024)
            except Exception as e:
                logger.warning(f"生成异常: {e}")
                continue

            if r.get("status") == "success":
                p = Path(r["result"]["image_path"]).resolve()
                raw_paths.append(p)

        # 统一重命名
        renamed: List[Path] = []
        for i, p in enumerate(raw_paths, 1):
            new_name = f"作品{i:02d}{p.suffix.lower() or '.png'}"
            new_path = p.parent / new_name
            try:
                if new_path.exists() and new_path != p:
                    new_path.unlink()
                if p != new_path:
                    p.rename(new_path)
                renamed.append(new_path)
            except Exception as e:
                logger.warning(f"重命名失败（保留原名）: {e}")
                renamed.append(p)

        return renamed

    def curate_article(self, image_dir: Path, title: str) -> Optional[Path]:
        """鉴赏 + 写文章"""
        from skills.image_curator import ImageCurator

        curator = ImageCurator({
            "generate_html": True,
            "generate_docx": True,
            "generate_pdf": True,
            "generate_clipboard": True,
        })
        r = curator.curate(str(image_dir), title=title)

        if r.get("status") != "success":
            logger.error(f"鉴赏失败: {r.get('error')}")
            return None

        md_path = Path(r["result"]["article_path"]).resolve()
        logger.info(f"✅ 文章: {md_path}")
        return md_path

    def format_wechat(
        self,
        md_path: Path,
        theme: str,
        qr_path: Optional[Path],
    ) -> Optional[Path]:
        """微信排版"""
        from skills.wechat_formatter import WechatFormatter

        fmt = WechatFormatter()
        kwargs = {"theme": theme, "open": False}
        if qr_path and qr_path.exists():
            kwargs["footer_image"] = str(qr_path)
            kwargs["footer_alt"] = "关注公众号"

        r = fmt.format(str(md_path), **kwargs)
        if r.get("status") != "success":
            logger.error(f"排版失败: {r.get('error')}")
            return None

        out_dir = Path(r["result"]["article_dir"]).resolve()
        logger.info(f"✅ 排版输出: {out_dir}")
        return out_dir

    def publish_wechat(self, article_dir: Path) -> dict:
        from skills.wechat_formatter import WechatFormatter

        fmt = WechatFormatter()
        try:
            r = fmt.publish(str(article_dir))
        except Exception as e:
            logger.error(f"❌ 推送异常: {e}")
            return {"published": False, "error": str(e)}

        if r.get("status") == "success":
            logger.info("✅ 已推送到公众号草稿箱")
            return {"published": True, "error": None}

        err = r.get("error") or "未知错误"
        logger.error(f"❌ 推送失败: {err}")
        logger.info("   排查：1) WECHAT_APP_ID/SECRET  2) IP 白名单  3) 账号是否认证")
        return {"published": False, "error": err}

    def publish_wechat_newspic(
        self,
        article_dir: Path,
        images: List[Path],
        title: str,
        content: str = "",
    ) -> dict:
        """推送贴图草稿（不经过 wechat_formatter 的 HTML 排版）"""
        try:
            # 直接调 publisher 里的 push_draft / upload_images_as_material
            import sys as _sys
            _wechat_publisher_dir = (
                PROJECT_ROOT / "skills" / "wechat_formatter" / "publisher"
            )
            if str(_wechat_publisher_dir) not in _sys.path:
                _sys.path.insert(0, str(_wechat_publisher_dir))

            # 用 importlib 动态导入，避免 package 命名冲突
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "wechat_publish_mod",
                str(_wechat_publisher_dir / "wechat_publish.py"),
            )
            wp = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(wp)

            token = wp.get_access_token()
            logger.info("✅ access_token 获取成功")

            image_media_ids = wp.upload_images_as_material(
                token, [str(p) for p in images]
            )
            if not image_media_ids:
                return {"published": False, "error": "所有图片上传为永久素材失败"}

            media_id = wp.push_draft(
                token,
                title=title[:20],
                content=content[:1000],
                article_type="newspic",
                image_media_ids=image_media_ids,
            )

            if media_id:
                logger.info(f"✅ 贴图已推送到草稿箱: {media_id}")
                return {"published": True, "error": None, "media_id": media_id}
            else:
                return {"published": False, "error": "推送贴图草稿失败"}
        except Exception as e:
            logger.error(f"❌ 贴图推送异常: {e}")
            import traceback
            traceback.print_exc()
            return {"published": False, "error": str(e)}
        
    # ---------- 主题/预设 智能匹配 ----------

    def load_presets_by_category(self) -> Dict[str, List[str]]:
        """从 presets_meta 读取所有预设，按分类聚合"""
        try:
            from presets_meta import PRESET_META, CATEGORY_ORDER
        except Exception as e:
            logger.warning(f"⚠️ 无法加载 presets_meta: {e}")
            return {}

        groups: Dict[str, List[str]] = {}
        for name, meta in PRESET_META.items():
            if not isinstance(meta, (list, tuple)) or len(meta) < 2:
                continue
            groups.setdefault(meta[1], []).append(name)

        ordered: Dict[str, List[str]] = {}
        for cat in CATEGORY_ORDER:
            if cat in groups:
                ordered[cat] = sorted(groups[cat])
        for cat, lst in groups.items():
            if cat not in ordered:
                ordered[cat] = sorted(lst)
        return ordered

    def load_custom_topics(self) -> List[str]:
        """读取 scripts/topics.txt 自定义主题池"""
        # 支持相对路径和绝对路径
        tf = Path(self.config["topics_file"])
        if not tf.is_absolute():
            tf = PROJECT_ROOT / tf

        if not tf.exists():
            return []

        try:
            lines = tf.read_text(encoding="utf-8").splitlines()
            return [
                l.strip() for l in lines
                if l.strip() and not l.strip().startswith("#")
            ]
        except Exception as e:
            logger.warning(f"⚠️ 读取 topics.txt 失败: {e}")
            return []

    def pick_topic_and_preset(
        self,
        topic: Optional[str],
        preset: Optional[str],
        preset_category: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """智能匹配主题 + 预设（详见 README）"""
        presets_by_cat = self.load_presets_by_category()

        # 都给了
        if topic and preset:
            return topic, preset

        # 只给主题
        if topic and not preset:
            style = self._guess_style(topic)
            cats = STYLE_TO_PRESET_CATS.get(style, [])
            return topic, self._pick_preset(presets_by_cat, cats)

        # 只给预设
        if preset and not topic:
            cat = self._guess_preset_cat(preset)
            styles = PRESET_CAT_TO_STYLES.get(cat or "", []) or list(TOPICS_BY_STYLE.keys())
            return self._pick_topic(styles), preset

        # 限定分类
        if preset_category:
            chosen_preset = self._pick_preset(presets_by_cat, [preset_category])
            styles = PRESET_CAT_TO_STYLES.get(preset_category, []) or list(TOPICS_BY_STYLE.keys())
            return self._pick_topic(styles), chosen_preset

        # 全随机
        all_cats = [c for c in presets_by_cat.keys() if c in PRESET_CAT_TO_STYLES]
        if not all_cats:
            return self._pick_topic(list(TOPICS_BY_STYLE.keys())), None

        cat = random.choice(all_cats)
        return (
            self._pick_topic(PRESET_CAT_TO_STYLES[cat]),
            self._pick_preset(presets_by_cat, [cat]),
        )

    def list_presets(self) -> Dict[str, List[str]]:
        """列出所有预设（按分类）"""
        return self.load_presets_by_category()

    def list_topics(self) -> Dict[str, List[str]]:
        """列出所有主题（按风格）"""
        return TOPICS_BY_STYLE

    # ---------- 内部工具 ----------

    def _pick_topic(self, styles: List[str]) -> str:
        """按风格抽取主题，自定义主题池权重 ×3"""
        pool: List[str] = []
        for s in styles:
            pool.extend(TOPICS_BY_STYLE.get(s, []))

        if not pool:
            pool = ALL_TOPICS

        # 自定义主题权重 ×3（想更极端就改成 ×5）
        custom = self.load_custom_topics()
        if custom:
            pool = pool + custom * 3

        return random.choice(pool)

    def _pick_preset(
        self, presets_by_cat: Dict[str, List[str]], categories: List[str],
    ) -> Optional[str]:
        pool: List[str] = []
        for c in categories:
            pool.extend(presets_by_cat.get(c, []))
        return random.choice(pool) if pool else None

    def _guess_style(self, topic: str) -> str:
        t = topic.lower()
        best, best_score = None, 0
        for style, kws in STYLE_KEYWORDS.items():
            score = sum(1 for k in kws if k in t)
            if score > best_score:
                best_score, best = score, style
        return best or random.choice(list(TOPICS_BY_STYLE.keys()))

    def _guess_preset_cat(self, preset: str) -> Optional[str]:
        try:
            from presets_meta import PRESET_META
            meta = PRESET_META.get(preset)
            if meta and len(meta) >= 2:
                return meta[1]
        except Exception:
            pass

        n = preset.lower()
        if any(k in n for k in ["mecha", "gundam", "eva", "transformers", "rider", "gits"]):
            return "机甲"
        if any(k in n for k in ["chinese", "ink", "cn_", "calligraphy", "hermit", "countryside"]):
            return "国风"
        if "anime" in n or "figure" in n:
            return "动漫"
        if "sketch" in n or "pencil" in n:
            return "素描"
        if any(k in n for k in ["jewelry", "watch", "bag", "nuclear"]):
            return "设计"
        if any(k in n for k in ["landscape", "healing"]):
            return "风景"
        if any(k in n for k in ["cat", "dog", "tiger", "dragon", "horse", "bird",
                                 "crane", "koi", "rabbit", "rat", "ox", "goat",
                                 "monkey", "rooster", "pig", "snake", "flower"]):
            return "动物"
        if any(k in n for k in ["portrait", "daily", "jp_", "pure_serene",
                                 "work_avatar", "beach", "nature_outdoor",
                                 "casual", "farm", "medical", "gallery"]):
            return "人像"
        return None

    @staticmethod
    def _err(msg: str) -> Dict[str, Any]:
        return {"status": "error", "error": msg}


# ============================================================
# CLI（直接运行此文件时使用）
# ============================================================

def _cli_main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="PromptForge 每日自动化任务（Skill CLI）",
    )
    parser.add_argument("--topic", "-t", default=None)
    parser.add_argument("--preset", "-p", default=None)
    parser.add_argument("--preset-category", default=None, choices=VALID_PRESET_CATEGORIES)
    parser.add_argument("--vary-preset", action="store_true")
    parser.add_argument("--count", "-c", type=int, default=6)
    parser.add_argument("--theme", default="newspaper")
    parser.add_argument("--output-root", default="output/daily")
    parser.add_argument("--qr", default="assets/qr/公众号结束处.png")
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--open", action="store_true")

    parser.add_argument("--type", choices=["news", "newspic", "both"], default="news",
                    help="发布类型：news=文章，newspic=贴图，both=都发")
                    
    parser.add_argument("--skip-curate", action="store_true")
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--image-dir", default=None)
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--list-topics", action="store_true")


                    
    args = parser.parse_args()

    pipe = DailyPipeline()

    if args.list_presets:
        cats = pipe.list_presets()
        if not cats:
            print("⚠️ 未加载到预设库")
            return 1
        total = 0
        for cat, names in cats.items():
            print(f"\n【{cat}】({len(names)} 个)")
            total += len(names)
            for i, n in enumerate(names, 1):
                print(f"  {i:3d}. {n}")
        print(f"\n共 {total} 个预设")
        return 0

    if args.list_topics:
        topics = pipe.list_topics()
        total = 0
        for style, tlist in topics.items():
            print(f"\n【{style}】({len(tlist)} 个)")
            total += len(tlist)
            for i, t in enumerate(tlist, 1):
                print(f"  {i:3d}. {t}")
        print(f"\n共 {total} 个主题")
        return 0

    result = pipe.execute(
        topic=args.topic,
        preset=args.preset,
        preset_category=args.preset_category,
        vary_preset=args.vary_preset,
        count=args.count,
        theme=args.theme,
        output_root=args.output_root,
        qr=args.qr,
        publish=not args.no_publish,
        open_browser=args.open,
        skip_curate=args.skip_curate,
        skip_generate=args.skip_generate,
        image_dir=args.image_dir,
        article_type=args.type,          # ✅ 补上这行
    )

    if result["status"] == "success":
        r = result["result"]
        print("\n" + "=" * 62)
        print("  🎉 全部完成！")
        print("=" * 62)
        print(f"📁 图片目录  : {r['image_dir']}")
        if r.get("md_path"):
            print(f"📄 文章      : {r['md_path']}")
        if r.get("article_dir"):
            print(f"🎨 排版输出  : {r['article_dir']}")
            print(f"🌐 浏览器预览: {r['preview_path']}")
            print(f"📋 富文本    : {r['clipboard_path']}")

        # 分渠道推送状态
        np_ok = r.get("news_published")
        pic_ok = r.get("newspic_published")
        if np_ok is not None:
            tag = "✅" if np_ok else "❌"
            print(f"📤 文章推送  : {tag} {r.get('news_error') or ''}")
        if pic_ok is not None:
            tag = "✅" if pic_ok else "❌"
            print(f"📤 贴图推送  : {tag} {r.get('newspic_error') or ''}")

        return 0
    else:
        print(f"\n❌ 失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(_cli_main())