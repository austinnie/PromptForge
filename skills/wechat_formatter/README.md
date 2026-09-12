# wechat_formatter · 微信公众号排版

Markdown 一键排版为微信公众号兼容 HTML。**内联样式、33 套主题、可视化画廊、AI 内容增强、封面图生成、可选推送草稿箱**。

---

## ✨ 功能

- 📝 **Markdown → 微信兼容 HTML**：所有样式内联，兼容公众号编辑器（不认 `<style>` 标签、不认 CSS class）
- 🎨 **33 套主题**：深度长文 / 科技产品 / 文艺随笔 / 活力动态 / 模板布局，五大分类
- 🖼️ **可视化画廊**：用真实文章预览 20 个核心主题，浏览器里点选
- 🤖 **AI 内容增强**（可选）：自动识别对话体、连续图片、核心观点，套用 `dialogue` / `gallery` / `callout` 容器
- 🎯 **CJK 排版修复**：中英文之间自动加空格、加粗标点自动移出标记
- 🔗 **外链转脚注**：微信不允许外链，自动转文末脚注
- 🖼️ **图片本地化**：`![[image]]` 和 `![](image)` 自动搜索并复制到 `images/`
- 🎨 **封面图生成**（可选）：复用 `image_generator` 生成 2.35:1 Notion 风格封面
- 📤 **一键推送草稿箱**（可选）：自动上传图片到微信 CDN + 推送到公众号草稿箱

---

## 📦 依赖

```cmd
pip install markdown requests
```

| 依赖 | 用途 | 缺失后果 |
|---|---|---|
| `markdown` | Markdown → HTML 转换（核心） | ❌ 排版完全不可用 |
| `requests` | 推送草稿箱时调用微信 API | ⚠️ 只影响推送，排版正常 |

---

## ⚙️ 配置

### 排版（不需要配置）

排版、画廊、预览全部本地运行，**开箱即用**。

### 推送草稿箱（可选）

在项目根目录 `.env` 里填：

```ini
# ============================================================
# 公众号排版 / 推送
# ============================================================
WECHAT_APP_ID=你的AppID
WECHAT_APP_SECRET=你的AppSecret
WECHAT_AUTHOR=作者名
WECHAT_DEFAULT_THEME=newspaper
WECHAT_OUTPUT_DIR=./output/wechat
```

**获取 AppID / AppSecret**：

