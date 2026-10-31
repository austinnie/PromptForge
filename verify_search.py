# verify_search.py
"""search_engine 验证。"""
import sys
from pathlib import Path

from skills.search_engine import SearchEngine

print("=" * 60)
print("search_engine 验证")
print("=" * 60)

skill = SearchEngine({"output_dir": "output/search_test"})
print(f"✅ 实例化: {skill.get_name()}")

# ---- 图片搜索 ----
print("\n[图片搜索: 水墨山水]")
r = skill.execute(action="search", query="水墨山水", kind="images", limit=5)
if r["status"] == "success":
    items = r["result"]["items"]
    print(f"   找到 {len(items)} 条")
    for i, it in enumerate(items[:3], 1):
        print(f"   {i}. {it.get('width')}x{it.get('height')} {it.get('title', '')[:40]}")
else:
    print(f"   ❌ {r.get('error')}")

# ---- 图片下载 ----
if r["status"] == "success" and r["result"]["items"]:
    print("\n[下载 2 张测试]")
    test_items = r["result"]["items"][:2]
    dl = skill.execute(
        action="download_batch",
        items=[{"url": it["url"], "referer": it.get("referer")} for it in test_items],
        save_dir="output/search_test/images",
    )
    if dl["status"] == "success":
        dr = dl["result"]
        print(f"   成功: {dr['success']}/{dr['total']}")
        print(f"   目录: {dr['save_dir']}")
        # 列出文件
        p = Path(dr["save_dir"])
        for f in sorted(p.iterdir())[:3]:
            if f.is_file():
                print(f"   📄 {f.name} ({f.stat().st_size // 1024} KB)")

# ---- 视频搜索 ----
print("\n[视频搜索: 海边日落]")
try:
    rv = skill.execute(action="search", query="海边日落", kind="videos", limit=5)
    if rv["status"] == "success":
        items = rv["result"]["items"]
        print(f"   找到 {len(items)} 条")
        for i, it in enumerate(items[:3], 1):
            print(f"   {i}. {it.get('title', '')[:50]}")
            print(f"      {it.get('url', '')[:80]}")
    else:
        print(f"   ⚠️ {rv.get('error')}")
except Exception as e:
    print(f"   ⚠️ 视频搜索跳过: {e}")

print("\n" + "=" * 60)
print("完成")
print("=" * 60)