# core/skill_routes.py
"""技能触发词路由表。新增技能只需在这里加一行，不用改 analyzer。"""

SKILL_ROUTES = {
    # ---- 内容生成 ----
    "news_aggregator": {
        "keywords": ["新闻", "今日新闻", "新闻简报", "news", "简报"],
        "system_hint": "📰 正在抓取新闻...",
    },
    "novel_writer": {
        "keywords": ["写小说", "生成小说", "小说生成", "连载"],
        "system_hint": "✍️ 开始创作小说...",
    },
    "tech_hot_article": {
        "keywords": ["技术文章", "技术热点", "写篇技术", "技术博客"],
        "system_hint": "📝 生成技术文章...",
    },
    "music_generator": {
        "keywords": ["生成音乐", "作曲", "编曲", "music", "配乐"],
        "system_hint": "🎵 音乐生成中...",
    },
    "voice_assistant": {
        "keywords": ["语音合成", "tts", "朗读", "转语音", "念一下"],
        "system_hint": "🔊 语音合成中...",
    },

    # ---- 图片后处理 ----
    "image_curator": {
        "keywords": ["图片鉴赏", "鉴赏", "图片点评", "写图集"],
        "system_hint": "🖼️ 图片鉴赏中...",
    },
    "wechat_formatter": {
        "keywords": ["排版", "微信排版", "公众号排版"],
        "system_hint": "🎨 排版中...",
    },

    # ---- 媒体播放 ----
    "video_player": {
        "keywords": ["播放视频", "看视频", "放视频", "视频播放"],
        "system_hint": "▶️ 打开视频播放器...",
    },
    "music_player": {
        "keywords": ["播放音乐", "听歌", "放歌", "音乐播放"],
        "system_hint": "🎧 播放音乐...",
    },
    "radio_player": {
        "keywords": ["听广播", "收音机", "电台", "广播"],
        "system_hint": "📻 打开电台...",
    },

    # ---- 搜索 / 分发 ----
    "search_engine": {
        "keywords": ["搜索", "搜图", "搜视频", "查一下", "帮我搜"],
        "system_hint": "🔍 搜索中...",
    },
    "social_auto_upload": {
        "keywords": ["分发", "上传到", "发布到", "一键发布"],
        "system_hint": "📤 分发中...",
    },
    "daily_pipeline": {
        "keywords": ["每日任务", "每日生图", "今天的图", "daily"],
        "system_hint": "📅 执行每日管线...",
    },
    "video_sniffer": {
        "keywords": ["嗅探", "嗅探视频", "抓视频", "解析视频"],
        "system_hint": "🎯 嗅探中...",
    },
}


def match_skill(text: str) -> tuple[str, str] | None:
    """返回 (skill_name, matched_keyword) 或 None"""
    tl = text.lower()
    for name, cfg in SKILL_ROUTES.items():
        for kw in cfg["keywords"]:
            if kw.lower() in tl:
                return name, kw
    return None