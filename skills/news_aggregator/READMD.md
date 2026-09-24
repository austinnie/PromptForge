# news_aggregator

RSS 新闻聚合器：从 7 大类新闻源抓取、去重、AI 摘要，输出每日简报。

---

## ✨ 功能

- **7 大类新闻源**：`tech` / `business` / `world` / `china` / `usa` / `japan` / `korea`
- **多源抓取**：并行拉取，带源可用性验证
- **缓存机制**：RSS 源可用性缓存 30 分钟，减少重复验证
- **智能去重**：按标题前缀去重
- **AI 摘要**：LLM 生成每日新闻简报摘要
- **本地保存**：简报默认保存到 `./skills/news_aggregator/output/`

---

## 📦 依赖

```bash
pip install feedparser requests
```

可选：


# AI 摘要需要 LLM 后端（Agnes 需注册 / Ollama 本地）
# 具体依赖由 core.llm_client 管理
⚙️ 配置（.env）
```ini
# 新闻功能总开关
NEWS_ENABLED=true

# 简报输出目录
NEWS_OUTPUT_DIR=./output/news

# 默认新闻分类（逗号分隔）
NEWS_FEEDS=world,technology,business,china,science

# 每条源最多抓取条数
NEWS_MAX_ARTICLES=15

# 是否验证 RSS 源
NEWS_VALIDATE_FEEDS=true

# 是否启用 AI 摘要
NEWS_ENABLE_SUMMARY=true

# 摘要用的 Ollama 模型名（仅 ollama 后端生效）
NEWS_SUMMARY_MODEL=qwen2.5:1.5b

# RSS 源缓存秒数
NEWS_CACHE_TTL=3600

# 抓取用的 User-Agent
NEWS_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36

# 该 skill 专属 LLM 后端（可选，不配则用全局 LLM_BACKENDS）
# NEWS_LLM_BACKENDS=ollama
```

🐍 Python 调用
```python
from skills import NewsAggregator

aggregator = NewsAggregator({
    "output_dir": "./output/news",
    "validate_feeds": True,
    "top_n": 15,
})

# 抓取科技新闻
result = aggregator.execute(category="tech", top_n=15)

if result["status"] == "success":
    print(f"抓取 {result['result']['total_fetched']} 条")
    print(f"去重后 {result['result']['unique_count']} 条")
    print(result["result"]["report_file"])
```

📁 输出结构
```text
skills/news_aggregator/output/
├── .feed_cache/                      # RSS 源可用性缓存
│   └── tech.json
└── news_tech_20260924_080000.txt     # 生成的简报
```

🔧 分类说明
分类	说明
tech	科技新闻（TechCrunch / Verge / Wired 等）
business	财经新闻（Bloomberg / FT / WSJ 等）
world	国际新闻（BBC / Reuters / AP 等）
china	中国新闻（BBC 中文 / 新华网 / 36kr 等）
usa	美国新闻
japan	日本新闻
korea	韩国新闻

❓ 常见问题
Q1：抓取很慢 / 源不可用？

默认会验证每个 RSS 源，源多时耗时长。可设 NEWS_VALIDATE_FEEDS=false 跳过

验证结果会缓存 30 分钟，重复运行会变快

Q2：AI 摘要失败？

检查 LLM_BACKENDS 配置（默认 agnes,ollama）

若只想走 Ollama，设 NEWS_LLM_BACKENDS=ollama

查看日志中 ⚠️ LLM 后端 xxx 调用失败 的提示

Q3：简报输出在哪里？

默认 ./skills/news_aggregator/output/

可通过 NEWS_OUTPUT_DIR 或构造参数 output_dir 覆盖

📄 License
与主项目一致。