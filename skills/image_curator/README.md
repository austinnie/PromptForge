# image_curator · 图片鉴赏文章生成

给定一个图片目录，用多模态 AI 逐张鉴赏，自动生成**图文混排**的文章，支持一键粘贴到微信公众号 / 知乎。

---

## ✨ 功能

- 🖼️ 自动扫描目录中的图片（`.png` / `.jpg` / `.jpeg` / `.webp` / `.bmp` / `.gif`）
- 🎨 使用多模态大模型逐张鉴赏：主体、构图、色彩、光影、风格、氛围
- 🔁 失败自动重试：单张最多 3 次，第 2 次起自动换"更简单"的提示词
- 🛡️ 文件名兜底：连续失败时用文件名生成占位描述，保证文章不出现空洞
- 📝 **多格式输出**
- 📂 输出目录自带 `assets/`，图片本地化，**离线可看**
- 😴 图片间自动节流，避免触发 API 限流
- 🖼️ 送模型前自动缩到最长边 1280px，省 token

### 支持的输出格式

| 格式 | 文件 | 用途 |
|---|---|---|
| Markdown | `article.md` | 版本管理、二次编辑 |
| HTML | `article.html` | 优雅排版，浏览器直接看 |
| Word | `article.docx` | 导入公众号、线下分发 |
| PDF | `article.pdf` | 打印、正式存档 |
| 富文本 | `clipboard.html` | 一键复制到微信 / 知乎编辑器 |

---

## 📦 依赖

### 安装

```cmd
pip install -r requirements.txt
```

### requirements.txt（image_curator 专用）

```txt
requests>=2.31.0          # 调用 Agnes 多模态 API
Pillow>=10.0.0            # 图片缩放、格式转换
python-dotenv>=1.0.0      # 读取 .env 中的 AGNES_API_KEY
python-docx>=1.1.0        # 生成 Word (.docx)
xhtml2pdf>=0.2.11         # 生成 PDF（Windows 友好，纯 Python）
```

### 依赖说明

| 依赖 | 用途 | 缺失后果 |
|---|---|---|
| `requests` | 调用 Agnes API | ❌ 技能无法运行 |
| `Pillow` | 图片处理 | ❌ 技能无法运行 |
| `python-dotenv` | 读 `.env` | ❌ 无法初始化引擎 |
| `python-docx` | 生成 Word | ⚠️ 跳过 Word 输出，其余正常 |
| `xhtml2pdf` | 生成 PDF | ⚠️ 跳过 PDF 输出，其余正常 |

> 前三个是必需的，后两个不装也不崩，代码会自动跳过对应格式。

### 验证安装

```cmd
python -c "import requests, PIL, dotenv, docx, xhtml2pdf; print('OK')"
```

输出 `OK` 即可。

### 可选增强

```cmd
:: PDF 高质量排版（Windows 需先装 GTK）
:: 装了会优先使用它生成 PDF，比 xhtml2pdf 效果好
pip install weasyprint
```

PDF 生成走三级回退：

```
weasyprint → xhtml2pdf → 浏览器打印版 article.print.html
```

---

## ⚙️ 配置

### 1. 在 `.env` 里配置 API Key

项目根目录需要 `.env`（参考 `.env.sample`）：

```env
AGNES_API_KEY=你的_api_key
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
AGNES_VIDEO_MODEL=agnes-video-2.5-flash
```

- 注册地址：<https://platform.agnes-ai.com/>
- `.env` 已加入 `.gitignore`，**不要提交到仓库**

### 2. 依赖的 Settings 字段

`config/settings.py` 需暴露以下字段（已有则跳过）：

```python
class Settings:
    agnes_api_key: str       # 从 .env 读
    agnes_base_url: str      # Agnes API 地址
    agnes_video_model: str   # Agnes 模型名（视觉用同一个）
```

---

## 🚀 使用

### 命令行

```cmd
:: 全格式（默认 md,html,docx,pdf,clipboard）
python skills/image_curator/image_curator_cli.py output/机甲 --open

:: 自定义标题
python skills/image_curator/image_curator_cli.py output/机甲 -t "机甲之美" --open

:: 递归子目录
python skills/image_curator/image_curator_cli.py output/机甲 -r

:: 限定张数
python skills/image_curator/image_curator_cli.py output/机甲 --max-images 20

:: 只生成 Markdown + 微信富文本
python skills/image_curator/image_curator_cli.py output/机甲 -f md,clipboard
```

### 参数说明

| 参数 | 简写 | 说明 | 默认 |
|---|---|---|---|
| `directory` | — | 图片目录（必填） | — |
| `--title` | `-t` | 文章标题 | 目录名 |
| `--intro` | — | 引言 | AI 生成 |
| `--recursive` | `-r` | 递归子目录 | 关 |
| `--max-images` | — | 最多处理张数 | 100 |
| `--formats` | `-f` | 输出格式（逗号分隔） | `md,html,docx,pdf,clipboard` |
| `--open` | — | 完成后打开（优先级：clipboard > html > docx > pdf） | 关 |

### Python 调用

