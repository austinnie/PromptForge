# multimedia/workflow.py
import json
import os
import re
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import tempfile

# 导入技能
from skills.novel_writer.skill import NovelWriterOllama
from skills.voice_assistant.skill import VoiceAssistant
from skills.music_generator.skill import MusicMaestro

# 导入视频处理器
from handlers.video_handler import VideoHandler
from .subtitle import generate_srt_from_script

# 新版 moviepy
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips, TextClip, CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip

# ==================== 常量配置 ====================
MAX_SCENES = 16
MIN_PARAGRAPH_LEN = 30
DESC_CHARS = 100
NARRATION_CHARS = 300

VOICE_CHARS_PER_SECOND = 2.8
MAX_VOICE_CHARS = 2000
VOICE_SPEED = 1.1

DEFAULT_CHAPTER_COUNT = 1
DEFAULT_WORDS_PER_CHAPTER = 200
DEFAULT_STYLE = '简洁'
DEFAULT_TEMPERATURE = 0.85


class MultimediaWorkflow:
    def __init__(self, app):
        self.app = app
        self.output_dir = app.settings.output_dir / "multimedia"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 统一分段时长
        self.segment_duration = app.settings.video_segment_duration
        print(f"🔍 [MultimediaWorkflow] 分段时长 = {self.segment_duration} 秒")

        # 初始化各技能
        self.novel_writer = NovelWriterOllama({
            'default_model': app.settings.ollama_model,
            'ollama_url': app.settings.ollama_url,
            'default_language': 'zh',
            'output_dir': str(self.output_dir / 'novels')
        })

        self.tts = VoiceAssistant({
            'output_dir': str(self.output_dir / 'audio'),
            'default_voice': 'zh-CN-XiaoxiaoNeural',
        })

        self.music_gen = MusicMaestro({
            'output_dir': str(self.output_dir / 'music'),
            'ollama_host': app.settings.ollama_url,
            'ollama_model': app.settings.ollama_model,
            'music_mode': 'auto',
        })

        self.video_handler = VideoHandler(app)

        # 临时目录用于存放合并过程中的中间文件
        self.temp_dir = self.output_dir / "temp_merge"
        self.temp_dir.mkdir(exist_ok=True)

    def execute(self, theme: str, **kwargs) -> Dict[str, Any]:
        """
        全自动创作主流程（改进版：每个场景独立合成）
        """
        self.app._append_message("system", "📝 正在生成故事脚本...")

        # 1. 准备小说参数
        novel_params = self._prepare_novel_params(theme, kwargs)

        # 2. 生成小说
        novel_result = self.novel_writer.execute(**novel_params)
        if novel_result['status'] != 'success':
            raise Exception(f"小说生成失败: {novel_result.get('error')}")
        novel_data = novel_result['result']
        self.app._append_message("system",
            f"✅ 小说生成完成！共 {len(novel_data['chapters'])} 章，{novel_data['total_words']} 字")

        # 3. 拆分为场景
        scenes = self._novel_to_scenes(novel_data)
        if not scenes:
            scenes = [{
                'scene_description': '美丽的风景，高质量视觉画面',
                'narration': novel_data.get('summary', '一个美丽的故事')
            }]

        # 4. 提取情绪
        emotion = self._extract_emotion_from_script(novel_data)
        
        # ✅ 提取全局信息（在循环前执行一次）
        character_name = self._extract_character_name(novel_data)
        global_style = novel_data.get('genre', '科幻')
        self.app._append_message("system", f"👤 角色: {character_name or '未命名'}, 风格: {global_style}")
          
              
        total_scenes = len(scenes)
        self.app._append_message("system", f"🎬 共 {total_scenes} 个场景，每个 {self.segment_duration} 秒")

        # 5. 为每个场景生成独立内容
        merged_segments = []
        for idx, scene in enumerate(scenes):
            self.app._append_message("system", f"  📹 处理场景 {idx+1}/{total_scenes}...")

            desc = scene.get('scene_description', '')
            narration = scene.get('narration', '')

            if not desc:
                desc = "风景画面"
            if not narration:
                narration = "这是一个美丽的场景。"

            # 5.1 生成视频片段          
            video_path = self._generate_video_segment(desc, idx, emotion, global_style, character_name)
            if not video_path:
                self.app._append_message("system", f"  ⚠️ 场景 {idx+1} 视频生成失败，跳过")
                continue

            # 5.2 生成语音片段
            voice_path = self._generate_voice_segment(narration, idx)
            if not voice_path:
                self.app._append_message("system", f"  ⚠️ 场景 {idx+1} 语音生成失败，使用无声视频")
                subtitle_path = None
            else:
                # 5.3 生成字幕片段
                subtitle_path = self._generate_subtitle_for_segment(narration, voice_path, idx)

            # 5.4 生成音乐片段（背景音乐）
            music_path = self._generate_music_segment(emotion, self.segment_duration, idx)

            # 5.5 合并单个片段
            merged_path = self._merge_single_segment(
                video_path, voice_path, music_path, subtitle_path, idx
            )
            if merged_path:
                merged_segments.append(merged_path)
                self.app._append_message("system", f"  ✅ 场景 {idx+1} 合并完成")
            else:
                self.app._append_message("system", f"  ⚠️ 场景 {idx+1} 合并失败，跳过")

        if not merged_segments:
            raise Exception("未能生成任何有效的视频片段")

        # 6. 拼接所有片段
        self.app._append_message("system", "🎬 正在拼接所有片段...")
        final_path = self._concatenate_segments(merged_segments)

        self.app._append_message("system", f"✅ 全部完成！视频已保存至: {final_path}")

        # 清理临时目录（可选）
        # shutil.rmtree(self.temp_dir, ignore_errors=True)

        return {
            "status": "success",
            "final_video": final_path,
            "novel": novel_data,
            "scenes": scenes,
            "video_segments": merged_segments,
        }

    # ==================== 场景级生成方法 ====================

    def _generate_voice_segment(self, text: str, idx: int) -> Optional[str]:
        """生成单个场景的语音"""
        if len(text) > MAX_VOICE_CHARS:
            text = text[:MAX_VOICE_CHARS] + "..."
        result = self.tts.execute(
            action='tts',
            text=text,
            voice='zh-CN-XiaoxiaoNeural',
            speed=VOICE_SPEED,
            output_file=None
        )
        if result['status'] == 'success':
            audio_path = result['result'].get('audio_path')
            return audio_path
        return None

    def _generate_music_segment(self, emotion: str, duration: int, idx: int) -> Optional[str]:
        """生成单个场景的背景音乐"""
        result = self.music_gen.execute(
            topic="背景音乐",
            emotion=emotion,
            duration=duration,
            language='zh',
            use_enhanced=True,
            force_mode=None
        )
        if result['status'] in ('success', 'partial_success'):
            audio_file = result['result'].get('audio_file')
            if audio_file and os.path.exists(audio_file):
                # 如果是 MIDI，跳过（无法被 moviepy 读取）
                if audio_file.lower().endswith('.mid'):
                    print(f"⚠️ 音乐生成返回 MIDI，moviepy 不支持，跳过")
                    return None
                # 截取准确时长
                try:
                    audio_clip = AudioFileClip(audio_file)
                    if audio_clip.duration > duration:
                        audio_clip = audio_clip.subclip(0, duration)
                        temp_audio = self.temp_dir / f"music_seg_{idx:03d}.mp3"
                        audio_clip.write_audiofile(str(temp_audio), fps=44100, bitrate='192k')
                        audio_clip.close()
                        return str(temp_audio)
                    elif audio_clip.duration < duration:
                        audio_clip = audio_clip.loop(duration=duration)
                        temp_audio = self.temp_dir / f"music_seg_{idx:03d}.mp3"
                        audio_clip.write_audiofile(str(temp_audio), fps=44100, bitrate='192k')
                        audio_clip.close()
                        return str(temp_audio)
                    else:
                        return audio_file
                except Exception as e:
                    print(f"音乐剪辑异常: {e}")
                    return audio_file
        return None
    
    def _generate_subtitle_for_segment(self, text: str, voice_path: str, idx: int) -> Optional[str]:
        """生成单个场景的字幕"""
        script = {"narration": text}
        return generate_srt_from_script(script, voice_path)

    def _merge_single_segment(self, video_path: str, voice_path: str,
                              music_path: str, subtitle_path: str, idx: int) -> Optional[str]:
        """合并单个场景的视频、语音、音乐、字幕为一个片段"""
        try:
            video = VideoFileClip(video_path)
            audio_tracks = []

            if voice_path and os.path.exists(voice_path):
                voice_audio = AudioFileClip(voice_path)
                audio_tracks.append(voice_audio)

            if music_path and os.path.exists(music_path):
                # 跳过 MIDI 文件（moviepy 不支持）
                if music_path.lower().endswith('.mid'):
                    print(f"⚠️ 跳过 MIDI 文件（moviepy 不支持）: {music_path}")
                else:
                    try:
                        bg_audio = AudioFileClip(music_path).with_volume_scaling(0.3)
                        if bg_audio.duration < video.duration:
                            bg_audio = bg_audio.loop(duration=video.duration)
                        else:
                            bg_audio = bg_audio.subclip(0, video.duration)
                        audio_tracks.append(bg_audio)
                    except Exception as e:
                        print(f"⚠️ 加载音乐失败: {e}")

            if audio_tracks:
                final_audio = CompositeAudioClip(audio_tracks)
                video = video.with_audio(final_audio)

            if subtitle_path and os.path.exists(subtitle_path):
                try:
                    generator = lambda txt: TextClip(txt, font='Arial', fontsize=24,
                                                     color='white', stroke_color='black', stroke_width=1)
                    subtitles = SubtitlesClip(subtitle_path, generator)
                    video = CompositeVideoClip([video, subtitles.set_position(('center', 'bottom'))])
                except Exception as e:
                    print(f"字幕加载失败: {e}")

            output_path = self.temp_dir / f"merged_seg_{idx:03d}.mp4"
            video.write_videofile(str(output_path), fps=24, codec='libx264', audio_codec='aac')
            video.close()
            return str(output_path)

        except Exception as e:
            print(f"合并片段 {idx} 失败: {e}")
            return None
        
    def _concatenate_segments(self, segment_paths: List[str]) -> str:
        """拼接所有已合并的片段"""
        clips = [VideoFileClip(p) for p in segment_paths]
        final_video = concatenate_videoclips(clips, method="compose")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"final_{timestamp}.mp4"
        final_video.write_videofile(str(output_path), fps=24, codec='libx264', audio_codec='aac')
        for clip in clips:
            clip.close()
        return str(output_path)

    # ==================== 辅助方法（原有，完整保留） ====================

    def _prepare_novel_params(self, theme: str, user_kwargs: dict) -> dict:
        required = ['genre', 'title', 'outline', 'characters']
        if all(k in user_kwargs for k in required):
            return {k: user_kwargs[k] for k in required}

        prompt = f"""请根据用户给出的主题，生成一部小说的完整创作参数。
用户主题：{theme}

请以 JSON 格式输出以下字段：
- "genre": 小说类型（科幻/奇幻/言情/悬疑/武侠/都市）
- "title": 一个吸引人的小说标题
- "outline": 故事大纲（200字以内）
- "characters": 主要角色设定（包括姓名、性格、背景等，100字以内）

只输出 JSON，不要其他内容。"""

        response = self._call_ollama(prompt, temperature=0.7)
        try:
            params = json.loads(response)
        except:
            params = {
                "genre": "科幻",
                "title": theme[:20],
                "outline": theme,
                "characters": "主角：一位勇敢的探索者"
            }

        for k in required:
            if k in user_kwargs and user_kwargs[k]:
                params[k] = user_kwargs[k]

        params.setdefault('chapter_count', DEFAULT_CHAPTER_COUNT)
        params.setdefault('words_per_chapter', DEFAULT_WORDS_PER_CHAPTER)
        params.setdefault('style', DEFAULT_STYLE)
        params.setdefault('temperature', DEFAULT_TEMPERATURE)
        params.setdefault('language', 'zh')
        return params

    def _call_ollama(self, prompt: str, temperature: float = 0.7) -> str:
        import requests
        url = self.app.settings.ollama_url + "/api/generate"
        payload = {
            "model": self.app.settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature}
        }
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                return resp.json().get('response', '')
        except Exception as e:
            print(f"Ollama 调用失败: {e}")
        return ""

    def _novel_to_scenes(self, novel_data: dict) -> List[dict]:
        """将小说拆分为场景列表，优先解析【场景】标记"""
        import re
        scenes = []
        target_chars = max(20, int(self.segment_duration * VOICE_CHARS_PER_SECOND * 1.1))
        print(f"🔍 [场景拆分] 目标每场景旁白字数: {target_chars} 字")

        for chapter in novel_data.get('chapters', []):
            content = chapter.get('content', '')
            
            # 尝试按 【场景】 分割
            # 匹配 【场景】 开头，直到下一个 【场景】 或结束
            scene_blocks = re.split(r'【场景】\s*', content)
            # 如果分割后长度>1，说明有标记
            if len(scene_blocks) > 1:
                for block in scene_blocks:
                    block = block.strip()
                    if not block:
                        continue
                    # 提取画面和旁白
                    desc_match = re.search(r'画面[：:]\s*(.+?)(?:\n|$)', block)
                    narr_match = re.search(r'旁白[：:]\s*(.+?)(?:\n|$)', block)
                    # 如果没有明确的画面或旁白，尝试整段作为描述
                    if desc_match:
                        desc = desc_match.group(1).strip()
                    else:
                        # 取第一行作为描述
                        lines = block.split('\n')
                        desc = lines[0].strip()
                    if narr_match:
                        narration = narr_match.group(1).strip()
                    else:
                        # 取剩余部分作为旁白
                        if desc_match:
                            # 移除描述部分
                            rest = re.sub(r'画面[：:]\s*.+?\n', '', block, count=1)
                        else:
                            rest = block
                        narration = rest.strip()
                    # 如果描述太长，截断
                    if len(desc) > DESC_CHARS:
                        desc = desc[:DESC_CHARS] + "，高质量视觉画面"
                    # 如果旁白太长，截断
                    if len(narration) > NARRATION_CHARS:
                        narration = narration[:NARRATION_CHARS]
                    scenes.append({
                        'scene_description': desc,
                        'narration': narration
                    })
                    if len(scenes) >= MAX_SCENES:
                        break
                if len(scenes) >= MAX_SCENES:
                    break
                continue

            # 如果没有场景标记，回退到按句子拆分
            sentences = re.split(r'(?<=[。！？；\n])\s*', content)
            sentences = [s.strip() for s in sentences if s.strip()]
            if not sentences:
                continue
            current_block = ""
            for sent in sentences:
                if len(current_block) + len(sent) <= target_chars:
                    current_block += sent
                else:
                    if current_block:
                        desc = current_block[:DESC_CHARS] + "，高质量视觉画面"
                        scenes.append({
                            'scene_description': desc,
                            'narration': current_block.strip()
                        })
                    current_block = sent
            if current_block:
                desc = current_block[:DESC_CHARS] + "，高质量视觉画面"
                scenes.append({
                    'scene_description': desc,
                    'narration': current_block.strip()
                })
            if len(scenes) >= MAX_SCENES:
                break

        if not scenes:
            scenes = [{
                'scene_description': '美丽的风景，高质量视觉画面',
                'narration': novel_data.get('summary', '一个美丽的故事')
            }]

        print(f"✅ 拆分为 {len(scenes)} 个场景，平均每场景约 {sum(len(s['narration']) for s in scenes) // len(scenes)} 字")
        return scenes

    def _extract_character_name(self, novel_data: dict) -> str:
        """从小说数据中提取主角名称"""
        import re
        summary = novel_data.get('summary', '')
        # 匹配 "主角李明" 或 "李明是一位"
        patterns = [
            r'主角[：:]\s*([^\s，。、]+)',
            r'([^\s，。、]{2,4})[是为]一位',
            r'([^\s，。、]{2,4})[是为]一个',
        ]
        for pattern in patterns:
            match = re.search(pattern, summary)
            if match:
                return match.group(1)
        # 从第一章提取
        chapters = novel_data.get('chapters', [])
        if chapters:
            content = chapters[0].get('content', '')
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    return match.group(1)
        return None
    
    def _extract_emotion_from_script(self, novel_data: dict) -> str:
        full_text = "".join([c.get('content', '') for c in novel_data.get('chapters', [])])
        emotion_map = {
            'joyful': ['快乐', '喜悦', '开心', '阳光', '笑容', '幸福'],
            'melancholic': ['悲伤', '失落', '哭泣', '沉重', '告别', '思念'],
            'epic': ['宏伟', '冒险', '英雄', '壮丽', '远征', '战斗'],
            'peaceful': ['宁静', '安详', '平和', '柔和', '夜', '月光'],
            'mysterious': ['神秘', '未知', '诡异', '谜', '黑暗', '秘密'],
        }
        for emotion, keywords in emotion_map.items():
            if any(k in full_text for k in keywords):
                return emotion
        return 'epic'

    def _generate_video_segment(self, prompt: str, idx: int, emotion: str = '',
                                global_style: str = None, character_name: str = None) -> Optional[str]:
        continuity_parts = [f"Scene {idx+1}", "continuation of the story"]
        if character_name:
            continuity_parts.append(f"character '{character_name}' appears in all scenes, consistent appearance")
        if global_style:
            continuity_parts.append(f"{global_style} style, cinematic coherence")
        continuity_parts.append("same visual style, consistent color tone")
        continuity = ", ".join(continuity_parts)
        full_prompt = f"{prompt}, {continuity}"
        if emotion:
            full_prompt += f", {emotion} style"

        # 重试一次
        for attempt in range(2):
            try:
                result = self.video_handler.generate_video_from_prompt(full_prompt, duration=self.segment_duration)
                if result:
                    return result
                if attempt == 0:
                    print(f"⏳ 场景 {idx+1} 生成失败，重试中...")
                    time.sleep(5)
            except Exception as e:
                print(f"⚠️ 场景 {idx+1} 尝试 {attempt+1} 失败: {e}")
                if attempt == 0:
                    time.sleep(5)
        return None
    
    def __repr__(self):
        return f"<MultimediaWorkflow(segment_duration={self.segment_duration})>"