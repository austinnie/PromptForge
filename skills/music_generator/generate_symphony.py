#!/usr/bin/env python
"""
🎻 AI 交响乐大师 - 多乐器合成（完整版）
支持 10+ 种编曲风格
"""
import sys
import os
import json
import random
import subprocess
from pathlib import Path
from datetime import datetime
import tempfile
import time

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

SOUNDFONTS_DIR = project_root / "skills" / "music_generator" / "soundfonts"
OUTPUT_DIR = project_root / "skills" / "music_generator" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOUNDFONT_PATHS = [
    SOUNDFONTS_DIR / "SGM-V2.01.sf2",
    SOUNDFONTS_DIR / "GeneralUser-GS.sf2",
]
SOUNDFONT_PATH = next((p for p in SOUNDFONT_PATHS if p.exists()), None)

FLUIDSYNTH_PATHS = [
    SOUNDFONTS_DIR / "fluidsynth-v2.6.0-win10-x64-cpp11" / "bin" / "fluidsynth.exe",
]
FLUIDSYNTH_PATH = next((p for p in FLUIDSYNTH_PATHS if p.exists()), None)

# ==================== 乐器定义 ====================

INSTRUMENTS = {
    # 键盘类
    "piano": {"program": 0, "name": "钢琴", "family": "keyboard"},
    "piano_bright": {"program": 1, "name": "明亮钢琴", "family": "keyboard"},
    "electric_piano": {"program": 4, "name": "电钢琴", "family": "keyboard"},
    "harpsichord": {"program": 6, "name": "大键琴", "family": "keyboard"},
    "organ": {"program": 19, "name": "管风琴", "family": "keyboard"},
    "accordion": {"program": 21, "name": "手风琴", "family": "keyboard"},
    
    # 弦乐
    "violin": {"program": 40, "name": "小提琴", "family": "strings"},
    "viola": {"program": 41, "name": "中提琴", "family": "strings"},
    "cello": {"program": 42, "name": "大提琴", "family": "strings"},
    "contrabass": {"program": 43, "name": "低音提琴", "family": "strings"},
    "strings": {"program": 48, "name": "弦乐合奏", "family": "strings"},
    "slow_strings": {"program": 49, "name": "慢板弦乐", "family": "strings"},
    "pizzicato": {"program": 45, "name": "拨弦", "family": "strings"},
    "harp": {"program": 46, "name": "竖琴", "family": "strings"},
    
    # 木管
    "flute": {"program": 73, "name": "长笛", "family": "woodwind"},
    "piccolo": {"program": 72, "name": "短笛", "family": "woodwind"},
    "oboe": {"program": 68, "name": "双簧管", "family": "woodwind"},
    "clarinet": {"program": 71, "name": "单簧管", "family": "woodwind"},
    "bassoon": {"program": 70, "name": "巴松管", "family": "woodwind"},
    "saxophone": {"program": 65, "name": "萨克斯", "family": "woodwind"},
    
    # 铜管
    "trumpet": {"program": 56, "name": "小号", "family": "brass"},
    "trombone": {"program": 57, "name": "长号", "family": "brass"},
    "tuba": {"program": 58, "name": "大号", "family": "brass"},
    "french_horn": {"program": 60, "name": "法国圆号", "family": "brass"},
    "brass": {"program": 61, "name": "铜管合奏", "family": "brass"},
    
    # 吉他
    "acoustic_guitar": {"program": 24, "name": "原声吉他", "family": "guitar"},
    "clean_guitar": {"program": 27, "name": "清音吉他", "family": "guitar"},
    "overdriven_guitar": {"program": 29, "name": "过载吉他", "family": "guitar"},
    "distortion_guitar": {"program": 30, "name": "失真吉他", "family": "guitar"},
    
    # 贝斯
    "acoustic_bass": {"program": 32, "name": "原声贝斯", "family": "bass"},
    "electric_bass": {"program": 33, "name": "电贝斯", "family": "bass"},
    "slap_bass": {"program": 34, "name": "击弦贝斯", "family": "bass"},
    
    # 合成器
    "synth_pad": {"program": 88, "name": "合成器", "family": "synth"},
    "synth_lead": {"program": 80, "name": "合成主音", "family": "synth"},
    "synth_bass": {"program": 39, "name": "合成贝斯", "family": "synth"},
    
    # 人声
    "choir": {"program": 52, "name": "合唱", "family": "vocal"},
    "synth_voice": {"program": 54, "name": "合成人声", "family": "vocal"},
    
    # 打击
    "timpani": {"program": 47, "name": "定音鼓", "family": "percussion"},
    "vibraphone": {"program": 11, "name": "颤音琴", "family": "percussion"},
    "marimba": {"program": 12, "name": "马林巴", "family": "percussion"},
    "xylophone": {"program": 13, "name": "木琴", "family": "percussion"},
    
    # 民族乐器
    "erhu": {"program": 110, "name": "二胡", "family": "ethnic"},
    "pipa": {"program": 106, "name": "琵琶", "family": "ethnic"},
    "gu_zheng": {"program": 107, "name": "古筝", "family": "ethnic"},
    "di_zi": {"program": 72, "name": "笛子", "family": "ethnic"},  # 用短笛代替
    
    # 其他
    "harmonica": {"program": 22, "name": "口琴", "family": "wind"},
    "recorder": {"program": 74, "name": "竖笛", "family": "wind"},
    "pan_flute": {"program": 75, "name": "排笛", "family": "wind"},
}

