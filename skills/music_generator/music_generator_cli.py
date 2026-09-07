#!/usr/bin/env python
"""
🎵 AI 音乐大师 - 直接生成 MP3（音量修复版）
"""
import sys
import os
import json
import random
import subprocess
from pathlib import Path
from datetime import datetime
import tempfile

# 添加项目根目录
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ==================== 配置 ====================
SOUNDFONTS_DIR = project_root / "skills" / "music_generator" / "soundfonts"
OUTPUT_DIR = project_root / "skills" / "music_generator" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 查找 SoundFont
SOUNDFONT_PATHS = [
    SOUNDFONTS_DIR / "GeneralUser-GS.sf2",
    SOUNDFONTS_DIR / "SGM-V2.01.sf2",
    SOUNDFONTS_DIR / "FluidR3_GM.sf2",
]
SOUNDFONT_PATH = next((p for p in SOUNDFONT_PATHS if p.exists()), None)

# 查找 FluidSynth
FLUIDSYNTH_PATHS = [
    SOUNDFONTS_DIR / "fluidsynth-v2.6.0-win10-x64-cpp11" / "bin" / "fluidsynth.exe",
    Path("C:/Program Files/FluidSynth/bin/fluidsynth.exe"),
    Path("C:/Program Files (x86)/FluidSynth/bin/fluidsynth.exe"),
]
FLUIDSYNTH_PATH = next((p for p in FLUIDSYNTH_PATHS if p.exists()), None)

# ==================== 音乐生成引擎 ====================

