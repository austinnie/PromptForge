# verify_social_upload.py
"""social_auto_upload 验证（dry_run 模式，不需要真装 sau）。"""
import sys
from pathlib import Path

from skills.social_auto_upload import (
    SocialAutoUpload, SUPPORTED_PLATFORMS, NOTE_PLATFORMS,
)

print("=" * 60)
print("social_auto_upload 验证（dry_run 模式）")
print("=" * 60)

skill = SocialAutoUpload({"dry_run": True})
print(f"✅ 实例化: {skill.get_name()}")

# ---- 1. 平台列表 ----
print("\n[1] 平台支持列表")
r = skill.execute(action="list_platforms")
d = r["result"]
print(f"   视频平台: {len(d['all'])} 个")
print(f"   图文平台: {d['note']}")
print(f"   定时平台: {d['schedule']}")
print(f"   sau 状态: {'✅ 已安装' if d['sau_available'] else '❌ 未安装'}")

# ---- 2. dry_run 发布视频 ----
print("\n[2] dry_run 发布视频（不会真发）")
# 找一张图片当假视频
test_file = Path("output/test_p4.txt")
if not test_file.exists():
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("test", encoding="utf-8")

r = skill.execute(
    action="publish_video",
    platform="douyin",
    file=str(test_file),
    title="测试视频标题",
    desc="测试描述",
    tags=["科技", "AI"],
    dry_run=True,
)
if r["status"] == "success":
    d = r["result"]
    print(f"   ✅ dry_run 成功")
    print(f"   命令: {d['cmd_str']}")
else:
    print(f"   ❌ {r.get('error')}")

# ---- 3. dry_run 发布图文 ----
print("\n[3] dry_run 发布图文到小红书")
r = skill.execute(
    action="publish_note",
    platform="xiaohongshu",
    images=[str(test_file)],
    title="小红书标题",
    note="这是一条测试正文",
    tags=["好物推荐"],
    dry_run=True,
)
if r["status"] == "success":
    d = r["result"]
    print(f"   ✅ dry_run 成功")
    print(f"   命令: {d['cmd_str']}")

# ---- 4. 验证不支持的平台 ----
print("\n[4] 边界：小红书不支持视频")
r = skill.execute(
    action="publish_video",
    platform="douyin",    # OK
    file=str(test_file),
    title="x",
    dry_run=True,
)
print(f"   douyin 视频: {r['status']}")

r = skill.execute(
    action="publish_note",
    platform="bilibili",  # bilibili 不在 NOTE_PLATFORMS
    images=[str(test_file)],
    title="x",
    dry_run=True,
)
print(f"   bilibili 图文: {r['status']} (应为 error)")
print(f"   → {r.get('error')[:80]}")

# ---- 5. 缺失文件 ----
print("\n[5] 边界：文件不存在")
r = skill.execute(
    action="publish_video",
    platform="douyin",
    file="nonexistent.mp4",
    title="x",
    dry_run=True,
)
print(f"   不存在文件: {r['status']} (应为 error)")

print("\n" + "=" * 60)
print("完成")
print("=" * 60)

if not skill._sau_path:
    print("\n💡 要真的发内容，需要安装 social-auto-upload：")
    print("   git clone https://github.com/dreammis/social-auto-upload.git \\")
    print("     skills/social_auto_upload/social-auto-upload")
    print("   cd skills/social_auto_upload/social-auto-upload")
    print("   pip install -r requirements.txt")
    print("   playwright install chromium")
    print("\n   装完后：python scripts/social_upload_cli.py --login douyin")