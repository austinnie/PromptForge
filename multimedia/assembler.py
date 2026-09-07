# multimedia/assembler.py
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime

# 新版 moviepy 导入方式
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, \
    concatenate_videoclips, TextClip, CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip  # 新版位置


def assemble_video(
    video_segments: List[str],
    music_path: str,
    voice_path: str,
    subtitle_path: Optional[str] = None,
    output_dir: Path = None
) -> str:
    """将多个视频片段、背景音乐、语音、字幕合成最终视频"""
    if not video_segments:
        raise ValueError("至少需要一个视频片段")

    # 1. 拼接视频
    clips = [VideoFileClip(p) for p in video_segments]
    final_video = concatenate_videoclips(clips, method="compose")

    # 2. 准备音频
    audio_tracks = []
    if voice_path and os.path.exists(voice_path):
        voice_audio = AudioFileClip(voice_path)
        audio_tracks.append(voice_audio)
    if music_path and os.path.exists(music_path):
        bg_audio = AudioFileClip(music_path).volumex(0.3)
        if bg_audio.duration < final_video.duration:
            bg_audio = bg_audio.loop(duration=final_video.duration)
        else:
            bg_audio = bg_audio.subclip(0, final_video.duration)
        audio_tracks.append(bg_audio)

    if audio_tracks:
        final_audio = CompositeAudioClip(audio_tracks)
        final_video = final_video.set_audio(final_audio)

    # 3. 添加字幕
    if subtitle_path and os.path.exists(subtitle_path):
        try:
            generator = lambda txt: TextClip(
                txt, font='Arial', fontsize=24,
                color='white', stroke_color='black', stroke_width=1
            )
            subtitles = SubtitlesClip(subtitle_path, generator)
            final_video = CompositeVideoClip([
                final_video,
                subtitles.set_position(('center', 'bottom'))
            ])
        except Exception as e:
            print(f"字幕加载失败: {e}")

    # 4. 输出
    output_dir = output_dir or Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"final_{timestamp}.mp4"

    final_video.write_videofile(str(output_path), fps=24, codec='libx264', audio_codec='aac')
    return str(output_path)