class MusicGenerator:
    """直接生成 MP3 的音乐引擎"""
    
    # 情绪配置
    EMOTIONS = {
        "peaceful": {
            "name": "宁静",
            "tempo": 70,
            "chords": [
                [0, 4, 7], [0, 4, 7], [5, 9, 12], [5, 9, 12],
                [0, 4, 7], [0, 4, 7], [7, 11, 14], [0, 4, 7],
            ],
            "scale": [0, 2, 4, 6, 8, 10],
            "description": "舒缓、空灵，适合冥想和放松"
        },
        "melancholic": {
            "name": "深情",
            "tempo": 80,
            "chords": [
                [0, 3, 7], [5, 8, 12], [3, 7, 10], [0, 3, 7],
                [5, 8, 12], [3, 7, 10], [8, 11, 15], [0, 3, 7],
            ],
            "scale": [0, 2, 3, 5, 7, 8, 10],
            "description": "伤感、深情，适合思念和回忆"
        },
        "joyful": {
            "name": "欢乐",
            "tempo": 120,
            "chords": [
                [0, 4, 7], [2, 6, 9], [4, 8, 11], [5, 9, 12],
                [0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7],
            ],
            "scale": [0, 2, 4, 5, 7, 9, 11],
            "description": "欢快、活泼，适合庆祝和快乐时刻"
        },
        "epic": {
            "name": "壮丽",
            "tempo": 110,
            "chords": [
                [0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7],
                [5, 9, 12], [7, 11, 14], [0, 4, 7], [4, 8, 11],
            ],
            "scale": [0, 2, 4, 5, 7, 9, 11],
            "description": "宏大、激昂，适合史诗和英雄主题"
        },
        "mysterious": {
            "name": "神秘",
            "tempo": 90,
            "chords": [
                [0, 4, 7], [3, 7, 10], [0, 4, 7], [5, 9, 12],
                [8, 12, 15], [3, 7, 10], [5, 9, 12], [0, 4, 7],
            ],
            "scale": [0, 1, 3, 6, 8, 10],
            "description": "神秘、悬疑，适合探索和未知"
        }
    }
    
    def __init__(self):
        self.soundfont = SOUNDFONT_PATH
        self.fluidsynth = FLUIDSYNTH_PATH
        self._check_dependencies()
    
    def _check_dependencies(self):
        """检查依赖"""
        if not self.soundfont:
            print("❌ 没有找到 SoundFont 文件")
            print(f"请将 .sf2 文件放到: {SOUNDFONTS_DIR}")
            raise FileNotFoundError("SoundFont 未找到")
        
        if not self.fluidsynth:
            print("❌ 没有找到 FluidSynth")
            print("请下载 FluidSynth 并放到 soundfonts/ 目录")
            raise FileNotFoundError("FluidSynth 未找到")
        
        print(f"✅ SoundFont: {self.soundfont.name}")
        print(f"✅ FluidSynth: {self.fluidsynth}")
    
    def generate_midi_data(self, emotion: str, duration: int) -> bytes:
        """生成 MIDI 数据（内存中）"""
        try:
            from midiutil import MIDIFile
        except ImportError:
            print("❌ midiutil 未安装，请运行: pip install midiutil")
            return None
        
        config = self.EMOTIONS.get(emotion, self.EMOTIONS["peaceful"])
        tempo = config["tempo"]
        chords = config["chords"]
        scale = config["scale"]
        
        midi = MIDIFile(2)
        track_chord = 0
        track_melody = 1
        time = 0
        
        midi.addTempo(track_chord, time, tempo)
        midi.addTempo(track_melody, time, tempo)
        
        # 钢琴音色
        midi.addProgramChange(track_chord, 0, time, 0)
        midi.addProgramChange(track_melody, 0, time, 0)
        
        base_note = 60  # C4
        total_beats = duration * (tempo / 60)
        current_beat = 0
        chord_index = 0
        beat_per_chord = 4
        
        # ✅ 音量调高
        CHORD_VOLUME = 110      # 原来 80
        BASS_VOLUME = 90        # 原来 60
        MELODY_VOLUME = 100     # 原来 70
        GRACE_VOLUME = 70       # 原来 50
        
        while current_beat < total_beats:
            chord = chords[chord_index % len(chords)]
            chord_duration = min(beat_per_chord, total_beats - current_beat)
            
            # 和弦
            for note_offset in chord:
                pitch = base_note + note_offset
                if 0 <= pitch <= 127:
                    midi.addNote(track_chord, 0, pitch, current_beat, chord_duration, CHORD_VOLUME)
            
            # 低音
            root = base_note + chord[0] - 12
            if 0 <= root <= 127:
                midi.addNote(track_chord, 0, root, current_beat, chord_duration, BASS_VOLUME)
            
            # 旋律
            beats = 0
            while beats < beat_per_chord and current_beat + beats < total_beats:
                note_idx = random.randint(0, len(scale) - 1)
                octave = random.choice([0, 12]) if random.random() < 0.3 else 0
                pitch = base_note + scale[note_idx] + octave
                dur = random.choice([0.5, 0.5, 1.0, 0.25])
                
                if 0 <= pitch <= 127:
                    midi.addNote(track_melody, 0, pitch, current_beat + beats, dur, MELODY_VOLUME)
                
                # 装饰音
                if random.random() < 0.1:
                    grace = pitch + random.choice([-2, 2])
                    if 0 <= grace <= 127:
                        midi.addNote(track_melody, 0, grace, current_beat + beats + 0.1, 0.15, GRACE_VOLUME)
                
                beats += dur
            
            chord_index += 1
            current_beat += beat_per_chord
        
        # 导出为字节
        import io
        buffer = io.BytesIO()
        midi.writeFile(buffer)
        return buffer.getvalue()
    
    def synthesize_to_mp3(self, midi_data: bytes) -> bytes:
        """合成 MIDI 为 MP3（带音量增益）"""
        if not midi_data:
            return None
        
        # 临时文件
        tmp_midi = tempfile.NamedTemporaryFile(suffix='.mid', delete=False)
        tmp_midi.write(midi_data)
        tmp_midi.close()
        
        tmp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        tmp_wav.close()
        
        tmp_mp3 = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        tmp_mp3.close()
        
        try:
            # MIDI -> WAV
            cmd = [
                str(self.fluidsynth),
                "-ni",
                str(self.soundfont),
                tmp_midi.name,
                "-F", tmp_wav.name,
                "-r", "44100"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
                cwd=str(self.fluidsynth.parent)
            )
            
            if result.returncode != 0 or not os.path.exists(tmp_wav.name) or os.path.getsize(tmp_wav.name) == 0:
                cmd2 = [
                    str(self.fluidsynth),
                    "-ni",
                    "-F", tmp_wav.name,
                    "-r", "44100",
                    str(self.soundfont),
                    tmp_midi.name
                ]
                result = subprocess.run(cmd2, capture_output=True, timeout=60, cwd=str(self.fluidsynth.parent))
                
                if result.returncode != 0:
                    print("❌ FluidSynth 合成失败")
                    return None
            
            # ✅ WAV -> MP3（增加音量）
            try:
                cmd = [
                    "ffmpeg",
                    "-i", tmp_wav.name,
                    "-b:a", "192k",
                    "-vol", "400",  # ✅ 增加音量（100=原始，400=4倍）
                    "-y",
                    tmp_mp3.name
                ]
                subprocess.run(cmd, capture_output=True, timeout=30, check=True)
                
                with open(tmp_mp3.name, 'rb') as f:
                    return f.read()
                    
            except FileNotFoundError:
                print("⚠️ ffmpeg 未安装，返回 WAV 数据")
                with open(tmp_wav.name, 'rb') as f:
                    return f.read()
            
        except Exception as e:
            print(f"❌ 合成失败: {e}")
            return None
        finally:
            # 清理
            for path in [tmp_midi.name, tmp_wav.name, tmp_mp3.name]:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except:
                    pass
    
    def generate_lyrics(self, topic: str, emotion: str, language: str) -> dict:
        """生成歌词"""
        emo_name = self.EMOTIONS.get(emotion, self.EMOTIONS["peaceful"])["name"]
        
        # 尝试调用 Ollama
        lyrics = self._try_ollama(topic, emotion, language)
        if lyrics:
            return lyrics
        
        # 默认歌词
        return {
            "title": f"{topic}之歌",
            "emotion": emotion,
            "language": language,
            "structure": {
                "verse": [
                    f"在{emo_name}的光辉中，",
                    f"我听见{topic}的呼唤",
                    f"微风轻拂过心间，",
                    f"带来永恒的旋律"
                ],
                "chorus": [
                    f"{topic}，如此{emo_name}，",
                    f"照亮我前行的路",
                    f"在这无尽的时空里，",
                    f"与你共舞"
                ],
                "bridge": [
                    f"当星光洒落，",
                    f"当万物沉寂",
                    f"我依然能听见",
                    f"那来自远方的歌"
                ]
            },
            "vocal_style": "空灵治愈" if emotion == "peaceful" else "力量激昂"
        }
    
    def _try_ollama(self, topic: str, emotion: str, language: str) -> dict:
        """尝试调用 Ollama 生成歌词"""
        try:
            import requests
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5:7b",
                    "prompt": f"创作一首关于'{topic}'的{emotion}风格歌词，语言:{language}，只返回JSON格式：{{'title':'标题','structure':{{'verse':['主歌1','主歌2'],'chorus':['副歌'],'bridge':['桥段']}}}}",
                    "stream": False,
                    "options": {"temperature": 0.8, "num_predict": 512}
                },
                timeout=15
            )
            if response.status_code == 200:
                import re
                text = response.json().get("response", "")
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    return json.loads(match.group())
        except:
            pass
        return None
    
    def create_music(self, topic: str = "星辰大海", emotion: str = "peaceful", 
                     duration: int = 30, language: str = "zh") -> dict:
        """创建音乐"""
        print(f"\n🎵 创作: {topic}")
        print(f"  情绪: {emotion} ({self.EMOTIONS.get(emotion, {}).get('name', '')})")
        print(f"  时长: {duration} 秒")
        print("⏳ 生成中...")
        
        # 1. 生成歌词
        lyrics = self.generate_lyrics(topic, emotion, language)
        
        # 2. 生成 MIDI
        midi_data = self.generate_midi_data(emotion, duration)
        if not midi_data:
            return {"status": "error", "message": "MIDI 生成失败"}
        
        # 3. 合成 MP3
        mp3_data = self.synthesize_to_mp3(midi_data)
        if not mp3_data:
            return {"status": "error", "message": "MP3 合成失败"}
        
        # 4. 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{emotion}_{topic}_{timestamp}.mp3"
        # 清理文件名
        filename = ''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)
        output_path = OUTPUT_DIR / filename
        
        with open(output_path, 'wb') as f:
            f.write(mp3_data)
        
        # 5. 保存歌词
        lyrics_path = output_path.with_suffix('.json')
        with open(lyrics_path, 'w', encoding='utf-8') as f:
            json.dump(lyrics, f, ensure_ascii=False, indent=2)
        
        return {
            "status": "success",
            "audio_file": str(output_path),
            "lyrics_file": str(lyrics_path),
            "lyrics": lyrics,
            "size_kb": len(mp3_data) / 1024,
            "duration": duration,
            "emotion": emotion
        }


