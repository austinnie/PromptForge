# github_repo_daily

每天推荐一个 GitHub 仓库，自动生成介绍文章并发布到微信公众号草稿箱。

从 GitHub Trending 每日榜单中挑选一个**未推荐过**的仓库，抓取 README 与基础信息，用本地 Ollama 生成一篇介绍文章，再通过已有的 `wechat_formatter` 排版并推送到微信公众号草稿箱。

---

## ✨ 功能

- 🔥 **抓取 Trending**：解析 `https://github.com/trending?since=daily` 每日榜单
- 🎯 **智能去重**：自动跳过历史已推荐过的仓库（本地 `history.json` 记录）
- 📡 **GitHub API**：获取仓库 stars / forks / 语言 / topics / README
- 🧠 **Ollama 生成**：本地大模型生成 800–1200 字通俗介绍文章
- 🎨 **微信排版**：复用 `wechat_formatter` 的 33 套主题，一键排版
- 📤 **推送草稿箱**：可直接推送到微信公众号草稿箱（可选关闭）
- 🔁 **失败兜底**：Trending 抓取失败时使用内置候选仓库；Ollama 失败时输出基础模板文章

---

## 📦 依赖

### Python 依赖

```bash
pip install requests
```

### 外部服务

| 服务 | 用途 | 说明 |
|------|------|------|
| Ollama | 本地 LLM 生成文章 | 默认 `http://localhost:11434`，需拉取模型如 `qwen2.5:7b` |
| wechat_formatter | 排版 + 推送 | 已在项目内，需配置 `WECHAT_APP_ID` / `WECHAT_APP_SECRET` |

### 环境变量（可选）

```ini
# GitHub Personal Access Token，用于提高 API 速率限制（未认证 60 次/小时，认证 5000 次/小时）
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Ollama 服务
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

> 不设置 `GITHUB_TOKEN` 也能跑，只是频繁调用可能触发限流。

---

## 🚀 快速开始

### 1. 拉取 Ollama 模型

```bash
ollama pull qwen2.5:7b
ollama serve
```

### 2. 配置微信公众号

在项目 `.env` 中设置：

```ini
WECHAT_APP_ID=wx_xxxxxxxxxxxxxxxx
WECHAT_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

并将当前公网 IP 加入微信公众号后台 → 基础配置 → IP 白名单。

### 3. 运行

```bash
# 生成并发布到公众号草稿箱（默认）
python skills/github_repo_daily/github_repo_daily_cli.py

# 只生成本地文章，不发布
python skills/github_repo_daily/github_repo_daily_cli.py --no-publish

# 指定 Ollama 模型
python skills/github_repo_daily/github_repo_daily_cli.py --model qwen2.5:14b

# 指定微信排版主题
python skills/github_repo_daily/github_repo_daily_cli.py --theme terracotta
```

---

## 🐍 Python 调用

```python
from skills.github_repo_daily import GitHubRepoDaily

skill = GitHubRepoDaily({
    "wechat_publish": True,
    "wechat_theme": "newspaper",
    "ollama_model": "qwen2.5:7b",
})

result = skill.execute()

if result["status"] == "success":
    print("推荐仓库:", result["result"]["repo"])
    print("仓库链接:", result["result"]["repo_url"])
    print("文章路径:", result["result"]["article_path"])
    print("已发布:",   result["result"]["published"])
else:
    print("失败:", result["error"])
```

---

## 📁 输出结构

```
output/
└── github_repo_daily/
    ├── history.json                     # 已推荐仓库记录（去重用）
    ├── tmp/                             # 待排版的临时 md
    │   └── 20260923_080000.md
    └── 20260923/                        # 按日期归档
        └── ollama_ollama.md             # 生成的介绍文章

output/
└── wechat/                              # wechat_formatter 输出
    └── 20260923_080100_article/
        ├── article.html
        ├── preview.html
        └── images/
```

---

## ⚙️ 参数配置

`GitHubRepoDaily(config)` 支持的配置项：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `output_dir` | `./output/github_repo_daily` | 输出根目录 |
| `history_file` | `history.json` | 历史记录文件名 |
| `github_token` | `$GITHUB_TOKEN` | GitHub Token，可选 |
| `ollama_url` | `$OLLAMA_URL` / `http://localhost:11434` | Ollama 地址 |
| `ollama_model` | `$OLLAMA_MODEL` / `qwen2.5:7b` | Ollama 模型 |
| `wechat_theme` | `newspaper` | 微信排版主题名 |
| `wechat_publish` | `True` | 是否推送到公众号草稿箱 |
| `max_trending` | `25` | 每次从 Trending 取多少个候选 |
| `log_level` | `INFO` | 日志级别 |

