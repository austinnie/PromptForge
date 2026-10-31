# verify_github_daily.py
"""github_repo_daily 验证（分段：抓取 → 详情 → 写作，不推送）。

不跑完整流程（避免真的推送公众号），只验证核心环节。
"""
import sys
from pathlib import Path

from skills.github_repo_daily import GitHubRepoDaily

print("=" * 60)
print("github_repo_daily 验证")
print("=" * 60)

skill = GitHubRepoDaily({"output_dir": "output/github_test"})
print(f"✅ 实例化: {skill.get_name()}")
print(f"   历史文件: {skill._history_file}")
print(f"   历史记录: {len(skill._load_history())} 条")

# ---- 1. 抓 Trending ----
print("\n[1] 抓 GitHub Trending")
repos = skill._fetch_trending()
print(f"   抓到 {len(repos)} 个")
for i, r in enumerate(repos[:5], 1):
    print(f"   {i}. {r['full_name']}")
    if r["description"]:
        print(f"      {r['description'][:60]}")

if not repos:
    print("❌ Trending 抓取失败，退出")
    sys.exit(1)

# ---- 2. 挑一个未推荐过的 ----
print("\n[2] 挑选未推荐过的仓库")
picked = skill._pick_repo(repos)
if picked:
    print(f"   ✅ {picked['full_name']}")
else:
    print(f"   ⚠️ 全部已推荐过，使用第一个: {repos[0]['full_name']}")
    picked = repos[0]

# ---- 3. 拿详情 ----
print(f"\n[3] 获取详情: {picked['full_name']}")
info = skill._get_repo_details(picked["owner"], picked["repo"])
if not info:
    print("❌ 获取失败")
    sys.exit(1)

print(f"   ⭐ {info['stars']}  🍴 {info['forks']}")
print(f"   🔤 {info['language']}")
print(f"   📄 {info['license']}")
print(f"   🏷️ {', '.join(info['topics'][:5]) if info['topics'] else '(无)'}")
print(f"   📖 README: {len(info['readme'])} 字符")

# ---- 4. 写文章（不配图不推送）----
print(f"\n[4] LLM 写文章（500 字快速测试）")
article = skill._generate_article(info, words=500)
if article:
    print(f"   ✅ 标题: {article['title']}")
    print(f"   📝 字数: {len(article['body'])}")
    print(f"\n   正文预览:")
    for line in article["body"].split("\n")[:8]:
        print(f"   {line[:80]}")
else:
    print("❌ 文章生成失败")

print("\n" + "=" * 60)
print("完成（未推送公众号，未生成配图）")
print("=" * 60)
print("\n💡 完整测试请用：")
print("   python scripts/github_daily_cli.py --no-publish --open")