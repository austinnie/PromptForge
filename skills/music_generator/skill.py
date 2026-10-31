"""
music_generator - AI 音乐大师 Skill（融合版）

后端优先级（自动检测）：
  A. SymphonyGenerator  → MIDI (40+ 乐器 × 13 编曲) → FluidSynth → MP3
     需要: soundfonts/*.sf2 + fluidsynth.exe + (可选) ffmpeg
  B. numpy_wav          → 直接合成 WAV（零依赖兜底）
  C. musicgen           → transformers + GPU 高质量（可选）

所有后端都可以跑通，最差情况用 numpy 也能出声。
"""

from __future__ import annotations

import io
import logging
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 依赖探测
# ============================================================

def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _soundfonts_dir() -> Path:
    return Path(__file__).resolve().parent / "soundfonts"


def _find_soundfont() -> Optional[Path]:
    d = _soundfonts_dir()
    for name in ("GeneralUser-GS.sf2", "SGM-V2.01.sf2", "FluidR3_GM.sf2"):
        p = d / name
        if p.exists():
            return p
    return None


def _find_fluidsynth() -> Optional[Path]:
    candidates = [
        _soundfonts_dir() / "fluidsynth-v2.6.0-win10-x64-cpp11" / "bin" / "fluidsynth.exe",
        Path("C:/Program Files/FluidSynth/bin/fluidsynth.exe"),
        Path("C:/Program Files (x86)/FluidSynth/bin/fluidsynth.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _has_ffmpeg() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def detect_hardware() -> Dict[str, Any]:
    """探测所有可用后端。"""
    hw: Dict[str, Any] = {
        "numpy": False,
        "soundfont": None,
        "fluidsynth": None,
        "ffmpeg": False,
        "torch": False,
        "cuda": False,
        "transformers": False,
        "recommended": "none",
        "backends": [],
    }

    try:
        import numpy  # noqa
        hw["numpy"] = True
    except ImportError:
        return hw

    hw["soundfont"] = _find_soundfont()
    hw["fluidsynth"] = _find_fluidsynth()
    hw["ffmpeg"] = _has_ffmpeg()

    try:
        import torch
        hw["torch"] = True
        hw["cuda"] = torch.cuda.is_available()
    except ImportError:
        pass
    try:
        import transformers  # noqa
        hw["transformers"] = True
    except ImportError:
        pass

    # 构建可用后端列表
    if hw["soundfont"] and hw["fluidsynth"]:
        hw["backends"].append("symphony")
    if hw["numpy"]:
        hw["backends"].append("numpy_wav")
    if hw["torch"] and hw["cuda"] and hw["transformers"]:
        hw["backends"].append("musicgen")

    hw["recommended"] = hw["backends"][0] if hw["backends"] else "none"

    return hw


# ============================================================
# 常量：乐器 / 编曲 / 情绪 / 和弦
# ============================================================

INSTRUMENTS = {
    "piano": {"program": 0, "name": "钢琴"},
    "piano_bright": {"program": 1, "name": "明亮钢琴"},
    "electric_piano": {"program": 4, "name": "电钢琴"},
    "harpsichord": {"program": 6, "name": "大键琴"},
    "organ": {"program": 19, "name": "管风琴"},
    "accordion": {"program": 21, "name": "手风琴"},
    "violin": {"program": 40, "name": "小提琴"},
    "viola": {"program": 41, "name": "中提琴"},
    "cello": {"program": 42, "name": "大提琴"},
    "contrabass": {"program": 43, "name": "低音提琴"},
    "strings": {"program": 48, "name": "弦乐合奏"},
    "slow_strings": {"program": 49, "name": "慢板弦乐"},
    "pizzicato": {"program": 45, "name": "拨弦"},
    "harp": {"program": 46, "name": "竖琴"},
    "flute": {"program": 73, "name": "长笛"},
    "piccolo": {"program": 72, "name": "短笛"},
    "oboe": {"program": 68, "name": "双簧管"},
    "clarinet": {"program": 71, "name": "单簧管"},
    "bassoon": {"program": 70, "name": "巴松管"},
    "saxophone": {"program": 65, "name": "萨克斯"},
    "trumpet": {"program": 56, "name": "小号"},
    "trombone": {"program": 57, "name": "长号"},
    "tuba": {"program": 58, "name": "大号"},
    "french_horn": {"program": 60, "name": "法国圆号"},
    "brass": {"program": 61, "name": "铜管合奏"},
    "acoustic_guitar": {"program": 24, "name": "原声吉他"},
    "clean_guitar": {"program": 27, "name": "清音吉他"},
    "overdriven_guitar": {"program": 29, "name": "过载吉他"},
    "distortion_guitar": {"program": 30, "name": "失真吉他"},
    "acoustic_bass": {"program": 32, "name": "原声贝斯"},
    "electric_bass": {"program": 33, "name": "电贝斯"},
    "slap_bass": {"program": 34, "name": "击弦贝斯"},
    "synth_pad": {"program": 88, "name": "合成器"},
    "synth_lead": {"program": 80, "name": "合成主音"},
    "synth_bass": {"program": 39, "name": "合成贝斯"},
    "choir": {"program": 52, "name": "合唱"},
    "synth_voice": {"program": 54, "name": "合成人声"},
    "timpani": {"program": 47, "name": "定音鼓"},
    "vibraphone": {"program": 11, "name": "颤音琴"},
    "marimba": {"program": 12, "name": "马林巴"},
    "xylophone": {"program": 13, "name": "木琴"},
    "erhu": {"program": 110, "name": "二胡"},
    "pipa": {"program": 106, "name": "琵琶"},
    "gu_zheng": {"program": 107, "name": "古筝"},
    "di_zi": {"program": 72, "name": "笛子"},
    "harmonica": {"program": 22, "name": "口琴"},
    "pan_flute": {"program": 75, "name": "排笛"},
}


ARRANGEMENTS = {
    "symphony": {
        "name": "交响乐", "mood": "庄重、宏大",
        "tracks": [
            {"instrument": "strings", "role": "和弦"},
            {"instrument": "violin", "role": "旋律", "octave_offset": 12},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "flute", "role": "装饰", "octave_offset": 12},
            {"instrument": "harp", "role": "琶音"},
            {"instrument": "brass", "role": "和声"},
        ],
    },
    "piano_orchestra": {
        "name": "钢琴协奏", "mood": "优雅、深情",
        "tracks": [
            {"instrument": "piano", "role": "主旋律"},
            {"instrument": "strings", "role": "伴奏"},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "harp", "role": "装饰"},
        ],
    },
    "string_quartet": {
        "name": "弦乐四重奏", "mood": "典雅、细腻",
        "tracks": [
            {"instrument": "violin", "role": "旋律", "octave_offset": 12},
            {"instrument": "viola", "role": "和声"},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "contrabass", "role": "根音", "octave_offset": -24},
        ],
    },
    "epic": {
        "name": "史诗", "mood": "壮丽、震撼",
        "tracks": [
            {"instrument": "strings", "role": "主旋律"},
            {"instrument": "brass", "role": "和声"},
            {"instrument": "trumpet", "role": "旋律", "octave_offset": 12},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "timpani", "role": "打击"},
            {"instrument": "choir", "role": "和声"},
        ],
    },
    "chinese": {
        "name": "中国风", "mood": "诗意、典雅",
        "tracks": [
            {"instrument": "gu_zheng", "role": "主旋律"},
            {"instrument": "erhu", "role": "和声"},
            {"instrument": "di_zi", "role": "旋律", "octave_offset": 12},
            {"instrument": "harp", "role": "伴奏"},
            {"instrument": "pipa", "role": "装饰"},
        ],
    },
    "jazz": {
        "name": "爵士", "mood": "慵懒、优雅",
        "tracks": [
            {"instrument": "piano", "role": "和弦"},
            {"instrument": "electric_bass", "role": "低音", "octave_offset": -12},
            {"instrument": "saxophone", "role": "主旋律"},
            {"instrument": "vibraphone", "role": "装饰"},
        ],
    },
    "rock": {
        "name": "摇滚", "mood": "力量、激情",
        "tracks": [
            {"instrument": "distortion_guitar", "role": "主旋律"},
            {"instrument": "electric_bass", "role": "低音", "octave_offset": -12},
            {"instrument": "piano_bright", "role": "和弦"},
            {"instrument": "organ", "role": "伴奏"},
        ],
    },
    "electronic": {
        "name": "电子", "mood": "未来、科技",
        "tracks": [
            {"instrument": "synth_lead", "role": "主旋律"},
            {"instrument": "synth_bass", "role": "低音", "octave_offset": -12},
            {"instrument": "synth_pad", "role": "伴奏"},
            {"instrument": "electric_piano", "role": "和弦"},
        ],
    },
    "new_age": {
        "name": "新世纪", "mood": "空灵、治愈",
        "tracks": [
            {"instrument": "piano", "role": "主旋律"},
            {"instrument": "flute", "role": "旋律", "octave_offset": 12},
            {"instrument": "harp", "role": "伴奏"},
            {"instrument": "synth_pad", "role": "和弦"},
            {"instrument": "choir", "role": "和声"},
        ],
    },
    "folk": {
        "name": "民谣", "mood": "温暖、亲切",
        "tracks": [
            {"instrument": "acoustic_guitar", "role": "伴奏"},
            {"instrument": "piano", "role": "主旋律"},
            {"instrument": "harmonica", "role": "装饰"},
            {"instrument": "strings", "role": "伴奏"},
        ],
    },
    "baroque": {
        "name": "巴洛克", "mood": "典雅、华丽",
        "tracks": [
            {"instrument": "harpsichord", "role": "主旋律"},
            {"instrument": "violin", "role": "旋律", "octave_offset": 12},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "flute", "role": "装饰", "octave_offset": 12},
        ],
    },
    "tango": {
        "name": "探戈", "mood": "热情、戏剧",
        "tracks": [
            {"instrument": "accordion", "role": "主旋律"},
            {"instrument": "violin", "role": "和声"},
            {"instrument": "piano", "role": "和弦"},
            {"instrument": "contrabass", "role": "低音", "octave_offset": -24},
        ],
    },
    "chamber": {
        "name": "室内乐", "mood": "优雅、精致",
        "tracks": [
            {"instrument": "violin", "role": "主旋律", "octave_offset": 12},
            {"instrument": "cello", "role": "低音", "octave_offset": -12},
            {"instrument": "piano", "role": "伴奏"},
            {"instrument": "harp", "role": "装饰"},
        ],
    },
}


