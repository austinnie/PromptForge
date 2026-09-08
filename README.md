# 💬 智能生图 (PromptForge: a AI Chat Image Generator)

一个基于 Stable Diffusion 和多种 AI API 的智能对话式图像生成工具。用户通过自然语言描述即可生成高质量图片，支持本地模型和云端 API 双模式。

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ 主要特性

- **双模式生成**: 支持本地 Stable Diffusion 模型和多种云端 API (免费/付费)
- **自然语言交互**: 通过对话即可生成、修改图片，支持上下文理解
- **丰富的 API 支持**: 集成 Pollinations (免费)、Agnes AI (免费)、通义万相、文心一格、腾讯混元、HuggingFace 等
- **智能意图分析**: 自动识别用户意图（文生图、图生图、双人合成、普通对话）
- **LLM 增强**: 可选 Ollama 本地大模型优化提示词
- **图生图 & 双人合成**: 支持上传参考图进行修改，或将两张图合成为双人场景
- **安全过滤**: 内置内容安全检查器，防止生成不当内容
- **轻量级 GUI**: 基于 Tkinter 的简洁图形界面，开箱即用

## 🚀 快速开始

### 环境要求

- Python 3.8 或更高版本
- 至少 8GB RAM (本地模式建议 16GB+)
- 可选: Ollama (用于 LLM 增强)

### 安装

1. **克隆项目**
```bash
git clone https://github.com/yourusername/PromptForge.git
cd chat_image_generator
```

2. 创建虚拟环境 (推荐)

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 配置环境变量 (可选)

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API 密钥
```

5. 启动应用
```bash
python main.py
```

## 📖 使用指南

### 基本操作

1. **选择模式**: 在工具栏切换 `local` (本地) 或 `api` (云端) 模式
2. **选择模型/API**: 
   - 本地模式: 点击 "📂 选择模型" 加载 `.safetensors` 或 `.ckpt` 文件
   - API 模式: 从下拉列表选择提供商 (Pollinations, Agnes, 通义万相等)
3. **输入描述**: 在输入框用自然语言描述你想要的图片
4. **发送**: 按 `Ctrl+Enter` 或点击 "🚀 发送" 按钮

### 支持的操作

| 操作类型 | 示例输入 | 说明 |
|---------|---------|------|
| 文生图 | "生成一张美丽的日落风景" | 从文字生成图片 |
| 图生图 | "把这张图改成油画风格" | 需先上传图片 |
| 双人合成 | "让他们拥抱在一起" | 需上传两张人物图片 |
| 普通对话 | "你好，能帮我生成图片吗？" | 自然语言问答 |

### 上下文记忆

应用会记住你的偏好（风格、场景等），并在后续生成中自动应用。你可以说 "显示偏好" 或 "清除上下文" 来管理。

## 🖥️ API 提供商配置

### 免费无需注册
- **Pollinations AI**: 无需配置，开箱即用
- **Free API**: 社区免费代理，无需注册

### 需要注册 (免费/付费)
- **Agnes AI**: [注册获取 API Key](https://apihub.agnes-ai.com)，无限期免费
- **HuggingFace**: [获取 Access Token](https://huggingface.co/settings/tokens)，免费有限速

### 付费 API (需在 .env 配置)
- 通义万相 (阿里云百炼)
- 文心一格 (百度智能云)
- 腾讯混元

## ⚙️ 配置说明
### 环境变量 (.env)
```ini
# 生成模式: local / api
GENERATION_MODE=api
API_PROVIDER=pollinations

# 本地模型路径
SD_MODEL_PATH=/path/to/model.safetensors

# Pollinations (免费)
POLLINATIONS_MODEL=flux

# Agnes AI (免费)
AGNES_API_KEY=your_api_key_here
# 备用路由（主路由不可用时自动切换）
# AGNES_BASE_URL=https://apihub.agnes-ai.cn/v1
# AGNES_BASE_URL=https://api.agnes-ai.cn/v1
AGNES_IMAGE_MODEL=agnes-image-2.1-flash
AGNES_TEXT_MODEL=agnes-2.5-flash
AGNES_VIDEO_MODEL=agnes-video-v2.0
AGNES_VISION_MODEL=agnes-2.5-flash
# ============================================================
# 视频生成配置
# ============================================================

# 单个视频分段长度
VIDEO_SEGMENT_DURATION=10

# ✅ 是否启用自动循环拼接
# true  = 自动拆分并合并多个 10 秒片段
# false = 只生成 10 秒
VIDEO_AUTO_MERGE=true

# 目标视频时长（秒）
# 注意：Agnes API 单次4-12 秒
VIDEO_DURATION=60

# 通义万相 (阿里云)
TONGYI_API_KEY=your_api_key
TONGYI_MODEL=wanx-v1

# 其他 API 配置...
```

### 生成参数
在 .env 中可调整默认参数：

DEFAULT_STEPS=20 - 推理步数

DEFAULT_CFG=7.5 - 提示词引导强度

DEFAULT_WIDTH=512 - 默认宽度

DEFAULT_HEIGHT=768 - 默认高度

### 📁 项目结构
```text
chat_image_generator/
├── main.py                 # 应用入口
├── gui/
│   └── app.py             # 主界面 (Tkinter)
├── core/                  # 核心逻辑
│   ├── intent_analyzer.py # 意图分析
│   ├── prompt_builder.py  # 提示词构建
│   ├── context_manager.py # 上下文管理
│   └── safety.py          # 安全检查
├── api_engines/           # API 引擎
│   ├── base.py           # 基类
│   ├── pollinations.py   # Pollinations
│   ├── agnes.py          # Agnes AI
│   ├── freeapi.py        # Free API
│   ├── tongyi.py         # 通义万相
│   ├── yige.py           # 文心一格
│   └── hunyuan.py        # 腾讯混元
├── handlers/              # 意图处理器
│   ├── text_to_image.py
│   ├── image_to_image.py
│   ├── couple_handler.py
│   └── chat_handler.py
├── services/              # 服务
│   ├── llm_service.py    # Ollama 集成
│   └── pipeline_pool.py  # 模型池管理
├── config/
│   └── settings.py       # 全局配置
└── requirements.txt      # 依赖列表
```

## 🔧 开发与扩展

### 添加新的 API 提供商

1. 在 `api_engines/` 创建新引擎类，继承 `BaseEngine`
2. 实现 `generate_single()` 方法
3. 在 `api_engines/__init__.py` 的 `create_engine()` 中注册
4. 在 `config/settings.py` 添加配置项

### 自定义意图

在 `core/intent_analyzer.py` 的 `IntentAnalyzer` 类中添加新的触发词和处理逻辑。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📝 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [Stable Diffusion](https://stability.ai/) - 强大的图像生成模型
- [Diffusers](https://github.com/huggingface/diffusers) - 优秀的扩散模型库
- [Pollinations AI](https://pollinations.ai/) - 免费图像生成 API
- [Agnes AI](https://apihub.agnes-ai.com) - 免费多模态 AI API

## ⚠️ 免责声明

本项目仅供学习和研究使用。生成的图片内容由用户输入的提示词决定，使用者需遵守相关法律法规和服务条款。对于本地模式，请确保使用的模型符合其各自的许可协议。
