# tech_hot_article

> 基于实时技术热点，自动生成技术文章，生成配图，输出 Word 文档

## 概览

- **文件数**: 1
- **类数**: 1
- **方法数**: 14
- **函数数**: 0

## 技能描述

技术热点文章生成器，从多个 RSS 源获取当前技术热点，基于热点生成完整技术文章，自动生成配图，输出 Word 文档。每次执行保证热点不同、图片不同、文章不同。

## 功能特性

- 📡 **热点抓取**：从 Hacker News、TechCrunch、The Verge、Dev.to 等多个 RSS 源获取实时热点
- 🤖 **文章生成**：基于热点信息，使用 Ollama 生成完整技术文章
- 🎨 **配图生成**：使用 Pillow 生成科技感配图，每次配色和样式不同
- 📄 **Word 导出**：生成包含标题、文章、配图的 Word 文档
- 🎯 **多种风格**：支持专业分析型、通俗科普型、深度技术型等多种写作风格

## 依赖

```bash
pip install feedparser python-docx Pillow requests
```

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `style` | string | 随机 | 写作风格 (专业分析型/通俗科普型/深度技术型/行业观察型/趋势预测型) |
| `hot_index` | integer | 随机 | 选择第几个热点 (0-9)，不指定则随机 |
| `model` | string | qwen2.5:7b | 使用的 Ollama 模型 |

## 输出

| 字段 | 说明 |
|------|------|
| `title` | 文章标题 |
| `hot_topic` | 热点标题 |
| `hot_source` | 热点来源 |
| `style` | 写作风格 |
| `model` | 使用的模型 |
| `word_file` | Word 文档路径 |
| `image_file` | 配图路径 |
| `article_file` | 文章元信息 JSON 路径 |

## 使用方法

```bash
python -m markflow.cli.commands execute tech_hot_article [参数]
```

### 示例

```bash
# 随机生成一篇技术文章
python -m markflow.cli.commands execute tech_hot_article

# 指定写作风格
python -m markflow.cli.commands execute tech_hot_article style="深度技术型"

# 指定使用第几个热点
python -m markflow.cli.commands execute tech_hot_article hot_index=0

# 指定模型
python -m markflow.cli.commands execute tech_hot_article model="qwen2.5:7b"
```

### 查看完整参数说明：

```bash
python -m markflow.cli.commands info tech_hot_article
```

## 输出位置

生成的输出保存在 `skills/tech_hot_article/output/` 目录下。

| 路径 | 说明 |
|------|------|
| `skills/tech_hot_article/output/articles/` | 文章元信息 JSON |
| `skills/tech_hot_article/output/images/` | 配图 PNG |
| `skills/tech_hot_article/output/word/` | Word 文档 |

## 热点来源

| 来源 | 说明 |
|------|------|
| Hacker News | 技术社区热点 |
| TechCrunch | 科技新闻 |
| The Verge | 科技新闻 |
| Wired | 科技新闻 |
| Ars Technica | 技术深度文章 |
| ZDNet | 科技新闻 |
| VentureBeat | 科技新闻 |
| Dev.to | 开发者社区 |

## 写作风格

| 风格 | 说明 |
|------|------|
| 专业分析型 | 深入分析技术原理和架构 |
| 通俗科普型 | 用通俗语言解释技术概念 |
| 深度技术型 | 技术细节深入探讨 |
| 行业观察型 | 从行业角度分析趋势 |
| 趋势预测型 | 预测技术发展趋势 |

---

*文档自动生成于 2026-08-25*
