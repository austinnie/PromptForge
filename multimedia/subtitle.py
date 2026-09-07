# multimedia/subtitle.py
import os
import re
from datetime import timedelta
from mutagen import File  # 需要安装 mutagen

def generate_srt_from_script(script: dict, voice_path: str, words_per_second: float = 3.0) -> str:
    """根据旁白文本和语音时长生成简单的 SRT 字幕"""
    narration = script.get("narration", "")
    if not narration:
        return None

    # 获取语音时长（秒）
    try:
        audio = File(voice_path)
        if audio:
            total_duration = audio.info.length
        else:
            total_duration = len(narration) / words_per_second
    except Exception:
        total_duration = len(narration) / words_per_second

    # 按句子拆分
    sentences = re.split(r'[，。！？；\n]+', narration)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return None

    total_chars = sum(len(s) for s in sentences)
    base_dir = os.path.dirname(voice_path)
    srt_path = os.path.join(base_dir, "subtitle.srt")

    with open(srt_path, 'w', encoding='utf-8') as f:
        start_time = 0.0
        for idx, sent in enumerate(sentences, 1):
            duration = (len(sent) / total_chars) * total_duration
            end_time = start_time + duration
            start_str = str(timedelta(seconds=start_time)).split('.')[0] + ',000'
            end_str = str(timedelta(seconds=end_time)).split('.')[0] + ',000'
            f.write(f"{idx}\n{start_str} --> {end_str}\n{sent}\n\n")
            start_time = end_time

    return srt_path