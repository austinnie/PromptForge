#!/usr/bin/env python
"""
📰 技术热点文章生成器 - 命令行工具

用法:
  python tech_hot_article_cli.py                    # 随机生成一篇
  python tech_hot_article_cli.py --style "深度技术型"
  python tech_hot_article_cli.py --index 0
  python tech_hot_article_cli.py --help
"""

import sys
import os
import json
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from skills.tech_hot_article import TechHotArticle


def main():
    parser = argparse.ArgumentParser(
        description="📰 技术热点文章生成器 - 基于实时热点生成技术文章",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tech_hot_article_cli.py                           # 随机生成
  python tech_hot_article_cli.py --style 深度技术型        # 指定风格
  python tech_hot_article_cli.py --index 0                 # 使用第1个热点
  python tech_hot_article_cli.py --model qwen2.5:7b       # 指定模型
  python tech_hot_article_cli.py --words 2000              # 指定字数
  python tech_hot_article_cli.py --list                   # 列出当前热点
  python tech_hot_article_cli.py --open                   # 生成后打开文档

写作风格:
  专业分析型   - 深入分析技术原理和架构
  通俗科普型   - 用通俗语言解释技术概念
  深度技术型   - 技术细节深入探讨
  行业观察型   - 从行业角度分析趋势
  趋势预测型   - 预测技术发展趋势
        """
    )

    parser.add_argument("--style", "-s", type=str, default=None,
                       help="写作风格 (专业分析型/通俗科普型/深度技术型/行业观察型/趋势预测型)")
    parser.add_argument("--index", "-i", type=int, default=None,
                       help="选择第几个热点 (0-9)，不指定则随机")
    parser.add_argument("--model", "-m", type=str, default="qwen2.5:7b",
                       help="使用的 Ollama 模型 (默认: qwen2.5:7b)")
    parser.add_argument("--words", "-w", type=int, default=None,
                       help="文章目标字数（默认 1500）")
    parser.add_argument("--list", "-l", action="store_true",
                       help="列出当前热点，不生成文章")
    parser.add_argument("--output", "-o", type=str, default=None,
                       help="输出目录 (默认: ./skills/tech_hot_article/output)")
    parser.add_argument("--open", action="store_true",
                       help="生成后自动打开 Word 文档")

    args = parser.parse_args()

    # 初始化
    config = {"model": args.model}
    if args.output:
        config["output_dir"] = args.output
    if args.words:
        config["article_words"] = args.words

    generator = TechHotArticle(config)

    # 列出热点模式
    if args.list:
        print("\n📡 正在获取技术热点...")
        hot_items = generator.get_hot_topics()
        if not hot_items:
            print("❌ 未获取到热点")
            return

        print(f"\n📰 当前技术热点 (共 {len(hot_items)} 条):")
        print("=" * 70)
        for i, item in enumerate(hot_items):
            score = item.get("score", 0)
            source = item.get("source", "未知")
            print(f"  {i}. [{source}] {item['title'][:60]}")
            if score:
                print(f"     🔥 热度: {score}")
        print("=" * 70)
        print("\n💡 使用 --index <数字> 选择热点生成文章")
        return

    # 生成文章模式
    print("\n📰 技术热点文章生成器")
    print("=" * 60)

    kwargs = {
        "model": args.model,
        "style": args.style,
        "hot_index": args.index,
    }

    print(f"📝 参数: 风格={args.style or '随机'}, 热点索引={args.index or '随机'}, 字数={args.words or '默认'}")

    result = generator.execute(**kwargs)

    if result["status"] == "success":
        data = result["result"]
        print("\n" + "=" * 60)
        print("   ✅ 文章生成完成！")
        print("=" * 60)
        print(f"\n📄 标题: {data['title']}")
        print(f"📡 热点: {data['hot_topic']}")
        print(f"📰 来源: {data['hot_source']}")
        print(f"🎨 风格: {data['style']}")
        print(f"📁 Word文档: {data['word_file']}")

        # ✅ 显示所有配图（多图支持）
        if data.get('image_files'):
            print(f"🖼️  配图 ({len(data['image_files'])} 张):")
            for i, img in enumerate(data['image_files'], 1):
                print(f"     {i}. {img}")
        else:
            print(f"🖼️  配图: 无")

        print(f"📋 元数据: {data['article_file']}")
        print(f"⏱️  生成时间: {data['generated_at']}")

        # 自动打开 Word 文档
        if args.open:
            try:
                if sys.platform == "win32":
                    os.startfile(data['word_file'])
                    print("\n📂 正在打开 Word 文档...")
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", data['word_file']])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", data['word_file']])
            except Exception as e:
                print(f"\n⚠️ 打开文档失败: {e}")

    else:
        print(f"\n❌ 生成失败: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    main()