# ==================== 编曲风格定义 ====================

ARRANGEMENTS = {
    "symphony": {
        "name": "交响乐",
        "description": "完整的管弦乐编制",
        "mood": "庄重、宏大",
        "tracks": [
            {"instrument": "strings", "role": "和弦", "octave_offset": 0},
            {"instrument": "violin", "role": "旋律", "octave_offset": 12},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "flute", "role": "装饰", "octave_offset": 12},
            {"instrument": "harp", "role": "琶音", "octave_offset": 0},
            {"instrument": "brass", "role": "和声", "octave_offset": 0},
        ]
    },
    "piano_orchestra": {
        "name": "钢琴协奏",
        "description": "钢琴为主，弦乐伴奏",
        "mood": "优雅、深情",
        "tracks": [
            {"instrument": "piano", "role": "主旋律", "octave_offset": 0},
            {"instrument": "strings", "role": "伴奏", "octave_offset": 0},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "harp", "role": "装饰", "octave_offset": 0},
        ]
    },
    "string_quartet": {
        "name": "弦乐四重奏",
        "description": "精致典雅的室内乐",
        "mood": "典雅、细腻",
        "tracks": [
            {"instrument": "violin", "role": "第一小提琴", "octave_offset": 12},
            {"instrument": "viola", "role": "第二小提琴", "octave_offset": 0},
            {"instrument": "cello", "role": "大提琴", "octave_offset": -12},
            {"instrument": "contrabass", "role": "低音", "octave_offset": -24},
        ]
    },
    "brass_ensemble": {
        "name": "铜管合奏",
        "description": "雄壮有力的铜管乐",
        "mood": "雄壮、辉煌",
        "tracks": [
            {"instrument": "trumpet", "role": "主旋律", "octave_offset": 0},
            {"instrument": "french_horn", "role": "和声", "octave_offset": 0},
            {"instrument": "trombone", "role": "低音", "octave_offset": -12},
            {"instrument": "tuba", "role": "根音", "octave_offset": -24},
        ]
    },
    "folk": {
        "name": "民谣",
        "description": "温暖亲切的民谣风格",
        "mood": "温暖、亲切",
        "tracks": [
            {"instrument": "acoustic_guitar", "role": "伴奏", "octave_offset": 0},
            {"instrument": "piano", "role": "旋律", "octave_offset": 0},
            {"instrument": "harmonica", "role": "装饰", "octave_offset": 0},
            {"instrument": "strings", "role": "背景", "octave_offset": 0},
        ]
    },
    "epic": {
        "name": "史诗",
        "description": "壮丽的电影配乐风格",
        "mood": "壮丽、震撼",
        "tracks": [
            {"instrument": "strings", "role": "主旋律", "octave_offset": 0},
            {"instrument": "brass", "role": "和声", "octave_offset": 0},
            {"instrument": "trumpet", "role": "高音", "octave_offset": 12},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "timpani", "role": "打击", "octave_offset": 0},
            {"instrument": "choir", "role": "合唱", "octave_offset": 0},
        ]
    },
    
    # ===== 新增风格 =====
    
    "jazz": {
        "name": "爵士乐",
        "description": "慵懒随性的爵士风格",
        "mood": "慵懒、优雅",
        "tracks": [
            {"instrument": "piano", "role": "和弦", "octave_offset": 0},
            {"instrument": "electric_bass", "role": "低音", "octave_offset": -12},
            {"instrument": "saxophone", "role": "主旋律", "octave_offset": 0},
            {"instrument": "vibraphone", "role": "装饰", "octave_offset": 0},
        ]
    },
    "rock": {
        "name": "摇滚乐",
        "description": "充满力量的摇滚风格",
        "mood": "力量、激情",
        "tracks": [
            {"instrument": "distortion_guitar", "role": "主旋律", "octave_offset": 0},
            {"instrument": "electric_bass", "role": "低音", "octave_offset": -12},
            {"instrument": "piano_bright", "role": "和弦", "octave_offset": 0},
            {"instrument": "organ", "role": "背景", "octave_offset": 0},
        ]
    },
    "electronic": {
        "name": "电子音乐",
        "description": "现代电子音乐风格",
        "mood": "未来、科技",
        "tracks": [
            {"instrument": "synth_lead", "role": "主旋律", "octave_offset": 0},
            {"instrument": "synth_bass", "role": "低音", "octave_offset": -12},
            {"instrument": "synth_pad", "role": "背景", "octave_offset": 0},
            {"instrument": "electric_piano", "role": "和弦", "octave_offset": 0},
        ]
    },
    "chinese": {
        "name": "中国风",
        "description": "东方韵味民族风格",
        "mood": "诗意、典雅",
        "tracks": [
            {"instrument": "gu_zheng", "role": "主旋律", "octave_offset": 0},
            {"instrument": "erhu", "role": "和声", "octave_offset": 0},
            {"instrument": "di_zi", "role": "装饰", "octave_offset": 12},
            {"instrument": "harp", "role": "背景", "octave_offset": 0},
            {"instrument": "pipa", "role": "伴奏", "octave_offset": 0},
        ]
    },
    "wind_ensemble": {
        "name": "管乐合奏",
        "description": "木管与铜管的对话",
        "mood": "清新、明亮",
        "tracks": [
            {"instrument": "flute", "role": "主旋律", "octave_offset": 12},
            {"instrument": "oboe", "role": "和声", "octave_offset": 0},
            {"instrument": "clarinet", "role": "伴奏", "octave_offset": 0},
            {"instrument": "bassoon", "role": "低音", "octave_offset": -12},
            {"instrument": "french_horn", "role": "背景", "octave_offset": 0},
        ]
    },
    "chamber": {
        "name": "室内乐",
        "description": "精致小型合奏",
        "mood": "优雅、精致",
        "tracks": [
            {"instrument": "violin", "role": "主旋律", "octave_offset": 12},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "piano", "role": "伴奏", "octave_offset": 0},
            {"instrument": "harp", "role": "装饰", "octave_offset": 0},
        ]
    },
    "new_age": {
        "name": "新世纪",
        "description": "空灵治愈的冥想音乐",
        "mood": "空灵、治愈",
        "tracks": [
            {"instrument": "piano", "role": "主旋律", "octave_offset": 0},
            {"instrument": "flute", "role": "装饰", "octave_offset": 12},
            {"instrument": "harp", "role": "伴奏", "octave_offset": 0},
            {"instrument": "synth_pad", "role": "背景", "octave_offset": 0},
            {"instrument": "choir", "role": "和声", "octave_offset": 0},
        ]
    },
    "tango": {
        "name": "探戈",
        "description": "热情戏剧的探戈风格",
        "mood": "热情、戏剧性",
        "tracks": [
            {"instrument": "accordion", "role": "主旋律", "octave_offset": 0},
            {"instrument": "violin", "role": "和声", "octave_offset": 0},
            {"instrument": "piano", "role": "节奏", "octave_offset": 0},
            {"instrument": "contrabass", "role": "低音", "octave_offset": -24},
            {"instrument": "strings", "role": "背景", "octave_offset": 0},
        ]
    },
    "baroque": {
        "name": "巴洛克",
        "description": "古典巴洛克风格",
        "mood": "典雅、华丽",
        "tracks": [
            {"instrument": "harpsichord", "role": "主旋律", "octave_offset": 0},
            {"instrument": "violin", "role": "和声", "octave_offset": 12},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "flute", "role": "装饰", "octave_offset": 12},
        ]
    },
}

