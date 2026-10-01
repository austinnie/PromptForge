# video_generator

> 视频生成 Skill，支持文生视频和长视频拼接

## 功能

- 🎬 **文生视频**：输入文字描述生成视频
- 📹 **长视频拼接**：自动拆分多段生成后拼接成长视频
- 🔄 **多引擎支持**：Agnes 等

## 依赖

```bash
pip install Pillow requests
```

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | string | 必填 | 提示词 |
| `duration` | integer | 60 | 目标总时长（秒） |
| `segment_duration` | integer | 10 | 单段时长（秒） |
| `width` | integer | 768 | 宽度 |
| `height` | integer | 768 | 高度 |
| `engine` | string | agnes | 引擎名称 |

## 输出

| 字段 | 说明 |
|------|------|
| `video_path` | 生成的视频路径 |
| `duration` | 视频时长 |
| `segments` | 片段数量 |
| `segment_duration` | 单段时长 |
| `elapsed` | 生成耗时 |

## 当前能力边界（重要）

**当前引擎 = Agnes reference 模式。** 也就是说：

- 传图进去时，图是**风格/构图参考**，不是首帧。
- 不传图就是纯文生视频。
- 没有 keyframe(first_frame) 路径。想要「每镜从自己的关键帧出发」的多镜头叙事，
  现在这套做不到——那是 `keyframe-video-production` SKILL 描述的形态，属于方案 B。

**长视频 = 一段图生视频 + N 段文生视频拼接。** 不是多镜头叙事：

- 第 1 段带参考图（如果传了图），后面每段是纯文生视频。
- 每段沿用同一条 prompt，只追加「继续上一段，保持连贯」。
- 段间有 10~15 秒随机冷却，降低 Agnes 创建任务接口的限流风险。
- 拼出来的是同一镜头的连续画面，不是多镜头切换。

**不带任务记录落盘，也不分类重试。** 任何一段失败就跳过继续下一段。
如果想让它整夜跑、失败能续，那需要方案 B 的落盘 + 分类重试机制。

## 可用引擎

| 引擎 | 免费 | 说明 |
|------|------|------|
| `agnes` | ✅ | 推荐，需注册获取 API Key |

## 使用方法

### Python 调用

```python
from skills.video_generator import VideoGenerator

# 创建实例
generator = VideoGenerator({"engine": "agnes"})

# 生成 60 秒视频（自动拆分为 6 段 10 秒片段）
result = generator.generate(
    prompt="月光下的森林，镜头缓缓推进",
    duration=60,
    segment_duration=10,
)
print(result["result"]["video_path"])

# 生成 30 秒短视频
result = generator.generate(
    prompt="日落海边",
    duration=30,
)
print(result["result"]["video_path"])
```


###  CLI 调用

```bash
# 默认 60 秒视频
python skills/video_generator/video_generator_cli.py "月光下的森林，镜头缓缓推进"

# 生成 30 秒视频
python skills/video_generator/video_generator_cli.py "日落海边" --duration 30

# 生成 120 秒长视频
python skills/video_generator/video_generator_cli.py "星空" --duration 120 --segment-duration 10

# 生成后自动打开视频
python skills/video_generator/video_generator_cli.py "森林" --open
```

###  输出位置
生成的视频保存在 ./output/videos/ 目录下。

###  环境变量配置
在 .env 文件中配置：

```ini
# Agnes AI（推荐）
AGNES_API_KEY=your_api_key_here
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
AGNES_VIDEO_MODEL=agnes-video-2.5-flash
```
