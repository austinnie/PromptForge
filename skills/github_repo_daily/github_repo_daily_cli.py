#!/usr/bin/env python
"""GitHub 仓库每日推荐 CLI"""

import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from skills.github_repo_daily import GitHubRepoDaily


def main():
    parser = argparse.ArgumentParser(description="GitHub 仓库每日推荐")
    parser.add_argument("--no-publish", action="store_true", help="不发布到微信公众号")
    parser.add_argument("--theme", default="newspaper", help="微信排版主题")
    parser.add_argument("--model", default=None, help="Ollama 模型")
    args = parser.parse_args()

    config = {
        "wechat_publish": not args.no_publish,
        "wechat_theme": args.theme,
    }
    if args.model:
        config["ollama_model"] = args.model

    skill = GitHubRepoDaily(config)
    result = skill.execute()

    if result["status"] == "success":
        print(f"✅ 推荐仓库: {result['result']['repo']}")
        print(f"📄 文章: {result['result']['article_path']}")
        print(f"📤 已发布: {result['result']['published']}")
    else:
        print(f"❌ 失败: {result.get('error')}")


if __name__ == "__main__":
    main()