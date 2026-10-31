# verify_voice.py
"""voice_assistant 验证。"""
import sys

try:
    import edge_tts
    print(f"✅ edge-tts 已安装")
except ImportError:
    print(f"❌ edge-tts 未安装. 请: pip install edge-tts")
    sys.exit(1)

from skills.voice_assistant.skill import VoiceAssistant

va = VoiceAssistant({"output_dir": "output/audio"})
print(f"✅ {va.get_name()}")

print("\n[中文 TTS]")
r = va.execute(action="tts", text="你好，我是 PromptForge 语音助手。", voice="zh-CN-XiaoxiaoNeural")
print(f"  {r['status']}")
if r["status"] == "success":
    print(f"  {r['result']['audio_file']} ({r['result']['bytes']} bytes)")

print("\n[英文 TTS]")
r = va.execute(action="tts", text="Hello from PromptForge.", voice="en-US-JennyNeural")
print(f"  {r['status']}: {r['result'].get('audio_file')}")

print("\n[长文本分段]")
r = va.execute(action="tts", text="这是测试句子。" * 300)
if r["status"] == "success":
    print(f"  ✅ {r['result']['chunks']} 段合成成功")