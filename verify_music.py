# verify_music.py
"""music_generator 验证（20 秒短版，测所有后端）。"""
import sys
from pathlib import Path

from skills.music_generator import MusicMaestro, detect_hardware

print("=" * 60)
print("music_generator 验证")
print("=" * 60)

hw = detect_hardware()
print("硬件探测:")
print(f"  numpy:      {'✅' if hw['numpy'] else '❌'}")
print(f"  soundfont:  {hw['soundfont'].name if hw['soundfont'] else '❌'}")
print(f"  fluidsynth: {'✅' if hw['fluidsynth'] else '❌'}")
print(f"  ffmpeg:     {'✅' if hw['ffmpeg'] else '❌'}")
print(f"  torch:      {'✅' if hw['torch'] else '❌'}")
print(f"  cuda:       {'✅' if hw['cuda'] else '❌'}")
print(f"  可用后端:   {hw['backends']}")
print(f"  推荐后端:   {hw['recommended']}")

if hw["recommended"] == "none":
    print("\n❌ 没有任何可用后端")
    sys.exit(1)

maestro = MusicMaestro({"output_dir": "output/music_test"})
print(f"\n✅ 实例化: {maestro.get_name()}")

# ---- 测试 1：交响乐（如可用）----
if "symphony" in hw["backends"]:
    print("\n[测试 1: 交响乐 · 壮丽 · 20 秒]")
    r = maestro.execute(
        topic="星辰大海", emotion="epic",
        arrangement="symphony", duration=20,
        lyrics=False,
    )
    if r["status"] == "success":
        d = r["result"]
        p = Path(d["audio_file"])
        print(f"   ✅ {p.name} ({p.stat().st_size // 1024} KB, {d['backend']})")
    else:
        print(f"   ❌ {r.get('error')}")

# ---- 测试 2：中国风 ----
if "symphony" in hw["backends"]:
    print("\n[测试 2: 中国风 · 宁静 · 15 秒]")
    r = maestro.execute(
        topic="江南雨巷", emotion="peaceful",
        arrangement="chinese", duration=15,
        lyrics=False,
    )
    if r["status"] == "success":
        d = r["result"]
        p = Path(d["audio_file"])
        print(f"   ✅ {p.name} ({p.stat().st_size // 1024} KB)")
    else:
        print(f"   ❌ {r.get('error')}")

# ---- 测试 3：numpy 兜底 ----
if "numpy_wav" in hw["backends"]:
    print("\n[测试 3: numpy 兜底 · 壮丽 · 10 秒]")
    r = maestro.execute(
        topic="测试兜底", emotion="epic",
        arrangement="symphony", duration=10,
        lyrics=False, backend="numpy_wav",
    )
    if r["status"] == "success":
        d = r["result"]
        p = Path(d["audio_file"])
        print(f"   ✅ {p.name} ({p.stat().st_size // 1024} KB, {d['backend']})")
    else:
        print(f"   ❌ {r.get('error')}")

# ---- 测试 4：LLM 歌词 ----
print("\n[测试 4: LLM 歌词]")
lyrics = maestro.generate_lyrics("星辰大海", "epic", "symphony", "zh")
if lyrics:
    print(f"   ✅ 歌词生成成功 ({len(lyrics)} 字)")
    print(f"   预览: {lyrics.split(chr(10))[0][:50]}")
else:
    print(f"   ⚠️ 歌词生成失败（LLM 不可用，不影响音频）")

print("\n" + "=" * 60)
print("完成")
print("=" * 60)