# ==================== 情绪配置 ====================

EMOTION_CONFIG = {
    "peaceful": {"tempo": 70, "scale": [0, 2, 4, 6, 8, 10], "name": "宁静"},
    "melancholic": {"tempo": 80, "scale": [0, 2, 3, 5, 7, 8, 10], "name": "深情"},
    "joyful": {"tempo": 120, "scale": [0, 2, 4, 5, 7, 9, 11], "name": "欢乐"},
    "epic": {"tempo": 110, "scale": [0, 2, 4, 5, 7, 9, 11], "name": "壮丽"},
    "mysterious": {"tempo": 90, "scale": [0, 1, 3, 6, 8, 10], "name": "神秘"},
    "romantic": {"tempo": 85, "scale": [0, 2, 3, 5, 7, 9, 11], "name": "浪漫"},
    "energetic": {"tempo": 140, "scale": [0, 2, 4, 5, 7, 9, 11], "name": "活力"},
}

# ==================== 和弦进行 ====================

CHORD_PROGRESSIONS = {
    "peaceful": [[0, 4, 7], [0, 4, 7], [5, 9, 12], [5, 9, 12], [0, 4, 7], [0, 4, 7], [7, 11, 14], [0, 4, 7]],
    "melancholic": [[0, 3, 7], [5, 8, 12], [3, 7, 10], [0, 3, 7], [5, 8, 12], [3, 7, 10], [8, 11, 15], [0, 3, 7]],
    "joyful": [[0, 4, 7], [2, 6, 9], [4, 8, 11], [5, 9, 12], [0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7]],
    "epic": [[0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7], [4, 8, 11]],
    "mysterious": [[0, 4, 7], [3, 7, 10], [0, 4, 7], [5, 9, 12], [8, 12, 15], [3, 7, 10], [5, 9, 12], [0, 4, 7]],
    "romantic": [[0, 4, 7], [5, 9, 12], [2, 6, 9], [7, 11, 14], [0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7]],
    "energetic": [[0, 4, 7], [7, 11, 14], [5, 9, 12], [0, 4, 7], [0, 4, 7], [7, 11, 14], [5, 9, 12], [0, 4, 7]],
}

