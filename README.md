# 💬 PromptForge：智能对话式 AI 图像 / 视频 / 多媒体生成器

一个基于 Stable Diffusion 和多种 AI API 的智能对话式创作工具。用户通过自然语言描述即可生成高质量图片、视频，甚至完成从小说脚本到成片的全自动多媒体创作。支持本地模型与云端 API 双模式。

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ 主要特性

- **双模式生成**：支持本地 Stable Diffusion 模型和多种云端 API（免费 / 付费）
- **图像生成**：文生图、图生图、双人合成、多人合成（3+ 张图）
- **视频生成**：集成 Agnes 视频模型，按 10 秒分段并自动循环拼接至目标时长
- **多媒体全自动创作**：小说脚本 → 场景拆分 → 视频片段 → 语音旁白 → 背景音乐 → 字幕 → 最终成片
- **自然语言交互**：通过对话即可生成、修改图片，支持上下文理解与偏好记忆
- **丰富的 API 支持**：Pollinations（免费）、Agnes AI（免费）、Free API、通义万相、文心一格、腾讯混元、HuggingFace、Replicate、Stability AI
- **智能意图分析**：自动识别文生图、图生图、双人/多人合成、视频生成、多媒体创作、普通对话
- **LLM 增强**：可选 Ollama 本地大模型优化提示词、生成小说、生成技术文章
- **技能系统**：内置 `image_generator`、`video_generator`、`music_generator`、`news_aggregator`、`novel_writer`、`tech_hot_article`、`voice_assistant`
- **安全过滤**：内置内容安全检查器，支持安全开关与敏感词清理
- **轻量级 GUI**：基于 Tkinter 的简洁图形界面，支持图片缩略图预览、双击查看大图

## 🚀 快速开始

### 环境要求

- Python 3.8 或更高版本
- 至少 8GB RAM（本地模式建议 16GB+）
- 可选：Ollama（用于 LLM 增强、小说生成、新闻摘要）
- 可选：FFmpeg（用于视频 / 音频合并）
- 可选：FluidSynth + SoundFont（用于 MIDI 音乐合成）
- 视频生成需要可访问 Agnes API，并配置 `AGNES_API_KEY`

### 安装

1. **克隆项目**

```bash
git clone https://github.com/austinnie/PromptForge.git
cd PromptForge
```

2. **创建虚拟环境（推荐）**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

> PyTorch 建议按官方说明安装 CPU 或 CUDA 版本：
> `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`

4. **配置环境变量（可选）**

```bash
cp .env.sample .env
# 编辑 .env 文件，填入你的 API 密钥
```

5. **启动应用**

```bash
python main.py
```

## 📖 使用指南

### 基本操作

1. **选择模式**：在工具栏切换 `local`（本地）或 `api`（云端）模式
2. **选择模型 / API**：
   - 本地模式：点击“📂 选择模型”加载 `.safetensors` 或 `.ckpt` 文件
   - API 模式：从下拉列表选择提供商（Pollinations、Agnes、通义万相等）
3. **输入描述**：在输入框用自然语言描述你想要的图片或视频
4. **发送**：按 `Ctrl+Enter` 或点击“🚀 发送”按钮

### 支持的操作

| 操作类型 | 示例输入 | 说明 |
|---------|---------|------|
| 文生图 | “生成一张美丽的日落风景” | 从文字生成图片 |
| 图生图 | “把这张图改成油画风格” | 需先上传 1 张图片 |
| 双人合成 | “让他们拥抱在一起” | 需上传 2 张人物图片 |
| 多人合成 | “把这三个人放在同一个场景里” | 需上传 3 张以上人物图片 |
| 视频生成 | “生成一段 60 秒的日落海浪视频” | 需 API 模式，且选择支持视频的提供商（Agnes） |
| 多媒体创作 | “创作一个关于月光森林的视频” | 全自动：小说 → 视频 → 语音 → 音乐 → 字幕 → 成片 |
| 普通对话 | “你好，能帮我生成图片吗？” | 自然语言问答 |

### 视频生成

1. 在 `.env` 中配置视频相关参数：

```ini
VIDEO_SEGMENT_DURATION=10
VIDEO_AUTO_MERGE=true
VIDEO_DURATION=60
```