# ==================== CLI 界面 ====================

def interactive_mode():
    """交互式模式"""
    print("\n" + "=" * 60)
    print("   🎵 AI 音乐大师 - 直接生成 MP3")
    print("=" * 60)
    
    # 主题
    topic = input("\n📝 歌曲主题 (默认: 星辰大海): ").strip()
    if not topic:
        topic = "星辰大海"
    
    # 情绪
    print("\n🎵 选择情绪:")
    emotions = list(MusicGenerator.EMOTIONS.keys())
    for i, key in enumerate(emotions, 1):
        config = MusicGenerator.EMOTIONS[key]
        print(f"  {i}. {config['name']} ({key}) - {config['description']}")
    
    choice = input(f"\n选择 (1-{len(emotions)}, 默认 1): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(emotions):
        emotion = emotions[int(choice) - 1]
    else:
        emotion = "peaceful"
    
    # 时长
    duration_input = input("\n⏱️ 时长(秒, 默认 30): ").strip()
    duration = int(duration_input) if duration_input.isdigit() else 30
    
    return topic, emotion, duration


def main():
    # 检查依赖
    if not SOUNDFONT_PATH:
        print("❌ 没有找到 SoundFont 文件")
        print(f"请将 .sf2 文件放到: {SOUNDFONTS_DIR}")
        return
    
    if not FLUIDSYNTH_PATH:
        print("❌ 没有找到 FluidSynth")
        print(f"请将 fluidsynth.exe 放到: {SOUNDFONTS_DIR}/fluidsynth/bin/")
        return
    
    # 获取参数
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h"]:
        print("""
用法:
  python music_generator_cli.py              # 交互式模式
  python music_generator_cli.py --quick "主题" "情绪" 30  # 快速生成

情绪: peaceful, melancholic, joyful, epic, mysterious
        """)
        return
    
    # 快速模式
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        topic = sys.argv[2] if len(sys.argv) > 2 else "星辰大海"
        emotion = sys.argv[3] if len(sys.argv) > 3 else "peaceful"
        duration = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else 30
    else:
        topic, emotion, duration = interactive_mode()
    
    # 生成音乐
    print("\n" + "=" * 60)
    print("   🎵 开始创作...")
    print("=" * 60)
    
    generator = MusicGenerator()
    result = generator.create_music(topic, emotion, duration)
    
    if result["status"] == "success":
        print("\n" + "=" * 60)
        print("   ✅ 音乐创作完成！")
        print("=" * 60)
        print(f"\n📁 音频: {result['audio_file']}")
        print(f"📝 歌词: {result['lyrics_file']}")
        print(f"📊 大小: {result['size_kb']:.1f} KB")
        print(f"⏱️ 时长: {result['duration']} 秒")
        
        # 显示歌词预览
        lyrics = result.get("lyrics", {})
        if lyrics:
            print(f"\n📝 歌词预览:")
            print(f"   标题: {lyrics.get('title', '未命名')}")
            for section, lines in lyrics.get("structure", {}).items():
                if lines:
                    print(f"\n   [{section.upper()}]")
                    for line in lines[:3]:
                        print(f"      {line}")
                    if len(lines) > 3:
                        print(f"      ... ({len(lines) - 3} 行)")
        
        # 自动播放
        try:
            audio_path = Path(result['audio_file'])
            if sys.platform == "win32":
                os.startfile(str(audio_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(audio_path)])
            else:
                subprocess.run(["xdg-open", str(audio_path)])
            print("\n🎵 正在播放...")
        except:
            print("\n💡 请手动打开播放器播放")
    else:
        print(f"\n❌ 生成失败: {result.get('message', '未知错误')}")

if __name__ == "__main__":
    main()