# ==================== 交响乐生成引擎 ====================

class SymphonyGenerator:
    """多乐器交响乐生成器"""
    
    def __init__(self):
        self.soundfont = SOUNDFONT_PATH
        self.fluidsynth = FLUIDSYNTH_PATH
        self._check_dependencies()
    
    def _check_dependencies(self):
        if not self.soundfont:
            print("❌ 没有找到 SoundFont")
            sys.exit(1)
        if not self.fluidsynth:
            print("❌ 没有找到 FluidSynth")
            sys.exit(1)
        print(f"✅ SoundFont: {self.soundfont.name}")
        print(f"✅ FluidSynth: {self.fluidsynth}")
    
    def generate_symphony_midi(self, emotion: str, duration: int, arrangement_name: str, complexity: int = 1) -> bytes:
        """生成多乐器交响乐 MIDI"""
        try:
            from midiutil import MIDIFile
        except ImportError:
            print("❌ midiutil 未安装")
            return None
        
        arrangement = ARRANGEMENTS.get(arrangement_name, ARRANGEMENTS["symphony"])
        config = EMOTION_CONFIG.get(emotion, EMOTION_CONFIG["peaceful"])
        chords = CHORD_PROGRESSIONS.get(emotion, CHORD_PROGRESSIONS["peaceful"])
        scale = config["scale"]
        tempo = config["tempo"]
        base_note = 60
        
        num_tracks = len(arrangement["tracks"])
        midi = MIDIFile(num_tracks)
        
        for track_idx, track_info in enumerate(arrangement["tracks"]):
            inst_name = track_info["instrument"]
            inst = INSTRUMENTS.get(inst_name)
            if not inst:
                continue
            
            midi.addTempo(track_idx, 0, tempo)
            midi.addProgramChange(track_idx, 0, 0, inst["program"])
            
            self._generate_track(
                midi, track_idx, track_info, 
                chords, scale, base_note, 
                duration, tempo, complexity
            )
        
        import io
        buffer = io.BytesIO()
        midi.writeFile(buffer)
        return buffer.getvalue()
    
    def _generate_track(self, midi, track_idx, track_info, chords, scale, base_note, duration, tempo, complexity):
        """生成单个轨道的音符"""
        inst_name = track_info["instrument"]
        inst = INSTRUMENTS.get(inst_name)
        if not inst:
            return
        
        volume = track_info.get("volume", 85)
        octave_offset = track_info.get("octave_offset", 0)
        role = track_info.get("role", "旋律")
        
        total_beats = duration * (tempo / 60)
        current_beat = 0
        chord_idx = 0
        beat_per_chord = 4
        channel = 0
        
        # 根据复杂度调整音符密度
        density = 1.0 + (complexity - 1) * 0.3
        
        if role in ["主旋律", "旋律", "第一小提琴"]:
            while current_beat < total_beats:
                chord = chords[chord_idx % len(chords)]
                
                note_offset = random.choice(scale)
                octave = octave_offset + random.choice([0, 12]) if random.random() < 0.3 else octave_offset
                pitch = base_note + note_offset + octave
                dur = random.choice([0.5, 0.5, 1.0, 0.25]) * density
                
                if 0 <= pitch <= 127:
                    midi.addNote(track_idx, channel, pitch, current_beat, dur, int(volume * 1.0))
                
                chord_idx += 1
                current_beat += beat_per_chord / 2
        
        elif role in ["和弦", "和声", "伴奏"]:
            while current_beat < total_beats:
                chord = chords[chord_idx % len(chords)]
                chord_duration = min(beat_per_chord, total_beats - current_beat)
                
                for note_offset in chord:
                    pitch = base_note + note_offset + octave_offset
                    if 0 <= pitch <= 127:
                        midi.addNote(track_idx, channel, pitch, current_beat, chord_duration, int(volume * 0.9))
                
                chord_idx += 1
                current_beat += beat_per_chord
        
        elif role in ["低音", "根音"]:
            while current_beat < total_beats:
                chord = chords[chord_idx % len(chords)]
                chord_duration = min(beat_per_chord, total_beats - current_beat)
                
                root = base_note + chord[0] + octave_offset
                if 0 <= root <= 127:
                    midi.addNote(track_idx, channel, root, current_beat, chord_duration, int(volume * 0.9))
                
                chord_idx += 1
                current_beat += beat_per_chord
        
        elif role == "打击":
            # 定音鼓：只在强拍出现
            beat = 0
            while beat < total_beats:
                if beat % 2 == 0:  # 偶数拍
                    pitch = base_note + 47  # 定音鼓音高
                    midi.addNote(track_idx, channel, pitch, beat, 0.5, int(volume * 0.9))
                beat += 1
        
        else:
            # 装饰
            beat = 0
            while beat < total_beats:
                if random.random() < 0.2 * density:
                    note_offset = random.choice(scale)
                    pitch = base_note + note_offset + octave_offset
                    dur = random.choice([0.25, 0.5])
                    if 0 <= pitch <= 127:
                        midi.addNote(track_idx, channel, pitch, beat, dur, int(volume * 0.7))
                beat += 0.5
    
    def synthesize_to_mp3(self, midi_data: bytes) -> bytes:
        """合成 MIDI 为 MP3"""
        if not midi_data:
            return None
        
        tmp_midi = tempfile.NamedTemporaryFile(suffix='.mid', delete=False)
        tmp_midi.write(midi_data)
        tmp_midi.close()
        
        tmp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        tmp_wav.close()
        
        tmp_mp3 = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        tmp_mp3.close()
        
        try:
            # 方法1
            print("   🔧 尝试合成...")
            cmd1 = [
                str(self.fluidsynth),
                "-ni",
                "-F", tmp_wav.name,
                "-r", "44100",
                str(self.soundfont),
                tmp_midi.name
            ]
            
            result1 = subprocess.run(
                cmd1,
                capture_output=True,
                timeout=120,
                cwd=str(self.fluidsynth.parent)
            )
            
            if result1.returncode != 0 or not os.path.exists(tmp_wav.name) or os.path.getsize(tmp_wav.name) < 1000:
                # 方法2
                cmd2 = [
                    str(self.fluidsynth),
                    "-ni",
                    str(self.soundfont),
                    tmp_midi.name,
                    "-F", tmp_wav.name,
                    "-r", "44100"
                ]
                result1 = subprocess.run(
                    cmd2,
                    capture_output=True,
                    timeout=120,
                    cwd=str(self.fluidsynth.parent)
                )
            
            if not os.path.exists(tmp_wav.name) or os.path.getsize(tmp_wav.name) < 1000:
                return None
            
            # WAV -> MP3
            try:
                cmd_mp3 = [
                    "ffmpeg",
                    "-i", tmp_wav.name,
                    "-b:a", "192k",
                    "-filter:a", "volume=3",
                    "-y",
                    tmp_mp3.name
                ]
                subprocess.run(cmd_mp3, capture_output=True, timeout=30, check=True)
                
                if os.path.exists(tmp_mp3.name) and os.path.getsize(tmp_mp3.name) > 1000:
                    with open(tmp_mp3.name, 'rb') as f:
                        return f.read()
                else:
                    with open(tmp_wav.name, 'rb') as f:
                        return f.read()
                    
            except:
                with open(tmp_wav.name, 'rb') as f:
                    return f.read()
            
        except Exception as e:
            print(f"   ❌ 合成错误: {e}")
            return None
        finally:
            for path in [tmp_midi.name, tmp_wav.name, tmp_mp3.name]:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except:
                    pass
    
    def create_symphony(self, topic: str = "星辰大海", emotion: str = "epic", 
                        duration: int = 30, arrangement: str = "symphony",
                        complexity: int = 1) -> dict:
        """创建交响乐"""
        print(f"\n🎻 创作交响乐: {topic}")
        print(f"  情绪: {EMOTION_CONFIG.get(emotion, {}).get('name', emotion)}")
        print(f"  编曲: {ARRANGEMENTS[arrangement]['name']}")
        print(f"  风格: {ARRANGEMENTS[arrangement]['mood']}")
        print(f"  时长: {duration} 秒")
        print("⏳ 生成中...")
        
        midi_data = self.generate_symphony_midi(emotion, duration, arrangement, complexity)
        if not midi_data:
            return {"status": "error", "message": "MIDI 生成失败"}
        
        mp3_data = self.synthesize_to_mp3(midi_data)
        if not mp3_data:
            return {"status": "error", "message": "MP3 合成失败"}
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"symphony_{emotion}_{arrangement}_{timestamp}.mp3"
        filename = ''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)
        output_path = OUTPUT_DIR / filename
        
        with open(output_path, 'wb') as f:
            f.write(mp3_data)
        
        return {
            "status": "success",
            "audio_file": str(output_path),
            "arrangement": arrangement,
            "arrangement_name": ARRANGEMENTS[arrangement]['name'],
            "emotion": emotion,
            "duration": duration,
            "size_kb": len(mp3_data) / 1024,
            "tracks": len(ARRANGEMENTS[arrangement]["tracks"])
        }