```python
from skills.image_curator import ImageCurator

curator = ImageCurator({
    "generate_html": True,
    "generate_docx": True,
    "generate_pdf": True,
    "generate_clipboard": True,
})
result = curator.curate("output/机甲", title="机甲之美")
print(result["result"]["article_path"])
```

### 自定义鉴赏提示词

```python
curator = ImageCurator({
    "description_prompt": "用诗意的语言描述这张图，80 字以内。",
    "vision_max_size": 1024,      # 送模型前缩放
    "throttle_seconds": 3,        # 图间冷却
})
```

---

## 📂 输出结构

```
output/articles/20260912_HHMMSS_机甲/
├── article.md           # Markdown 文章
├── article.html         # 网页阅读版（优雅排版）
├── article.docx         # Word（可导入公众号）
├── article.pdf          # PDF
├── clipboard.html       # 微信/知乎富文本（点"复制全文"）
├── metadata.json        # 原始数据（标题、引言、每张图描述）
└── assets/              # 本地化图片副本
    ├── 20260910_205612_api_美女机甲图片.png
    └── ...
```

---

## 📱 微信公众号 / 知乎发布流程

### 方式一：Word 导入

1. 打开 `article.docx`
2. 微信公众平台 → 图文编辑 → 右上角 **文档导入**（或使用"壹伴助手"等插件的"导入 Word"）
3. **导入后逐张检查图片** —— Word 里的本地图片，公众号需重新上传
4. ⚠️ 公众号对 Word 导入支持有限（15M / 10M 限制），图片多时建议用方式二

### 方式二：富文本一键复制（推荐）

1. 浏览器打开 `clipboard.html`
2. 点顶部橙色按钮 **📋 复制全文**
3. 到微信公众平台编辑器 / 知乎编辑器里 `Ctrl+V`
4. **图片需手动上传** —— 把 `assets/` 里的图片拖进编辑器即可

> 微信编辑器会保留粘贴的内联样式，但会过滤部分属性（如 `border-radius`），属于正常现象。核心排版（标题、分隔线、图片居中、正文行距）都会保留。

---

## 🧰 目录结构

```
skills/image_curator/
├── __init__.py              # 导出 ImageCurator
├── skill.py                 # 主技能逻辑
├── writers.py               # 多格式输出器（Word / PDF / 富文本）
├── image_curator_cli.py     # 命令行入口
├── retry_empty.py           # 补跑工具：只重跑描述为空的图
├── meta.json                # 技能元数据
└── README.md                # 本文档
```

---

## 🔧 常见问题

### Q1：某张图没有鉴赏文字

**原因**：模型对个别图返回空 / 过短描述，重试 3 次仍失败。
**表现**：`metadata.json` 里该条目 `error` 非空。
**处理**：

```cmd
:: 只重跑失败 / 描述过短的图
python skills/image_curator/retry_empty.py output/articles/20260912_XXXXXX_机甲
```

如果反复失败，说明模型确实"描述不出来"（图片是半成品/敏感内容），可用文件名兜底策略（见 `skill.py` 的 `_analyze_image`）。

### Q2：PDF 里图片缺失

**原因**：xhtml2pdf 无法处理中文路径 / 空格。
**解决**：`writers.py` 里已改为 **base64 内嵌图片**。若仍缺图，装 `weasyprint`：

```cmd
pip install weasyprint
```

### Q3：提示"视觉引擎初始化失败"

检查 `.env`：

```cmd
python -c "import sys; sys.path.insert(0,'.'); from config.settings import settings; print('key:', settings.agnes_api_key[:8] + '...'); print('url:', settings.agnes_base_url)"
```

Key 或 URL 为空 → 补 `.env`。

### Q4：API 返回 429（限流）

调大冷却时间：

```python
curator = ImageCurator({"throttle_seconds": 5})   # 默认 2s
```

### Q5：导入微信后样式错乱

微信编辑器会过滤部分 CSS。`clipboard.html` 里所有样式已内联，兼容性良好。若仍有问题，检查：

- 标题层级是否用了 `<h1>`（微信只认 `<h2>` 以下）
- 图片是否手动上传过
- 是否用旧版 IE 打开（不推荐）

### Q6：`ImportError: cannot import name 'ImageCurator'`

检查 `__init__.py` 存在且内容为：

```python
from .skill import ImageCurator

__all__ = ["ImageCurator"]
```

若报 `(unknown location)`，通常意味着 `__init__.py` 缺失或为空。

---

## 🔌 扩展方向

| 想法 | 实现难度 | 备注 |
|---|---|---|
| 多张图汇总成"策展人导读" | ⭐ | 现在只有引言 |
| 自动按主题/文件名分组 | ⭐⭐ | 聚类算法 |
| 每张图打分 + 推荐指数 | ⭐ | 提示词加"打分" |
| 自动上传图床，微信/知乎免手动传图 | ⭐⭐ | 接 SM.MS / OSS |
| 生成微信公众号"素材"格式 | ⭐⭐ | 直接调微信 API |
| 视频化（图片 + TTS + 配乐 → mp4） | ⭐⭐⭐ | 复用 `video_generator` |

---

## 📄 License

与主项目一致。