# image_generator

> 图像生成 Skill，支持文生图和图生图

## 功能

- 📝 **文生图**：输入文字描述生成图片
- 🖼️ **图生图**：基于参考图生成新图片
- 🔄 **多引擎支持**：Agnes、Pollinations、HuggingFace、Stability、Replicate、FreeAPI
- ⚡ **自动回退**：API 失败时自动切换到备用引擎

## 依赖

```bash
pip install Pillow requests
```
## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | string | 必填 | 提示词 |
| `width` | integer | 1024 | 宽度 |
| `height` | integer | 1024 | 高度 |
| `steps` | integer | 25 | 推理步数 |
| `cfg` | float | 7.5 | 引导强度 |
| `seed` | integer | 随机 | 随机种子 |
| `engine` | string | agnes | 引擎名称 |

## 输出

| 字段 | 说明 |
|------|------|
| `image_path` | 生成的图片路径 |
| `engine` | 使用的引擎 |
| `seed` | 使用的种子 |
| `width` | 图片宽度 |
| `height` | 图片高度 |
| `elapsed` | 生成耗时 |

## 可用引擎

| 引擎 | 免费 | 说明 |
|------|------|------|
| `agnes` | ✅ | 推荐，需注册获取 API Key |
| `pollinations` | ✅ | 完全免费，无需 API Key |
| `huggingface` | ✅ | 免费有限速，需 API Token |
| `freeapi` | ✅ | 社区免费代理，稳定性较差 |
| `stability` | ❌ | 按量付费 |
| `replicate` | ❌ | 按量付费 |

## 使用方法

### Python 调用

```python
from skills.image_generator import ImageGenerator

# 创建实例
generator = ImageGenerator({"engine": "agnes"})

# 文生图
result = generator.generate("a beautiful sunset over the ocean")
print(result["result"]["image_path"])

# 指定尺寸和引擎
result = generator.generate(
    prompt="cyberpunk city",
    width=1024,
    height=768,
    engine="pollinations",
)
print(result["result"]["image_path"])

# 图生图
from PIL import Image
init_image = Image.open("input.png")
result = generator.generate_from_image(
    prompt="make it look like oil painting",
    image=init_image,
    strength=0.6,
)
print(result["result"]["image_path"])
```

### CLI 调用

```bash
# 文生图
python skills/image_generator/image_generator_cli.py "a beautiful sunset over the ocean"

# 指定尺寸
python skills/image_generator/image_generator_cli.py "sunset" --width 1024 --height 1024

# 指定引擎
python skills/image_generator/image_generator_cli.py "sunset" --engine pollinations

# 图生图
python skills/image_generator/image_generator_cli.py "make it oil painting" --input ref.png --strength 0.6

# 列出可用引擎
python skills/image_generator/image_generator_cli.py --engines

# 生成后自动打开图片
python skills/image_generator/image_generator_cli.py "sunset" --open
```

### 输出位置
生成的图片保存在 ./output/images/ 目录下。

### 环境变量配置
在 .env 文件中配置：

```ini
# 默认引擎
IMAGE_GENERATOR_ENGINE=agnes

# Agnes（推荐）
AGNES_API_KEY=your_api_key_here
AGNES_IMAGE_MODEL=agnes-image-2.1-flash

# Pollinations（免费，无需配置）
POLLINATIONS_MODEL=flux

# HuggingFace
HF_API_TOKEN=your_token_here
HF_MODEL=sdxl

# Stability
STABILITY_API_KEY=your_key_here

# Replicate
REPLICATE_API_TOKEN=your_token_here
```
