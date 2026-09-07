# novel_writer

> 使用本地 Ollama 大模型自动写小说

## 概览

- **文件数**: 1
- **类数**: 1
- **方法数**: 12
- **函数数**: 1

## 技能描述

使用本地 Ollama 大模型自动写小说

## 依赖

```bash
pip install requests
pip install json
```

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `genre` | string | `` | 小说类型 (科幻/奇幻/言情/悬疑/武侠/都市) |
| `title` | string | `` | 小说标题 |
| `outline` | string | `` | 故事大纲，描述主要情节 |
| `characters` | string | `` | 主要角色设定 |
| `chapter_count` | integer | `` | 要生成的章节数量，默认 3，范围 1-10 |
| `words_per_chapter` | integer | `` | 每章目标字数，默认 500，范围 200-2000 |
| `style` | string | `` | 写作风格 (简洁/细腻/幽默/严肃)，默认 细腻 |
| `temperature` | float | `` | 创意程度 0-1，默认 0.85 |
| `model` | string | `` | 使用的模型，默认 qwen2.5:7b |
| `ollama_url` | string | `` | Ollama 服务地址，默认 http://localhost:11434 |

## 输出

| 字段 | 说明 |
|------|------|
| `title` | 小说标题 |
| `genre` | 小说类型 |
| `chapters` | 所有章节列表，每章包含标题和内容 |
| `summary` | 小说简介 |
| `total_words` | 总字数 |
| `model_used` | 使用的模型名称 |
| `generated_at` | 生成时间 |

## 使用方法

```bash
python -m markflow.cli.commands execute novel_writer [参数]
```

### 示例

```bash
# 首次生成小说
python -m markflow.cli.commands execute novel_writer genre="科幻" title="星际行者" outline="探索宇宙" chapter_count=3

# 断点续写
python -m markflow.cli.commands execute novel_writer genre="科幻" title="星际行者" chapter_count=6 continue_from="./novel.txt"
```

查看完整参数说明：

```bash
python -m markflow.cli.commands info novel_writer
```

## 输出位置

生成的输出保存在 `skills/novel_writer/output/` 目录下。

---

*文档自动生成于 2026-08-23 17:13:23*