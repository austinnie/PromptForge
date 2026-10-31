# verify_video_sniffer.py
"""video_sniffer 验证。"""
import sys

from skills.video_sniffer import VideoSniffer

print("=" * 60)
print("video_sniffer 验证")
print("=" * 60)

# 检查 yt-dlp
try:
    import yt_dlp
    print(f"✅ yt-dlp: {yt_dlp.version.__version__}")
except ImportError:
    print("⚠️ yt-dlp 未安装（HTML 后备仍可用）: pip install yt-dlp")

skill = VideoSniffer({"output_dir": "output/sniffer_test"})
print(f"✅ 实例化: {skill.get_name()}")

# ---- 测试 1：B站视频（yt-dlp 主路径）----
print("\n[测试 1: B站视频]")
test_url = "https://www.bilibili.com/video/BV1GJ411x7h7"
r = skill.execute(action="analyze", url=test_url)
if r["status"] == "success":
    data = r["result"]
    print(f"   方法: {data['method']}, 找到 {data['count']} 个")
    for v in data["videos"][:3]:
        print(f"   - [{v.get('duration_str')}] {v.get('title', '')[:60]}")
else:
    print(f"   ⚠️ {r.get('error')}")

# ---- 测试 2：HTML 后备（用一个含 <video> 的页面）----
print("\n[测试 2: HTML 后备 - W3C 示例页]")
test_url = "https://www.w3schools.com/html/html5_video.asp"
r = skill.execute(action="analyze", url=test_url)
if r["status"] == "success":
    data = r["result"]
    print(f"   方法: {data['method']}, 找到 {data['count']} 个")
    for v in data["videos"][:3]:
        print(f"   - [{v.get('kind')}] {v['url'][:80]}")
else:
    print(f"   ⚠️ {r.get('error')}")

# ---- 测试 3：提取相关视频 ----
print("\n[测试 3: 提取相关视频]")
r = skill.execute(action="related", url="https://www.bilibili.com/video/BV1GJ411x7h7", max_count=5)
if r["status"] == "success":
    data = r["result"]
    print(f"   找到 {data['count']} 个相关链接")
    for link in data["links"][:3]:
        print(f"   - {link['title'][:50]}")
        print(f"     {link['url']}")
else:
    print(f"   ⚠️ {r.get('error')}")

print("\n" + "=" * 60)
print("完成")
print("=" * 60)