1. 登录 [https://developers.weixin.qq.com/platform](https://developers.weixin.qq.com/platform)
2. 进入你的公众号 → **基础信息**
3. `AppID`：直接复制
4. `AppSecret`：点"重置"，微信会生成 32 位字符串，**只显示一次，立刻保存**
5. 把当前机器的**公网 IP** 加入 **API IP 白名单**

**查公网 IP**：

```cmd
curl ifconfig.me
```

---

## 🚀 使用

### 命令行

```cmd
:: 默认主题（newspaper）排版
python skills/wechat_formatter/wechat_formatter_cli.py article.md

:: 指定主题
python skills/wechat_formatter/wechat_formatter_cli.py article.md --theme terracotta

:: 主题画廊（浏览器里挑）
python skills/wechat_formatter/wechat_formatter_cli.py article.md --gallery

:: AI 内容增强 + 自动打开
python skills/wechat_formatter/wechat_formatter_cli.py article.md --enhance --open

:: 排版 → 生成封面 → 推送草稿箱
python skills/wechat_formatter/wechat_formatter_cli.py article.md --theme terracotta --cover --publish

:: 只生成封面
python skills/wechat_formatter/wechat_formatter_cli.py cover --title "标题" --topic "主题"

:: 只推送已排版好的文章
python skills/wechat_formatter/wechat_formatter_cli.py publish --dir output/wechat/xxx
```

### 参数说明

**`format`（默认命令）**：

| 参数 | 简写 | 说明 | 默认 |
|---|---|---|---|
| `input` | — | Markdown 路径（必填） | — |
| `--theme` | `-t` | 主题名 | `newspaper` |
| `--gallery` | `-g` | 打开主题画廊 | 关 |
| `--enhance` | `-e` | 启用 AI 内容增强 | 关 |
| `--open` | `-o` | 完成后打开浏览器 | 关 |
| `--recommend` | — | 画廊推荐主题列表 | 空 |
| `--cover` | — | 同时生成封面 | 关 |
| `--publish` | — | 排版后推送草稿箱 | 关 |
| `--dry-run` | — | 推送时只上传图片不推草稿 | 关 |

### Python 调用

```python
from skills.wechat_formatter import WechatFormatter

fmt = WechatFormatter()

# 单主题排版
result = fmt.format("article.md", theme="terracotta")
print(result["result"]["article_path"])

# 画廊模式
result = fmt.format("article.md", gallery=True)

# 生成封面
result = fmt.generate_cover("标题", "主题描述")

# 推送草稿箱
result = fmt.publish("output/wechat/xxx", cover_path="cover.jpg")
```

---

## 🎨 主题列表（33 套）

### 独立风格（9）

| 主题 | ID | 风格 |
|---|---|---|
| 赤陶 | `terracotta` | 暖橙色，满底圆角标题 |
| 字节蓝 | `bytedance` | 蓝青渐变，科技现代 |
| 中国风 | `chinese` | 朱砂红，古典雅致 |
| 报纸 | `newspaper` | 纽约时报风，衬线体 |
| GitHub | `github` | 开发者风，浅色代码块 |
| 少数派 | `sspai` | 中文科技媒体红 |
| 包豪斯 | `bauhaus` | 红蓝黄三原色，几何 |
| 墨韵 | `ink` | 纯黑水墨，极简 |
| 暗夜 | `midnight` | 深色+霓虹，赛博朋克 |

### 精选风格（7）

`sports` / `mint-fresh` / `sunset-amber` / `lavender-dream` / `coffee-house` / `wechat-native` / `magazine`

### 卡片系列（3，新增）

| 主题 | ID | 风格 |
|---|---|---|
| 暖光卡片 | `warm-card` | 暖白底 + 方格纹理 |
| 清新卡片 | `fresh-card` | 淡绿底 + 点状纹理 |
| 静谧卡片 | `ocean-card` | 淡蓝底 + 网格纹理 |

### 模板布局（14）

4 种布局（`minimal` / `focus` / `elegant` / `bold`）× 6 种配色（`gold` / `blue` / `red` / `green` / `navy` / `gray`），例如 `minimal-gold`、`focus-blue`、`elegant-green`、`bold-blue`。

完整清单：`python skills/wechat_formatter/wechat_formatter_cli.py --help` 或看 `themes/` 目录。

---

## 📂 输出结构

```
output/wechat/20260912_HHMMSS_article/
├── article.html         # 微信兼容 HTML（可复制到公众号后台）
├── preview.html         # 浏览器预览版（含"复制到微信"按钮）
├── images/              # 本地化的图片副本
│   ├── xxx.png
│   └── ...
└── gallery.html         # 画廊模式时生成
```

---

## 📱 发布到公众号

### 方式一：手动粘贴（推荐，0 成本）

1. 浏览器打开 `preview.html`
2. 点右上角 **"复制到微信"** 按钮
3. 到 [公众号后台](https://mp.weixin.qq.com) → 图文编辑 → `Ctrl+V`
4. **图片需手动上传**：从 `output/wechat/xxx/images/` 拖进编辑器

**30 秒搞定**，样式完全保留。

### 方式二：自动推送（需账号有 API 权限）

```cmd
python skills/wechat_formatter/wechat_formatter_cli.py article.md --theme terracotta --publish
```

**前提**：

- `.env` 里配好 `WECHAT_APP_ID` / `WECHAT_APP_SECRET`
- 当前 IP 已加入微信后台 IP 白名单
- **账号已认证**（未认证个人号可能无草稿箱权限）

推送成功后到公众号后台 → **内容管理 → 草稿箱** 查看。

---

## 🔧 常见问题

### Q1：报错 `No module named 'markdown'`

```cmd
pip install markdown
```

### Q2：报错 `errcode=40164`（IP 不在白名单）

查当前 IP：

```cmd
curl ifconfig.me
```

把它加入微信后台 → 基础信息 → **API IP 白名单**。

> 家宽 / VPN 的 IP 会变，一变就要重新加。

### Q3：报错 `errcode=48001`（API 未授权）

**未认证的个人订阅号**不开放草稿箱接口。两个选择：

- 用**方式一手动粘贴**（推荐）
- 花钱**认证账号**（300 元/年）

### Q4：报错 `errcode=40001` / `40125`（AppSecret 无效）

去微信后台 **重置 AppSecret**，重新填 `.env`。

### Q5：排版后打开浏览器显示"文件找不到"

老版本的相对路径 bug。**升级到最新版**已修复（用 `Path.as_uri()`）。

### Q6：中文排版加空格太频繁

`fix_cjk_spacing` 自动在中英文之间加空格。不想加就把 `formatter/engine.py` 里的这行注释掉：

```python
content = engine.fix_cjk_spacing(content)
```

---

## 🧰 目录结构

```
skills/wechat_formatter/
├── __init__.py
├── skill.py                      # 主入口：WechatFormatter
├── wechat_formatter_cli.py       # 命令行
├── meta.json
├── README.md
├── formatter/
│   ├── __init__.py
│   └── engine.py                 # 排版引擎（Markdown → 微信 HTML）
├── publisher/
│   ├── __init__.py
│   └── wechat_publish.py         # 推送草稿箱
├── cover/
│   ├── __init__.py
│   └── cover_generator.py        # 封面生成（复用 image_generator）
├── themes/                       # 33 个主题 JSON
└── templates/
    ├── preview.html              # 预览页模板
    └── gallery.html              # 画廊页模板
```

---

## 🔌 与其他技能的衔接

```
图片目录 → image_curator → article.md
                              ↓
                       wechat_formatter
                              ↓
                套主题 → 生成封面 → 推草稿箱 / 手动粘贴
```

`image_curator` 生成的 `article.md` 天然带配图和配文，`wechat_formatter` 直接排版即可。

---

## 📄 License

与主项目一致。