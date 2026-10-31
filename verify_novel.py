# verify_novel.py
"""novel_writer 验证（快速短篇测试）。"""
import sys
from pathlib import Path

from skills.novel_writer import NovelWriter

print("=" * 60)
print("novel_writer 验证")
print("=" * 60)

writer = NovelWriter({"output_dir": "output/novels"})
print(f"✅ 实例化: {writer.get_name()}")

print("\n[LLM 探测]")
if not writer._check_llm():
    print("❌ LLM 后端不可用")
    sys.exit(1)
print("✅ LLM 可用")

print("\n[生成 2 章测试]")
result = writer.execute(
    genre="科幻",
    title="验证测试 · 短篇",
    outline="未来的一个夜晚，一名工程师发现自己实验室的 AI 开始有了自我意识。",
    characters="工程师陈默，AI 代号 ORACLE",
    chapter_count=2,
    words_per_chapter=300,
    language="zh",
)

if result["status"] != "success":
    print(f"❌ 失败: {result.get('error')}")
    sys.exit(1)

r = result["result"]
print(f"\n✅ 生成成功")
print(f"   文件:   {r['novel_file']}")
print(f"   章节:   {r['chapter_count']} 章")
print(f"   字数:   {r['total_words']} 字")
print(f"   耗时:   {r['elapsed']}")
print(f"\n📖 简介:\n   {r['summary'][:200]}...")

print("\n[续写 1 章测试]")
result2 = writer.execute(
    genre="科幻",
    title="验证测试 · 短篇",
    chapter_count=1,
    words_per_chapter=300,
    language="zh",
    continue_from=r["novel_file"],
)

if result2["status"] == "success":
    r2 = result2["result"]
    print(f"✅ 续写成功: 共 {r2['chapter_count']} 章, {r2['total_words']} 字")
else:
    print(f"❌ 续写失败: {result2.get('error')}")

print("\n" + "=" * 60)
print("完成")
print("=" * 60)