# ==================== CLI ====================

def main():
    print("\n" + "=" * 60)
    print("   🎻 AI 交响乐大师 - 多乐器合成（完整版）")
    print("=" * 60)
    
    # 主题
    topic = input("\n📝 歌曲主题 (默认: 星辰大海): ").strip() or "星辰大海"
    
    # 情绪
    print("\n🎵 选择情绪:")
    emotions = ["peaceful", "melancholic", "joyful", "epic", "mysterious", "romantic", "energetic"]
    names = ["宁静", "深情", "欢乐", "壮丽", "神秘", "浪漫", "活力"]
    for i, (e, n) in enumerate(zip(emotions, names), 1):
        print(f"  {i}. {n} ({e})")
    choice = input(f"选择 (1-{len(emotions)}, 默认 4): ").strip()
    emotion = emotions[int(choice) - 1] if choice.isdigit() and 1 <= int(choice) <= len(emotions) else "epic"
    
    # 编曲风格
    print("\n🎼 选择编曲风格:")
    arr_keys = list(ARRANGEMENTS.keys())
    for i, key in enumerate(arr_keys, 1):
        arr = ARRANGEMENTS[key]
        print(f"  {i:2}. {arr['name']:8} - {arr['description']} ({arr['mood']})")
    choice = input(f"选择 (1-{len(arr_keys)}, 默认 1): ").strip()
    arrangement = arr_keys[int(choice) - 1] if choice.isdigit() and 1 <= int(choice) <= len(arr_keys) else "symphony"
    
    # 时长
    duration = int(input("\n⏱️ 时长(秒, 默认 30): ").strip() or "30")
    
    # 复杂度
    complexity = int(input("\n🎚️ 复杂度 (1-3, 默认 1): ").strip() or "1")
    complexity = max(1, min(3, complexity))
    
    print("\n" + "=" * 60)
    print("   🎻 开始创作交响乐...")
    print("=" * 60)
    
    generator = SymphonyGenerator()
    result = generator.create_symphony(topic, emotion, duration, arrangement, complexity)
    
    if result["status"] == "success":
        print("\n" + "=" * 60)
        print("   ✅ 交响乐创作完成！")
        print("=" * 60)
        print(f"\n📁 音频: {result['audio_file']}")
        print(f"🎼 编曲: {result['arrangement_name']}")
        print(f"🎵 乐器数: {result['tracks']} 种")
        print(f"📊 大小: {result['size_kb']:.1f} KB")
        print(f"⏱️ 时长: {result['duration']} 秒")
        
        # 自动播放
        try:
            if sys.platform == "win32":
                os.startfile(result['audio_file'])
            print("\n🎵 正在播放...")
        except:
            print("\n💡 请手动打开播放器播放")
    else:
        print(f"\n❌ 生成失败: {result.get('message', '未知错误')}")

if __name__ == "__main__":
    main()