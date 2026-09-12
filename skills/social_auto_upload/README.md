# social_auto_upload

多平台内容分发 skill。内嵌 `social-auto-upload`，通过 `social_auto_upload_cli.py` 或 `sau` CLI 将视频/图文上传到抖音、快手、小红书、B站、视频号、百家号、支付宝生活号、微博、虎扑、YouTube 等平台。

## 快速使用

以小红书为例，同一平台下三种内容形态分别调用不同子命令：

### 1. 图文混排文章（多图 + 标题 + 长正文 + 标签）

```bash
python social_auto_upload_cli.py publish-note xiaohongshu \
  cover.png detail1.png detail2.png \
  "春季露营装备清单｜新手必看" \
  --note "这次整理了 10 件入门级露营装备，从帐篷到炊具都实测过，附上避坑建议……" \
  --tags 露营,户外,好物推荐 \
  --account myaccount
```

- `images`：位置参数，可传入多张图片，顺序即为文章内展示顺序。
- `--note`：正文内容（可长文）。
- `--tags`：逗号分隔。
- `--account`：账号名，对应 `cookies/xiaohongshu_myaccount.json`。

### 2. 单图 / 纯图片笔记

```bash
python social_auto_upload_cli.py publish-note xiaohongshu \
  photo.png \
  "今日份的晚霞" \
  --account myaccount
```

- 只需一张图片时可省略 `--note` 和 `--tags`。

### 3. 视频（含封面图 + 简介 + 标签 + 定时发布）

```bash
python social_auto_upload_cli.py publish-video xiaohongshu \
  vlog.mp4 \
  "周末露营 Vlog" \
  --desc "两天的露营记录，全程 4K 拍摄" \
  --thumbnail cover.png \
  --tags 露营,Vlog \
  --schedule "2026-03-24 21:30" \
  --account myaccount
```

- `file`：视频文件路径（位置参数）。
- `--thumbnail`：封面图（可选，部分平台必填，如微博/百家号）。
- `--schedule`：定时发布时间，格式 `YYYY-MM-DD HH:MM`，未指定则立即发布。

### 登录 / 校验

```bash
python social_auto_upload_cli.py login xiaohongshu --account myaccount
python social_auto_upload_cli.py check xiaohongshu --account myaccount
```

### 其他平台示例

```bash
# B站（需指定分区 tid）
python social_auto_upload_cli.py publish-video bilibili demo.mp4 "示例标题" --desc "示例简介" --tid 249 --account myaccount

# YouTube（含播放列表与可见性）
python social_auto_upload_cli.py publish-video youtube demo.mp4 "示例标题" --desc "示例简介" --tags tag1,tag2 --playlist "我的系列" --visibility public --account myaccount
```

### YouTube 示例

```bash
# 登录（交互式，会弹出浏览器登录 Google 账号）
sau youtube login --account myaccount

# 检查登录态
sau youtube check --account myaccount

# 上传视频（完整参数）
sau youtube upload-video \
  --account myaccount \
  --file video.mp4 \
  --title "示例标题" \
  --desc "示例简介" \
  --tags tag1,tag2 \
  --thumbnail cover.png \
  --playlist "我的系列" \
  --visibility public
```

说明：

- `--playlist` 可选，用于系列 / 连载。
- `--visibility` 可选 `public` / `unlisted` / `private`。
- YouTube 不支持 `upload-note`，图文请用小红书 / 抖音 / 快手。

## 支持的平台

| 平台 | 登录 | 视频 | 图文 | 定时 |
|------|------|------|------|------|
| 抖音 | ✅ | ✅ | ✅ | ✅ |
| 快手 | ✅ | ✅ | ✅ | ✅ |
| 小红书 | ✅ | ✅ | ✅ | ✅ |
| B站 | ✅ | ✅ | ❌ | ✅ |
| 视频号 | ✅ | ✅ | ❌ | ✅ |
| 百家号 | ✅ | ✅ | ❌ | ❌ |
| 支付宝生活号 | ✅ | ✅ | ❌ | ❌ |
| 微博 | ✅ | ✅ | ❌ | ❌ |
| 虎扑 | ✅ | ✅ | ❌ | ❌ |
| YouTube | ✅ | ✅ | ❌ | ❌ |

## 账号文件

登录后 cookie 保存在 `cookies/{platform}_{account}.json`。

## 依赖

- Python >= 3.10
- 安装依赖：`pip install -e .`
- B站上传依赖 `biliup`，首次运行会自动下载。

## 作为 Skill 调用

在 PromptForge 中可通过 `SocialAutoUpload` 类调用：

```python
from skills.social_auto_upload import SocialAutoUpload

sau = SocialAutoUpload()
sau.login("xiaohongshu", account="myaccount")

# 图文混排文章
sau.publish_note(
    "xiaohongshu",
    images=["cover.png", "detail1.png", "detail2.png"],
    title="春季露营装备清单｜新手必看",
    note="这次整理了 10 件入门级露营装备……",
    tags=["露营", "户外", "好物推荐"],
    account="myaccount",
)

# 视频
sau.publish_video(
    "xiaohongshu",
    file="vlog.mp4",
    title="周末露营 Vlog",
    desc="两天的露营记录",
    thumbnail="cover.png",
    tags=["露营", "Vlog"],
    account="myaccount",
)
```

## 说明

- 详细参数请参考 `python social_auto_upload_cli.py --help`。
- 部分平台需要特定参数（如 B站 `--tid`、YouTube `--playlist`/`--visibility`）。
- “图文混排”由 `publish-note` 的「多图 + `--note` 正文」组合实现；视频+封面由 `publish-video` 的 `--thumbnail` 实现。