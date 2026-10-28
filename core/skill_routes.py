# core/skill_routes.py
"""技能触发词路由表 + skill 注册信息。

一条记录同时描述：
  - keywords:        用户输入的触发词
  - system_hint:     命中后的提示语
  - module / class:  skill 实现（SkillHandler 直接用，不用再维护 SKILL_MAP）
  - config_overrides: 覆盖 execute() 的部分参数
  - kwargs_builder:  可选，把 intent → execute kwargs 的映射（缺省用通用映射）

新增 skill 只需在本文件加一条。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Callable, Union


SKILL_ROUTES: Dict[str, Dict[str, Any]] = {

    # ============ GitHub 每日 ============
    "github_repo_daily": {
        "keywords": [
            "github推荐", "github仓库", "github项目", "github trending",
            "每日仓库", "推荐仓库", "推荐项目", "仓库推荐", "项目推荐",
            "github 日报", "github日报", "开源项目推荐",
        ],
        "system_hint": "🐙 正在抓取今日 GitHub 推荐仓库...",
        "module": "skills",
        "class": "GitHubRepoDaily",
        "config_overrides": {
            "wechat_publish": True,
            "wechat_theme": "newspaper",
        },
    },

    # ============ 内容生成 ============
    "news_aggregator": {
        "keywords": ["今日新闻", "新闻简报", "抓新闻", "看新闻", "新闻聚合"],
        "system_hint": "📰 正在抓取新闻...",
        "module": "skills",
        "class": "NewsAggregator",
        "kwargs_builder": lambda intent: {
            "category": "tech",
            "top_n": 15,
        },
    },
    "novel_writer": {
        "keywords": ["写小说", "生成小说", "小说生成", "写一部小说", "连载小说"],
        "system_hint": "✍️ 开始创作小说...",
        "module": "skills.novel_writer.skill",
        "class": "NovelWriterOllama",
        "kwargs_builder": lambda intent: {
            "genre": "科幻",
            "title": (intent.get("prompt") or intent.get("original_text", ""))[:20],
            "outline": intent.get("prompt") or intent.get("original_text", ""),
            "characters": "主角",
            "chapter_count": 1,
            "words_per_chapter": 500,
        },
    },
    "tech_hot_article": {
        "keywords": ["技术文章", "技术热点", "写篇技术", "技术博客", "技术日报"],
        "system_hint": "📝 生成技术文章...",
        "module": "skills.tech_hot_article.skill",
        "class": "TechHotArticle",
        "kwargs_builder": lambda intent: {"style": "专业分析型", "words": 1500},
    },
    "music_generator": {
        "keywords": ["生成音乐", "作曲", "编曲", "生成一首歌", "配乐"],
        "system_hint": "🎵 音乐生成中...",
        "module": "skills.music_generator.skill",
        "class": "MusicMaestro",
        "kwargs_builder": lambda intent: {
            "topic": intent.get("prompt") or intent.get("original_text", ""),
            "emotion": "peaceful",
            "duration": 30,
            "language": "zh",
        },
    },
    "voice_assistant": {
        "keywords": ["语音合成", "转语音", "朗读一下", "念一下", "tts"],
        "system_hint": "🔊 语音合成中...",
        "module": "skills.voice_assistant.skill",
        "class": "VoiceAssistant",
        "kwargs_builder": lambda intent: {
            "action": "tts",
            "text": intent.get("prompt") or intent.get("original_text", ""),
            "voice": "zh-CN-XiaoxiaoNeural",
        },
    },

    # ============ 图片后处理 ============
    "image_curator": {
        "keywords": ["图片鉴赏", "鉴赏图片", "图片点评", "写图集", "图片配文"],
        "system_hint": "🖼️ 图片鉴赏中...",
        "module": "skills",
        "class": "ImageCurator",
        "kwargs_builder": lambda intent: {"directory": "output"},
    },
    "wechat_formatter": {
        "keywords": ["微信排版", "公众号排版", "排版文章"],
        "system_hint": "🎨 排版中...",
        "module": "skills",
        "class": "WechatFormatter",
        # 需要 md_path，缺省时返回空 → 触发"需要用户另外指定"提示
        "kwargs_builder": lambda intent: {},
    },

    # ============ 媒体播放 ============
    "video_player": {
        "keywords": ["播放视频", "看视频", "放视频", "打开视频"],
        "system_hint": "▶️ 搜索视频中...",
        "module": "skills",
        "class": "VideoPlayer",
        "kwargs_builder": lambda intent: {
            "action": "search",
            "query": intent.get("prompt") or intent.get("original_text", ""),
            "source": "all",
            "limit": 10,
        },
    },
    "music_player": {
        "keywords": ["播放音乐", "听歌", "放首歌", "打开音乐"],
        "system_hint": "🎧 搜索音乐中...",
        "module": "skills",
        "class": "MusicPlayer",
        "kwargs_builder": lambda intent: {
            "action": "search",
            "query": intent.get("prompt") or intent.get("original_text", ""),
        },
    },
    "radio_player": {
        "keywords": ["听广播", "打开收音机", "听电台", "放电台"],
        "system_hint": "📻 打开电台...",
        "module": "skills",
        "class": "RadioPlayer",
        "kwargs_builder": lambda intent: {
            "action": "play",
            "station": intent.get("prompt") or intent.get("original_text", ""),
            "category": "china",
        },
    },

    # ============ 搜索 / 分发 ============
    "search_engine": {
        "keywords": ["帮我搜图", "搜一下图片", "搜索图片", "找找图"],
        "system_hint": "🔍 搜索中...",
        "module": "skills",
        "class": "SearchEngine",
        "kwargs_builder": lambda intent: {
            "action": "search",
            "query": intent.get("prompt") or intent.get("original_text", ""),
            "kind": "images",
            "limit": 20,
        },
    },
    "social_auto_upload": {
        "keywords": ["一键分发", "上传到小红书", "上传到抖音", "发布到B站"],
        "system_hint": "📤 分发中...",
        "module": "skills",
        "class": "SocialAutoUpload",
        # 没有可用默认参数，缺省返回空 → skill 会提示用户"需要目录"
        "kwargs_builder": lambda intent: {},
    },
    "daily_pipeline": {
        "keywords": ["每日任务", "每日生图", "执行每日", "今日生图"],
        "system_hint": "📅 执行每日管线...",
        "module": "skills",
        "class": "DailyPipeline",
        "kwargs_builder": lambda intent: {},
    },
    "video_sniffer": {
        "keywords": ["嗅探视频", "抓视频", "解析视频", "下载视频"],
        "system_hint": "🎯 嗅探中...",
        "module": "skills",
        "class": "VideoSniffer",
        "kwargs_builder": lambda intent: {
            "action": "analyze",
            "url": intent.get("prompt") or intent.get("original_text", ""),
        },
    },
    # ============ 模型管理 ============
    "local_model_manage": {
        "keywords": [
            "切换模型", "换个模型", "换模型", 
            "模型列表", "有哪些模型", "列出模型", "查看模型", 
            "列出所有", "所有模型", "本地模型"  # ★ 新增
        ],
        "system_hint": "📦 正在处理模型管理...",
        "module": "handlers.model_handler",
        "class": "ModelHandler",
        "kwargs_builder": lambda intent: {
            "action": intent.get("params", {}).get("action", "list"),
            "model_id": intent.get("params", {}).get("model_id")
        },
    },    
}


def match_skill(text: str) -> Optional[tuple[str, str]]:
    """返回 (skill_name, matched_keyword) 或 None。

    匹配规则：
      1. 遍历 SKILL_ROUTES，按定义顺序
      2. 每个 skill 的 keywords 按长度倒序，避免短词命中
    """
    tl = text.lower()
    for name, cfg in SKILL_ROUTES.items():
        kws = sorted(cfg["keywords"], key=len, reverse=True)
        for kw in kws:
            if kw.lower() in tl:
                return name, kw
    return None