2. 切换到 API 模式，选择支持视频生成的提供商（如 Agnes）
3. 输入视频描述，例如：

```text
生成一段 60 秒的日落海浪视频
```

4. 当 `VIDEO_AUTO_MERGE=true` 时，应用会根据 `VIDEO_SEGMENT_DURATION` 自动拆分并合并多个视频片段

> 注意：Agnes API 单次视频生成时长通常为 4-12 秒，长视频通过分段拼接实现，需要安装 FFmpeg。

### 多媒体全自动创作

输入“创作视频 ...”“全自动 ...”“生成故事 ...”等指令，会触发 `MultimediaWorkflow`：

1. 用 Ollama 生成小说脚本并拆分为场景
2. 为每个场景生成视频片段、语音旁白、背景音乐、字幕
3. 逐段合并，最终拼接为完整视频

### 上下文记忆

应用会记住你的偏好（风格、场景等），并在后续生成中自动应用。你可以说“显示偏好”“上下文”或“清除上下文”来管理。

## 🖥️ API 提供商配置

### 免费无需注册

- **Pollinations AI**：无需配置，开箱即用
- **Free API**：社区免费代理，无需注册（稳定性较差）

### 需要注册（免费 / 付费）

- **Agnes AI**：[注册获取 API Key](https://apihub.agnes-ai.com)，支持图像、文本、视频、视觉模型，无限期免费
- **HuggingFace**：[获取 Access Token](https://huggingface.co/settings/tokens)，免费有限速
- **Replicate**：[获取 API Token](https://replicate.com/account/api-tokens)，按量付费，支持真正的图生图
- **Stability AI**：[获取 API Key](https://platform.stability.ai/account/keys)，按量付费，支持真正的图生图

### 付费 API（需在 .env 配置）

- 通义万相（阿里云百炼）
- 文心一格（百度智能云）
- 腾讯混元

## ⚙️ 配置说明

### 环境变量（.env）

```ini
# ============================================================
# 生成模式
# ============================================================
GENERATION_MODE=api          # local / api
API_PROVIDER=pollinations    # pollinations / agnes / huggingface / tongyi / yige / hunyuan / freeapi / replicate / stability

# ============================================================
# 本地模型
# ============================================================
SD_MODEL_PATH=/path/to/model.safetensors

# ============================================================
# Pollinations（免费，无需 Key）
# ============================================================
POLLINATIONS_MODEL=flux

# ============================================================
# Agnes AI（免费，需注册）
# ============================================================
AGNES_API_KEY=your_api_key_here
# 备用路由（主路由不可用时自动切换）
# AGNES_BASE_URL=https://apihub.agnes-ai.cn/v1
# AGNES_BASE_URL=https://api.agnes-ai.cn/v1
AGNES_IMAGE_MODEL=agnes-image-2.1-flash
AGNES_TEXT_MODEL=agnes-2.5-flash
AGNES_VIDEO_MODEL=agnes-video-2.5-flash
AGNES_VISION_MODEL=agnes-2.5-flash

# ============================================================
# 视频生成配置
# ============================================================
VIDEO_SEGMENT_DURATION=10    # 单个视频分段长度（秒）
VIDEO_AUTO_MERGE=true        # 是否启用自动循环拼接
VIDEO_DURATION=60            # 目标视频时长（秒）
                             # 注意：Agnes API 单次 4-12 秒

# ============================================================
# 通义万相（阿里云）
# ============================================================
TONGYI_API_KEY=your_api_key
TONGYI_MODEL=wanx-v1

# ============================================================
# 文心一格（百度）
# ============================================================
YIGE_API_KEY=your_api_key
YIGE_SECRET_KEY=your_secret_key

# ============================================================
# 腾讯混元
# ============================================================
HUNYUAN_SECRET_ID=your_secret_id
HUNYUAN_SECRET_KEY=your_secret_key

# ============================================================
# HuggingFace
# ============================================================
HF_API_TOKEN=your_token
HF_MODEL=sdxl

# ============================================================
# Replicate / Stability（付费，支持图生图）
# ============================================================
REPLICATE_API_TOKEN=your_token
REPLICATE_MODEL=stability-ai/stable-diffusion

STABILITY_API_KEY=your_key
STABILITY_MODEL=stable-diffusion-xl-1024-v1-0

# ============================================================
# Free API（社区免费代理）
# ============================================================
FREEAPI_MODEL=flux

# ============================================================
# 生成参数
# ============================================================
DEFAULT_STEPS=20             # 推理步数
DEFAULT_CFG=7.5              # 提示词引导强度
DEFAULT_STRENGTH=0.35        # 图生图默认强度
DEFAULT_WIDTH=512            # 默认宽度
DEFAULT_HEIGHT=768           # 默认高度

# ============================================================
# 安全
# ============================================================
SAFE_MODE=true
ENABLE_SAFETY_CHECK=true     # 是否启用安全检测

# ============================================================
# LLM（Ollama）
# ============================================================
LLM_ENABLED=true
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b

# ============================================================
# 技术文章配图引擎
# ============================================================
ARTICLE_IMAGE_ENGINE=agnes
```

### 生成参数

在 `.env` 中可调整默认参数：

```ini
DEFAULT_STEPS=20             # 推理步数
DEFAULT_CFG=7.5              # 提示词引导强度
DEFAULT_STRENGTH=0.35        # 图生图默认强度
DEFAULT_WIDTH=512            # 默认宽度
DEFAULT_HEIGHT=768           # 默认高度
```

### 安全配置

安全开关可在 `.env` 中配置，用于控制内容安全检查器的行为。

```ini
SAFE_MODE=true
ENABLE_SAFETY_CHECK=true     # 是否启用安全检测
```

## 📁 项目结构

```text
PromptForge/
├── main.py                       # 应用入口
├── gui/
│   └── app.py                    # 主界面 (Tkinter)
├── core/                         # 核心逻辑
│   ├── intent_analyzer.py        # 意图分析
│   ├── prompt_builder.py         # 提示词构建
│   ├── context_manager.py        # 上下文管理
│   └── safety.py                 # 安全检查
├── api_engines/                  # API 引擎
│   ├── base.py                   # 基类
│   ├── pollinations.py           # Pollinations
│   ├── agnes.py                  # Agnes AI（图像/文本/视频/视觉）
│   ├── freeapi.py                # Free API
│   ├── tongyi.py                 # 通义万相
│   ├── yige.py                   # 文心一格
│   ├── hunyuan.py                # 腾讯混元
│   ├── huggingface.py            # HuggingFace
│   ├── replicate.py              # Replicate（支持图生图）
│   └── stability.py              # Stability AI（支持图生图）
├── handlers/                     # 意图处理器
│   ├── base.py
│   ├── text_to_image.py
│   ├── image_to_image.py
│   ├── couple_handler.py
│   ├── multi_person_handler.py
│   ├── chat_handler.py
│   ├── video_handler.py
│   └── multimedia_handler.py
├── services/                     # 服务
│   ├── llm_service.py            # Ollama 集成
│   ├── pipeline_pool.py          # 模型池管理
│   └── image_processor.py        # 图片后处理
├── skills/                       # 技能模块
│   ├── image_generator/          # 图像生成
│   ├── video_generator/          # 视频生成
│   ├── music_generator/          # 音乐生成（MIDI + MusicGen）
│   ├── news_aggregator/          # 新闻聚合 + AI 摘要
│   ├── novel_writer/             # 小说生成（多语言）
│   ├── tech_hot_article/         # 技术热点文章 + 配图 + Word
│   └── voice_assistant/          # 语音合成 / 识别
├── multimedia/                   # 多媒体工作流
│   ├── workflow.py               # 全自动创作主流程
│   ├── assembler.py              # 视频合成
│   └── subtitle.py               # 字幕生成
├── config/
│   └── settings.py               # 全局配置
├── .env.sample                   # 环境变量模板
└── requirements.txt              # 依赖列表
```

## 🔧 开发与扩展

### 添加新的 API 提供商

1. 在 `api_engines/` 创建新引擎类，继承 `BaseEngine`
2. 实现 `generate_single()` 方法
3. 在 `api_engines/__init__.py` 的 `create_engine()` 中注册
4. 在 `config/settings.py` 添加配置项
5. 如果该提供商支持视频生成，请按现有 Agnes 视频流程扩展分段与拼接逻辑

### 自定义意图

在 `core/intent_analyzer.py` 的 `IntentAnalyzer` 类中添加新的触发词和处理逻辑。

### 技能系统

技能模块位于 `skills/` 目录，每个技能包含：

- `skill.py`：核心实现
- `meta.json`：元信息
- `*_cli.py`：命令行入口
- `README.md`：使用说明

可按需添加新技能模块，并在 `skills/__init__.py` 中注册。

当前包含：

- `image_generator`：图像生成技能，支持文生图、图生图，多引擎切换与自动回退
- `video_generator`：视频生成技能，支持文生视频与长视频分段拼接
- `music_generator`：AI 音乐大师，自动写词、谱曲，支持 MIDI 与 MusicGen 两种模式
- `news_aggregator`：新闻聚合器，RSS 新闻抓取 + AI 智能摘要，支持多分类
- `novel_writer`：小说生成技能，使用本地 Ollama 大模型自动写小说，支持多语言与断点续写
- `tech_hot_article`：技术热点文章生成器，基于实时热点生成文章，自动配图并输出 Word 文档
- `voice_assistant`：语音合成（TTS）与语音识别（STT）助手，支持多语言与长文本分段

### image_generator 单独使用举例
```text
# 文生图
python skills/image_generator/image_generator_cli.py "a beautiful sunset over the ocean" --open

# 指定引擎
python skills/image_generator/image_generator_cli.py "sunset" --engine pollinations --open

# 指定尺寸
python skills/image_generator/image_generator_cli.py "cyberpunk city" --width 1024 --height 768 --open

# 指定推理步数与引导强度
python skills/image_generator/image_generator_cli.py "portrait of a girl" --steps 30 --cfg 7.5 --open

# 指定随机种子（可复现）
python skills/image_generator/image_generator_cli.py "sunset" --seed 12345 --open

# 图生图
python skills/image_generator/image_generator_cli.py "make it oil painting style" --input ./test.png --strength 0.6 --open

# 列出可用引擎
python skills/image_generator/image_generator_cli.py --engines
```

### video_generator 单独使用举例

```text
# 默认 60 秒视频
python skills/video_generator/video_generator_cli.py "月光下的森林，镜头缓缓推进" --open

# 生成 30 秒视频
python skills/video_generator/video_generator_cli.py "日落海边" --duration 30 --open

# 生成 120 秒长视频
python skills/video_generator/video_generator_cli.py "星空" --duration 120 --segment-duration 10 --open

# 指定分辨率
python skills/video_generator/video_generator_cli.py "雪山日出" --width 1280 --height 720 --open

# 指定单段时长
python skills/video_generator/video_generator_cli.py "城市夜景" --duration 60 --segment-duration 5 --open

# 生成后自动打开视频
python skills/video_generator/video_generator_cli.py "森林" --open
```

### music_generator 单独使用举例

```text
# 交互式模式（推荐，会提示选择主题、情绪、时长）
python skills/music_generator/music_generator_cli.py

# 快速生成（主题 + 情绪 + 时长）
python skills/music_generator/music_generator_cli.py --quick "星辰大海" "peaceful" 30

# 快速生成（自定义主题 + 壮丽情绪 + 60 秒）
python skills/music_generator/music_generator_cli.py --quick "月光下的森林" "epic" 60

# 查看帮助
python skills/music_generator/music_generator_cli.py --help

# 多乐器交响乐（高级功能）
python skills/music_generator/generate_symphony.py
```

可用情绪：peaceful, melancholic, joyful, epic, mysterious

## news_aggregator 单独使用举例
```python
# Python 调用（推荐）
from skills import NewsAggregator

# 抓取国际新闻，生成简报
aggregator = NewsAggregator({
    "output_dir": "./output/news",
    "ai_model": "qwen2.5:1.5b",
    "validate_feeds": True,
    "top_n": 15,
})
result = aggregator.execute(category="world", top_n=15)
print(result["result"]["report_file"])

# 抓取科技新闻
result = aggregator.execute(category="tech", top_n=20)

# 抓取财经新闻
result = aggregator.execute(category="business", top_n=10)

# 抓取中国新闻
result = aggregator.execute(category="china", top_n=15)
```
可用分类：world, tech, business, china, usa, japan, korea

## novel_writer 单独使用举例
```python
# Python 调用（推荐）
from skills.novel_writer.skill import NovelWriterOllama

# 创建实例
writer = NovelWriterOllama({
    "default_model": "qwen2.5:1.5b",
    "ollama_url": "http://localhost:11434",
    "output_dir": "./skills/novel_writer/output/novels",
})

# 生成科幻小说（1 章，600 字）
result = writer.execute(
    genre="科幻",
    title="星际行者",
    outline="探索未知宇宙，发现外星文明",
    characters="主角：李晨，一位勇敢的探险家",
    chapter_count=1,
    words_per_chapter=600,
)
print(result["result"]["saved_to"])

# 多语言支持（日语）
result = writer.execute(
    genre="SF",
    title="星の旅人",
    outline="宇宙を探検する少年の冒険",
    characters="主人公：アキラ",
    chapter_count=1,
    words_per_chapter=800,
    language="ja",
)

# 断点续写（从已有文件继续）
result = writer.execute(
    genre="科幻",
    title="星际行者",
    outline="继续探索",
    characters="李晨",
    chapter_count=3,
    continue_from="./skills/novel_writer/output/novels/zh_星际行者_xxx.txt",
)
```
支持语言：中文、English、日本語、Español、Français、Deutsch 等 17 种

## tech_hot_article 单独使用举例
```text
# 随机生成一篇技术文章（默认 1500 字，自动配图 3 张）
python skills/tech_hot_article/tech_hot_article_cli.py

# 指定写作风格
python skills/tech_hot_article/tech_hot_article_cli.py --style "深度技术型"

# 指定使用第 1 个热点
python skills/tech_hot_article/tech_hot_article_cli.py --index 0

# 指定字数
python skills/tech_hot_article/tech_hot_article_cli.py --words 2000

# 指定模型
python skills/tech_hot_article/tech_hot_article_cli.py --model qwen2.5:7b

# 列出当前热点（不生成文章）
python skills/tech_hot_article/tech_hot_article_cli.py --list

# 生成后自动打开 Word 文档
python skills/tech_hot_article/tech_hot_article_cli.py --open

# 组合使用
python skills/tech_hot_article/tech_hot_article_cli.py --style "深度技术型" --words 2000 --open
```
写作风格：专业分析型, 通俗科普型, 深度技术型, 行业观察型, 趋势预测型

## voice_assistant 单独使用举例
```text
# 文本转语音（TTS）
python skills/voice_assistant/skill.py --action tts --text "你好，欢迎使用 PromptForge"

# 指定语音和语速
python skills/voice_assistant/skill.py --action tts --text "Hello World" --voice en-US-JennyNeural --speed 1.2

# 长文本朗读（会自动分段）
python skills/voice_assistant/skill.py --action tts --text "很长的一段文字..." --voice zh-CN-XiaoxiaoNeural

# 语音识别（STT）
python skills/voice_assistant/skill.py --action stt --audio ./test.mp3 --language zh-CN

# 列出可用语音
python skills/voice_assistant/skill.py --action list_voices

# 指定输出路径
python skills/voice_assistant/skill.py --action tts --text "测试" --output ./output/test.mp3
```
可用语音：zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural, en-US-JennyNeural, ja-JP-NanamiNeural, ko-KR-SunHiNeural 等

## 通用调用方式（Python 统一入口）
```python
# 所有 skills 都可以通过统一方式调用
from skills import (
    ImageGenerator,
    VideoGenerator,
    MusicMaestro,
    NewsAggregator,
    NovelWriterOllama,
    TechHotArticle,
    VoiceAssistant,
)

# 图像生成
img_gen = ImageGenerator({"engine": "agnes"})
result = img_gen.generate("a beautiful sunset")
print(result["result"]["image_path"])

# 视频生成
vid_gen = VideoGenerator({"engine": "agnes"})
result = vid_gen.generate("月光下的森林", duration=30)
print(result["result"]["video_path"])

# 音乐生成
music = MusicMaestro({"music_mode": "auto"})
result = music.execute(topic="星辰大海", emotion="peaceful", duration=30)
print(result["result"]["audio_file"])

# 新闻聚合
news = NewsAggregator({"output_dir": "./output/news"})
result = news.execute(category="world", top_n=15)
print(result["result"]["report_file"])

# 小说生成
writer = NovelWriterOllama()
result = writer.execute(
    genre="科幻", title="星际行者",
    outline="探索宇宙", characters="李晨",
    chapter_count=1, words_per_chapter=600,
)
print(result["result"]["saved_to"])

# 技术文章
article = TechHotArticle()
result = article.execute(style="深度技术型")
print(result["result"]["word_file"])

# 语音合成
voice = VoiceAssistant()
result = voice.execute(action="tts", text="你好")
print(result["result"]["audio_path"])
```

## Skills 调用汇总表

| Skill | 命令行工具 | 主要用途 |
|-------|-----------|----------|
| `image_generator` | `image_generator_cli.py` | 文生图、图生图 |
| `video_generator` | `video_generator_cli.py` | 文生视频、长视频拼接 |
| `music_generator` | `music_generator_cli.py` | 音乐生成（MIDI/MusicGen） |
| `news_aggregator` | 仅 Python 调用 | 新闻抓取 + AI 摘要 |
| `novel_writer` | 仅 Python 调用 | 小说生成（多语言） |
| `tech_hot_article` | `tech_hot_article_cli.py` | 技术文章生成 + 配图 |
| `voice_assistant` | `skill.py --action` | TTS / STT |

## 完整调用路径对照

| Skill | 完整命令行路径 |
|-------|--------------|
| `image_generator` | `python skills/image_generator/image_generator_cli.py` |
| `video_generator` | `python skills/video_generator/video_generator_cli.py` |
| `music_generator` | `python skills/music_generator/music_generator_cli.py` |
| `news_aggregator` | Python 调用 `from skills import NewsAggregator` |
| `novel_writer` | Python 调用 `from skills.novel_writer.skill import NovelWriterOllama` |
| `tech_hot_article` | `python skills/tech_hot_article/tech_hot_article_cli.py` |
| `voice_assistant` | `python skills/voice_assistant/skill.py --action tts` |

### 外部工具依赖

部分功能需要额外的外部工具：

| 工具 | 用途 | 安装方式 |
|------|------|---------|
| FFmpeg | 视频 / 音频合并 | [ffmpeg.org](https://ffmpeg.org/download.html) |
| FluidSynth | MIDI → WAV 合成 | 放入 `skills/music_generator/soundfonts/` |
| SoundFont (.sf2) | MIDI 音色库 | 放入 `skills/music_generator/soundfonts/` |
| Ollama | LLM 增强、小说、新闻摘要 | [ollama.com](https://ollama.com/) |

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的特性分支（`git checkout -b feature/AmazingFeature`）
3. 提交更改（`git commit -m 'Add some AmazingFeature'`）
4. 推送到分支（`git push origin feature/AmazingFeature`）
5. 开启 Pull Request

## 📝 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](https://github.com/austinnie/PromptForge/blob/main/LICENSE) 文件。

## 🙏 致谢

- [Stable Diffusion](https://stability.ai/) - 强大的图像生成模型
- [Diffusers](https://github.com/huggingface/diffusers) - 优秀的扩散模型库
- [Pollinations AI](https://pollinations.ai/) - 免费图像生成 API
- [Agnes AI](https://apihub.agnes-ai.com) - 免费多模态 AI API
- [MoviePy](https://zulko.github.io/moviepy/) - 视频编辑库
- [edge-tts](https://github.com/rany2/edge-tts) - 免费 TTS
- [Ollama](https://ollama.com/) - 本地大模型运行环境

## ⚠️ 免责声明

本项目仅供学习和研究使用。生成的图片、视频、音乐、文章等内容由用户输入的提示词决定，使用者需遵守相关法律法规和服务条款。对于本地模式，请确保使用的模型符合其各自的许可协议。
