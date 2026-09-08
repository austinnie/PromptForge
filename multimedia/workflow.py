# multimedia/workflow.py
import json
import os
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 导入技能
from skills.novel_writer.skill import NovelWriterOllama
from skills.voice_assistant.skill import VoiceAssistant
from skills.music_generator.skill import MusicMaestro

# 导入视频处理器和合成器
from handlers.video_handler import VideoHandler
from .subtitle import generate_srt_from_script
from .assembler import assemble_video
from skills.music_generator.music_generator_cli import MusicGenerator

class MultimediaWorkflow:
    def __init__(self, app):
        self.app = app
        self.output_dir = app.settings.output_dir / "multimedia"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化各技能（传入配置字典）
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
            'music_mode': 'auto',  # auto / midi / musicgen
        })

        self.video_handler = VideoHandler(app)

    def execute(self, theme: str, **kwargs) -> Dict[str, Any]:
        """
        全自动创作主流程
        :param theme: 用户主题
        :param kwargs: 可选覆盖参数
        :return: 结果字典
        """
        self.app._append_message("system", "📝 正在生成故事脚本...")

        # 1. 准备小说参数（自动补全）
        novel_params = self._prepare_novel_params(theme, kwargs)

        # 2. 调用小说生成器
        novel_result = self.novel_writer.execute(**novel_params)
        if novel_result['status'] != 'success':
            raise Exception(f"小说生成失败: {novel_result.get('error')}")

        novel_data = novel_result['result']
        self.app._append_message("system",
            f"✅ 小说生成完成！共 {len(novel_data['chapters'])} 章，{novel_data['total_words']} 字")

        # 3. 将小说拆分为场景
        scenes = self._novel_to_scenes(novel_data)

        # 如果无场景，用默认场景
        if not scenes:
            scenes = [{
                'scene_description': '美丽的风景，高质量视觉画面',
                'narration': novel_data.get('summary', '一个美丽的故事')
            }]

        # 4. 提取情绪
        emotion = self._extract_emotion_from_script(novel_data)

        # 5. 估算视频总时长（每个场景 5 秒）
        total_video_duration = len(scenes) * 5  # 秒

        # 6. 并行生成语音、音乐，但视频片段串行生成（避免 API 限流）
        self.app._append_message("system", f"🎬 准备生成 {len(scenes)} 个视频片段（每个 5 秒），总时长约 {total_video_duration} 秒")

        # 语音（完整旁白）
        full_narration = "\n".join([s['narration'] for s in scenes])
        self.app._append_message("system", "🎙️ 正在合成语音旁白...")
        voice_path = self._generate_voice(full_narration, kwargs.get('voice', 'zh-CN-XiaoxiaoNeural'))

        # 音乐（根据估算时长）
        self.app._append_message("system", "🎵 正在生成背景音乐...")
        music_path = self._generate_music(
            theme=theme,
            emotion=emotion,
            duration=total_video_duration  # 传入估算的视频总时长
        )

        # 串行生成视频片段
        self.app._append_message("system", "🎬 正在生成视频片段（串行，避免 API 限流）...")
        video_segments = []
        for i, scene in enumerate(scenes):
            self.app._append_message("system", f"  📹 生成第 {i+1}/{len(scenes)} 个片段...")
            desc = scene.get('scene_description', '')
            if desc:
                path = self._generate_video_segment(desc, i, emotion)
                if path:
                    video_segments.append(path)
                    self.app._append_message("system", f"  ✅ 第 {i+1} 个片段完成")
                else:
                    self.app._append_message("system", f"  ⚠️ 第 {i+1} 个片段生成失败，跳过")
            else:
                self.app._append_message("system", f"  ⚠️ 第 {i+1} 个场景无描述，跳过")

        if not video_segments:
            raise Exception("未能生成任何视频片段")

        # 7. 生成字幕
        self.app._append_message("system", "📝 生成字幕...")
        srt_path = self._generate_subtitle(full_narration, voice_path)

        # 8. 合成最终视频
        self.app._append_message("system", "🎬 合成最终视频...")
        final_path = assemble_video(
            video_segments=video_segments,
            music_path=music_path,
            voice_path=voice_path,
            subtitle_path=srt_path,
            output_dir=self.output_dir
        )

        self.app._append_message("system", f"✅ 全部完成！视频已保存至: {final_path}")

        return {
            "status": "success",
            "final_video": final_path,
            "novel": novel_data,
            "scenes": scenes,
            "video_segments": video_segments,
            "music": music_path,
            "voice": voice_path,
            "subtitle": srt_path,
        }

    # ==================== 辅助方法 ====================

    def _prepare_novel_params(self, theme: str, user_kwargs: dict) -> dict:
        """自动补全小说生成参数（使用 Ollama），调整为极短篇"""
        required = ['genre', 'title', 'outline', 'characters']
        if all(k in user_kwargs for k in required):
            return {k: user_kwargs[k] for k in required}

        # 调用 Ollama 生成缺失参数
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

        # 合并用户参数
        for k in required:
            if k in user_kwargs and user_kwargs[k]:
                params[k] = user_kwargs[k]

        # ✅ 设置极短篇默认值
        params.setdefault('chapter_count', 1)         # 只生成 1 章
        params.setdefault('words_per_chapter', 200)   # 每章 200 字
        params.setdefault('style', '简洁')            # 简洁风格
        params.setdefault('temperature', 0.85)
        params.setdefault('language', 'zh')
        return params

    def _call_ollama(self, prompt: str, temperature: float = 0.7) -> str:
        """调用 Ollama API"""
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
        """将小说拆分为场景列表，限制最多 8 个场景"""
        import re
        scenes = []
        max_scenes = 8

        for chapter in novel_data.get('chapters', []):
            content = chapter.get('content', '')
            # 首先按段落拆分
            paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
            # 如果段落太少（少于2），则按句子拆分
            if len(paragraphs) < 2:
                # 按中文句号、问号、感叹号拆分
                sentences = re.split(r'[。！？；\n]+', content)
                paragraphs = [s.strip() for s in sentences if s.strip()]
            
            for para in paragraphs:
                if len(para) < 30:
                    continue
                # 取前 120 字作为视频描述（增加描述长度）
                desc = para[:120] + "，高质量视觉画面" if len(para) > 120 else para + "，高质量视觉画面"
                # 旁白取前 300 字
                narration = para[:300]
                scenes.append({
                    'scene_description': desc,
                    'narration': narration
                })
                if len(scenes) >= max_scenes:
                    break
            if len(scenes) >= max_scenes:
                break

        return scenes

    def _extract_emotion_from_script(self, novel_data: dict) -> str:
        """从小说内容推断情绪"""
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

    def _generate_video_segment(self, prompt: str, idx: int, emotion: str = '') -> Optional[str]:
        """生成单个视频片段，加入连贯性提示"""
        # 加入场景编号和连贯性提示
        continuity = f"Scene {idx+1}, continuation of the story, consistent characters and visual style"
        full_prompt = f"{prompt}, {continuity}"
        if emotion:
            full_prompt += f", {emotion} style"
        return self.video_handler.generate_video_from_prompt(full_prompt, duration=5)

    def _generate_music_midi(self, theme: str, emotion: str, duration: int) -> Optional[str]:
        result = self.music_gen.execute(
            topic=theme,
            emotion=emotion,
            duration=duration,
            language='zh',
            use_enhanced=True,
            force_mode=None
        )
        if result['status'] not in ('success', 'partial_success'):
            return None

        audio_file = result['result'].get('audio_file')
        if not audio_file or not os.path.exists(audio_file):
            return None

        # 如果是 MIDI，转换为 WAV
        if audio_file.lower().endswith('.mid'):
            wav_file = audio_file.replace('.mid', '.wav')
            if not os.path.exists(wav_file):
                print(f"🎵 转换 MIDI 到 WAV: {audio_file} -> {wav_file}")
                # 使用 fluidsynth 转换（需安装 fluidsynth 并指定 SoundFont）
                soundfont = self.music_gen.engine.config.get('soundfont', '')  # 可在配置中指定
                if not soundfont:
                    # 尝试常见路径
                    soundfont = './skills/music_generator/soundfonts/GeneralUser-GS.sf2'
                    if not os.path.exists(soundfont):
                        soundfont = './skills/music_generator/soundfonts/SGM-V2.01.sf2'
                if not os.path.exists(soundfont):
                    print("⚠️ 未找到 SoundFont，无法转换 MIDI，跳过音乐")
                    return None

                cmd = ['fluidsynth', '-ni', soundfont, audio_file, '-F', wav_file, '-r', '44100']
                try:
                    subprocess.run(cmd, check=True, timeout=60, capture_output=True)
                    print(f"✅ MIDI 转换成功: {wav_file}")
                    audio_file = wav_file
                except Exception as e:
                    print(f"❌ MIDI 转换失败: {e}")
                    return None
            else:
                audio_file = wav_file

        return audio_file

    def _generate_music(self, theme: str, emotion: str, duration: int) -> Optional[str]:
        """生成背景音乐，优先使用 MP3（MusicGenerator），失败则回退到 MIDI（MusicMaestro）"""
        # 方式1：MP3（首选）
        try:
            from skills.music_generator.music_generator_cli import MusicGenerator
            gen = MusicGenerator()
            result = gen.create_music(
                topic=theme,
                emotion=emotion,
                duration=duration,
                language='zh'
            )
            if result["status"] == "success":
                audio_file = result["audio_file"]
                if audio_file and os.path.exists(audio_file):
                    print(f"✅ 使用 MP3 音乐: {audio_file}")
                    return audio_file
            else:
                print(f"⚠️ MP3 生成失败: {result.get('message', '未知错误')}")
        except Exception as e:
            print(f"⚠️ MP3 生成异常: {e}")
        
        # 方式2：MIDI（备选）
        print("🔄 回退到 MIDI 模式...")
        return self._generate_music_midi(theme, emotion, duration)
    
    def _generate_voice(self, text: str, voice: str) -> Optional[str]:
        """合成语音，限制文本长度"""
        # 限制旁白长度
        if len(text) > 2000:
            text = text[:2000] + " ..."
        result = self.tts.execute(
            action='tts',
            text=text,
            voice=voice,
            speed=1.0,
            output_file=None
        )
        if result['status'] == 'success':
            return result['result'].get('audio_path')
        return None

    def _generate_subtitle(self, text: str, voice_path: str) -> Optional[str]:
        """生成字幕（复用原有函数）"""
        script = {"narration": text}
        return generate_srt_from_script(script, voice_path)