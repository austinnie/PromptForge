# skills/music_generator/skill.py
"""
AI 音乐大师 - 智能自适应音乐生成 (完整修复版)
"""
import os
import json
import random
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# ==================== 硬件检测 ====================
def detect_hardware() -> Dict[str, Any]:
    """检测硬件环境"""
    hardware_info = {
        "has_gpu": False,
        "gpu_type": None,
        "gpu_memory": 0,
        "cpu_count": os.cpu_count() or 1,
        "recommended_mode": "midi"
    }
    
    try:
        import torch
        if torch.cuda.is_available():
            hardware_info["has_gpu"] = True
            hardware_info["gpu_type"] = "cuda"
            hardware_info["gpu_memory"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            hardware_info["recommended_mode"] = "musicgen" if hardware_info["gpu_memory"] >= 4 else "midi"
            logger.info(f"✅ 检测到 CUDA GPU: {hardware_info['gpu_memory']:.1f} GB")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            hardware_info["has_gpu"] = True
            hardware_info["gpu_type"] = "mps"
            hardware_info["recommended_mode"] = "musicgen"
            logger.info("✅ 检测到 Apple MPS")
        else:
            logger.info("ℹ️ 未检测到 GPU，使用 CPU 模式")
    except ImportError:
        logger.info("ℹ️ PyTorch 未安装，使用基础模式")
    except Exception as e:
        logger.warning(f"⚠️ 硬件检测异常: {e}")
    
    return hardware_info


# ==================== 音乐引擎 ====================

class MusicEngine:
    """音乐生成引擎 - 支持多种后端"""
    
    # ✅ 修复：正确接收 config 参数
    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            config = {}
        self.config = config
        self.output_dir = Path(self.config.get("output_dir", "./skills/music_generator/output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 检测硬件
        self.hardware = detect_hardware()
        self.mode = self.config.get("music_mode", self.hardware["recommended_mode"])
        
        # 检测可用后端
        self._init_backends()
    
    def _init_backends(self):
        """初始化各个音频生成后端"""
        self.backends = {}
        
        # 1. MIDI 后端
        try:
            from midiutil import MIDIFile
            self.backends["midi"] = {
                "available": True,
                "name": "MIDI 合成器",
                "description": "轻量级 MIDI 生成，任何环境都可运行",
                "quality": "⭐⭐⭐",
                "speed": "极快"
            }
        except ImportError:
            self.backends["midi"] = {"available": False}
            logger.warning("⚠️ midiutil 未安装，请运行: pip install midiutil")
        
        # 2. MusicGen
        try:
            import torch
            from transformers import MusicgenForConditionalGeneration, AutoProcessor
            self.backends["musicgen"] = {
                "available": True,
                "name": "MusicGen (Meta)",
                "description": "AI 生成高质量音乐",
                "quality": "⭐⭐⭐⭐⭐",
                "speed": "中等" if self.hardware["has_gpu"] else "较慢",
                "requires_gpu": True
            }
        except ImportError:
            self.backends["musicgen"] = {"available": False}
            logger.debug("MusicGen 不可用 (需安装: pip install transformers torch)")
    
    def get_available_backends(self) -> List[Dict]:
        """获取所有可用的后端"""
        available = []
        for name, info in self.backends.items():
            if info.get("available", False):
                available.append({
                    "id": name,
                    **info
                })
        return available
    
    # ==================== 增强版旋律生成 ====================
    
    def _generate_advanced_melody(self, emotion: str, duration: int, tempo: int = 120) -> Optional['MIDIFile']:
        """
        生成更丰富的旋律 (内部方法)
        包含和弦进行、旋律线和装饰音
        """
        try:
            from midiutil import MIDIFile
        except ImportError:
            logger.error("❌ midiutil 未安装")
            return None
        
        midi = MIDIFile(2)  # 2个轨道: 0=和弦, 1=旋律
        track_chord = 0
        track_melody = 1
        time_pos = 0
        
        midi.addTempo(track_chord, time_pos, tempo)
        midi.addTempo(track_melody, time_pos, tempo)
        
        # ===== 1. 定义和弦进行 (每个情绪不同) =====
        chord_progressions = {
            "epic": [
                [0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7],
                [5, 9, 12], [7, 11, 14], [0, 4, 7], [4, 8, 11],
            ],
            "joyful": [
                [0, 4, 7], [2, 6, 9], [4, 8, 11], [5, 9, 12],
                [0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7],
            ],
            "melancholic": [
                [0, 3, 7], [5, 8, 12], [3, 7, 10], [0, 3, 7],
                [5, 8, 12], [3, 7, 10], [8, 11, 15], [0, 3, 7],
            ],
            "peaceful": [
                [0, 4, 7], [0, 4, 7], [5, 9, 12], [5, 9, 12],
                [0, 4, 7], [0, 4, 7], [7, 11, 14], [0, 4, 7],
            ],
            "mysterious": [
                [0, 4, 7], [3, 7, 10], [0, 4, 7], [5, 9, 12],
                [8, 12, 15], [3, 7, 10], [5, 9, 12], [0, 4, 7],
            ],
        }
        
        # ===== 2. 定义旋律音阶 =====
        melody_scales = {
            "epic": [0, 2, 4, 5, 7, 9, 11],
            "joyful": [0, 2, 4, 5, 7, 9, 11],
            "melancholic": [0, 2, 3, 5, 7, 8, 10],
            "peaceful": [0, 2, 4, 6, 8, 10],
            "mysterious": [0, 1, 3, 6, 8, 10],
        }
        
        chords = chord_progressions.get(emotion, chord_progressions["epic"])
        scale = melody_scales.get(emotion, melody_scales["epic"])
        base_note = 60  # C4
        
        # ===== 3. 生成音乐 =====
        total_beats = duration * (tempo / 60)
        current_beat = 0
        chord_index = 0
        beat_per_chord = 4
        
        chord_volume = 80
        melody_volume = 70
        chord_channel = 0
        melody_channel = 1
        
        while current_beat < total_beats:
            # ---- 添加和弦 ----
            chord = chords[chord_index % len(chords)]
            chord_duration = min(beat_per_chord, total_beats - current_beat)
            
            # 和弦根音
            root_pitch = base_note + chord[0] - 12
            if 0 <= root_pitch <= 127:
                midi.addNote(track_chord, chord_channel, root_pitch, 
                            current_beat, chord_duration, chord_volume - 20)
            
            # 和弦其他音
            for note_offset in chord:
                pitch = base_note + note_offset
                if 0 <= pitch <= 127:
                    midi.addNote(track_chord, chord_channel, pitch, 
                                current_beat, chord_duration, chord_volume)
            
            # ---- 添加旋律 ----
            beats_in_chord = 0
            while beats_in_chord < beat_per_chord and current_beat + beats_in_chord < total_beats:
                note_idx = random.randint(0, len(scale) - 1)
                octave_shift = random.choice([0, 12, 24]) if random.random() < 0.3 else 0
                melody_pitch = base_note + scale[note_idx] + octave_shift
                note_duration = random.choice([0.5, 0.5, 1.0, 0.25])
                
                if 0 <= melody_pitch <= 127:
                    midi.addNote(track_melody, melody_channel, melody_pitch,
                                current_beat + beats_in_chord, note_duration, melody_volume)
                
                # 装饰音
                if random.random() < 0.08 and beats_in_chord + 0.2 < beat_per_chord:
                    grace_pitch = melody_pitch + random.choice([-2, 2])
                    if 0 <= grace_pitch <= 127:
                        midi.addNote(track_melody, melody_channel, grace_pitch,
                                    current_beat + beats_in_chord + 0.1, 0.15, melody_volume - 30)
                
                beats_in_chord += note_duration
            
            chord_index += 1
            current_beat += beat_per_chord
        
        return midi
    
    def _generate_basic_melody(self, emotion: str, duration: int, kwargs: Dict) -> Optional['MIDIFile']:
        """基础旋律生成"""
        try:
            from midiutil import MIDIFile
        except ImportError:
            return None
        
        midi = MIDIFile(1)
        track = 0
        time_pos = 0
        tempo = kwargs.get("tempo", 120)
        
        midi.addTempo(track, time_pos, tempo)
        
        scale_map = {
            "joyful": ([0, 2, 4, 5, 7, 9, 11], [0.5, 0.5, 1.0, 0.25]),
            "melancholic": ([0, 2, 3, 5, 7, 8, 10], [1.0, 0.5, 0.5, 1.5]),
            "epic": ([0, 2, 4, 7, 9, 11], [0.5, 1.0, 0.75, 0.25]),
            "peaceful": ([0, 2, 4, 6, 8, 10], [1.5, 1.0, 0.5, 2.0]),
            "mysterious": ([0, 1, 3, 6, 8, 10], [1.0, 0.75, 0.5, 1.25])
        }
        
        scale, durations = scale_map.get(emotion, scale_map["peaceful"])
        scale_base = 60
        channel = 0
        volume = kwargs.get("volume", 100)
        
        beats_per_second = tempo / 60
        total_beats = duration * beats_per_second
        current_time = 0
        note_count = 0
        
        while current_time < total_beats and note_count < 500:
            note_idx = random.randint(0, len(scale) - 1)
            octave_shift = random.choice([0, 12, 24])
            pitch = scale_base + scale[note_idx] + octave_shift
            duration_val = random.choice(durations)
            
            if 0 <= pitch <= 127:
                midi.addNote(track, channel, pitch, current_time, duration_val, volume)
            
            current_time += duration_val
            note_count += 1
            
            if random.random() < 0.15 and current_time < total_beats:
                for i in [0, 4, 7]:
                    chord_pitch = pitch - 12 + i
                    if 0 <= chord_pitch <= 127:
                        midi.addNote(track, channel, chord_pitch, current_time - 0.2, 0.5, volume - 30)
        
        return midi
    
    def compose_with_midi(self, emotion: str, duration: int, **kwargs) -> Optional[Path]:
        """使用 MIDI 谱曲"""
        try:
            from midiutil import MIDIFile
        except ImportError:
            logger.error("❌ midiutil 未安装")
            return None
        
        use_enhanced = kwargs.pop("use_enhanced", True)
        
        if use_enhanced:
            logger.info(f"🎼 [MIDI增强模式] 生成丰富旋律...")
            midi = self._generate_advanced_melody(emotion, duration, kwargs.get("tempo", 120))
        else:
            logger.info(f"🎼 [MIDI基础模式] 生成旋律...")
            midi = self._generate_basic_melody(emotion, duration, kwargs)
        
        if midi is None:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        midi_file = self.output_dir / f"melody_{emotion}_{timestamp}.mid"
        
        with open(midi_file, "wb") as f:
            midi.writeFile(f)
        
        logger.info(f"✅ MIDI 生成完成: {midi_file}")
        return midi_file
    
    def compose_with_musicgen(self, prompt: str, duration: int, **kwargs) -> Optional[Path]:
        """使用 MusicGen 生成音乐"""
        try:
            import torch
            from transformers import MusicgenForConditionalGeneration, AutoProcessor
        except ImportError:
            logger.error("❌ MusicGen 未安装")
            return None
        
        logger.info(f"🎼 [MusicGen模式] 生成音乐...")
        logger.info(f"📝 描述: {prompt}")
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.hardware.get("gpu_type") == "mps":
            device = "mps"
        
        logger.info(f"💻 使用设备: {device}")
        
        try:
            model_name = kwargs.get("musicgen_model", "facebook/musicgen-small")
            
            logger.info("📥 加载 MusicGen 模型...")
            model = MusicgenForConditionalGeneration.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32
            )
            processor = AutoProcessor.from_pretrained(model_name)
            
            model = model.to(device)
            model.eval()
            
            inputs = processor(
                text=[prompt],
                padding=True,
                return_tensors="pt"
            ).to(device)
            
            max_new_tokens = min(int(duration * 8.5), 512)
            
            logger.info(f"🎵 正在生成音频 (约 {duration} 秒)...")
            start_time = time.time()
            
            with torch.no_grad():
                audio_values = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.7,
                    guidance_scale=3.0
                )
            
            elapsed = time.time() - start_time
            logger.info(f"✅ 生成完成，用时 {elapsed:.1f} 秒")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"music_{timestamp}.wav"
            
            try:
                import scipy.io.wavfile as wavfile
                import numpy as np
                audio_numpy = audio_values[0].cpu().numpy()
                if np.max(np.abs(audio_numpy)) > 0:
                    audio_numpy = audio_numpy / np.max(np.abs(audio_numpy))
                wavfile.write(output_file, rate=32000, data=audio_numpy.T)
                return output_file
            except ImportError:
                import numpy as np
                audio_numpy = audio_values[0].cpu().numpy()
                with open(output_file, 'wb') as f:
                    f.write(audio_numpy.tobytes())
                return output_file
            
        except Exception as e:
            logger.error(f"❌ MusicGen 生成失败: {e}")
            return None
    
    def generate_music(self, prompt: str, duration: int, emotion: str = "epic", **kwargs) -> Tuple[Optional[Path], str]:
        """智能选择最优方式生成音乐"""
        force_mode = kwargs.get("force_mode")
        use_enhanced = kwargs.get("use_enhanced", True)
        
        # ✅ 重要：从 kwargs 中移除 use_enhanced，避免重复传递
        if "use_enhanced" in kwargs:
            del kwargs["use_enhanced"]
        if "force_mode" in kwargs:
            del kwargs["force_mode"]
        
        if force_mode == "musicgen":
            result = self.compose_with_musicgen(prompt, duration, **kwargs)
            if result:
                return result, "musicgen"
            logger.warning("⚠️ MusicGen 失败，降级到 MIDI")
        
        if self.hardware["has_gpu"] and self.hardware["gpu_memory"] >= 4:
            logger.info("🚀 检测到高性能 GPU，尝试使用 MusicGen...")
            result = self.compose_with_musicgen(prompt, duration, **kwargs)
            if result:
                return result, "musicgen"
        
        logger.info("🎹 使用 MIDI 模式")
        midi_path = self.compose_with_midi(
            emotion=emotion, 
            duration=duration, 
            use_enhanced=use_enhanced,
            **kwargs
        )
        return midi_path, "midi"


# ==================== 核心主类 ====================

class MusicMaestro:
    """顶级音乐大师 - 自适应智能版"""
    
    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            config = {}
        self.config = config
        self.name = "music_generator"
        self.version = "2.0.0"
        
        # ✅ 修复：正确传递 config
        self.engine = MusicEngine(config)
        
        available = self.engine.get_available_backends()
        logger.info(f"🎵 可用音乐引擎: {[b['id'] for b in available]}")
        logger.info(f"💡 推荐模式: {self.engine.hardware['recommended_mode']}")
        
        self._setup_logging()
        logger.info("🎵 音乐大师已就绪")
    
    def _setup_logging(self):
        log_level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _call_ollama(self, prompt: str, timeout: int = 20) -> str:
        """调用 Ollama 生成歌词"""
        try:
            import requests
            ollama_host = self.config.get("ollama_host", "http://localhost:11434")
            ollama_model = self.config.get("ollama_model", "qwen2.5:7b")
            
            # 快速健康检查
            try:
                health_check = requests.get(f"{ollama_host}/api/tags", timeout=3)
                if health_check.status_code != 200:
                    return ""
            except:
                return ""
            
            response = requests.post(
                f"{ollama_host}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.8, "num_predict": 512}
                },
                timeout=timeout
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except:
            return ""
    
    def generate_lyrics(self, topic: str, language: str, emotion: str) -> Dict[str, Any]:
        """生成歌词"""
        logger.info(f"✍️ 正在创作歌词... 主题: {topic}, 语言: {language}")
        
        prompt = f"""创作一首关于 "{topic}" 的歌曲歌词。
情绪: {emotion}。
语言: {language}。
只返回 JSON，格式:
{{"title": "标题", "structure": {{"verse": ["主歌1", "主歌2"], "chorus": ["副歌"], "bridge": ["桥段"]}}, "vocal_style": "风格"}}"""
        
        response = self._call_ollama(prompt, timeout=20)
        
        try:
            if response:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except:
            pass
        
        # 默认歌词
        emotion_names = {
            "joyful": "欢乐",
            "melancholic": "深情",
            "epic": "壮丽",
            "peaceful": "宁静",
            "mysterious": "神秘"
        }
        emo_name = emotion_names.get(emotion, "美丽")
        
        return {
            "title": f"{topic}之歌",
            "structure": {
                "verse": [
                    f"在{emo_name}的{emotion}中，",
                    f"我听见{topic}的呼唤"
                ],
                "chorus": [
                    f"{topic}，如此{emo_name}，",
                    f"让我心潮澎湃"
                ],
                "bridge": [
                    f"在这永恒的旋律中..."
                ]
            },
            "vocal_style": "空灵治愈" if emotion == "peaceful" else "力量激昂"
        }
    
    def _build_music_prompt(self, topic: str, emotion: str) -> str:
        """构建音乐生成提示词"""
        style_map = {
            "joyful": "uplifting, happy, major key, fast tempo",
            "melancholic": "sad, emotional, minor key, slow tempo",
            "epic": "orchestral, grand, powerful, cinematic",
            "peaceful": "calm, ambient, soft, relaxing",
            "mysterious": "dark, ambient, suspenseful, ethereal"
        }
        style = style_map.get(emotion, "beautiful, emotional")
        return f"{style}, about {topic}, instrumental, high quality"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行音乐创作"""
        logger.info(f"🚀 开始创作...")
        
        topic = kwargs.get("topic", "星辰大海")
        emotion = kwargs.get("emotion", "epic")
        language = kwargs.get("language", "zh")
        duration = int(kwargs.get("duration", 30))
        use_enhanced = kwargs.get("use_enhanced", True)
        
        # 1. 生成歌词
        lyrics_data = self.generate_lyrics(topic, language, emotion)
        
        # 2. 构建音乐描述
        music_prompt = self._build_music_prompt(topic, emotion)
        
        # 3. 生成音乐
        logger.info(f"🎯 目标时长: {duration} 秒")
        
        audio_path, mode_used = self.engine.generate_music(
            prompt=music_prompt,
            duration=duration,
            emotion=emotion,
            use_enhanced=use_enhanced,
            force_mode=kwargs.get("force_mode")
        )
        
        # 4. 构建结果
        result = {
            "status": "success" if audio_path else "partial_success",
            "metadata": {
                "skill": self.name,
                "version": self.version,
                "generated_at": datetime.now().isoformat(),
                "mode_used": mode_used,
                "hardware": {
                    "gpu_available": self.engine.hardware["has_gpu"],
                    "gpu_type": self.engine.hardware["gpu_type"],
                    "gpu_memory_gb": self.engine.hardware["gpu_memory"]
                }
            },
            "result": {
                "lyrics": lyrics_data,
                "audio_file": str(audio_path) if audio_path else None,
                "mode_used": mode_used,
                "directory": str(self.engine.output_dir)
            }
        }
        
        if mode_used == "midi" and audio_path:
            result["result"]["note"] = "MIDI 文件已生成，请使用 MIDI 播放器打开"
        
        logger.info("🎶 创作完成！")
        return result
    
    def __repr__(self):
        return f"<MusicMaestro(name={self.name}, version={self.version})>"


# ==================== 导出 ====================
__all__ = ["MusicMaestro", "MusicEngine", "detect_hardware"]