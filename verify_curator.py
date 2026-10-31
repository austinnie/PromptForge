# verify_curator.py
"""image_curator 验证。"""
import sys

from skills.image_curator.skill import ImageCurator

print("=" * 60)
print("image_curator 验证")
print("=" * 60)

# 检查 vision 引擎
curator = ImageCurator({"output_dir": "output/curator"})
if curator._vision_provider is None:
    print("❌ vision provider 未初始化")
    print("   检查 .env 是否有 AGNES_API_KEY")
    sys.exit(1)
print(f"✅ 视觉引擎: {curator.get_name()}")

# 扫描 output 目录里已有的图片
from pathlib import Path
test_dir = Path("output")
if not test_dir.exists():
    print(f"❌ {test_dir} 目录不存在")
    sys.exit(1)

images = list(test_dir.glob("*.png")) + list(test_dir.glob("*.jpg"))[:3]
if not images:
    print(f"❌ {test_dir} 里没有图片，请先生成一张")
    sys.exit(1)

print(f"\n找到 {len(images)} 张图片，开始鉴赏...")
print(f"   取前 2 张做测试")

# 只取前 2 张测试（节省 API 额度）
r = curator.curate(
    directory=str(test_dir),
    title="验证测试",
    max_images=2,
)

print(f"\n状态: {r['status']}")
if r["status"] == "success":
    res = r["result"]
    print(f"  📄 Markdown: {res.get('article_md')}")
    print(f"  🌐 HTML:     {res.get('article_html')}")
    print(f"  🖼️ 图片数:   {res.get('image_count')}")
    print(f"  ⏱️  耗时:    {res.get('elapsed')}")
    print(f"  📁 目录:     {res.get('output_dir')}")
else:
    print(f"  ❌ {r.get('error')}")