EMOTION_CONFIG = {
    "peaceful":   {"tempo": 70,  "scale": [0, 2, 4, 6, 8, 10],       "name": "宁静"},
    "melancholic":{"tempo": 80,  "scale": [0, 2, 3, 5, 7, 8, 10],    "name": "深情"},
    "joyful":     {"tempo": 120, "scale": [0, 2, 4, 5, 7, 9, 11],    "name": "欢乐"},
    "epic":       {"tempo": 110, "scale": [0, 2, 4, 5, 7, 9, 11],    "name": "壮丽"},
    "mysterious": {"tempo": 90,  "scale": [0, 1, 3, 6, 8, 10],       "name": "神秘"},
    "romantic":   {"tempo": 85,  "scale": [0, 2, 3, 5, 7, 9, 11],    "name": "浪漫"},
    "energetic":  {"tempo": 140, "scale": [0, 2, 4, 5, 7, 9, 11],    "name": "活力"},
}


CHORD_PROGRESSIONS = {
    "peaceful":   [[0,4,7],[0,4,7],[5,9,12],[5,9,12],[0,4,7],[0,4,7],[7,11,14],[0,4,7]],
    "melancholic":[[0,3,7],[5,8,12],[3,7,10],[0,3,7],[5,8,12],[3,7,10],[8,11,15],[0,3,7]],
    "joyful":     [[0,4,7],[2,6,9],[4,8,11],[5,9,12],[0,4,7],[5,9,12],[7,11,14],[0,4,7]],
    "epic":       [[0,4,7],[5,9,12],[7,11,14],[0,4,7],[5,9,12],[7,11,14],[0,4,7],[4,8,11]],
    "mysterious": [[0,4,7],[3,7,10],[0,4,7],[5,9,12],[8,12,15],[3,7,10],[5,9,12],[0,4,7]],
    "romantic":   [[0,4,7],[5,9,12],[2,6,9],[7,11,14],[0,4,7],[5,9,12],[7,11,14],[0,4,7]],
    "energetic":  [[0,4,7],[7,11,14],[5,9,12],[0,4,7],[0,4,7],[7,11,14],[5,9,12],[0,4,7]],
}


