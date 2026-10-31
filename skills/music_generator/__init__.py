# skills/music_generator/__init__.py
"""music_generator - 融合版。

对外只暴露 MusicMaestro + detect_hardware。
SymphonyGenerator 是内部类，通过 MusicMaestro 使用。
"""
from .skill import (
    MusicMaestro,
    SymphonyGenerator,
    detect_hardware,
    EMOTION_CONFIG,
    ARRANGEMENTS,
    INSTRUMENTS,
)

__all__ = [
    "MusicMaestro",
    "SymphonyGenerator",
    "detect_hardware",
    "EMOTION_CONFIG",
    "ARRANGEMENTS",
    "INSTRUMENTS",
]