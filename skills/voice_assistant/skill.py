"""
voice_assistant - 语音合成 / 识别 Skill（P2 补齐版）

功能:
  - TTS (edge-tts): 文本 → mp3
  - STT (可选, whisper): 音频 → 文本
  - list_voices: 音色列表
  - 长文本自动分段

依赖:
  pip install edge-tts          # TTS 必需
  pip install openai-whisper    # STT 可选
"""

import asyncio
import concurrent.futures
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VoiceAssistant:
    name = "voice_assistant"
    version = "2.0.0"

    DEFAULT_VOICES = [
        {"name": "zh-CN-XiaoxiaoNeural", "locale": "zh-CN", "gender": "Female"},
        {"name": "zh-CN-YunxiNeural",    "locale": "zh-CN", "gender": "Male"},
        {"name": "zh-CN-YunyangNeural",  "locale": "zh-CN", "gender": "Male"},
        {"name": "en-US-JennyNeural",    "locale": "en-US", "gender": "Female"},
        {"name": "en-US-GuyNeural",      "locale": "en-US", "gender": "Male"},
        {"name": "ja-JP-NanamiNeural",   "locale": "ja-JP", "gender": "Female"},
    ]
    DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
    MAX_CHARS_PER_CHUNK = 2000

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        self.config.setdefault("output_dir", "./output/audio")
        self.config.setdefault("default_voice", self.DEFAULT_VOICE)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        action = kwargs.get("action", "tts")
        if action == "tts":
            return self._tts(kwargs)
        if action == "list_voices":
            return {"status": "success", "result": {"voices": self.DEFAULT_VOICES}}
        if action == "stt":
            return self._stt(kwargs)
        return {"status": "error", "error": f"不支持 action: {action}"}

    # ---------- TTS ----------

    def _tts(self, kwargs) -> Dict[str, Any]:
        text = (kwargs.get("text") or "").strip()
        if not text:
            return {"status": "error", "error": "text 不能为空"}

        voice = kwargs.get("voice") or self.config["default_voice"]
        rate = kwargs.get("rate") or "+0%"
        volume = kwargs.get("volume") or "+0%"

        chunks = self._split_text(text, self.MAX_CHARS_PER_CHUNK)
        logger.info(f"🎤 TTS: {len(text)} 字 → {len(chunks)} 段, voice={voice}")

        try:
            import edge_tts  # noqa
        except ImportError:
            return {"status": "error", "error": "edge-tts 未安装. 请: pip install edge-tts"}

        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_voice = re.sub(r"[^\w\-]", "_", voice)
        filename = f"tts_{ts}_{safe_voice}.mp3"
        filepath = Path(self.config["output_dir"]) / filename

        try:
            audio_bytes = self._synthesize(chunks, voice, rate, volume)
            filepath.write_bytes(audio_bytes)
            logger.info(f"✅ TTS: {filepath} ({len(audio_bytes)} bytes)")
            return {
                "status": "success",
                "result": {
                    "audio_file": str(filepath),
                    "voice": voice,
                    "chars": len(text),
                    "bytes": len(audio_bytes),
                    "chunks": len(chunks),
                },
                "metadata": {"skill": self.name, "version": self.version},
            }
        except Exception as e:
            logger.exception("TTS 失败")
            return {"status": "error", "error": str(e)}

    def _synthesize(self, chunks: List[str], voice: str, rate: str, volume: str) -> bytes:
        import edge_tts

        async def _do():
            all_audio = bytearray()
            for i, chunk in enumerate(chunks):
                logger.debug(f"  合成 {i + 1}/{len(chunks)} ({len(chunk)} 字)")
                communicate = edge_tts.Communicate(chunk, voice, rate=rate, volume=volume)
                async for piece in communicate.stream():
                    if piece["type"] == "audio":
                        all_audio.extend(piece["data"])
            return bytes(all_audio)

        try:
            asyncio.get_running_loop()
            running = True
        except RuntimeError:
            running = False

        if running:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(_do())).result()
        return asyncio.run(_do())

    # ---------- STT ----------

    def _stt(self, kwargs) -> Dict[str, Any]:
        audio_path = kwargs.get("audio_file")
        if not audio_path or not Path(audio_path).exists():
            return {"status": "error", "error": "audio_file 不存在"}
        try:
            import whisper
        except ImportError:
            return {"status": "error", "error": "whisper 未安装. 请: pip install openai-whisper"}
        try:
            model = whisper.load_model(kwargs.get("model", "base"))
            result = model.transcribe(str(audio_path))
            return {
                "status": "success",
                "result": {
                    "text": result.get("text", "").strip(),
                    "language": result.get("language", ""),
                    "audio_file": str(audio_path),
                },
            }
        except Exception as e:
            logger.exception("STT 失败")
            return {"status": "error", "error": str(e)}

    # ---------- 工具 ----------

    @staticmethod
    def _split_text(text: str, max_chars: int) -> List[str]:
        if len(text) <= max_chars:
            return [text]
        sentences = re.split(r"(?<=[。！？\.\!\?])\s*", text)
        chunks: List[str] = []
        current = ""
        for s in sentences:
            if not s:
                continue
            if len(current) + len(s) <= max_chars:
                current += s
            else:
                if current:
                    chunks.append(current)
                current = s
        if current:
            chunks.append(current)
        return chunks

    def get_name(self) -> str:
        return f"VoiceAssistant ({self.config['default_voice']})"

    def __repr__(self):
        return f"<VoiceAssistant(voice={self.config['default_voice']})>"