# ============================================================
# SymphonyGenerator（安全版：不 sys.exit，依赖缺失返回 None）
# ============================================================

class SymphonyGenerator:
    """多乐器交响乐生成器（FluidSynth + SoundFont）。"""

    def __init__(self, soundfont: Path, fluidsynth: Path):
        self.soundfont = soundfont
        self.fluidsynth = fluidsynth

    # ---------- MIDI 生成 ----------

    def _generate_midi_data(
        self,
        emotion: str,
        duration: int,
        arrangement_name: str,
        complexity: int = 1,
    ) -> Optional[bytes]:
        try:
            from midiutil import MIDIFile
        except ImportError:
            logger.warning("midiutil 未安装（pip install midiutil）")
            return None

        arrangement = ARRANGEMENTS.get(arrangement_name, ARRANGEMENTS["symphony"])
        config = EMOTION_CONFIG.get(emotion, EMOTION_CONFIG["epic"])
        chords = CHORD_PROGRESSIONS.get(emotion, CHORD_PROGRESSIONS["epic"])
        scale = config["scale"]
        tempo = config["tempo"]
        base_note = 60

        num_tracks = max(1, len(arrangement["tracks"]))
        midi = MIDIFile(num_tracks)

        for track_idx, track_info in enumerate(arrangement["tracks"]):
            inst = INSTRUMENTS.get(track_info["instrument"])
            if not inst:
                continue

            midi.addTempo(track_idx, 0, tempo)
            midi.addProgramChange(track_idx, 0, 0, inst["program"])

            self._generate_track(
                midi, track_idx, track_info,
                chords, scale, base_note, duration, tempo, complexity,
            )

        buf = io.BytesIO()
        midi.writeFile(buf)
        return buf.getvalue()

    def _generate_track(
        self, midi, track_idx, track_info,
        chords, scale, base_note, duration, tempo, complexity,
    ):
        volume = track_info.get("volume", 85)
        octave_offset = track_info.get("octave_offset", 0)
        role = track_info.get("role", "旋律")

        total_beats = duration * (tempo / 60)
        current_beat = 0
        chord_idx = 0
        beat_per_chord = 4
        density = 1.0 + (complexity - 1) * 0.3

        if role in ("主旋律", "旋律", "第一小提琴"):
            while current_beat < total_beats:
                note_offset = random.choice(scale)
                octave = octave_offset + (random.choice([0, 12]) if random.random() < 0.3 else 0)
                pitch = base_note + note_offset + octave
                dur = random.choice([0.5, 0.5, 1.0, 0.25]) * density
                if 0 <= pitch <= 127:
                    midi.addNote(track_idx, 0, pitch, current_beat, dur, int(volume))
                chord_idx += 1
                current_beat += beat_per_chord / 2

        elif role in ("和弦", "和声", "伴奏"):
            while current_beat < total_beats:
                chord = chords[chord_idx % len(chords)]
                dur = min(beat_per_chord, total_beats - current_beat)
                for note_offset in chord:
                    pitch = base_note + note_offset + octave_offset
                    if 0 <= pitch <= 127:
                        midi.addNote(track_idx, 0, pitch, current_beat, dur, int(volume * 0.9))
                chord_idx += 1
                current_beat += beat_per_chord

        elif role in ("低音", "根音"):
            while current_beat < total_beats:
                chord = chords[chord_idx % len(chords)]
                dur = min(beat_per_chord, total_beats - current_beat)
                root = base_note + chord[0] + octave_offset
                if 0 <= root <= 127:
                    midi.addNote(track_idx, 0, root, current_beat, dur, int(volume * 0.9))
                chord_idx += 1
                current_beat += beat_per_chord

        elif role == "打击":
            beat = 0
            while beat < total_beats:
                if beat % 2 == 0:
                    pitch = base_note + 47
                    midi.addNote(track_idx, 0, pitch, beat, 0.5, int(volume * 0.9))
                beat += 1

        else:  # 装饰/琶音
            beat = 0
            while beat < total_beats:
                if random.random() < 0.2 * density:
                    note_offset = random.choice(scale)
                    pitch = base_note + note_offset + octave_offset
                    dur = random.choice([0.25, 0.5])
                    if 0 <= pitch <= 127:
                        midi.addNote(track_idx, 0, pitch, beat, dur, int(volume * 0.7))
                beat += 0.5

    # ---------- MIDI → 音频 ----------

    def _synthesize(self, midi_data: bytes) -> Optional[Tuple[bytes, str]]:
        """返回 (audio_bytes, format) — format 为 "mp3" 或 "wav"。"""
        if not midi_data:
            return None

        tmp_midi = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
        tmp_midi.write(midi_data)
        tmp_midi.close()

        tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_wav.close()

        tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_mp3.close()

        try:
            # FluidSynth 两种命令格式都试
            for cmd in (
                [str(self.fluidsynth), "-ni", "-F", tmp_wav.name, "-r", "44100",
                 str(self.soundfont), tmp_midi.name],
                [str(self.fluidsynth), "-ni", str(self.soundfont),
                 tmp_midi.name, "-F", tmp_wav.name, "-r", "44100"],
            ):
                try:
                    r = subprocess.run(
                        cmd, capture_output=True, timeout=120,
                        cwd=str(self.fluidsynth.parent),
                    )
                    if r.returncode == 0 and os.path.getsize(tmp_wav.name) > 1000:
                        break
                except Exception:
                    continue

            if not os.path.exists(tmp_wav.name) or os.path.getsize(tmp_wav.name) < 1000:
                logger.warning("FluidSynth 合成失败")
                return None

            # 尝试 WAV → MP3
            try:
                r = subprocess.run(
                    ["ffmpeg", "-i", tmp_wav.name, "-b:a", "192k",
                     "-af", "volume=4", "-y", tmp_mp3.name],
                    capture_output=True, timeout=60,
                )
                if r.returncode == 0 and os.path.getsize(tmp_mp3.name) > 1000:
                    return Path(tmp_mp3.name).read_bytes(), "mp3"
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"ffmpeg 失败: {e}")

            # 退回到 WAV
            return Path(tmp_wav.name).read_bytes(), "wav"

        finally:
            for p in (tmp_midi.name, tmp_wav.name, tmp_mp3.name):
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except Exception:
                    pass

    # ---------- 主入口 ----------

    def create(
        self, emotion: str, duration: int, arrangement: str, complexity: int = 1,
    ) -> Optional[Tuple[bytes, str]]:
        """返回 (audio_bytes, format)；失败返回 None。"""
        midi = self._generate_midi_data(emotion, duration, arrangement, complexity)
        if not midi:
            return None
        return self._synthesize(midi)


