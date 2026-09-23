#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PromptForge GitHub 日报 - CLI 薄包装

真正的逻辑在 skills/github_repo_daily/skill.py。
这里只负责命令行参数 → config 映射，方便脚本/计划任务调用。

用法：
    python scripts/github_daily_task.py
    python scripts/github_daily_task.py --no-publish
    python scripts/github_daily_task.py --model qwen2.5:14b --theme terracotta
    python scripts/github_daily_task.py --no-illustration
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# 根目录定位 + 自检
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if not (PROJECT_ROOT / "skills" / "github_repo_daily").is_dir():
    sys.exit(f"❌ 项目根目录识别失败：{PROJECT_ROOT}")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from skills.github_repo_daily import GitHubRepoDaily

    parser = argparse.ArgumentParser(
        description="PromptForge GitHub 每日仓库推荐",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ---- 内容 ----
    parser.add_argument("--model", default=None,
                        help="Ollama 模型（默认 qwen2.5:7b）")
    parser.add_argument("--ollama-url", default=None,
                        help="Ollama 地址（默认 http://localhost:11434）")

    # ---- 配图 ----
    parser.add_argument("--illustration-count", type=int, default=None,
                        choices=range(0, 11), metavar="[0-10]",
                        help="配图数量（0 = 关掉配图，默认 3）")
    parser.add_argument("--illustration-engine", default=None,
                        choices=["agnes", "pollinations", "siliconflow"],
                        help="配图引擎（默认 agnes）")

    # ---- 排版 / 发布 ----
    parser.add_argument("--theme", default=None,
                        help="微信排版主题（默认 newspaper）")
    parser.add_argument("--no-publish", action="store_true",
                        help="不推草稿箱（默认推送）")

    # ---- 输出 ----
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="输出根目录（默认 output/github_repo_daily）")

    # ---- 调试 ----
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    # 加载 .env
    try:
        from dotenv import load_dotenv
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass

    # ---- 拼 config ----
    config: dict = {"log_level": args.log_level}
    if args.model:
        config["ollama_model"] = args.model
    if args.ollama_url:
        config["ollama_url"] = args.ollama_url
    if args.illustration_count is not None:
        config["illustration_count"] = args.illustration_count
    if args.illustration_engine:
        config["illustration_engine"] = args.illustration_engine
    if args.theme:
        config["wechat_theme"] = args.theme
    if args.no_publish:
        config["wechat_publish"] = False
    if args.output_dir:
        config["output_dir"] = str(args.output_dir)

    skill = GitHubRepoDaily(config)

    # ---- 执行 ----
    t0 = time.time()
    result = skill.execute()
    elapsed = time.time() - t0

    if result.get("status") != "success":
        print(f"\n❌ 失败: {result.get('error')}")
        print(f"⏱️  耗时: {elapsed:.1f}s")
        return 1

    r = result["result"]
    print("\n" + "=" * 62)
    print("  🎉 GitHub 日报完成！")
    print("=" * 62)
    print(f"🐙 仓库      : {r.get('repo', '')}")
    print(f"🔗 链接      : {r.get('repo_url', '')}")
    print(f"📄 文章      : {r.get('article_path', '')}")

    if r.get("illustrations"):
        print(f"🖼️  配图      : {len(r['illustrations'])} 张")

    published = r.get("published")
    if published is True:
        print("📤 推送      : ✅ 已推送到草稿箱")
    elif published is False:
        print("📤 推送      : ❌ 失败（详见日志）")
    else:
        print("📤 推送      : ⏭️  未启用")

    print(f"⏱️  耗时      : {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())