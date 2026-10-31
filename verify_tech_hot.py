# verify_tech_hot.py
"""tech_hot_article 验证（快速版：800 字 + 1 张图）。"""
import sys

from skills.tech_hot_article import TechHotArticle

print("=" * 60)
print("tech_hot_article 验证")
print("=" * 60)

skill = TechHotArticle({"output_dir": "output/articles_test"})
print(f"✅ 实例化: {skill.get_name()}")

print("\n[抓取热点]")
topics = skill.get_hot_topics()
print(f"   抓到 {len(topics)} 条")
for i, t in enumerate(topics[:3], 1):
    print(f"   {i}. [{t['source']}] {t['title'][:60]}")

print("\n[生成文章（800 字 + 1 图）]")
r = skill.execute(
    topic="",
    style="通俗科普型",
    words=800,
    images=1,
)

if r["status"] != "success":
    print(f"❌ 失败: {r.get('error')}")
    sys.exit(1)

data = r["result"]
print(f"\n✅ 完成！")
print(f"   📄 {data['article_md']}")
print(f"   📘 {data.get('article_docx')}")
print(f"   ✍️  {data['word_count']} 字")
print(f"   🖼️  {data['images_count']} 图")
print(f"   ⏱️  {data['elapsed']}")
print(f"   📁 {data['output_dir']}")

print("\n" + "=" * 60)
print("完成")
print("=" * 60)