---

## 🔧 工作流程

```
┌─────────────────────────────┐
│ 1. 抓取 GitHub Trending 日榜 │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 2. 过滤历史已推荐 → 随机挑选 │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 3. GitHub API 获取详情+README│
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 4. Ollama 生成介绍文章       │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 5. 保存 md + 记录 history    │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 6. wechat_formatter 排版     │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 7. 推送公众号草稿箱（可选）  │
└─────────────────────────────┘
```

---

## ⏰ 定时任务

### Windows 计划任务

参考 `scripts/register_task.ps1` 注册，或新建任务：

```powershell
$TaskName   = "PromptForge_GitHubRepoDaily"
$ProjectDir = "E:\SD_OpenVINO\PromptForge"
$Python     = "$ProjectDir\venv\Scripts\python.exe"
$Script     = "$ProjectDir\skills\github_repo_daily\github_repo_daily_cli.py"

$Action  = New-ScheduledTaskAction -Execute $Python -Argument $Script -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Daily -At "08:00"

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Force
```

### Windows 批处理

`scripts/run_github_repo_daily.bat`：

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python skills\github_repo_daily\github_repo_daily_cli.py >> "output\github_repo_daily\run.log" 2>&1
exit /b %ERRORLEVEL%
```

### Linux / macOS crontab

```cron
0 8 * * * cd /path/to/PromptForge && /path/to/venv/bin/python skills/github_repo_daily/github_repo_daily_cli.py >> output/github_repo_daily/run.log 2>&1
```

---

## 🛠 CLI 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `--no-publish` | 只生成本地文章，不推送公众号 | 关（默认推送） |
| `--theme` | 微信排版主题（如 `terracotta` / `newspaper`） | `newspaper` |
| `--model` | 覆盖 Ollama 模型 | 读环境变量 |

---

## ❓ 常见问题

### Q1: 抓取 Trending 失败 / 返回空列表

- GitHub 页面结构可能变化 → 检查 `fetch_trending_repos()` 里的正则
- 网络受限 → 检查代理；代码里有内置兜底仓库列表

### Q2: GitHub API 返回 403 / 429

- 未设置 `GITHUB_TOKEN` 时限流（60 次/小时）
- 建议在环境变量里配置 Personal Access Token

### Q3: Ollama 超时

- 首次加载大模型较慢 → 提前 `ollama run qwen2.5:7b` 预热一次
- 加大 `timeout` 参数或改用更小的模型

### Q4: 微信公众号推送失败 `errcode=40164`

- IP 不在白名单 → `curl ifconfig.me` 查 IP，加入后台白名单
- 家宽 IP 会变，变了要重新加

### Q5: 微信公众号推送失败 `errcode=48001`

- 未认证订阅号无草稿箱 API 权限 → 用 `--no-publish` 只生成 HTML，手动复制粘贴
- 参考 `wechat_formatter` 的 `preview.html` 手动复制流程

### Q6: 文章质量不满意

- 换个更大的 Ollama 模型：`--model qwen2.5:14b` 或 `qwen2.5:32b`
- 修改 `skill.py` 里 `generate_article()` 的 prompt 模板
- 调大 `readme` 截断长度（默认 4000 字符）给模型更多上下文

### Q7: 想推送到多个平台（小红书 / 知乎）

- 本项目已内置 `social_auto_upload` skill
- 在 `publish_to_wechat()` 后追加调用即可

---

## 📂 目录结构

```
skills/github_repo_daily/
├── __init__.py                  # 导出 GitHubRepoDaily
├── skill.py                     # 主技能逻辑
├── github_repo_daily_cli.py     # 命令行入口
├── meta.json                    # 技能元数据
└── README.md                    # 本文档
```

---

## 🔌 扩展方向

| 想法 | 难度 | 备注 |
|------|------|------|
| 支持按语言 / topic 过滤 Trending | ⭐ | URL 加 `?language=python` |
| 每周汇总 Top 10 生成周报 | ⭐⭐ | 聚合多篇文章 |
| 自动抓取仓库截图作为封面 | ⭐⭐ | 用 `screenshot` API |
| 生成中英双语版本 | ⭐ | prompt 双写 |
| 加入技术栈分析（依赖图） | ⭐⭐⭐ | 解析 package.json / requirements.txt |
| 推送到小红书 / 知乎 | ⭐ | 复用 `social_auto_upload` |
| 加入 Star 增长曲线图 | ⭐⭐⭐ | 调 GitHub API 时间序列 |

---

## 📄 License

与 PromptForge 主项目一致（MIT）。