# ============================================================
# numpy 兜底（保留我上一轮的能力，依赖全无时用）
# ============================================================

_A4 = 440.0
_SEMI = 2 ** (1 / 12)
_NOTE_OFFSETS = {
    "C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4,
    "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2,
}


def _freq_from_semitones(semi: int) -> float:
    return _A4 * (_SEMI ** semi)


def _numpy_compose(emotion: str, duration: int, sr: int = 22050):
    """numpy 直接合成简单和弦+琶音+鼓点，返回 int16 的 numpy 数组。"""
    import numpy as np

    config = EMOTION_CONFIG.get(emotion, EMOTION_CONFIG["epic"])
    chords = CHORD_PROGRESSIONS.get(emotion, CHORD_PROGRESSIONS["epic"])
    tempo = config["tempo"]

    total_samples = duration * sr
    audio = np.zeros(total_samples, dtype=np.float32)

    chord_dur = 2.0
    cursor = 0
    idx = 0
    while cursor < duration:
        chord = chords[idx % len(chords)]
        chord_len = min(chord_dur, duration - cursor)
        n = int(chord_len * sr)
        t = np.arange(n) / sr

        wave = np.zeros(n, dtype=np.float32)
        for i, off in enumerate(chord):
            f = _freq_from_semitones(off)
            wave += (0.3 if i == 0 else 0.2) * np.sin(2 * np.pi * f * t)

        # 高八度琶音
        arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12]
        arp_n = n // len(arp)
        for j, off in enumerate(arp):
            start = j * arp_n
            end = min(start + arp_n, n)
            if end <= start:
                continue
            at = np.arange(end - start) / sr
            f = _freq_from_semitones(off)
            wave[start:end] += 0.15 * np.sin(2 * np.pi * f * at)

        # ADSR
        a = int(0.05 * n)
        d = int(0.1 * n)
        r = int(0.1 * n)
        s = max(0, n - a - d - r)
        env = np.concatenate([
            np.linspace(0, 1, a) if a else np.array([], dtype=np.float32),
            np.linspace(1, 0.7, d) if d else np.array([], dtype=np.float32),
            np.full(s, 0.7, dtype=np.float32),
            np.linspace(0.7, 0, r) if r else np.array([], dtype=np.float32),
        ]).astype(np.float32)
        if len(env) < n:
            env = np.pad(env, (0, n - len(env)))
        env = env[:n]
        wave *= env

        start_s = int(cursor * sr)
        end_s = start_s + n
        if end_s > total_samples:
            end_s = total_samples
            wave = wave[:end_s - start_s]
        audio[start_s:end_s] += wave

        cursor += chord_len
        idx += 1

    # 归一化
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.85

    # 淡入淡出
    fade = int(0.5 * sr)
    if fade < total_samples // 2:
        audio[:fade] *= np.linspace(0, 1, fade)
        audio[-fade:] *= np.linspace(1, 0, fade)

    return (audio * 32767).astype(np.int16)


