# skills/__init__.py
"""技能模块 - 可插拔功能"""

from .news_aggregator import NewsAggregator
from .novel_writer.skill import NovelWriterOllama
from .voice_assistant.skill import VoiceAssistant
from .music_generator.skill import MusicMaestro  # 正确类名

__all__ = [
    'NewsAggregator',
    'NovelWriterOllama',
    'VoiceAssistant',
    'MusicMaestro',
]