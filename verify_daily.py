# verify_daily.py
"""daily_pipeline 验证（最小化参数：1 图 1 章，快速跑完）。"""
import sys

from skills.daily_pipeline import DailyPipeline

print("=" * 60)
print("daily_pipeline 验证（最小参数：1 张图）")
print("=" * 60)

pipeline = DailyPipeline({"output_dir": "output/daily_test"})
print(f"✅ 实例化: {pipeline.get_name()}")

print("\n[最小流程]")
r = pipeline.execute(
    topic="雨后的城市街头",
    count=1,
    skip_wechat=True,   # 先跳过排版，测纯流程
)

if r["status"] == "error":
    print(f"❌ 失败: {r.get('error')}")
    sys.exit(1)

data = r["result"]
print(f"\n{'✅' if r['status'] == 'success' else '⚠️'} {r['status']}")
print(f"   主题:   {data.get('topic')}")
print(f"   预设:   {data.get('preset') or '(无)'}")
print(f"   图片:   {len(data.get('images', []))} 张")
print(f"   文章:   {data.get('article_md')}")
print(f"   HTML:   {data.get('article_html')}")
print(f"   耗时:   {data.get('elapsed')}")

print("\n" + "=" * 60)
print("完成")
print("=" * 60)