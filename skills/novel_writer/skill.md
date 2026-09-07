# novel_writer_ollama

## 描述
使用本地 Ollama 大模型自动写小说

## 目的


## 输入
- **genre**: 小说类型 (科幻/奇幻/言情/悬疑/武侠/都市)
- **title**: 小说标题
- **outline**: 故事大纲，描述主要情节
- **characters**: 主要角色设定
- **chapter_count**: 要生成的章节数量，默认 3，范围 1-10
- **words_per_chapter**: 每章目标字数，默认 500，范围 200-2000
- **style**: 写作风格 (简洁/细腻/幽默/严肃)，默认 细腻
- **temperature**: 创意程度 0-1，默认 0.85
- **model**: 使用的模型，默认 qwen2.5:7b
- **ollama_url**: Ollama 服务地址，默认 http://localhost:11434

## 输出
- **title**: 小说标题
- **genre**: 小说类型
- **chapters**: 所有章节列表，每章包含标题和内容
- **summary**: 小说简介
- **total_words**: 总字数
- **model_used**: 使用的模型名称
- **generated_at**: 生成时间

## 步骤
无

## 依赖
- requests
- json

## 版本
1.0.0
