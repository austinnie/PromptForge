# handlers/skill_handler.py
"""通用 Skill 处理器：按名字从 skills 包动态调用 execute()"""

import importlib
import traceback
from typing import Dict, Any

from .base import BaseHandler


# skill_name -> (模块路径, 类名)
SKILL_MAP = {
    "news_aggregator":     ("skills",                "NewsAggregator"),
    "novel_writer":        ("skills.novel_writer.skill",  "NovelWriterOllama"),
    "voice_assistant":     ("skills.voice_assistant.skill","VoiceAssistant"),
    "music_generator":     ("skills.music_generator.skill","MusicMaestro"),
    "image_curator":       ("skills",                "ImageCurator"),
    "wechat_formatter":    ("skills",                "WechatFormatter"),
    "tech_hot_article":    ("skills.tech_hot_article.skill", "TechHotArticle"),
    "video_player":        ("skills",                "VideoPlayer"),
    "music_player":        ("skills",                "MusicPlayer"),
    "radio_player":        ("skills",                "RadioPlayer"),
    "search_engine":       ("skills",                "SearchEngine"),
    "social_auto_upload":  ("skills",                "SocialAutoUpload"),
    "daily_pipeline":      ("skills",                "DailyPipeline"),
    "video_sniffer":       ("skills",                "VideoSniffer"),
    "github_repo_daily":   ("skills",                "GitHubRepoDaily"),
}


class SkillHandler(BaseHandler):
    def handle(self, intent: Dict[str, Any]) -> None:
        skill_name = intent.get("params", {}).get("skill")
        if not skill_name:
            self._reply("❌ 未指定技能")
            return

        entry = SKILL_MAP.get(skill_name)
        if not entry:
            self._reply(f"❌ 技能未注册: {skill_name}")
            return

        # 并发保护（很多 skill 会弹浏览器 / 调外部服务）
        if getattr(self.app, "_skill_running", False):
            self._reply(f"⏳ 有任务正在执行（当前：{self.app._skill_current}）")
            return

        self.app._skill_running = True
        self.app._skill_current = skill_name

        try:
            mod = importlib.import_module(entry[0])
            cls = getattr(mod, entry[1])
            skill = cls(self._extract_config(skill_name))

            # 参数：从 intent.params 里挖，缺啥用默认
            kwargs = self._build_kwargs(skill_name, intent)

            self._reply(f"🚀 执行技能 {skill_name}...")
            self._update_status(f"⏳ {skill_name} 运行中...")

            result = skill.execute(**kwargs)

            if result.get("status") == "success":
                self._reply(f"✅ {skill_name} 完成")
                # 把关键产物回显给用户
                for key in ("report_file", "audio_file", "image_path",
                            "video_path", "article_path", "preview_path",
                            "saved_to", "repo_url", "article_dir"):
                    v = result.get("result", {}).get(key)
                    if v:
                        self._reply(f"   📄 {key}: {v}")
                self._update_status(f"✅ {skill_name} 完成")
            else:
                self._reply(f"❌ {skill_name} 失败: {result.get('error')}")
                self._update_status(f"❌ {skill_name} 失败")

        except Exception as e:
            self._reply(f"❌ 执行异常: {e}")
            self._update_status("❌ 异常")
            traceback.print_exc()
        finally:
            self.app._skill_running = False
            self.app._skill_current = None

    def _extract_config(self, skill_name: str) -> Dict[str, Any]:
        """从 app.settings 里按需取配置。这里是通用骨架，按需补。"""
        s = self.app.settings
        return {
            "output_dir": str(s.output_dir),
            "log_level": "INFO",
        }

    def _build_kwargs(self, skill_name: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        """把 intent 里的东西翻译成各 skill 需要的参数名。

        不同 skill 的 execute() 签名差异很大，集中在这里做映射，
        而不是散落到各 handler。
        """
        text = intent.get("prompt") or intent.get("original_text", "")

        if skill_name == "search_engine":
            return {"action": "search", "query": text, "kind": "images", "limit": 20}
        if skill_name == "novel_writer":
            return {
                "genre": "科幻", "title": text[:20],
                "outline": text, "characters": "主角",
                "chapter_count": 1, "words_per_chapter": 500,
            }
        if skill_name == "music_generator":
            return {"topic": text, "emotion": "peaceful",
                    "duration": 30, "language": "zh"}
        if skill_name == "voice_assistant":
            return {"action": "tts", "text": text, "voice": "zh-CN-XiaoxiaoNeural"}
        if skill_name == "radio_player":
            return {"action": "play", "station": text, "category": "china"}
        if skill_name == "video_player":
            return {"action": "search", "query": text, "source": "all", "limit": 10}
        if skill_name == "music_player":
            return {"action": "search", "query": text}
        if skill_name == "news_aggregator":
            return {"category": "tech", "top_n": 15}
        if skill_name == "tech_hot_article":
            return {"style": "专业分析型", "words": 1500}
        if skill_name == "image_curator":
            return {"directory": "output"}  # 需要用户另外指定目录

        # 默认：只传原始文本，让 skill 自己解析
        return {"text": text, "topic": text}