def _numpy_to_wav_bytes(pcm: "np.ndarray", sr: int = 22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


# ============================================================
# MusicMaestro：顶层
# ============================================================

class MusicMaestro:
    name = "music_generator"
    version = "2.0.0"

    EMOTIONS = list(EMOTION_CONFIG.keys())
    ARRANGEMENTS = list(ARRANGEMENTS.keys())

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()
        self.hardware = detect_hardware()

        # 建立后端实例
        self._symphony = None
        if "symphony" in self.hardware["backends"]:
            self._symphony = SymphonyGenerator(
                self.hardware["soundfont"], self.hardware["fluidsynth"],
            )

        logger.info(
            f"🎵 MusicMaestro v{self.version} | 后端: {self.hardware['backends']} "
            f"| 推荐: {self.hardware['recommended']}"
        )

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/music",
            "default_language": "zh",
            "default_backend": None,   # None = 自动选
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        start = time.time()

        try:
            topic = (kwargs.get("topic") or "").strip()
            emotion = kwargs.get("emotion") or "epic"
            duration = int(kwargs.get("duration", 30))
            arrangement = kwargs.get("arrangement") or "symphony"
            complexity = int(kwargs.get("complexity", 1))
            language = kwargs.get("language") or self.config["default_language"]
            want_lyrics = bool(kwargs.get("lyrics", True))
            backend_req = kwargs.get("backend") or self.config["default_backend"]

            if not topic:
                return {"status": "error", "error": "topic 不能为空"}

            if emotion not in EMOTION_CONFIG:
                emotion = "epic"
            if arrangement not in ARRANGEMENTS:
                arrangement = "symphony"

            logger.info(
                f"🎵 音乐生成 | topic={topic} emotion={emotion} "
                f"arrangement={arrangement} duration={duration}s"
            )

            # ---- 后端选择 ----
            backend = backend_req
            if not backend:
                backend = self.hardware["recommended"]

            audio_bytes: Optional[bytes] = None
            audio_format = "mp3"
            used_backend = backend

            # 后端 A：交响乐
            if backend == "symphony" and self._symphony:
                r = self._symphony.create(emotion, duration, arrangement, complexity)
                if r:
                    audio_bytes, audio_format = r
                else:
                    logger.warning("symphony 后端失败，尝试降级")

            # 后端 B：numpy
            if audio_bytes is None and "numpy_wav" in self.hardware["backends"]:
                try:
                    pcm = _numpy_compose(emotion, duration)
                    audio_bytes = _numpy_to_wav_bytes(pcm)
                    audio_format = "wav"
                    used_backend = "numpy_wav"
                    logger.info("✅ numpy 兜底合成完成")
                except Exception as e:
                    logger.warning(f"numpy 兜底失败: {e}")

            if audio_bytes is None:
                return {"status": "error", "error": "所有音乐后端都失败"}

            # ---- 保存音频 ----
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = re.sub(r"[^\w\u4e00-\u9fff]", "_", topic)[:20] or "music"
            filename = f"{emotion}_{arrangement}_{ts}_{safe_topic}.{audio_format}"
            audio_path = Path(self.config["output_dir"]) / filename
            audio_path.write_bytes(audio_bytes)
            logger.info(f"✅ 音频保存: {audio_path} ({len(audio_bytes)//1024} KB)")

            # ---- 歌词（可选）----
            lyrics = None
            lyrics_path = None
            if want_lyrics:
                lyrics = self.generate_lyrics(topic, emotion, arrangement, language)
                if lyrics:
                    lyrics_path = audio_path.with_suffix(".txt")
                    lyrics_path.write_text(
                        f"主题: {topic}\n情绪: {emotion}\n编曲: {ARRANGEMENTS[arrangement]['name']}\n\n{lyrics}",
                        encoding="utf-8",
                    )

            elapsed = f"{time.time() - start:.1f}s"
            logger.info(f"🎉 完成 ({used_backend}) | 耗时 {elapsed}")

            return {
                "status": "success",
                "result": {
                    "audio_file": str(audio_path),
                    "audio_format": audio_format,
                    "lyrics_file": str(lyrics_path) if lyrics_path else None,
                    "lyrics": lyrics,
                    "topic": topic,
                    "emotion": emotion,
                    "emotion_name": EMOTION_CONFIG[emotion]["name"],
                    "arrangement": arrangement,
                    "arrangement_name": ARRANGEMENTS[arrangement]["name"],
                    "duration": duration,
                    "backend": used_backend,
                    "bytes": len(audio_bytes),
                    "elapsed": elapsed,
                },
                "metadata": {"skill": self.name, "version": self.version},
            }

        except Exception as e:
            logger.exception("音乐生成失败")
            return {"status": "error", "error": str(e)}

    # ---------- 歌词 ----------

    def generate_lyrics(
        self, topic: str, emotion: str, arrangement: str, language: str,
    ) -> Optional[str]:
        try:
            from core.llm_client import get_default_client
            llm = get_default_client(temperature=0.85, max_tokens=600, timeout=60)

            lang_name = "中文" if language == "zh" else "English"
            emotion_name = EMOTION_CONFIG[emotion]["name"]
            arrangement_name = ARRANGEMENTS[arrangement]["name"]

            prompt = f"""为「{topic}」这个主题创作一首{lang_name}歌词。

情绪：{emotion_name}
风格：{arrangement_name}

结构（严格遵守）：
[主歌1] 4 行
[副歌] 4 行
[主歌2] 4 行
[副歌] 4 行
[桥段] 2 行
[副歌] 4 行

要求：情感真挚、押韵自然、有画面感。只输出歌词，保留 [主歌]/[副歌]/[桥段] 标签。"""

            raw = llm.generate(prompt)
            return (raw or "").strip() or None
        except Exception as e:
            logger.warning(f"歌词生成失败: {e}")
            return None

    # ---------- 展示 ----------

    def get_name(self) -> str:
        return f"MusicMaestro ({self.hardware['recommended']})"

    def __repr__(self):
        return f"<MusicMaestro(backends={self.hardware['backends']})>"