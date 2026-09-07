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

        # 4. 提取情绪
        emotion = self._extract_emotion_from_script(novel_data)

        # 5. 并行生成视频、音乐、语音
        self.app._append_message("system", "🎬 并行生成视频、音乐、旁白...")

        with ThreadPoolExecutor(max_workers=4) as executor:
            # 视频片段
            video_futures = []
            for i, scene in enumerate(scenes):
                desc = scene.get('scene_description', '')
                if desc:
                    future = executor.submit(
                        self._generate_video_segment,
                        desc,
                        i,
                        emotion
                    )
                    video_futures.append(future)

            # 音乐
            music_future = executor.submit(
                self._generate_music,
                theme=theme,
                emotion=emotion,
                duration=kwargs.get('music_duration', 30)
            )

            # 语音（完整旁白）
            full_narration = "\n".join([s['narration'] for s in scenes])
            tts_future = executor.submit(
                self._generate_voice,
                text=full_narration,
                voice=kwargs.get('voice', 'zh-CN-XiaoxiaoNeural')
            )

            # 收集视频
            video_segments = []
            for fut in as_completed(video_futures):
                path = fut.result()
                if path:
                    video_segments.append(path)
            # 按索引排序（假设文件名包含序号）
            video_segments.sort(key=lambda p: int(Path(p).stem.split('_')[-1]) if '_' in p.stem else 0)

            music_path = music_future.result()
            voice_path = tts_future.result()

        # 6. 生成字幕
        self.app._append_message("system", "📝 生成字幕...")
        srt_path = self._generate_subtitle(full_narration, voice_path)

        # 7. 合成最终视频
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
        """自动补全小说生成参数（使用 Ollama）"""
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

        # 设置默认值
        params.setdefault('chapter_count', 3)
        params.setdefault('words_per_chapter', 500)
        params.setdefault('style', '细腻')
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
        """将小说拆分为场景列表"""
        scenes = []
        for chapter in novel_data.get('chapters', []):
            content = chapter.get('content', '')
            import re
            sentences = re.split(r'[。！？；\n]+', content)
            for sent in sentences:
                sent = sent.strip()
                if len(sent) < 20:
                    continue
                desc = sent[:80] + "，高质量视觉画面" if len(sent) > 80 else sent + "，高质量视觉画面"
                scenes.append({
                    'scene_description': desc,
                    'narration': sent
                })
        if len(scenes) > 10:
            scenes = scenes[:10]
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
        """生成单个视频片段"""
        if emotion:
            prompt = f"{prompt}, {emotion} style"
        # 调用视频生成（这里需要 VideoHandler 返回文件路径）
        # 由于当前 VideoHandler 没有返回路径的方法，我们临时用占位
        # 实际应实现一个返回路径的方法
        print(f"生成视频片段 {idx}: {prompt[:30]}...")
        # 这里假设有一个方法 generate_video(prompt) 返回路径
        # 目前先返回 None，实际集成时需补全
        # 调用 VideoHandler 的方法
        return self.video_handler.generate_video_from_prompt(prompt, duration=5)

    def _generate_music(self, theme: str, emotion: str, duration: int) -> Optional[str]:
        """生成背景音乐"""
        result = self.music_gen.execute(
            topic=theme,
            emotion=emotion,
            duration=duration,
            language='zh',
            use_enhanced=True,
            force_mode=None
        )
        if result['status'] in ('success', 'partial_success'):
            return result['result'].get('audio_file')
        return None

    def _generate_voice(self, text: str, voice: str) -> Optional[str]:
        """合成语音"""
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
        # 构造一个简单脚本结构以复用 generate_srt_from_script
        script = {"narration": text}
        return generate_srt_from_script(script, voice_path)