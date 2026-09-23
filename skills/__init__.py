# skills/__init__.py
"""技能模块 - 可插拔功能"""

from .news_aggregator import NewsAggregator
from .novel_writer.skill import NovelWriterOllama
from .voice_assistant.skill import VoiceAssistant
from .music_generator.skill import MusicMaestro
from .image_curator import ImageCurator
from .wechat_formatter import WechatFormatter
from .tech_hot_article.skill import TechHotArticle  # ✅ 新增
from .image_generator import ImageGenerator    # ✅ 新增
from .video_generator import VideoGenerator
from .social_auto_upload import SocialAutoUpload
from .daily_pipeline import DailyPipeline

from .search_engine import SearchEngine
from .video_player import VideoPlayer
from .music_player import MusicPlayer
from .radio_player import RadioPlayer
from .video_sniffer import VideoSniffer
from .github_repo_daily import GitHubRepoDaily
__all__ = [
    'NewsAggregator',
    'NovelWriterOllama',
    'VoiceAssistant',
    'MusicMaestro',
    'ImageCurator',
    'ImageCurator',
    'TechHotArticle',  # ✅ 新增
    'ImageGenerator',    # ✅ 新增
    'VideoGenerator',
    'SocialAutoUpload',   
    'DailyPipeline',     
    # ✅ 新增
    'SearchEngine',
    'VideoPlayer',
    'MusicPlayer',
    'RadioPlayer',    
    'VideoSniffer',
    
    'GitHubRepoDaily',      # ✅ 新增
]
